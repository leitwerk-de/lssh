import unittest

from lssh.matching import has_glob, matches_host_term, matches_host_terms


class HostMatchingTests(unittest.TestCase):
    def test_globs_match_complete_alias_case_insensitively(self):
        for pattern in ('srv01.ba.*', 'SRV0?.BA.*', 'srv0[12].ba.*', '*ba*', '*'):
            with self.subTest(pattern=pattern):
                self.assertTrue(matches_host_term('Srv01.ba.example.org', [], pattern))
        for pattern in ('srv02.ba.*', 'srv0[23].ba.*', 'ba.*', 'srv01.ba.?', 'srv01.ba.[!e]*'):
            with self.subTest(pattern=pattern):
                self.assertFalse(matches_host_term('srv01.ba.example.org', [], pattern))

    def test_globs_never_match_keywords(self):
        self.assertFalse(matches_host_term('other', ['srv01.ba.example.org'], 'srv01.ba.*'))

    def test_digit_class_is_exactly_one_digit(self):
        self.assertTrue(matches_host_term('srv7.ba.example', [], 'srv[0-9].*'))
        self.assertFalse(matches_host_term('srv01.ba.example', [], 'srv[0-9].*'))
        self.assertTrue(matches_host_term('srv01.ba.example', [], 'srv[0-9][0-9].*'))

    def test_regex_quantifiers_and_full_alias_matching(self):
        for alias in ('srv1.ba.example', 'SRV01.ba.example', 'srv123.ba.example'):
            self.assertTrue(matches_host_terms(alias, ['produktion'], [r'srv[0-9]{1,3}\..*', 'prod'], regex=True))
        for alias in ('srv1234.ba.example', 'prefixsrv1.ba.example', 'srvx.ba.example'):
            self.assertFalse(matches_host_terms(alias, [], [r'srv[0-9]{1,3}\..*'], regex=True))
        self.assertFalse(matches_host_terms('other', ['srv1.ba.example'], ['srv[0-9]{1,3}.*'], regex=True))
        self.assertFalse(matches_host_terms('srv01.ba.example', [], ['srv[0-9]{1,3}.*']))

    def test_substring_and_keyword_case_are_preserved(self):
        self.assertTrue(matches_host_term('SRV01.ba.example', [], 'srv01'))
        self.assertTrue(matches_host_term('other', ['Production'], 'Prod'))
        self.assertFalse(matches_host_term('other', ['Production'], 'prod'))

    def test_all_terms_are_required(self):
        self.assertTrue(matches_host_terms('srv01.ba.example', ['produktion'], ['srv0?.*', '*example', 'prod']))
        self.assertFalse(matches_host_terms('srv01.ba.example', ['produktion'], ['srv0?.*', '*other']))
        self.assertFalse(matches_host_terms('srv01.ba.example', ['test'], ['srv0?.*', 'prod']))
        self.assertTrue(matches_host_terms('any', [], []))

    def test_bracket_detection_and_literal_unclosed_bracket(self):
        self.assertTrue(has_glob('srv['))
        self.assertTrue(matches_host_term('srv[', [], 'srv['))
        self.assertFalse(matches_host_term('before-srv[', [], 'srv['))
        self.assertTrue(matches_host_term('srv1', [], 'srv[!2]'))
        self.assertFalse(has_glob('srv01'))


if __name__ == '__main__':
    unittest.main()
