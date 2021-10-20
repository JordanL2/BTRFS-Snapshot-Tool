#!/usr/bin/python3

from datetime import *
import json
import os
import subprocess
import sys
import time


backup_types = [
    'btrfs', # Default
    'rsync',
]


def main():
    scriptpath = sys.argv.pop(0)
    if len(sys.argv) == 0:
        cli.help()
    else:
        path = sys.argv.pop(0)
    
    hostname = cmd("echo $HOSTNAME")
    subvol = cmd("sudo btrfs sub show {0} | head -n1".format(path))
    local_snapshots_path = path + '/.snapshots'

    # Config
    config_path = local_snapshots_path + "/CONFIG.json"
    config = load_config(config_path)
    if 'remote-backup' not in config:
        raise Exception("No remote-backup config section found")
    remote_backups = config['remote-backup']['remote-dir']
    remote_host = config['remote-backup']['remote-host']
    remote_user = config['remote-backup']['remote-user']
    ssh_options = config['remote-backup']['ssh-options']
    ssh_command = "{0} {1}@{2}".format(ssh_options, remote_user, remote_host)
    backup_type = backup_types[0]
    if 'backup-type' in config['remote-backup']:
        backup_type = config['remote-backup']['backup-type']
        if backup_type not in backup_types:
            raise Exception("Invalid backup type {} - valid types are: {}".format(backup_type, ', '.join(backup_types)))
    remote_snapshots_path = "{0}/{1}/{2}".format(remote_backups, hostname, subvol)

    # Ensure remote is accessible
    max_failures = 60
    failed = 0
    while failed < max_failures:
        try:
            cmd("ssh {0} \"echo 'hello'\"".format(ssh_command))
            break
        except Exception:
            failed += 1
            time.sleep(10)
    if failed == max_failures:
        raise Exception("Remote is not accessible")

    # Ensure remote snapshots dir exists
    cmd("ssh {0} \"sudo mkdir -p {1}\"".format(ssh_command, remote_snapshots_path))

    # Get list of local snapshots
    local_snapshots = snapshot_list(config, local_snapshots_path)
    if len(local_snapshots) == 0:
        print("There are no local snapshots to sync.")
        sys.exit()

    # Get most recent snapshot
    last_local_snapshot = local_snapshots[0][0]
    print("Last local snapshot is: {0}".format(last_local_snapshot))

    # Get list of remote snapshots
    remote_snapshots = snapshot_list(config, remote_snapshots_path, ssh_command)

    # Delete any non-readonly remote snapshots (didn't complete successfully)
    if backup_type == 'btrfs':
        for r in remote_snapshots.copy():
            flags = cmd("ssh {0} \"sudo btrfs subvolume show {1}/{2} | grep -E \\\"^\\s+Flags\\:\\\" | sed -e \\\"s/^\\s\\+Flags\\:\\s\\+//\\\"\"".format(ssh_command, remote_snapshots_path, r[0]))
            if 'readonly' not in flags:
                print("Remote snapshot {0} is not read-only, deleting".format(r[0]))
                cmd("ssh {0} \"sudo btrfs subvolume delete {1}/{2}\"".format(ssh_command, remote_snapshots_path, r[0]))
                remote_snapshots.remove(r)

    # Get last remote snapshot
    last_remote_snapshot = None
    if len(remote_snapshots) > 0:
        last_remote_snapshot = remote_snapshots[0][0]
        print("Last remote snapshot is: {0}".format(last_remote_snapshot))
        if last_remote_snapshot not in [s[0] for s in local_snapshots]:
            print("Last remote snapshot can not be found locally".format(last_remote_snapshot))
            last_remote_snapshot = None
    else:
        print("No remote snapshots found")

    # Sync to remote
    if last_remote_snapshot is None:
        # If no remote snapshot, or snapshot name doesn't exist, sync entire last snapshot
        if backup_type == 'btrfs':
            cmd("sudo btrfs send {0}/{1} | ssh {2} \"sudo btrfs receive {3}\"".format(local_snapshots_path, last_local_snapshot, ssh_command, remote_snapshots_path))
        elif backup_type == 'rsync':
            cmd("rsync -a --delete --rsync-path=\"sudo rsync\" -e \"ssh {0} -l {1}\" {3}/{4} {2}:{5}/".format(ssh_options, remote_user, remote_host, local_snapshots_path, last_local_snapshot, remote_snapshots_path))
    elif last_remote_snapshot == last_local_snapshot:
        # No new snapshot to sync
        print("Most recent local snapshot has already been synced.")
    else:
        # Otherwise sync differences between snapshots
        if backup_type == 'btrfs':
            cmd("sudo btrfs send -p {0}/{1} {0}/{2} | ssh {3} \"sudo btrfs receive {4}\"".format(local_snapshots_path, last_remote_snapshot, last_local_snapshot, ssh_command, remote_snapshots_path))
        elif backup_type == 'rsync':
            cmd("rsync -a --delete --link-dest={5}/{6}/ --rsync-path=\"sudo rsync\" -e \"ssh {0} -l {1}\" {3}/{4}/ {2}:{5}/{4}/".format(ssh_options, remote_user, remote_host, local_snapshots_path, last_local_snapshot, remote_snapshots_path, last_remote_snapshot))

    # Delete all old remote snapshots
    for r in remote_snapshots:
        if r[0] != last_local_snapshot:
            if backup_type == 'btrfs':
                cmd("ssh {0} \"sudo btrfs subvolume delete {1}/{2}\"".format(ssh_command, remote_snapshots_path, r[0]))
            elif backup_type == 'rsync':
                cmd("ssh {0} \"sudo rm -rf {1}/{2}\"".format(ssh_command, remote_snapshots_path, r[0]))

def cmd(command):
    print("--- CMD:", command)
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = result.stdout.decode('utf-8').rstrip("\n")
    stderr = result.stderr.decode('utf-8').rstrip("\n")
    print("  | OUT:", stdout)
    print("  | ERR:", stderr)
    if result.returncode != 0:
        raise Exception("Command returned code {}".format(result.returncode))
    return stdout

def snapshot_list(config, snapshots_path, ssh_options=None):
    if ssh_options is None:
        snapshots = os.listdir(snapshots_path)
    else:
        snapshots = cmd("ssh {0} \"ls -1 {1}\"".format(ssh_options, snapshots_path)).split()
    snapshots_dts = []
    for snapshot in snapshots:
        try:
            dt = datetime.strptime(snapshot, config['dateformat'])
            snapshots_dts.append((snapshot, dt))
        except ValueError:
            pass
    snapshots_dts.sort(key=lambda s: s[1], reverse=True)
    return snapshots_dts

def load_config(config_path):
    fh = open(config_path, 'r')
    config = json.load(fh)
    print("Config file:", config)

    config['dateformat'] = '%Y-%m-%d_%H-%M-%S'

    print("Final config:", config)
    return config


if __name__ == '__main__':
    main()
