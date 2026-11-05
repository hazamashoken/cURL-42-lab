import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('instructor', Path(__file__).parents[1] / 'scripts/instructor.py')
instructor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(instructor)


class InstructorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root_patch = patch.object(instructor, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_configuration_is_private_and_preserved(self):
        with patch('builtins.input', side_effect=['192.168.50.10', '', '']):
            instructor.configure()
        path = self.root / '.env'
        original = path.read_text()
        self.assertIn('TEAM_COUNT=10', original)
        self.assertIn('FTP_PASSIVE_ADDRESS=192.168.50.10', original)
        self.assertEqual(len(original.split('WORKER_CALLBACK_SECRET=')[1].strip()), 64)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with patch('builtins.input', side_effect=AssertionError('Must preserve existing settings')):
            instructor.configure()
        self.assertEqual(original, path.read_text())

    def test_bad_input_does_not_write_configuration(self):
        for answers in [['http://bad/host', '', ''], ['lab.example', '100', ''],
                        ['lab.example', '2', 'bad host']]:
            with self.subTest(answers=answers), patch('builtins.input', side_effect=answers):
                with self.assertRaises(ValueError):
                    instructor.configure()
                self.assertFalse((self.root / '.env').exists())

    def test_start_is_offline_and_prints_configured_urls(self):
        config = {'services': {'provision': {'environment': {'LAB_HOST': 'lab.example'}},
                               'http': {'environment': {'WORKER_CALLBACK_SECRET': 'safe-secret'}}}}
        with patch.object(instructor, 'run', return_value=json.dumps(config)) as run, patch('builtins.print') as output:
            instructor.execute('start')
        commands = [call.args for call in run.call_args_list]
        self.assertIn(('up', '-d', '--wait', '--no-build', '--pull', 'never'), commands)
        self.assertIn('http://lab.example:8080/dashboard', str(output.call_args_list))
        self.assertFalse(any('build' in command for command in commands))

    def test_reset_decline_never_deletes_volumes(self):
        with patch('builtins.input', return_value='no'), patch.object(instructor, 'run') as run:
            instructor.execute('reset')
        run.assert_not_called()

    def test_reset_stops_before_reprovisioning(self):
        with patch('builtins.input', return_value='RESET'), patch.object(instructor, 'run', return_value='{}') as run:
            with patch.object(instructor, 'show_urls'):
                instructor.execute('reset')
        self.assertEqual([call.args for call in run.call_args_list], [
            ('down', '--volumes', '--remove-orphans'),
            ('run', '--rm', '--no-deps', '--pull', 'never', 'provision'),
            ('up', '-d', '--wait', '--no-build', '--pull', 'never'),
        ])

    def test_failure_stops_subsequent_commands(self):
        with patch.object(instructor, 'run', side_effect=subprocess.CalledProcessError(1, 'docker')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                instructor.execute('start')
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
