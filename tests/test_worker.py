import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from lab.provision import provision
from lab.web import create_app
from lab.worker import unlock_result


class WorkerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.config = provision(root / 'fixtures', root / 'ftp', 'lab.example', 2)
        self.teams = self.config['teams']
        self.client = create_app(root / 'fixtures', root / 'state', 'secret').test_client()
        self.code = self.teams['team01']['unlock_code'].encode()

    def process(self, payload, topic='lab/team01/unlock'):
        return unlock_result(self.teams, topic, payload, 'http://http:8080', 'secret')

    def test_exact_payload_and_team_validation(self):
        for payload in [b'wrong', self.code + b'\n', b' ' + self.code, b'\xff',
                        self.teams['team02']['unlock_code'].encode()]:
            self.assertIn('incorrect', self.process(payload))
        for topic in ['lab/team99/unlock', 'lab/team01/chat', 'lab/team01/unlock/extra', 'other/team01/unlock']:
            self.assertIsNone(self.process(self.code, topic))
        self.assertEqual(self.client.get('/progress').json['completed'], 0)

    def test_authenticated_callback_and_duplicate_through_http_app(self):
        def transport(request, timeout):
            self.assertEqual(request.full_url, 'http://http:8080/internal/complete/team01')
            self.assertEqual(timeout, 5)
            response = self.client.open('/internal/complete/team01', method=request.method,
                                        headers=dict(request.header_items()), data=request.data)
            self.assertEqual(response.status_code, 200)
            return io.BytesIO(response.data)

        with patch('lab.worker.urlopen', side_effect=transport):
            self.assertIn('Unlocked!', self.process(self.code))
            before = self.client.get('/progress').json
            self.assertIn('already unlocked', self.process(self.code))
        self.assertEqual(before, self.client.get('/progress').json)
        self.assertEqual(before['completed'], 1)

    def test_callback_failure_is_retryable(self):
        with patch('lab.worker.urlopen', side_effect=URLError('offline')):
            with self.assertLogs(level='ERROR'):
                self.assertIn('unavailable', self.process(self.code))
        self.assertEqual(self.client.get('/progress').json['completed'], 0)


if __name__ == '__main__':
    unittest.main()
