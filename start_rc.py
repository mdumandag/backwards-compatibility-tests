import argparse
import os
import subprocess
from os import path

from util import SNAPSHOT_REPO, RELEASE_REPO, download_via_maven, IS_ON_WINDOWS


def parse_args():
    parser = argparse.ArgumentParser(description="Starts the remote controller")

    parser.add_argument(
        "--rc-version",
        dest="rc_version",
        action="store",
        type=str,
        required=True,
        help="Remote controller version",
    )

    parser.add_argument(
        "--jars",
        dest="jars",
        action="store",
        type=str,
        required=True,
        help="The name of the folder that will contain the JAR files",
    )

    parser.add_argument(
        "--use-simple-server",
        dest="use_simple_server",
        action="store_true",
        default=False,
        required=False,
        help="Use the RC in simple server mode",
    )

    return parser.parse_args()


def start_rc(rc_version: str, dst_folder: str, use_simple_server: bool):
    if rc_version.upper().endswith("-SNAPSHOT"):
        rc_repo = SNAPSHOT_REPO
    else:
        rc_repo = RELEASE_REPO

    download_via_maven(rc_repo, "hazelcast-remote-controller", rc_version, dst_folder)
    class_path = path.join(dst_folder, "*")

    args = [
        "java",
        "-cp",
        class_path,
        "com.hazelcast.remotecontroller.Main",
    ]

    if use_simple_server:
        args.append("--use-simple-server")

    enterprise_key = os.environ.get("HAZELCAST_ENTERPRISE_KEY", None)
    if enterprise_key:
        args.insert(1, "-Dhazelcast.enterprise.license.key=" + enterprise_key)

    rc_stdout = open("ignore/rc_stdout.log", "w")
    rc_stderr = open("ignore/rc_stderr.log", "w")

    return subprocess.Popen(
        args=args, stdout=rc_stdout, stderr=rc_stderr, shell=IS_ON_WINDOWS
    )


if __name__ == "__main__":
    args = parse_args()
    rc_version = args.rc_version
    jars = args.jars
    use_simple_server = args.use_simple_server
    start_rc(rc_version, jars, use_simple_server)