import argparse
import json

from util import (
    ClientKind,
    ClientReleaseParser,
    StableReleaseFilter,
    V4ReleaseFilter,
    get_tag,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Returns the client matrix")

    parser.add_argument(
        "--client",
        dest="client",
        action="store",
        type=str,
        choices=[kind.name.lower() for kind in ClientKind],
        required=True,
        help="Client type",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    client = args.client
    client_kind = ClientKind[client.upper()]
    client_release_parser = ClientReleaseParser(
        client_kind, [V4ReleaseFilter(), StableReleaseFilter()]
    )
    releases = client_release_parser.get_all_releases()
    tags = [get_tag(release) for release in releases]
    print(json.dumps(tags))
