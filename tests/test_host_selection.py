import contextlib
import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lssh import cli, cli_args
from lssh.hostlist import HostEntry


def host(alias, keywords=()):
    entry = HostEntry(alias, 'customer')
    entry.keywords.update(keywords)
    return entry


class HostSelectionTests(unittest.TestCase):
    def setUp(self):
        self.hosts = {alias: host(alias, keywords) for alias, keywords in (
            ('srv01.ba.example', ['produktion']),
            ('srv02.ba.example', ['test']),
            ('other', ['srv01.ba.example']),
        )}
        self.config = patch('lssh.hostlist.load_config', return_value=(self.hosts, {}))
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_one_match_is_concrete_alias(self):
        self.assertEqual(cli.select_host('srv0?.ba.*', ['prod'], '/unused'), ('srv01.ba.example', ['srv01.ba.example']))

    def test_regex_selects_alias_and_preserves_keyword_filter(self):
        self.assertEqual(cli.select_host(r'srv[0-9]{1,3}\..*', ['prod'], '/unused', regex=True)[0], 'srv01.ba.example')

    def test_invalid_regex_is_reported_without_loading_hosts(self):
        with contextlib.redirect_stderr(io.StringIO()) as output, self.assertRaises(SystemExit):
            cli.select_host('srv[', [], '/unused', regex=True)
        self.assertIn('Invalid host regular expression', output.getvalue())
        cli.hostlist.load_config.assert_not_called()

    def test_regex_requires_pattern_and_connection_mode(self):
        for arguments in (['--regex'], ['--regex', '--replay', 'srv.*'], ['--regex', '--version', 'srv.*']):
            with self.subTest(arguments=arguments), patch.object(sys, 'argv', ['lssh'] + arguments):
                args = cli_args.parse_args()
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    cli.check_for_conflicting_args(args)

    def test_no_match_preserves_error(self):
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as error:
            cli.select_host('missing.*', [], '/unused')
        self.assertEqual(error.exception.code, 1)
        self.assertIn('No matching hosts', output.getvalue())

    def test_multiple_matches_use_existing_tui(self):
        with patch('lssh.tui_dialog.hierarchical_option_dialog', return_value=(0, 1)) as dialog:
            self.assertEqual(cli.select_host('srv0?.ba.*', [], '/unused')[0], 'srv02.ba.example')
        self.assertEqual(dialog.call_args.args[0], [('customer', ['srv01.ba.example', 'srv02.ba.example'])])

    def test_tui_cancel_stops_without_connecting(self):
        with patch('lssh.tui_dialog.hierarchical_option_dialog', return_value=None), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.select_host('srv0?.ba.*', [], '/unused')
        self.assertEqual(error.exception.code, 1)

    def test_user_prefix_and_later_username_validation(self):
        self.assertEqual(cli.split_user_from_substring('root@srv01.ba.*'), ('root', 'srv01.ba.*'))
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
            cli.ensure_no_usernames(['prod', 'root@srv*'])

    def test_ssh_receives_alias_and_status_not_glob(self):
        with patch.object(sys, 'argv', ['lssh', 'root@srv01.ba.*']):
            args = cli_args.parse_args()
        with patch('lssh.cli.create_recording_directory', return_value=None), patch('lssh.ssh_agent.get_environment', return_value={}), patch('lssh.cli.subprocess.run', return_value=SimpleNamespace(returncode=23)) as run, contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.connect(args, 'root', 'srv01.ba.*', [], '/unused')
        self.assertEqual(run.call_args.args[0], ['ssh', 'root@srv01.ba.example'])
        self.assertEqual(error.exception.code, 23)


if __name__ == '__main__':
    unittest.main()
