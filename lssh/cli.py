import itertools, os, platform, re, shlex, subprocess, sys, time
from lssh import cli_args, hostlist, xdg_compat
from lssh.matching import compile_host_regex, matches_host_term, matches_host_terms

def group_options_by_customer(hosts):
    map_customer = {}
    for hostname in hosts:
        customer = hosts[hostname].customer
        if customer not in map_customer:
            map_customer[customer] = []
        map_customer[customer].append(hosts[hostname].display_name)
    customers = list(map_customer.keys())
    customers.sort()
    def make_option(customer):
        values = map_customer[customer]
        values.sort()
        return (customer, values)
    return [make_option(c) for c in customers]

def matches_substring(host, substring):
    return matches_host_term(host.display_name, host.keywords, substring)

def matches_all_substrings(host, substring, additional_substrings, regex=False):
    return matches_host_terms(host.display_name, host.keywords, [substring] + additional_substrings, regex=regex)

def ensure_no_usernames(substrings):
    for substr in substrings:
        if '@' in substr:
            print("Only the first substring may contain a username")
            sys.exit(1)

def split_user_from_substring(s):
    if s is None:
        return (None, None)
    idx = s.find('@')
    if idx == -1:
        # contains no username
        return (None, s)
    return (s[0:idx], s[idx+1:])

def create_recording_directory(hostname):
    recordings_basedir = xdg_compat.data_home() / 'lssh' / 'recordings'
    os.makedirs(recordings_basedir, exist_ok=True)
    name = time.strftime("%Y-%m-%d_%H-%M-%S") + '_' + hostname
    try:
        d = recordings_basedir / name
        os.mkdir(d)
        return d
    except FileExistsError:
        for i in itertools.count(2):
            try:
                d = recordings_basedir / (name + '_' + str(i))
                os.mkdir(d)
                return d
            except FileExistsError:
                pass

def check_for_conflicting_args(args):
    mode = [None] # array to allow access inside of the function add_mode
    specifying_arg = [None]
    def add_mode(new_mode, arg):
        if mode[0] is not None and mode[0] != new_mode:
            print("The arguments " + specifying_arg[0] + " and " + arg + " cannot be combined", file=sys.stderr)
            exit(1)
        mode[0] = new_mode
        specifying_arg[0] = arg
    if args.version:
        add_mode("version", "--version")
    if args.validate is not None:
        add_mode("validate", "--validate")
    if args.update:
        add_mode("update", "--update-hosts")
    if args.load is not None:
        add_mode("load", "--load-from")
    if args.replay:
        add_mode("replay", "--replay")
    if args.time is not None:
        add_mode("replay", "--timestamp")
    if args.regex:
        add_mode("connect", "--regex")
        if args.substring is None:
            print("--regex requires a host expression", file=sys.stderr)
            sys.exit(1)

def main(hosts_dir, update_hosts, attributes):
    args = cli_args.parse_args()
    check_for_conflicting_args(args)

    user, substring = split_user_from_substring(args.substring)
    additional_substrings = args.additional_substrings
    ensure_no_usernames(additional_substrings)
    general_proxy = None if "general_proxy" not in attributes else attributes["general_proxy"]
    if args.version:
        print("lssh version dev")
    elif args.validate is not None:
        hostlist.validate_config(args.validate, general_proxy)
    elif args.update:
        update_hosts()
    elif args.load is not None:
        hostlist.import_new_config(args.load, hosts_dir, general_proxy)
    elif args.replay or args.time is not None:
        from lssh import replay
        if substring is None:
            all_substrings = []
        else:
            all_substrings = [substring] + additional_substrings
        replay.replay(all_substrings, args.time)
    else:
        connect(args, user, substring, additional_substrings, hosts_dir)

def build_proxy_chain(selected, hosts):
    chain = [selected]
    cur_host = selected
    while cur_host in hosts and hosts[cur_host].jumphost is not None:
        cur_host = hosts[cur_host].jumphost
        if cur_host in chain:
            loop = " -> ".join([cur_host] + chain)
            print("Error: There is a loop in the proxy hosts!", file=sys.stderr)
            print("  ... -> " + loop, file=sys.stderr)
            exit(1)
        chain = [cur_host] + chain
    return chain

def show_proxy_chain(chain):
    if len(chain) == 1:
        print("Connecting to " + chain[0] + " without jumphost")
    else:
        print("Connecting via:")
        print("  " + " -> ".join(chain))

def select_host(substring, additional_substrings, hosts_dir, regex=False):
    if regex:
        try:
            compile_host_regex(substring)
        except re.error as error:
            print("Invalid host regular expression: " + str(error), file=sys.stderr)
            sys.exit(1)
    hosts, displaynames = hostlist.load_config(hosts_dir)
    if substring is None:
        matched_hosts = hosts
    else:
        matched_hosts = {}
        for display_name in hosts:
            host = hosts[display_name]
            if matches_all_substrings(host, substring, additional_substrings, regex=regex):
                matched_hosts[display_name] = hosts[display_name]

    if len(matched_hosts) == 0:
        if len(hosts) == 0:
            print("No hosts defined in the configuration")
        elif len(additional_substrings) == 0:
            print("No matching hosts for substring `" + substring + "' found")
        else:
            print("No matching hosts for the given substrings found")
        sys.exit(1)
    elif len(matched_hosts) == 1:
        selected = list(matched_hosts.keys())[0]
    else:
        from lssh import tui_dialog
        options = group_options_by_customer(matched_hosts)
        choice = tui_dialog.hierarchical_option_dialog(options, displaynames, 'select customer', 'select host')
        if choice is None:
            print("No host has been selected")
            sys.exit(1)
        selected = options[choice[0]][1][choice[1]]
    proxy_chain = build_proxy_chain(selected, hosts)
    return selected, proxy_chain

def connect(args, user, substring, additional_substrings, hosts_dir):
    from lssh import ssh_agent
    selected, proxy_chain = select_host(substring, additional_substrings, hosts_dir, regex=args.regex)

    options_dict = vars(args)
    command = ['ssh']
    for opt in cli_args.parameterless_options:
        count = options_dict[opt]
        if count is not None:
            command.append('-' + count * opt)
    for opt in cli_args.parameter_options:
        parameters = options_dict[opt]
        if parameters is not None:
            for param in parameters:
                command += ['-' + opt, param]
    if args.verbose is not None:
        command.append('-' + args.verbose * 'v')
    user_prefix = "" if user is None else user + "@"
    command.append(user_prefix + selected)
    try:
        rec_dir = create_recording_directory(selected)
    except Exception as e:
        print("Warning: Could not create directory for session recording: " + str(e), file=sys.stderr)
        rec_dir = None
    ssh_commandline = ' '.join([shlex.quote(arg) for arg in command])
    show_proxy_chain(proxy_chain)
    if args.verbose is not None:
        print("executing command: " + ssh_commandline)
    if rec_dir is not None:
        if platform.system() == "Darwin":
            final_command = ['script', '-r', str(rec_dir / 'output')] + command
        else:
            final_command = ['script', '-et'+str(rec_dir / 'timing'), rec_dir / 'output', '-c', ssh_commandline]
    else:
        final_command = command
    try:
        sys.exit(subprocess.run(final_command, env=ssh_agent.get_environment()).returncode)
    except KeyboardInterrupt:
        # User is allowed to interrupt the ssh process
        # Just ignore this case
        pass
