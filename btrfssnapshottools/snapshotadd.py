#!/usr/bin/python3

import json
import subprocess
import sys


def main():
    scriptpath = sys.argv.pop(0)
    if len(sys.argv) == 0:
        cli.help()
    else:
        path = sys.argv.pop(0)
    print("Adding snapshot for {}".format(path))

    snapshots_path = path + '/.snapshots'
    config_path = snapshots_path + "/CONFIG.json"

    cmd("sudo btrfs subvolume create {0}".format(snapshots_path))

    default_config = {
        'keep_days': 1,
    }

    fh = open(config_path, 'w')
    fh.write(json.dumps(default_config, indent=4))
    fh.close

    cmd("systemctl enable --now snapshot@`systemd-escape {0}`.timer".format(path))

    print("Set up snapshots for subvolume {0} with default configuration. Edit {1} to change configuration.".format(path, config_path))
    

def cmd(command):
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout = result.stdout.decode('utf-8').rstrip("\n")
    stderr = result.stderr.decode('utf-8').rstrip("\n")
    if result.returncode != 0:
        raise Exception("Command returned code {}".format(result.returncode))
    return stdout


if __name__ == '__main__':
    main()
