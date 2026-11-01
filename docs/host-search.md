# Selecting hosts

Host search applies to configured, concrete `Host` aliases. `HostName` is not
a separate search field, and patterns do not discover hosts through DNS.

Without glob characters, each term is a substring of an alias or a keyword.
Aliases are compared without case sensitivity. Keywords keep their existing
case-sensitive matching. Multiple terms are combined with AND; different terms
may match different keywords or the alias.

Terms containing `*`, `?` or `[` instead match the **entire alias**, using
Python's `fnmatchcase` rules after lowercasing the alias and pattern. They do not
match keywords. `*` matches any number of characters, including dots; `?`
matches one character; `[12]` and `[!12]` select or exclude characters.

Always quote patterns so that your shell does not expand local filenames:

```bash
lssh srv01
lssh 'srv01.ba.*'
lssh 'srv0?.ba.*'
lssh 'srv0[12].ba.*'
lssh 'root@srv01.ba.*' produktion
```

Only the first term may contain `user@`. A single matching alias connects
directly. Multiple matches open the existing host selection dialog; cancelling
does not connect. No matches produce an error. SSH always receives one concrete
alias, never the pattern.

Bash completion uses the same matching rules for completed filters and a current
glob. It understands quoted and escaped words, including an unfinished quote,
and preserves the first term's user prefix. An ordinary unfinished term uses
prefix completion. After an exact unique alias, no further host or keyword
suggestions are offered. SSH option values are not interpreted as host filters.

These rules concern host selection for connections. Recording and replay behavior
is unchanged.

## Digit classes and regular expressions

In a glob, `[0-9]` matches exactly one digit. Thus `lssh 'srv[0-9].*'`
matches `srv7.example`, but not `srv01.example`: the literal dot must follow
the first digit. For two digits, use `lssh 'srv[0-9][0-9].*'`.
Glob syntax does not interpret regex quantifiers such as `{1,3}`.

Use `--regex` to interpret the first host term as a Python regular expression
matching the entire alias, without case sensitivity:

```bash
lssh --regex 'srv[0-9]{1,3}.*'
lssh --regex 'root@srv[0-9]{1,3}\..*' produktion
```

In regex syntax `.` means any character; `\.` requires a literal dot.
Regex matching applies only to the alias. Additional terms retain their
ordinary substring, keyword or glob semantics and must all match. The first
term may still include a `user@` prefix. Invalid expressions produce an error
before a connection starts; unfinished invalid expressions in completion
produce no suggestions. `--regex` requires a host expression and cannot be
combined with replay, import, update, validation or version modes.
