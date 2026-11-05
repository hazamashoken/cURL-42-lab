import json
import os
import socket
from pathlib import Path

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


def make_server():
    config = json.loads((Path(os.getenv('FIXTURES_DIR', '/fixtures')) / 'config.json').read_text())
    root = Path(os.getenv('FTP_ROOT', '/ftp')).resolve()
    authorizer = DummyAuthorizer()
    for team, entry in config['teams'].items():
        authorizer.add_user(team, entry['ftp_password'], str(root / team), perm='elr')
        authorizer.override_perm(team, str(root / team / 'uploads'), perm='elrw', recursive=True)
    FTPHandler.authorizer = authorizer
    FTPHandler.masquerade_address = socket.gethostbyname(os.environ['FTP_PASSIVE_ADDRESS'])
    FTPHandler.passive_ports = range(30000, 30010)
    FTPHandler.banner = 'Crack the Cracker FTP lab'
    server = FTPServer(('0.0.0.0', 2121), FTPHandler)
    server.max_cons = 128
    server.max_cons_per_ip = 32
    return server


if __name__ == '__main__':
    make_server().serve_forever()
