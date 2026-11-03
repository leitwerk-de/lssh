# SSH config format

The lssh tool expects to find your ssh host configuration in a git repository. In the top-level directory of your repository, each file ending with `.txt` is read as an ssh configuration file.

Here is an example, how an ssh configuration file may look like:

```
Host example.com
    User root

Host a.example.com
    Port 4444

Host fileserver
    HostName ftp.central.example.com
    User ftp
```

These files are included in the configuration of ssh and must therefore be valid ssh_config syntax. But lssh puts further restrictions on the allowed configurations for security reasons. (For example to disallow code execution)

## Disallowed ssh_config options

For security reasons, the following options cannot be configured via the central git repository:

- ControlPath
- Match
- ForwardAgent
- ForwardX11
- ForwardX11Timeout
- ForwardX11Trusted
- GSSAPIDelegateCredentials
- HashKnownHosts
- HostKeyAlias
- CheckHostIP
- StrictHostKeyChecking
- UpdateHostKeys
- UserKnownHostsFile
- VerifyHostKeyDNS
- VisualHostKey
- Include
- LocalCommand
- PermitLocalCommand
- ProxyUseFdpass
- RemoteCommand
- XAuthLocation
- SendEnv

If one of these options appears in the git repository, lssh will not update the affected files in its machine-local configuration but will instead show an error message when executing `lssh --update-hosts`.

### RemoteCommand

A special case is the RemoteCommand config option, because you can specify a whitelist of allowed commands. For details, see [remote-command-whitellist.md](remote-command-whitellist.md).

## Additional lssh attributes

In each configuration file the options `#lssh:displayname` and `#lssh:filekeywords` can be specified once per file, see the following example:

```
#lssh:displayname example.com Hosts
#lssh:filekeywords demo, unreal

Host fileserver
    #lssh:keywords transfer, storage
    #lssh:assignedcustomer important-company
    HostKeyAlias fileserver
    HostName ftp.central.example.com
    User ftp
```

The hash character makes thiese lines a comment for ssh, but lssh reads these settings.

### `#lssh:displayname`

The value of this options tells lssh how to display this file (typically associated with one customer) in the tui dialog. If not given, the filename is used instead.

### `#lssh:filekeywords`

The comma-separated keywords of this options are associated with all hosts of this file. If one of the filekeywords or a substring of them is given on the lssh commandline, it will match all hosts of this file.

### `#lssh:keywords`

Keywords must be specified inside of a host block. If one of the given keywords or a substring is given on the lssh call, it will match this specific host.

### `#lssh:assignedcustomer`

This attribute allows to assign hosts of one file to a customer that is normally associated with another file. This is useful for adding automatic host-exports to the repository without modifying user-edited files.

Assume, the file in the example above is called `example.txt`. The `#lssh:assignedcustomer` instruction will ensure, that `fileserver` appears in the same customer section as the hosts defined in `important-company.txt`. Without this instruction, it would appear in the section `example.com Hosts`.

The names of both files will be added as search keywords for affected hosts. Filekeywords are taken from the file where the host is acutally described, not where it is assigned to.
