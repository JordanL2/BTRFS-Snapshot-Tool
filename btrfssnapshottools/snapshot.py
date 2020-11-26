#!/usr/bin/python3

from datetime import *
import json
import os
import re
import subprocess
import sys


def main():
    scriptpath = sys.argv.pop(0)
    if len(sys.argv) == 0:
        cli.help()
    else:
        path = sys.argv.pop(0)

    snapshots_path = path + '/.snapshots'
    config_path = snapshots_path + "/CONFIG.json"
    subvol = cmd("sudo btrfs sub show {0} | head -n1".format(path))
    
    # Config
    config = load_config(config_path)
    
    # Find previous snapshot
    previous_snapshots = os.listdir(snapshots_path)
    newest_snapshot = None
    dt_newest = None
    for old_snapshot in previous_snapshots:
        try:
            dt_old = datetime.strptime(old_snapshot, config['dateformat'])
            if dt_newest is None or dt_old > dt_newest:
                dt_newest = dt_old
                newest_snapshot = old_snapshot
        except ValueError:
            pass
    print("Previous snapshot is:", newest_snapshot)

    # Make Snapshot
    dt_now = datetime.now()
    timestamp = dt_now.strftime(config['dateformat'])
    deleted_snapshot = False
    cmd("btrfs subvolume snapshot -r {0} {1}/{2}".format(path, snapshots_path, timestamp))

    # # Delete snapshot if there's no difference to previous
    if newest_snapshot is not None:
        res = cmd("btrfs send --no-data -p {0}/{1} {0}/{2} | btrfs receive --dump | tail -n+2".format(snapshots_path, newest_snapshot, timestamp))
        if res == "":
            print("No difference between snapshot and previous, deleting.")
            cmd("btrfs subvolume delete --commit-each {0}/{1}".format(snapshots_path, timestamp))
            deleted_snapshot = True

    # Create bootloader entries
    if 'bootloader' in config and not deleted_snapshot:
        path_device = cmd("df --output=source {0} | tail -n+2".format(path))
        print("Path device: {0}".format(path_device))
        path_device_uuid = cmd("lsblk -o UUID -n {0} | perl -pe 'chomp' -".format(path_device))
        print("Path device UUID: {0}".format(path_device_uuid))

        if config['bootloader']['name'] == 'systemd-boot':
            for entry_name, entry in config['bootloader']['entries'].items():

                # Check for last entry, make sure enough time has passed
                previous_entries = os.listdir('/boot/loader/entries/')
                newest_entry = None
                dt_newest = None
                entry_regex = re.compile("snapshot-(\\d\\d\\d\\d-\\d\\d-\\d\\d_\\d\\d-\\d\\d-\\d\\d)-{0}.conf".format(entry_name))
                for old_entry in previous_entries:
                    entry_match = entry_regex.match(old_entry)
                    if entry_match:
                        dt_old = datetime.strptime(entry_match.group(1), config['dateformat'])
                        if dt_newest is None or dt_old > dt_newest:
                            dt_newest = dt_old
                            newest_entry = old_entry
                print("Previous {0} entry is: {1}".format(entry_name, newest_entry))

                if newest_entry is not None:
                    dt_difference = dt_now - dt_newest
                    seconds_difference = dt_difference.total_seconds()
                    if seconds_difference < (entry['min_gap_hours'] * 3600 - 60):
                        print("Previous entry too recent, not making {} entry".format(entry_name))
                        continue

                # Backup kernel / initrd
                linux_snapshot = "/snapshots/{0}-{1}".format(entry['linux'], timestamp)
                initrd_snapshot = "/snapshots/{0}-{1}".format(entry['initrd'], timestamp)
                cmd('mkdir -p /boot/snapshots')
                cmd("cp /boot/{0} /boot/{1}".format(entry['linux'], linux_snapshot))
                cmd("cp /boot/{0} /boot/{1}".format(entry['initrd'], initrd_snapshot))

                # Make entry
                entry_filename = "/boot/loader/entries/snapshot-{0}-{1}.conf".format(timestamp, entry_name)
                print("Making {0} entry - {1}".format(entry_name, entry_filename))
                fh = open(entry_filename, 'w')
                fh.write("title Snapshot - {0} - {1}\n".format(dt_now.strftime('%a %d-%b %H:%M:%S'), entry['title']))
                fh.write("linux   {0}\n".format(linux_snapshot))
                fh.write("initrd  {0}\n".format(initrd_snapshot))
                fh.write("options root=UUID={0} {1} rootflags=subvol=/{2}/.snapshots/{3}\n".format(path_device_uuid, entry['options'], subvol, timestamp))
                fh.close
    
    # Delete old snapshots
    for old_snapshot in previous_snapshots:
        try:
            dt_old = datetime.strptime(old_snapshot, config['dateformat'])
            dt_difference = dt_now - dt_old
            seconds_difference = dt_difference.total_seconds()
            if seconds_difference > config['keep_seconds']:
                print("Deleting snapshot {0} as it is too old".format(old_snapshot))
                cmd("btrfs subvolume delete --commit-each {0}/{1}".format(snapshots_path, old_snapshot))

                # Delete bootloader entry
                if 'bootloader' in config:
                    if config['bootloader']['name'] == 'systemd-boot':
                        for entry_name, entry in config['bootloader']['entries'].items():
                            entry_filename = "/boot/loader/entries/snapshot-{0}-{1}.conf".format(old_snapshot, entry_name)
                            print("Deleting snapshot {0} bootloader entry {1}".format(old_snapshot, entry_filename))
                            cmd("rm {0} || true".format(entry_filename))

                            # Delete kernel / initrd
                            linux_snapshot = "/snapshots/{0}-{1}".format(entry['linux'], old_snapshot)
                            initrd_snapshot = "/snapshots/{0}-{1}".format(entry['initrd'], old_snapshot)
                            cmd("rm /boot/{0} || true".format(entry['linux'], linux_snapshot))
                            cmd("rm /boot/{0} || true".format(entry['initrd'], initrd_snapshot))
        except ValueError:
            pass
    

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

def load_config(config_path):
    fh = open(config_path, 'r')
    config = json.load(fh)
    print("Config file:", config)

    config['dateformat'] = '%Y-%m-%d_%H-%M-%S'

    if 'keep_days' in config:
        config['keep_seconds'] = config['keep_days'] * 86400
    if 'keep_hours' in config:
        config['keep_seconds'] = config['keep_hours'] * 3600
    if 'keep_seconds' not in config:
        config['keep_seconds'] = 86400

    print("Final config:", config)
    return config


if __name__ == '__main__':
    main()
