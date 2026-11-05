#!/usr/bin/env python3
"""Host-side integration tests. Uses actual curl for all three protocols."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import unittest


def curl(*args, check=True):
    result = subprocess.run(['curl', '--noproxy', '*', '-sS', '--connect-timeout', '4',
                             '--max-time', '10', *args], capture_output=True)
    if check and result.returncode:
        raise AssertionError(f'curl exited {result.returncode}: {result.stderr.decode(errors="replace")}')
    return result


class Subscription:
    """Readiness is proven by delivery of a unique probe, never a fixed sleep."""
    def __init__(self, url):
        self.url = url
        self.directory = tempfile.TemporaryDirectory()
        self.output_path = Path(self.directory.name) / 'subscriber.out'
        self.output = self.output_path.open('wb')
        self.errors = tempfile.TemporaryFile()
        self.process = subprocess.Popen(['curl', '--noproxy', '*', '-sS', '-N', '--max-time', '60', url],
                                        stdout=self.output, stderr=self.errors)
        try:
            probe = 'ready-' + secrets.token_hex(12)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                curl('-d', probe, url)
                if self.wait_for(probe, timeout=0.2):
                    break
            else:
                raise AssertionError('MQTT subscriber never received readiness probe')
        except BaseException:
            self.close()
            raise

    def wait_for(self, text, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # Independent reader avoids moving the subprocess's shared file offset.
            with self.output_path.open('rb') as reader:
                if text.encode() in reader.read():
                    return True
            if self.process.poll() is not None:
                raise AssertionError('MQTT subscriber exited before receiving the expected message')
            time.sleep(0.02)
        return False

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=5)
        self.output.close()
        self.errors.close()
        self.directory.cleanup()


class Smoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        version = curl('--version').stdout.decode()
        protocols = next(line for line in version.splitlines() if line.startswith('Protocols:')).split()[1:]
        missing = {'http', 'ftp', 'mqtt'} - set(protocols)
        if missing:
            raise RuntimeError('Required curl protocols missing: ' + ', '.join(sorted(missing)))
        cls.http = f'http://{OPTIONS.host}:8080'
        cls.ftp = f'ftp://{OPTIONS.host}:2121'
        cls.mqtt = f'mqtt://{OPTIONS.host}:1883'
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.receipt = Path(cls.tmp.name) / 'receipt.txt'
        cls.receipt.write_text('team01 smoke receipt\n')
        cls.teams = {}
        for team in ['team01', 'team02']:
            body = curl('--fail', '--data-urlencode', f'team={team}', cls.http + '/check-in').stdout.decode()
            cls.teams[team] = {'password': cls.field(body, 'FTP password')}
            response = curl('-i', cls.http + f'/challenge/{team}').stdout.decode()
            filename = cls.field(response, 'X-Next-File')
            cls.teams[team]['file'] = filename
            content = curl('-u', f'{team}:{cls.teams[team]["password"]}', cls.ftp + '/' + filename).stdout.decode()
            cls.teams[team]['token'] = cls.field(content, 'API bearer token')
            mission = curl('--fail', '-H', 'Authorization: Bearer ' + cls.teams[team]['token'],
                           cls.http + f'/api/{team}/mission').stdout.decode()
            cls.teams[team]['code'] = cls.field(mission, 'One-time unlock code')
        if any(row['unlocked'] for row in cls.progress()['teams']):
            raise RuntimeError('Smoke tests require a clean lab with at least two teams. Reset first.')

    @staticmethod
    def field(body, name):
        for line in body.splitlines():
            if line.lower().startswith(name.lower() + ':'):
                return line.split(':', 1)[1].strip()
        raise AssertionError(f'Missing field: {name}')

    @classmethod
    def progress(cls):
        return json.loads(curl('--fail', cls.http + '/progress').stdout)

    def auth(self, team='team01'):
        return f'{team}:{self.teams[team]["password"]}'

    def status(self, *args):
        return int(curl('-o', os.devnull, '-w', '%{http_code}', *args).stdout)

    def test_01_redirect_and_check_in(self):
        response = curl('-i', self.http + '/start').stdout.decode()
        self.assertIn('302', response.splitlines()[0])
        self.assertEqual(self.field(response, 'Location'), '/briefing')
        self.assertEqual(self.field(response, 'X-Lab-Clue'), 'look-beyond-the-body')
        self.assertIn(b'Three Protocols', curl('-L', self.http + '/start').stdout)
        self.assertEqual(self.status('--data-urlencode', 'team=team01', self.http + '/check-in'), 200)
        self.assertEqual(self.status('--data-urlencode', 'team=not-a-team', self.http + '/check-in'), 400)
        self.assertEqual(self.status('-X', 'POST', self.http + '/check-in'), 400)

    def test_02_ftp_auth_listing_download_upload(self):
        for credentials in ['anonymous:anonymous', 'team01:wrong']:
            self.assertNotEqual(curl('-u', credentials, self.ftp + '/', check=False).returncode, 0)
        listing = curl('--list-only', '-u', self.auth(), self.ftp + '/').stdout
        self.assertIn(b'briefing.txt', listing)
        self.assertIn(self.teams['team01']['file'].encode(), listing)
        target = Path(self.tmp.name) / 'briefing.txt'
        curl('-u', self.auth(), '-o', str(target), self.ftp + '/briefing.txt')
        self.assertIn('lab/team01/chat', target.read_text())
        curl('-u', self.auth(), '-T', str(self.receipt), self.ftp + '/uploads/receipt.txt')
        self.assertEqual(curl('-u', self.auth(), self.ftp + '/uploads/receipt.txt').stdout, self.receipt.read_bytes())
        # Force PASV and honor the advertised IP to test the LAN data path.
        self.assertIn(b'briefing.txt', curl('--disable-epsv', '--no-ftp-skip-pasv-ip',
                                          '--list-only', '-u', self.auth(), self.ftp + '/').stdout)

    def test_03_ftp_isolation_and_read_only(self):
        for target in ['/briefing.txt', '/' + self.teams['team01']['file'], '/new.txt']:
            self.assertNotEqual(curl('-u', self.auth(), '-T', str(self.receipt), self.ftp + target,
                                     check=False).returncode, 0)
        self.assertNotIn(self.teams['team02']['file'].encode(), curl('--list-only', '-u', self.auth(), self.ftp + '/').stdout)
        for target in ['/' + self.teams['team02']['file'], '/%2e%2e/team02/' + self.teams['team02']['file']]:
            self.assertNotEqual(curl('--path-as-is', '-u', self.auth(), self.ftp + target, check=False).returncode, 0)
        self.assertNotEqual(curl('-u', self.auth('team02'), self.ftp + '/uploads/receipt.txt', check=False).returncode, 0)
        challenge = curl('-u', self.auth(), self.ftp + '/' + self.teams['team01']['file']).stdout
        self.assertIn(self.teams['team01']['token'].encode(), challenge)

    def test_04_api_and_callback_auth(self):
        for token in ['', 'wrong', self.teams['team02']['token']]:
            self.assertIn(self.status('-H', 'Authorization: Bearer ' + token,
                                      self.http + '/api/team01/mission'), [401, 403])
        self.assertEqual(self.status('-X', 'POST', self.http + '/internal/complete/team01'), 403)

    def subscribe(self, topic):
        sub = Subscription(self.mqtt + '/' + topic)
        self.addCleanup(sub.close)
        return sub

    def test_05_mqtt_chat(self):
        sub = self.subscribe('lab/team01/chat')
        message = 'hello-' + secrets.token_hex(8)
        curl('-d', message, self.mqtt + '/lab/team01/chat')
        self.assertTrue(sub.wait_for(message))

    def test_06_wrong_code(self):
        sub = self.subscribe('lab/team01/result')
        curl('-d', 'incorrect', self.mqtt + '/lab/team01/unlock')
        self.assertTrue(sub.wait_for('incorrect unlock code'))
        self.assertEqual(self.progress()['completed'], 0)

    def test_07_correct_code(self):
        sub = self.subscribe('lab/team01/result')
        curl('-d', self.teams['team01']['code'], self.mqtt + '/lab/team01/unlock')
        self.assertTrue(sub.wait_for('Unlocked!'))
        progress = self.progress()
        self.assertEqual(progress['completed'], 1)
        self.assertTrue(progress['teams'][0]['completed_at'])
        self.assertFalse(progress['teams'][1]['unlocked'])

    def test_08_duplicate_and_non_retained_result(self):
        before = self.progress()
        sub = self.subscribe('lab/team01/result')
        self.assertFalse(sub.wait_for('Unlocked!', timeout=0.3), 'Result must not be retained')
        curl('-d', self.teams['team01']['code'], self.mqtt + '/lab/team01/unlock')
        self.assertTrue(sub.wait_for('already unlocked'))
        self.assertEqual(before, self.progress())

    def test_09_restart_persistence(self):
        if not OPTIONS.restart_http:
            self.skipTest('Pass --restart-http on the facilitator host to test Compose restart')
        before = self.progress()
        subprocess.run(['docker', 'compose', 'restart', 'http'], check=True, timeout=60)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = curl('--fail', self.http + '/health', check=False)
            if result.returncode == 0:
                break
            time.sleep(0.2)
        else:
            self.fail('HTTP did not recover after restart')
        self.assertEqual(before, self.progress())

    def test_10_dashboard_no_secrets(self):
        for route in ['/dashboard', '/progress', '/guide']:
            response = curl('--fail', self.http + route).stdout.decode()
            for team in self.teams.values():
                for key in ['password', 'token', 'code']:
                    self.assertNotIn(team[key], response)
        progress = self.progress()
        self.assertEqual(set(progress), {'completed', 'teams'})
        self.assertEqual(set(progress['teams'][0]), {'team', 'unlocked', 'completed_at'})
        for route in ['/config.json', '/static/config.json', '/fixtures/config.json']:
            self.assertEqual(self.status(self.http + route), 404)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Facilitator LAN IPv4 or hostname')
    parser.add_argument('--restart-http', action='store_true', help='Restart app with Docker Compose to test persistence')
    OPTIONS = parser.parse_args()
    unittest.main(argv=['smoke'], verbosity=2)
