import argparse
import yaml
import os
import stat
from deepmerge import always_merger

# TODO:
# - validate various configuration values:
#   - validate that admin_host is a valid hostname
#   - validate that all directories are absolute paths
#   - validate that hostname is a valid hostname
#   - validate that all exclusions reference directories that are being backed up
#   - validate that backup_basedir is an absolute path
# - improve error handling

default_global_config = {
    "backup_basedir": "/tmp/backupdir",
    "uppercase_hostname": True,
    "admin_host": "admin.example.com",
}

default_host_config = {
    "directories": [
        '/var',
        '/etc',
        '/srv',
        '/export',
        '/opt'
    ],
    "exclusions": {
        '/var': [ '/var/lib/yum' ],
    }
}

# load global configuration
def load_global_config(args):
    config = default_global_config
    if args.config:
        if os.path.exists(args.config):
            with open(args.config, "r") as f:
                config = always_merger.merge(config, yaml.safe_load(f))
        else:
            raise FileNotFoundError(f"Global configuration file {args.config} not found")
    return config

# load host configuration
def load_host_config(args, global_config):
    config = default_host_config

    host_config_path = os.path.join(global_config["host_backup_dir"], "config.yml")

    if os.path.exists(host_config_path):
        if args.verbose:
            print(f"Loading host configuration from {host_config_path}")

        with open(host_config_path, "r") as f:
            config = always_merger.merge(config, yaml.safe_load(f))

    if args.host_config:
        if os.path.exists(args.host_config):
            with open(args.host_config, "r") as f:
                config = always_merger.merge(config, yaml.safe_load(f))
        else:
            raise FileNotFoundError(f"Host configuration file {args.host_config} not found")

    return config

import os
import subprocess

def run_ssh_command(admin_host, command, no_op=False, verbose=False):
    """
    Run a command on a remote host while preserving SSH_AUTH_SOCK.

    Args:
        hostname (str): The hostname to execute the command on.
        command (str): The command to execute.
        admin_host (str): The admin host to use for SSH connections.
        no_op (bool): If True, print the command instead of running it.
        verbose (bool): If True, print the command before running it.

    Raises:
        FileNotFoundError: If SSH_AUTH_SOCK is not set or the socket file does not exist.
    """
    ssh_auth_sock = os.getenv('SSH_AUTH_SOCK')
    if not ssh_auth_sock or not os.path.exists(ssh_auth_sock):
        raise FileNotFoundError("SSH_AUTH_SOCK is not set or points to a non-existent socket file.")
    
    # FIXME: I'm pretty sure we don't need to use sudo here
    full_command = f"sudo --preserve-env=SSH_AUTH_SOCK ssh -A {admin_host} '{command}'"

    if verbose or no_op:
        print(f"Command: {full_command}")
    
    if not no_op:
        subprocess.run(full_command, shell=True, check=True)

def backup_directory(hostname, directory, global_config, host_config, args):
    src = f"{hostname}:{directory}"
    # FIXME: this is a hack to get the directory name right
    dst = f"{global_config['host_backup_dir']}{directory}"

    exclude_args = []
    for exclude in host_config["exclusions"].get(directory, []):
        exclude_args.append(f"--exclude={exclude}")

    rsync_command = f"rsync -avxHP {' '.join(exclude_args)} {src} {dst}"
    run_ssh_command(global_config["admin_host"],
                    rsync_command,
                    no_op=True, # FIXME: args.no_op
                    verbose=args.verbose)

def backup(args, global_config, host_config):
    if args.verbose:
        print(f"Backing up {args.hostname}")

    for directory in host_config["directories"]:
        print(f"Backing up {directory}")
        backup_directory(args.hostname, directory, global_config, host_config, args)

def restore(args, global_config, host_config):
    if args.verbose:
        print(f"Restoring {args.hostname}")

def main():
    parser = argparse.ArgumentParser(description="Backup and restorespecified directories from a remote host using rsync.")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    parser.add_argument("--no-op", action="store_true", help="Print actions without performing them")
    parser.add_argument("--backup-basedir", default="/backupdir", help="Base directory for backups (default: /backupdir)")
    parser.add_argument("--admin-host", default="admin.example.com", help="Admin host to use for SSH connections (default: admin.example.com)")
    parser.add_argument("--uppercase-hostname", action="store_true", help="Convert hostname to uppercase for backup directory")
    parser.add_argument("--config", help="Path to global configuration file (YAML or JSON)")
    parser.add_argument("--host-config", help="Path to host-specific configuration file (YAML or JSON)")

    # create a subparser for the backup command
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    backup_parser = subparsers.add_parser("backup", help="Backup the specified directories")
    backup_parser.add_argument("hostname", help="Target hostname for backup")

    # create a subparser for the restore command
    restore_parser = subparsers.add_parser("restore", help="Restore the specified directories")
    restore_parser.add_argument("hostname", help="Target hostname for restore")

    args = parser.parse_args()

    # Load global configuration
    global_config = load_global_config(args)
    if args.verbose:
        print("Global configuration:")
        print(global_config)

    # Determine backup directory
    hostname = args.hostname.upper() if global_config["uppercase_hostname"] else args.hostname
    global_config["host_backup_dir"] = os.path.join(global_config["backup_basedir"], hostname)

    #if args.verbose:
    #    print("Global configuration:")
    #    print(global_config)

    # Create backup directory if it doesn't exist
    if not os.path.exists(global_config["host_backup_dir"]):
        if args.no_op:
            print(f"[NO-OP] Would create backup directory {global_config['host_backup_dir']}")
        else:
            os.makedirs(global_config["host_backup_dir"])
            mode = os.lstat(global_config["host_backup_dir"]).st_mode
            if stat.S_IMODE(mode) != 0o2770:
                print(f"Setting mode of {global_config['host_backup_dir']} to 0o2770")
                os.chmod(global_config["host_backup_dir"], 0o2770)

    # Load host-specific configuration
    host_config = load_host_config(args, global_config)
    if args.verbose:
        print("Host configuration:")
        print(host_config)


    if args.command == "backup":
        backup(args, global_config, host_config)
    elif args.command == "restore":
        restore(args, global_config, host_config)

if __name__ == "__main__":
    main()
