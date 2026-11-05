#!/usr/bin/env python3
"""Instructor controls for the curl lab (Python 3.10+, no extra packages)."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(*args, capture=False):
    result = subprocess.run(['docker', 'compose', *args], cwd=ROOT, check=True,
                            text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout


def configure():
    path = ROOT / '.env'
    if path.exists():
        print('Keeping existing .env settings and credentials.')
        return
    host = input('Facilitator LAN IPv4 address or hostname: ').strip()
    count = input('Number of teams [10]: ').strip() or '10'
    passive = input(f'FTP passive IPv4 address or hostname [{host}]: ').strip() or host
    for address in [host, passive]:
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', address):
            raise ValueError('Use an IPv4 address or hostname without a scheme, port or spaces.')
    if not count.isascii() or not count.isdecimal() or not 1 <= int(count) <= 99:
        raise ValueError('Team count must be between 1 and 99.')
    content = (f'LAB_HOST={host}\nTEAM_COUNT={int(count)}\nFTP_PASSIVE_ADDRESS={passive}\n'
               f'WORKER_CALLBACK_SECRET={secrets.token_hex(32)}\n')
    # Exclusive creation protects an existing configuration from accidental replacement.
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as file:
        file.write(content)
    print('Created .env with a private random callback secret.')


def show_urls():
    config = json.loads(run('config', '--format', 'json', capture=True))
    host = config['services']['provision']['environment']['LAB_HOST']
    print(f'\nParticipant guide: http://{host}:8080/guide')
    print(f'Projector dashboard: http://{host}:8080/dashboard')
    print(f'Health check: http://{host}:8080/health')
    print('Assign pairs team01 onward. Allow lab LAN TCP ports 8080, 2121, 1883, 30000–30009.')


def execute(action):
    if action == 'prepare':
        configure()
        config = json.loads(run('config', '--format', 'json', capture=True))
        secret = config['services']['http']['environment']['WORKER_CALLBACK_SECRET']
        if not secret or secret == 'replace-with-a-random-secret-before-starting':
            raise ValueError('Replace the example WORKER_CALLBACK_SECRET in .env with a random secret.')
        run('build')
        run('run', '--rm', '--no-deps', '--pull', 'never', 'provision')
        print('Preparation complete. Start the session with: python3 scripts/instructor.py start')
    elif action == 'start':
        run('up', '-d', '--wait', '--no-build', '--pull', 'never')
        show_urls()
    elif action == 'status':
        run('ps')
        show_urls()
    elif action == 'stop':
        run('down')
        print('Lab stopped. Credentials, uploads and progress are preserved.')
    elif action == 'reset':
        print('Reset deletes all team credentials, uploaded files and completion progress.')
        if input('Type RESET to regenerate the lab: ').strip() != 'RESET':
            print('Reset cancelled. Nothing changed.')
            return
        run('down', '--volumes', '--remove-orphans')
        run('run', '--rm', '--no-deps', '--pull', 'never', 'provision')
        run('up', '-d', '--wait', '--no-build', '--pull', 'never')
        show_urls()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'start', 'status', 'stop', 'reset'],
                        nargs='?', default='start', help='Default: start. Run prepare before the first session.')
    args = parser.parse_args()
    try:
        if args.action != 'prepare' and not (ROOT / '.env').exists():
            raise ValueError('No .env found. First run: python3 scripts/instructor.py prepare')
        run('version')
        execute(args.action)
    except FileNotFoundError:
        print('Docker was not found. Install Docker with Compose and start its engine.', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError:
        print('Docker command failed; no further steps were run. Check Docker access and the error above.\n'
              'If images are missing, run prepare while online before starting the session.', file=sys.stderr)
        return 1
    except (ValueError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print('\nCancelled.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
