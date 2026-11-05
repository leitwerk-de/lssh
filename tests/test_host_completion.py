import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lssh import tabcomplete


HOSTS = {
    'Srv01.ba.example': ['produktion', 'team blue'],
    'srv02.ba.example': ['test'],
    'srv01.other.example': ['produktion'],
    'unrelated': ['srv01.ba.example'],
}


class HostCompletionTests(unittest.TestCase):
    def complete(self, line, cache=True, point=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hosts.json'
            if cache:
                path.write_text(json.dumps(HOSTS))
            environment = {'COMP_LINE': line, 'COMP_POINT': str(len(line.encode()) if point is None else point)}
            output = io.StringIO()
            with patch.dict(os.environ, environment), patch.object(tabcomplete, 'host_cache_path', return_value=path), patch.object(tabcomplete, 'parse_hosts', return_value=HOSTS) as parse, patch.object(tabcomplete, 'argv', ['lssh', '__complete__', 'lssh', '', '']), contextlib.redirect_stdout(output):
                tabcomplete.main(directory)
            self.assertEqual(parse.call_count, 0 if cache else 1)
            return output.getvalue().splitlines()

    def test_current_glob_matches_only_aliases(self):
        for pattern in ("'srv0?.ba.*'", '"srv0[12].ba.*"', 'srv0\\?.ba.\\*', "'srv0?.ba.*", '"srv0?.ba.*'):
            for cache in (True, False):
                with self.subTest(pattern=pattern, cache=cache):
                    self.assertEqual(self.complete('lssh ' + pattern, cache), ['Srv01.ba.example', 'srv02.ba.example'])

    def test_previous_glob_and_keyword_restrict_current(self):
        self.assertEqual(self.complete("lssh 'srv0?.ba.*' prod"), ['produktion'])
        self.assertEqual(self.complete("lssh 'srv0?.ba.*' produktion "), ['Srv01.ba.example'])
        self.assertEqual(self.complete("lssh 'srv0?.ba.*' '*02*' "), ['srv02.ba.example'])
        self.assertEqual(self.complete("lssh 'srv0?.ba.*' 'team blue' "), ['Srv01.ba.example'])
        self.assertEqual(self.complete('lssh srv01.ba.* Prod'), [])

    def test_user_prefix_is_preserved_on_current_alias(self):
        self.assertEqual(self.complete("lssh 'root@srv01.ba.*'"), ['root@Srv01.ba.example'])
        self.assertEqual(self.complete('lssh root@srv02'), ['root@srv02.ba.example'])
        self.assertEqual(self.complete("lssh 'root@srv0?.ba.*' test "), ['srv02.ba.example'])
        self.assertEqual(self.complete('lssh prod root@srv*'), [])
        self.assertEqual(self.complete('lssh prod root@srv* '), [])

    def test_explicit_unique_alias_has_no_further_suggestions(self):
        self.assertEqual(self.complete('lssh srv02.ba.example '), [])
        self.assertEqual(self.complete('lssh SRV01.BA.EXAMPLE '), [])
        self.assertEqual(self.complete('lssh root@srv02.ba.example '), [])

    def test_unfinished_plain_tokens_keep_prefix_semantics(self):
        self.assertEqual(self.complete('lssh rv01'), [])
        self.assertEqual(self.complete('lssh SRV02'), ['srv02.ba.example'])

    def test_ssh_and_lssh_option_values_are_not_host_filters(self):
        for options in ('-p 2222', '-p2222', '-vp 2222', '-o "Name value"', '--validate /tmp/config', '--validate=/tmp/config', '--timestamp 2026-01-01_00-00-00'):
            with self.subTest(options=options):
                self.assertEqual(self.complete('lssh ' + options + ' srv02'), ['srv02.ba.example'])
        self.assertEqual(self.complete('lssh -p '), [])

    def test_quoted_escaped_and_open_words(self):
        self.assertEqual(tabcomplete.completion_words('lssh "team blue" srv'), ['lssh', 'team blue', 'srv'])
        self.assertEqual(tabcomplete.completion_words("lssh 'team blue"), ['lssh', 'team blue'])
        self.assertEqual(tabcomplete.completion_words('lssh team\\ blue '), ['lssh', 'team blue', ''])
        self.assertEqual(tabcomplete.completion_words('lssh "team '), ['lssh', 'team '])
        self.assertEqual(tabcomplete.completion_words('lssh srv\\'), ['lssh', 'srv'])
        self.assertEqual(tabcomplete.completion_words("lssh '' "), ['lssh', '', ''])

    def test_completion_uses_cursor_position(self):
        line = 'lssh srv02 ignored'
        self.assertEqual(self.complete(line, point=len('lssh srv02')), ['srv02.ba.example'])
        line = 'lssh -o "é value" srv02 ignored'
        self.assertEqual(self.complete(line, point=len('lssh -o "é value" srv02'.encode())), ['srv02.ba.example'])

    def test_option_completion(self):
        self.assertIn('--help', self.complete('lssh --'))
        self.assertEqual(self.complete('lssh --reg'), ['--regex'])
        self.assertEqual(self.complete('lssh --val'), ['--validate'])

    def test_regex_completion_and_additional_filters(self):
        self.assertEqual(self.complete("lssh --regex 'root@srv[0-9]{1,3}\\.ba\\..*'"), ['root@Srv01.ba.example', 'root@srv02.ba.example'])
        self.assertEqual(self.complete("lssh --regex 'srv[0-9]{1,3}\\.ba\\..*' produktion "), ['Srv01.ba.example'])
        self.assertEqual(self.complete("lssh --regex 'srv['"), [])
        self.assertEqual(self.complete("lssh --regex 'srv[' test "), [])
        self.assertEqual(self.complete("lssh -o --regex 'srv0?.ba.*'"), ['Srv01.ba.example', 'srv02.ba.example'])

    def test_directory_completion_still_delegates_to_bash(self):
        for option in ('--load-from', '--validate'):
            with self.subTest(option=option), patch.dict(os.environ, {'COMP_LINE': 'lssh ' + option + ' "/tmp/team blue', 'COMP_POINT': '999'}), patch.object(tabcomplete, 'argv', ['lssh', '__complete__', 'lssh', '', '']), patch('subprocess.run') as run:
                run.return_value.returncode = 0
                with self.assertRaises(SystemExit):
                    tabcomplete.main('/unused')
                self.assertEqual(run.call_args.args[0], ['bash', '-c', "compgen -d -- '/tmp/team blue'"])

    def test_missing_cache_and_host_directory_are_silent(self):
        with patch.dict(os.environ, {'COMP_LINE': 'lssh srv', 'COMP_POINT': '8'}), patch.object(tabcomplete, 'argv', ['lssh', '__complete__', 'lssh', '', '']), patch.object(tabcomplete, 'host_cache_path', side_effect=FileNotFoundError), patch.object(tabcomplete, 'parse_hosts', side_effect=FileNotFoundError), contextlib.redirect_stdout(io.StringIO()) as output:
            tabcomplete.main('/missing')
        self.assertEqual(output.getvalue().strip(), '')

    def test_shell_expressions_are_never_evaluated(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'executed'
            self.complete('lssh "$(touch ' + str(marker) + ')"')
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
