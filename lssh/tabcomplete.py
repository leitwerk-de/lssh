from json import load
from os import environ
from pathlib import Path
from sys import argv
import shlex
import re

try:
    from xdg import xdg_cache_home
except ImportError:
    from xdg.BaseDirectory import xdg_cache_home # Fallback for old xdg version (debian)

from lssh import recordings
from lssh.cli_args import parameter_options
from lssh.matching import has_glob, matches_host_term, matches_host_terms

# To activate tab completion in bash:
# complete -C 'lssh __complete__' lssh

def completion_words(line):
    """Parse shell words, including the active word and unfinished quotes.

    A sentinel distinguishes trailing whitespace from whitespace inside quotes.
    shlex performs no shell expansion or command execution.
    """
    lexer = shlex.shlex(line + '\0', posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ''
    words = []
    while True:
        try:
            word = lexer.get_token()
        except ValueError:
            # While typing, an open quote is a normal partial word.
            word = lexer.token
            words.append(word.removesuffix('\0'))
            break
        if word is None:
            break
        words.append(word.removesuffix('\0'))
    return words


def completion_context():
    if 'COMP_LINE' not in environ:
        current = argv[3] if len(argv) > 3 else ''
        previous = argv[4] if len(argv) > 4 else ''
        value_option = previous if previous in ('--timestamp', '--load-from', '--validate') else None
        return [], current, value_option, False
    line = environ['COMP_LINE']
    try:
        # Bash reports the cursor offset in bytes, not Unicode characters.
        line = line.encode()[:int(environ.get('COMP_POINT', len(line.encode())))].decode(errors='ignore')
    except ValueError:
        pass
    words = completion_words(line)[1:]
    terms = []
    pending = None
    options_ended = False
    regex = False
    for index, word in enumerate(words):
        active = index == len(words) - 1
        if pending:
            if active:
                return terms, word, pending, regex
            pending = None
        elif word == '--' and not options_ended:
            if active:
                return terms, word, 'option', regex
            options_ended = True
        elif word.startswith('-') and not options_ended:
            if active:
                return terms, word, 'option', regex
            if word == '--regex':
                regex = True
            if word in ('--timestamp', '--load-from', '--validate'):
                pending = word
            elif not word.startswith('--'):
                for offset, option in enumerate(word[1:], 1):
                    if option in parameter_options:
                        if offset == len(word) - 1:
                            pending = '-' + option
                        break
        elif active:
            return terms, word, None, regex
        else:
            terms.append(word)
    return terms, '', None, regex


def find_substrings():
    terms = completion_context()[0]
    if terms:
        terms[0] = terms[0].split('@', 1)[-1]
    return terms

def contains_substring(keywords, substring):
    for keyword in keywords:
        if substring in keyword:
            return True
    return False

def contains_all_substrings(keywords, substrings):
    for substr in substrings:
        if not contains_substring(keywords, substr):
            return False
    return True

def timestamp_completions(substrings):
    def matches(entry):
        return contains_all_substrings(entry[2], substrings)
    return [entry[1] for entry in recordings.find_recording_files() if matches(entry)]

def parse_hosts(hosts_dir):
    from json import dump
    from lssh.hostlist import load_config

    config, _ = load_config(hosts_dir, suppress_errors=True)
    hosts = {}
    for display_name in config:
        hosts[display_name] = list(config[display_name].keywords)
    return hosts

def host_cache_path():
    if type(xdg_cache_home) is str:
        cache = Path(xdg_cache_home)
    else:
        cache = xdg_cache_home()
    return cache / 'lssh' / 'hosts.json'

# Check if the given new_keyword reduces the given hosts in host_choices
# True, if there is at least one host that does not match the new_keyword
def restricts(new_keyword, host_choices, host_keyword_map):
    for host in host_choices:
        if not matches_host_term(host, host_keyword_map[host], new_keyword):
            return True
    return False

def main(hosts_dir):
    if len(argv) < 5:
        return
    terms, current_arg, value_option, regex = completion_context()

    if value_option == '--timestamp':
        # timestamp completion
        choices = timestamp_completions(find_substrings())
    elif value_option in ('--load-from', '--validate'):
        # file path completion
        from shlex import quote
        from subprocess import run
        from sys import exit
        compgen_cmd = "compgen -d -- " + quote(current_arg)
        exit(run(["bash", "-c", compgen_cmd]).returncode)
    elif value_option == 'option' or current_arg.startswith('-'):
        # option completion
        choices = ['--help', '--load-from', '--regex', '--replay', '--timestamp', '--update-hosts', '--validate', '--verbose', '--version']
    elif value_option is not None:
        return
    else:
        # substring completion
        try:
            try:
                with open(host_cache_path(), 'r') as f:
                    hosts = load(f)
            except FileNotFoundError:
                hosts = parse_hosts(hosts_dir)
            substrings = find_substrings()
            if any('@' in term for term in substrings[1:]) or (substrings and '@' in current_arg):
                return
            user_prefix = ''
            if not substrings and '@' in current_arg:
                user, current_arg = current_arg.split('@', 1)
                user_prefix = user + '@'
            host_choices = {h for h in hosts if matches_host_terms(h, hosts[h], substrings, regex=regex)}
            if len(host_choices) == 1 and any(not has_glob(term) and term.lower() == next(iter(host_choices)).lower() for term in substrings):
                # Only one host remaining and this host is already given explicitly. No further suggestions for the tab-completion
                choices = []
            else:
                if regex and not substrings:
                    choices = {h for h in host_choices if matches_host_terms(h, hosts[h], [current_arg], regex=True)}
                elif has_glob(current_arg):
                    choices = {h for h in host_choices if matches_host_term(h, hosts[h], current_arg)}
                else:
                    choices = {h for h in host_choices if h.lower().startswith(current_arg.lower())}
                    if not user_prefix:
                        keyword_options = {keyword for h in host_choices for keyword in hosts[h]}
                        choices |= {keyword for keyword in keyword_options if keyword.startswith(current_arg) and restricts(keyword, host_choices, hosts)}
                choices = {user_prefix + choice for choice in choices}
        except (FileNotFoundError, re.error):
            choices = []
        if choices:
            print("\n".join(sorted(choices)))
        return
    result = [x for x in choices if x.startswith(current_arg)]
    print("\n".join(result))
