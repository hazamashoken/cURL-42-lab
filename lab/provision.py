"""Run once before services start; existing fixtures are never silently replaced."""
import json
import os
from pathlib import Path
import re
import secrets


def provision(fixtures, ftp_root, host, count):
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host):
        raise ValueError('LAB_HOST must be an IPv4 address or hostname, without scheme or port')
    if not 1 <= count <= 99:
        raise ValueError('TEAM_COUNT must be between 1 and 99')
    fixtures, ftp_root = Path(fixtures), Path(ftp_root)
    config_file = fixtures / 'config.json'
    if config_file.exists():
        config = json.loads(config_file.read_text())
        if config['host'] != host or len(config['teams']) != count:
            raise ValueError('Configuration changed: reset the lab to regenerate fixtures')
        return config
    fixtures.mkdir(parents=True, exist_ok=True)
    ftp_root.mkdir(parents=True, exist_ok=True)
    if any(ftp_root.iterdir()):
        raise ValueError('Incomplete provisioning: reset before continuing')
    teams = {}
    for number in range(1, count + 1):
        team = f'team{number:02d}'
        entry = {
            'ftp_password': secrets.token_hex(12),
            'token': secrets.token_hex(24),
            'unlock_code': secrets.token_hex(16),
            'challenge_file': f'challenge-{secrets.token_hex(8)}.txt',
        }
        teams[team] = entry
        root = ftp_root / team
        (root / 'uploads').mkdir(parents=True)
        (root / 'briefing.txt').write_text(
            f'Welcome, {team}! Create receipt.txt in your text editor and upload it to uploads/.\n'
            f'Chat topic: lab/{team}/chat\nStart the subscriber BEFORE publishing.\n'
            f'curl -N --max-time 30 "mqtt://{host}:1883/lab/{team}/chat"\n'
            f'curl -d "hello-from-{team}" "mqtt://{host}:1883/lab/{team}/chat"\n'
            'Final mission: inspect the HTTP challenge response headers.\n'
        )
        (root / entry['challenge_file']).write_text(
            f'Team: {team}\nAPI bearer token: {entry["token"]}\n'
            f'Mission endpoint: http://{host}:8080/api/{team}/mission\n'
            'Hint: send an Authorization header with the Bearer scheme and your token.\n'
        )
    guide = Path(__file__).resolve().parent.parent / 'docs' / 'participant-guide.md'
    (fixtures / 'participant-guide.md').write_text(guide.read_text().replace('LAB_HOST', host))
    config = {'host': host, 'teams': teams}
    temporary = fixtures / 'config.json.tmp'
    temporary.write_text(json.dumps(config, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(config_file)
    return config


if __name__ == '__main__':
    result = provision(os.getenv('FIXTURES_DIR', '/fixtures'), os.getenv('FTP_ROOT', '/ftp'),
                       os.environ['LAB_HOST'], int(os.getenv('TEAM_COUNT', '10')))
    print(f'Fixtures ready: {len(result["teams"])} teams at {result["host"]}')
