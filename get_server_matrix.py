import argparse
import json

from util import (
    ClientKind,
    ClientReleaseParser,
    StableReleaseFilter,
    MajorVersionFilter,
    MatrixOptionKind,
    get_option_from_release,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Returns the server version matrix as a JSON array"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print(args)
