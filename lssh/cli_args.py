import argparse

parameterless_options = '46AaCfGgKkMNnqsTtVXxYy'
parameter_options = 'BbcDEeFIiJLlmOopQRSWw'

def parse_args():
    parser = argparse.ArgumentParser(prog='lssh')

    parser.add_argument('-r', '--replay', dest='replay', action='store_true', help='Watch a previously recored ssh session.')
    parser.add_argument('--timestamp', metavar='TIME', dest='time', help='The exact timestamp when the session recording was started, in the form YYYY-MM-DD_hh-mm-ss. (Implies --replay)')
    parser.add_argument('--update-hosts', dest='update', action='store_true', help='Update the hostlist configuration files using the configured command. (Typically git pull followed by lssh --load-from ...)')
    parser.add_argument('--load-from', dest='load', metavar='SRCDIR', help='Load a new ssh config from the directory SRCDIR (that contains them as *.txt files), validate the config and (if valid) store it at the central location configured in lssh. You should not call this manually but instead run `lssh --update-hosts` that will also pull updates before loading the files.')
    parser.add_argument('--validate', dest='validate', metavar='CONFDIR', help='Load the given ssh config from the directory CONFDIR, validate it, but do not store it anywhere. If valid, lssh will print nothing and exit with 0. If invalid, lssh will print the errors and exit with a non-zero exit status.')
    parser.add_argument('-v', '--verbose', action='count', help='Verbose mode. Enables printing the resulting ssh command line before connecting.')
    parser.add_argument('--version', dest='version', action='store_true', help='Show the current version number and exit.')
    parser.add_argument('--regex', action='store_true', help='Treat the first host term as a case-insensitive regular expression matching the entire alias. Additional terms remain substring/keyword/glob filters. Connection mode only.')

    options_summary = [c for c in parameterless_options + parameter_options]
    options_summary.sort(key=lambda c: (str.lower(c), c))
    pass_through = parser.add_argument_group('ssh options', 'The following options are passed through to the ssh command: ' + "".join(options_summary) + ", see the ssh(1) man page for details.")
    for opt in parameterless_options:
        pass_through.add_argument('-' + opt, action='count', help=argparse.SUPPRESS)
    for opt in parameter_options:
        pass_through.add_argument('-' + opt, action='append', help=argparse.SUPPRESS)

    parser.add_argument('substring', metavar='[user@]term', nargs='?', help="Host alias substring or keyword; terms containing *, ? or [ match the entire alias as a glob. Quote patterns, e.g. 'srv01.ba.*'. An optional user@ prefix sets the SSH user.")
    parser.add_argument('additional_substrings', metavar='term', nargs='*', help='Additional substring, keyword or quoted alias glob filters; every term must match.')

    return parser.parse_args()
