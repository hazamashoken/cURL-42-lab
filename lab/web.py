import hmac
import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from flask import Flask, Response, abort, jsonify, render_template, request


def create_app(fixtures=None, state=None, callback_secret=None):
    fixtures = Path(fixtures or os.getenv('FIXTURES_DIR', '/fixtures'))
    state = Path(state or os.getenv('STATE_DIR', '/state'))
    secret = callback_secret or os.environ['WORKER_CALLBACK_SECRET']
    if not secret:
        raise ValueError('Callback secret must not be empty')
    config = json.loads((fixtures / 'config.json').read_text())
    teams = config['teams']
    host = config['host']
    state.mkdir(parents=True, exist_ok=True)
    database = state / 'progress.sqlite3'
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS completions (team TEXT PRIMARY KEY, completed_at TEXT NOT NULL)')
    app = Flask(__name__, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 4096

    def plain(body, status=200, headers=None):
        return Response(body + '\n', status=status, headers=headers, mimetype='text/plain')

    def get_team(team):
        if team not in teams:
            abort(404)
        return teams[team]

    @app.after_request
    def no_cache(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/health')
    def health():
        return plain('ok')

    @app.get('/start')
    def start():
        return plain('The briefing moved. Follow the redirect.', 302,
                     {'Location': '/briefing', 'X-Lab-Clue': 'look-beyond-the-body'})

    @app.get('/briefing')
    def briefing():
        return plain('Crack the Cracker — Three Protocols, One Tool\n'
                     'Inspect HTTP headers, check in with your team, explore FTP, then chat over MQTT.\n'
                     f'Guide: http://{host}:8080/guide\n'
                     'POST your team as URL-encoded form data to /check-in.\n'
                     'Final challenge: /challenge/YOUR_TEAM')

    @app.get('/guide')
    def guide():
        return plain((fixtures / 'participant-guide.md').read_text())

    @app.post('/check-in')
    def check_in():
        team = request.form.get('team', '')
        if team not in teams:
            return plain('Unknown team. Ask your facilitator for your identifier.', 400)
        return plain(f'Team: {team}\nFTP username: {team}\n'
                     f'FTP password: {teams[team]["ftp_password"]}\n'
                     f'FTP address: ftp://{host}:2121/\n'
                     'Next objective: list your FTP directory and download briefing.txt.')

    @app.get('/challenge/<team>')
    def challenge(team):
        entry = get_team(team)
        return plain('Find the next file. Follow the clues across three protocols.',
                     headers={'X-Next-File': entry['challenge_file']})

    @app.get('/api/<team>/mission')
    def mission(team):
        entry = get_team(team)
        if not hmac.compare_digest(request.headers.get('Authorization', '').encode(),
                                   f'Bearer {entry["token"]}'.encode()):
            return plain('A valid team bearer token is required.', 401,
                         {'WWW-Authenticate': 'Bearer'})
        return plain(f'Unlock topic: lab/{team}/unlock\nResult topic: lab/{team}/result\n'
                     f'One-time unlock code: {entry["unlock_code"]}\n'
                     'Subscribe to the result topic BEFORE publishing the exact code.')

    @app.post('/internal/complete/<team>')
    def complete(team):
        if not hmac.compare_digest(request.headers.get('Authorization', '').encode(),
                                   f'Bearer {secret}'.encode()):
            return plain('Forbidden', 403)
        get_team(team)
        with closing(sqlite3.connect(database, timeout=10)) as db, db:
            inserted = db.execute('INSERT OR IGNORE INTO completions VALUES (?, ?)',
                                  (team, datetime.now(timezone.utc).isoformat())).rowcount
        return plain(f'{team}: Unlocked! Cracker cracked.' if inserted else f'{team}: already unlocked.')

    @app.get('/progress')
    def progress():
        with closing(sqlite3.connect(database)) as db:
            completed = dict(db.execute('SELECT team, completed_at FROM completions'))
        rows = [{'team': team, 'unlocked': team in completed,
                 'completed_at': completed.get(team)} for team in teams]
        return jsonify(teams=rows, completed=sum(row['unlocked'] for row in rows))

    @app.get('/dashboard')
    def dashboard():
        return render_template('dashboard.html')

    return app
