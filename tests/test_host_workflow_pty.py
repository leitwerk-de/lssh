"""End-to-end host selection with real PTYs and a local SSH argument probe."""

import errno
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest


ROOT = Path(__file__).parents[1]


@unittest.skipUnless(os.name == 'posix', 'requires POSIX pseudo terminals')
class HostWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.hosts = self.root / 'hosts'
        self.hosts.mkdir()
        (self.hosts / 'customer.txt').write_text('''Host srv01.ba.example
    HostName srv01.invalid
    #lssh:keywords produktion
Host srv02.ba.example
    HostName srv02.invalid
    #lssh:keywords test
Host *.ignored
    User ignored
''')
        self.probe = self.root / 'ssh-arguments.json'
        binary = self.root / 'bin'
        binary.mkdir()
        ssh = binary / 'ssh'
        ssh.write_text('#!' + sys.executable + '\nimport json,os,sys\n'
                       'open(os.environ["SSH_PROBE"],"w").write(json.dumps(sys.argv[1:]))\n'
                       'print("LOCAL_SSH_PROBE")\nraise SystemExit(23)\n')
        ssh.chmod(0o755)
        self.launcher = self.root / 'lssh-test'
        self.launcher.write_text('import os\nfrom lssh import main\n'
                                 'main.main(os.environ["TEST_HOSTS"], lambda: None)\n')
        self.environment = dict(os.environ, TERM='xterm', TEST_HOSTS=str(self.hosts),
                                SSH_PROBE=str(self.probe), SSH_AUTH_SOCK='/unused-local-probe',
                                PATH=str(binary) + os.pathsep + os.environ['PATH'],
                                XDG_CACHE_HOME=str(self.root / 'cache'),
                                XDG_DATA_HOME=str(self.root / 'data'),
                                PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')

    def run_cli(self, arguments, keys=None):
        master, slave = os.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 100, 0, 0))
        settings = termios.tcgetattr(slave)

        def child_setup():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

        process = subprocess.Popen([sys.executable, str(self.launcher), *arguments],
                                   stdin=slave, stdout=slave, stderr=slave,
                                   env=self.environment, preexec_fn=child_setup)
        os.close(slave)
        output = bytearray()
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                if select.select([master], [], [], .1)[0]:
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not data:
                        break
                    output.extend(data)
                    if keys is not None and b'select host' in output:
                        os.write(master, keys)
                        keys = None
                if process.poll() is not None:
                    break
            process.wait(timeout=2)
            self.assertEqual(termios.tcgetattr(master), settings)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        text = output.decode(errors='replace')
        self.assertNotIn('Traceback', text)
        return process.returncode, text

    def test_single_glob_passes_concrete_alias_to_ssh_and_records(self):
        code, output = self.run_cli(['root@srv0?.ba.*', 'produktion'])
        self.assertEqual(code, 23, output)
        self.assertEqual(json.loads(self.probe.read_text()), ['root@srv01.ba.example'])
        recordings = list((self.root / 'data/lssh/recordings').iterdir())
        self.assertEqual(len(recordings), 1)
        self.assertTrue(recordings[0].name.endswith('_srv01.ba.example'))
        self.assertIn('LOCAL_SSH_PROBE', (recordings[0] / 'output').read_text())
        self.assertTrue((recordings[0] / 'timing').exists())

    def test_digit_class_glob_with_one_digit_alias(self):
        with (self.hosts / 'customer.txt').open('a') as stream:
            stream.write('Host srv7.ba.example\n    HostName srv7.invalid\n')
        code, output = self.run_cli(['srv[0-9].*'])
        self.assertEqual(code, 23, output)
        self.assertEqual(json.loads(self.probe.read_text()), ['srv7.ba.example'])

    def test_regex_quantifier_with_username_and_keyword(self):
        code, output = self.run_cli(['--regex', r'root@srv[0-9]{1,3}\..*', 'produktion'])
        self.assertEqual(code, 23, output)
        self.assertEqual(json.loads(self.probe.read_text()), ['root@srv01.ba.example'])

    def test_invalid_regex_never_starts_ssh(self):
        code, output = self.run_cli(['--regex', 'srv['])
        self.assertEqual(code, 1, output)
        self.assertIn('Invalid host regular expression', output)
        self.assertFalse(self.probe.exists())

    def test_multiple_glob_matches_can_be_selected_in_real_tui(self):
        code, output = self.run_cli(['srv0?.ba.*'], b'\r\r')
        self.assertEqual(code, 23, output)
        self.assertEqual(json.loads(self.probe.read_text()), ['srv01.ba.example'])

    def test_cancelled_glob_selection_never_starts_ssh(self):
        code, output = self.run_cli(['srv0?.ba.*'], b'q')
        self.assertEqual(code, 1, output)
        self.assertFalse(self.probe.exists())

    def test_no_match_never_starts_ssh(self):
        code, output = self.run_cli(['srv03.ba.*'])
        self.assertEqual(code, 1, output)
        self.assertIn('No matching hosts', output)
        self.assertFalse(self.probe.exists())

    def test_bash_invokes_completion_with_and_without_host_cache(self):
        environment = dict(self.environment, COMP_LINE="lssh 'root@srv0?.ba.*'", COMP_POINT='999')
        for cached in (False, True):
            with self.subTest(cached=cached):
                process = subprocess.run(['bash', '-c', '"$1" "$2" __complete__ lssh "root@srv0?.ba.*" lssh',
                                          'completion-test', sys.executable, str(self.launcher)],
                                         env=environment, capture_output=True, text=True, check=True)
                self.assertEqual(process.stdout.splitlines(), ['root@srv01.ba.example', 'root@srv02.ba.example'])


if __name__ == '__main__':
    unittest.main()
