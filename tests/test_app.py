import shutil
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from pathlib import Path

from lab.provision import provision
from lab.web import create_app


class LabTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = provision(self.root / 'fixtures', self.root / 'ftp', 'lab.example', 2)
        self.app = create_app(self.root / 'fixtures', self.root / 'state', 'test-secret')
        self.client = self.app.test_client()
        self.team = self.config['teams']['team01']

    def test_fixture_persistence_and_validation(self):
        again = provision(self.root / 'fixtures', self.root / 'ftp', 'lab.example', 2)
        self.assertEqual(self.config, again)
        with self.assertRaises(ValueError):
            provision(self.root / 'fixtures', self.root / 'ftp', 'changed.example', 2)
        for host in ['bad/host', 'bad\nhost', 'http://example.com']:
            with self.assertRaises(ValueError):
                provision(self.root / host.replace('/', '_'), self.root / 'other', host, 2)
        for count in [0, 100]:
            with self.assertRaises(ValueError):
                provision(self.root / 'invalid', self.root / 'other', 'lab.example', count)
        partial = self.root / 'partial-ftp'
        partial.mkdir()
        (partial / 'unfinished').touch()
        with self.assertRaises(ValueError):
            provision(self.root / 'partial-fixtures', partial, 'lab.example', 2)
        self.assertNotEqual(self.team['token'], self.config['teams']['team02']['token'])
        guide = (self.root / 'fixtures' / 'participant-guide.md').read_text()
        self.assertIn('http://lab.example:8080/start', guide)
        self.assertNotIn('LAB_HOST', guide)

    def test_http_exercises(self):
        response = self.client.get('/start')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/briefing')
        self.assertEqual(response.headers['X-Lab-Clue'], 'look-beyond-the-body')
        self.assertEqual(self.client.get('/health').status_code, 200)
        response = self.client.post('/check-in', data={'team': 'team01'})
        self.assertIn(self.team['ftp_password'], response.text)
        self.assertIn('ftp://lab.example:2121', response.text)
        for team in ['', '../team01', 'team99']:
            self.assertEqual(self.client.post('/check-in', data={'team': team}).status_code, 400)
        response = self.client.get('/challenge/team01')
        self.assertEqual(response.headers['X-Next-File'], self.team['challenge_file'])
        self.assertEqual(self.client.get('/challenge/nope').status_code, 404)

    def test_api_authentication(self):
        for token in ['', 'wrong', self.config['teams']['team02']['token']]:
            response = self.client.get('/api/team01/mission', headers={'Authorization': 'Bearer ' + token})
            self.assertEqual(response.status_code, 401)
        response = self.client.get('/api/team01/mission', headers={'Authorization': 'Bearer ' + self.team['token']})
        self.assertIn(self.team['unlock_code'], response.text)

    def test_callback_auth_idempotency_and_restart(self):
        url = '/internal/complete/team01'
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self.client.post(url, headers={'Authorization': 'Bearer wrong'}).status_code, 403)
        headers = {'Authorization': 'Bearer test-secret'}
        self.assertEqual(self.client.post('/internal/complete/nope', headers=headers).status_code, 404)
        self.assertIn('Unlocked', self.client.post(url, headers=headers).text)
        before = self.client.get('/progress').json
        self.assertIn('already unlocked', self.client.post(url, headers=headers).text)
        restarted = create_app(self.root / 'fixtures', self.root / 'state', 'test-secret').test_client()
        self.assertEqual(before, restarted.get('/progress').json)
        self.assertEqual(before['completed'], 1)
        self.assertFalse(before['teams'][1]['unlocked'])

    def test_concurrent_completion_preserves_first_timestamp(self):
        def complete(_):
            with self.app.test_client() as client:
                return client.post('/internal/complete/team01',
                                   headers={'Authorization': 'Bearer test-secret'}).text
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(complete, range(8)))
        self.assertEqual(sum('Unlocked!' in response for response in responses), 1)
        self.assertEqual(sum('already unlocked' in response for response in responses), 7)
        self.assertEqual(self.client.get('/progress').json['completed'], 1)

    def test_reset_regenerates_secrets_and_clears_uploads_and_progress(self):
        self.client.post('/internal/complete/team01', headers={'Authorization': 'Bearer test-secret'})
        receipt = self.root / 'ftp' / 'team01' / 'uploads' / 'receipt.txt'
        receipt.write_text('old receipt')
        for directory in ['fixtures', 'ftp', 'state']:
            shutil.rmtree(self.root / directory)
        fresh = provision(self.root / 'fixtures', self.root / 'ftp', 'new.lab.example', 2)
        for field in ['ftp_password', 'token', 'unlock_code', 'challenge_file']:
            self.assertNotEqual(self.team[field], fresh['teams']['team01'][field])
        restarted = create_app(self.root / 'fixtures', self.root / 'state', 'test-secret').test_client()
        self.assertEqual(restarted.get('/progress').json['completed'], 0)
        self.assertFalse(receipt.exists())
        self.assertIn('http://new.lab.example:8080/start', restarted.get('/guide').text)

    def test_public_routes_do_not_leak_secrets(self):
        for route in ['/dashboard', '/progress', '/guide', '/briefing', '/health']:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            for team in self.config['teams'].values():
                for field in ['token', 'ftp_password', 'unlock_code']:
                    self.assertNotIn(team[field], response.text)
        for route in ['/config.json', '/static/config.json', '/fixtures/config.json']:
            self.assertEqual(self.client.get(route).status_code, 404)


if __name__ == '__main__':
    unittest.main()
