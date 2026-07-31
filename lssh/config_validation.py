import os, re, shlex, subprocess, tempfile

instruction_whitelist = {
    'addkeystoagent',
    'addressfamily',
    'batchmode',
    'bindaddress',
    'bindinterface',
    'canonicaldomains',
    'canonicalizefallbacklocal',
    'canonicalizehostname',
    'canonicalizemaxdots',
    'canonicalizepermittedcnames',
    'casignaturealgorithms',
    'certificatefile',
    'challengeresponseauthentication',
    'ciphers',
    'clearallforwardings',
    'compression',
    'connectionattempts',
    'connecttimeout',
    'controlmaster',
    'controlpersist',
    'dynamicforward',
    'enablesshkeysign',
    'escapechar',
    'exitonforwardfailure',
    'fingerprinthash',
    'gatewayports',
    'globalknownhostsfile',
    'gssapiauthentication',
    'gssapiclientidentity',
    'gssapikeyexchange',
    'gssapirenewalforcesrekey',
    'gssapiserveridentity',
    'gssapitrustdns',
    'hostbasedauthentication',
    'hostbasedkeytypes',
    'hostkeyalgorithms',
    'identitiesonly',
    'identityagent',
    'identityfile',
    'ignoreunknown',
    'ipqos',
    'kbdinteractiveauthentication',
    'kbdinteractivedevices',
    'kexalgorithms',
    'localforward',
    'loglevel',
    'macs',
    'nohostauthenticationforlocalhost',
    'numberofpasswordprompts',
    'passwordauthentication',
    'pkcs11provider',
    'port',
    'preferredauthentications',
    'proxyjump',
    'pubkeyacceptedkeytypes',
    'pubkeyauthentication',
    'rekeylimit',
    'remoteforward',
    'requesttty',
    'revokedhostkeys',
    'serveralivecountmax',
    'serveraliveinterval',
    'setenv',
    'streamlocalbindmask',
    'streamlocalbindunlink',
    'syslogfacility',
    'tcpkeepalive',
    'tunnel',
    'tunneldevice',
}

# The following entries are intentionally not listed on the instruction_whitelist:
# ControlPath:
#   An attacker could redirect ssh connections by providing a CrontrolMaster socket
#   and redirecting the ControlPath of other users to this socket.
# Match:
#   Match exec ... allows an attacker to specify arbitrary commands
# ForwardAgent:
#   An attacker could enable agent forwarding and then misuse the agent of a victim.
# ForwardX11, ForwardX11Timeout, ForwardX11Trusted:
#   An attacer could enable X11 forwarding and misuse the display connection of a victim.
# GSSAPIDelegateCredentials:
#   An attacker controlling the target server could steal credentials when enabling this option.
# HashKnownHosts:
#   This is a client-side security setting. An attacker could disable hashing, resulting in worse security.
# CheckHostIP, StrictHostKeyChecking, UpdateHostKeys, UserKnownHostsFile, VerifyHostKeyDNS, VisualHostKey:
#   Hostkeys are security-critical. An attacker could effectively bypass hostkey checking, resulting in
#   victims connecting to the wrong server without noticing.
# HostKeyAlias
#   This field is automatically added for each host that contains a HostName setting.
#   It is needed for security reasons and must not be set manually.
# Include:
#   An attacker could include unwanted files (needs to be owned by root, but there might be a way to do so).
#   This would bypass all the other security measures.
# LocalCommand, PermitLocalCommand, ProxyCommand, ProxyUseFdpass, RemoteCommand, XAuthLocation:
#   An attacker could specify arbitrary commands
# SendEnv:
#   Environment variables should generally not contain secrets. But to be completely sure, sending
#   these variables is disallowed.

def parse_escaped_command(command):
    remaining = command
    main_command = ""
    main_command_finished = False
    while remaining != "":
        m = re.match('( |"\'"|\'[^\']+\')(.*)$', remaining)
        if m:
            part = m.group(1)
            if part == " ":
                if main_command != "":
                    main_command_finished = True
            elif not main_command_finished:
                main_command += part
            remaining = m.group(2)
            continue
        m = re.match('([^ \'"]+)(.*)$', remaining)
        if m:
            part = m.group(1)
            if not shlex.quote(part) == part:
                return None
            if not main_command_finished:
                main_command += part
            remaining = m.group(2)
            continue
        return None
    return main_command

class HostSection():
    def __init__(self, hostname, headline, context):
        self.__context = context
        self.__hostname = hostname
        self.__lines = [] if headline is None else [headline]
        self.__connectname = None
        self.__connectname_line = None
        self.__command = None
        self.__command_linenr = None
        self.__username = None
        self.__username_line = None
        self.__config_insert_pos = 0 if headline is None else 1
        self.__config_indentation = "    "
        self.__proxy_given = False
    def err(self, msg):
        self.__context["errors"].append(msg)
    def add_neutral_line(self, line):
        # empty line or comment line, nothing to check
        self.__lines.append(line)
    def add_setting(self, line_nr, ws_before, command, ws_between, argument):
        if command.lower() == "hostname":
            if self.__hostname is None:
                self.err("Option HostName is not allowed on line " + str(line_nr) + ", only allowed in an explicit Host section (one host, no wildcards)")
            elif self.__connectname is not None:
                self.err("Option HostName is only allowed once per host block. (Appeared in line " + str(self.__connectname_line) + " and " + str(line_nr) + ")")
            else:
                self.__connectname = argument
                self.__connectname_line = line_nr
        elif command.lower() == "user":
            if self.__hostname is not None and self.__username is not None:
                self.err("Option User is only allowed once per host block. (Appeared in line " + str(self.__username_line) + " and " + str(line_nr) + ")")
            self.__username = argument
            self.__username_line = line_nr
        elif command.lower() == "remotecommand":
            program = parse_escaped_command(argument)
            if program is None:
                parts = [p for p in argument.split(" ") if p != ""]
                suggestion = " ".join([shlex.quote(p) for p in parts])
                self.err("The command on line " + str(line_nr) + " looks not properly escaped, suggested replacement (but use with care, might be wrong): " + suggestion)
            elif self.__hostname is None:
                self.err("Option RemoteCommand is not allowed on line " + str(line_nr) + ", only allowed in an explicit Host section (one host, no wildcards)")
            elif self.__command is not None:
                self.err("Option RemoteCommand is only allowed once per host block. (Appeared in line " + str(self.__command_linenr) + " and " + str(line_nr) + ")")
            else:
                self.__command = program
                self.__command_linenr = line_nr
        elif command.lower() == "proxyjump":
            self.__proxy_given = True
        else:
            if command.lower() not in instruction_whitelist:
                self.err("Config option `" + command.lower() + "' (line " + str(line_nr) + ") is not whitelisted.")
        self.__lines.append(ws_before + command + ws_between + argument)
        self.__config_insert_pos = len(self.__lines)
        self.__config_indentation = ws_before
    def finalize(self):
        if self.__hostname is None:
            # No specific block, nothing to check
            return None
        if self.__command is not None:
            cmdtarget_hostname = self.__connectname if self.__connectname is not None else self.__hostname
            whitelisted = False
            for user, hostname, command in self.__context["cmd_whitelist"]:
                if command == self.__command and (user is None or user == self.__username) and (hostname is None or hostname == cmdtarget_hostname):
                    whitelisted = True
                    break
            if not whitelisted:
                display_username = self.__username if self.__username is not None else "<any user>"
                self.err("Command `" + self.__command + "' (line " + str(self.__command_linenr) + ") is not whitelisted for " + display_username + "@" + cmdtarget_hostname)

        additional_settings = []
        # Add a HostKeyAlias if a hostname was set
        if self.__connectname is not None:
            additional_settings.append("HostKeyAlias " + self.__hostname)
        # Add a ProxyJump if activated and no ProxyJump is given
        if self.__context["general_proxy"] is not None and not self.__proxy_given and self.__context["general_proxy"] != self.__hostname:
            additional_settings.append("ProxyJump " + self.__context["general_proxy"])
        for setting in additional_settings:
            self.__lines.insert(self.__config_insert_pos, self.__config_indentation + setting)
    def get_lines(self):
        return self.__lines

def ssh_check_validity(content, context):
    fd, path = tempfile.mkstemp()
    f = open(fd, "w")
    try:
        with f:
            f.write(content)
        ssh_result = subprocess.run(["ssh", "-TF", path, "-G", "localhost"], capture_output=True)
        error_lines = ssh_result.stderr.decode().split("\n")
        # remove the last line, that is most likely empty
        if error_lines[-1] == "":
            error_lines = error_lines[0:-1]
        def remove_prefix(line):
            if line.startswith(path + ": "):
                return line[len(path)+2:]
            elif line.startswith(path + " "):
                return line[len(path)+1:]
            return line
        error_lines = [remove_prefix(line) for line in error_lines]
        if ssh_result.returncode != 0 and len(error_lines) == 0:
            error_lines.append("ssh failed to validate the file (exit " + str(ssh_result.returncode) + ") but did not produce error output")
        context["errors"] += error_lines
    finally:
        os.unlink(path)

def transform_config(content, cmd_whitelist, general_proxy):
    '''
    Check if the given ssh config file content is valid and safe.
    The content is given as a single string.
    A config is not safe, if it contains instructions that may cause harm to the user.
    An example is executing commands via 'Match exec ...'

    A tuple (errors, content) is returned.
    errors is an empty array and content contains the modified file content, if the check was successful.
    errors is a non-empty array and content is None if errors occurred.
    '''
    lines = content.split("\n")
    context = {
        "cmd_whitelist": cmd_whitelist,
        "general_proxy": general_proxy,
        "errors": [],
    }
    cur_section = HostSection(None, None, context)
    sections = [cur_section]
    line_nr = 1
    for line in lines:
        if re.match('^\\s*$', line):
            # line is empty
            cur_section.add_neutral_line(line)
        elif re.match('^\\s*#.*', line):
            # line just contains a comment
            cur_section.add_neutral_line(line)
        else:
            m = re.match('^(\\s*)([a-zA-Z]+)(\\s+)(\\S.*)$', line)
            if m:
                # found a setting
                ws_before = m.group(1)
                command = m.group(2)
                ws_between = m.group(3)
                argument = m.group(4)

                if command.lower() == 'host':
                    cur_section.finalize()
                    if '*' in argument or '?' in argument or ' ' in argument.strip():
                        cur_section = HostSection(None, None, context)
                    elif not re.match('^[a-zA-Z0-9\\.\\-_]+$', argument.strip()):
                        context["errors"].append("The hostname " + argument.strip() + " (line " + str(line_nr) + ") contains invalid characters.")
                        cur_section = HostSection(None, None, context)
                    else:
                        cur_section = HostSection(argument, line, context)
                    sections.append(cur_section)
                else:
                    cur_section.add_setting(line_nr, ws_before, command, ws_between, argument)
            else:
                # could not parse this line
                context["errors"].append("Line " + str(line_nr) + " could not be parsed by the validator.")
        line_nr += 1
    cur_section.finalize()

    if len(context["errors"]) == 0:
        ssh_check_validity(content, context)

    if len(context["errors"]) > 0:
        result = None
    else:
        result = [line for section in sections for line in section.get_lines()]
    return (context["errors"], result)
