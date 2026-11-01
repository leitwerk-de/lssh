"""Host search rules shared by selection and completion."""

from fnmatch import fnmatchcase
import re


def compile_host_regex(pattern):
    return re.compile(pattern, re.IGNORECASE)


def has_glob(term):
    return any(character in term for character in '*?[')


def matches_host_term(alias, keywords, term):
    if has_glob(term):
        return fnmatchcase(alias.lower(), term.lower())
    return term.lower() in alias.lower() or any(term in keyword for keyword in keywords)


def matches_host_terms(alias, keywords, terms, regex=False):
    if regex and terms:
        return compile_host_regex(terms[0]).fullmatch(alias) is not None and all(
            matches_host_term(alias, keywords, term) for term in terms[1:])
    return all(matches_host_term(alias, keywords, term) for term in terms)
