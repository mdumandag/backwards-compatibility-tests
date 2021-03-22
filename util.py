import os
import re

import subprocess
import sys
import urllib.request

from abc import ABC, abstractmethod
from enum import Enum
from os import path
from typing import List, Dict, Callable
from urllib.parse import urlparse

# Slightly modified version of
# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
# that allows optional patch release versions.
VERSION_PATTERN = re.compile(
    r"""
            ^
            (?P<major>0|[1-9]\d*)
            \.
            (?P<minor>0|[1-9]\d*)
            \.?
            (?P<patch>0|[1-9]\d*)?
            (?:-(?P<prerelease>
                (?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)
                (?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*
            ))?
            (?:\+(?P<buildmetadata>
                [0-9a-zA-Z-]+
                (?:\.[0-9a-zA-Z-]+)*
            ))?
            $
        """,
    re.VERBOSE,
)

VERSION_ATTRIBUTE = "Version"
TAG_ATTRIBUTE = "Github"

IMDG_CLIENTS = (
    "https://raw.githubusercontent.com/hazelcast/rel-scripts/master/imdg-clients.txt"
)
IMDG_SERVERS = "https://raw.githubusercontent.com/hazelcast/rel-scripts/master/imdg-open-source.txt"

CLIENT_HEADER = "======= %s Client\n---\n(.*?)\n---\n==="

RELEASE_REPO = "http://repo1.maven.apache.org/maven2"
ENTERPRISE_RELEASE_REPO = "https://repository.hazelcast.com/release/"
SNAPSHOT_REPO = "https://oss.sonatype.org/content/repositories/snapshots"
ENTERPRISE_SNAPSHOT_REPO = "https://repository.hazelcast.com/snapshot/"

IS_ON_WINDOWS = os.name == "nt"
CLASS_PATH_SEPARATOR = ";" if IS_ON_WINDOWS else ":"


class Version:
    def __init__(self, version: str):
        self.version_str = version
        m = re.match(VERSION_PATTERN, version)
        if not m:
            raise ValueError("Cannot parse %s version" % version)

        parts = m.groupdict()
        self.major = int(parts["major"])
        self.minor = int(parts["minor"])
        self.patch = int(parts["patch"] or 0)
        self.pre_release = parts["prerelease"]
        self.build_metadata = parts["buildmetadata"]
        self.stable = not self.pre_release and not self.build_metadata

    def __repr__(self):
        return "Version(major=%s, minor=%s, patch=%s, pre_release=%s, build_metadata=%s, stable=%s)" % (
            self.major,
            self.minor,
            self.patch,
            self.pre_release,
            self.build_metadata,
            self.stable,
        )


class ClientKind(Enum):
    CS = ".NET/CSharp"
    CPP = "C\\+\\+"
    PY = "Python"
    NODE = "NodeJS"
    GO = "Go"


class MatrixOptionKind(Enum):
    TAG = 0
    VERSION = 1


class ClientRelease:
    def __init__(self, kind: ClientKind, version: str, tag: str):
        self.kind = kind
        self.version = Version(version)
        self.tag = tag

    def __repr__(self):
        return "ClientRelease(kind=%s, version=%s, tag=%s)" % (
            self.kind.name,
            self.version,
            self.tag,
        )


class ReleaseFilter(ABC):
    @abstractmethod
    def filter(self, release: ClientRelease) -> bool:
        pass


class MajorVersionFilter(ReleaseFilter):
    def __init__(self, major_versions: List[int]):
        self._versions = frozenset(major_versions)

    def filter(self, release: ClientRelease) -> bool:
        return release.version.major in self._versions


class StableReleaseFilter(ReleaseFilter):
    def filter(self, release: ClientRelease) -> bool:
        return release.version.stable


CURRENT_STABLE_SERVER_PATTERN = re.compile("========== Current Stable\n---\n(.*?)\n---", re.DOTALL)
PREVIOUS_STABLE_SERVER_PATTERN = re.compile("========== Previous Stable\n---\n(.*?)\n---\n========== Development: SHOW", re.DOTALL)


class ServerReleaseParser:
    def __init__(self, filters: List[ReleaseFilter]):
        self._filters = filters

    def get_all_releases(self):
        with urllib.request.urlopen(IMDG_SERVERS) as r:
            raw_data = r.read().decode()

        stable_match = re.search(CURRENT_STABLE_SERVER_PATTERN, raw_data)
        if not stable_match:
            raise ValueError("Cannot find a match on the server data "
                             "located at %s for the current stable version." % IMDG_SERVERS)

        previous_match = re.search(PREVIOUS_STABLE_SERVER_PATTERN, raw_data)
        if not previous_match:
            raise ValueError("Cannot find a match on the server data "
                             "located at %s for the previous stable versions." % IMDG_SERVERS)

class ClientReleaseParser:
    def __init__(self, kind: ClientKind, filters: List[ReleaseFilter]):
        self._kind = kind
        self._pattern = re.compile(CLIENT_HEADER % kind.value, re.DOTALL)
        self._filters = filters

    def get_all_releases(self):
        with urllib.request.urlopen(IMDG_CLIENTS) as r:
            raw_data = r.read().decode()

        match = re.search(self._pattern, raw_data)
        if not match:
            raise ValueError(
                "Cannot find a match on the clients data "
                "located at %s for the %s client." % (IMDG_CLIENTS, self._kind.name)
            )

        all_releases = self._parse_releases(match.group(1))
        filtered_releases = []

        for release in all_releases:
            should_add = True
            for filter in self._filters:
                if not filter.filter(release):
                    should_add = False
                    break

            if should_add:
                filtered_releases.append(release)

        return filtered_releases

    def _parse_releases(self, releases: str) -> List[ClientRelease]:
        all_releases = []
        for release in releases.split("---\n"):
            version = None
            tag = None
            release = release.strip()
            for attr in release.split("\n"):
                parts = attr.split(": ")
                if len(parts) != 2:
                    continue

                key, value = parts
                if VERSION_ATTRIBUTE == key:
                    version = value
                elif TAG_ATTRIBUTE == key:
                    tag = value

            if version and tag:
                all_releases.append(ClientRelease(self._kind, version, tag))

        return all_releases


def get_tag(release: ClientRelease) -> str:
    pr = urlparse(release.tag)

    head, tail = path.split(pr.path)
    while not tail:
        head, tail = path.split(head)
    return tail


def get_version(release: ClientRelease) -> str:
    return release.version.version_str


MATRIX_OPTION_KIND_TO_GETTER: Dict[MatrixOptionKind, Callable[[ClientRelease], str]] = {
    MatrixOptionKind.TAG: get_tag,
    MatrixOptionKind.VERSION: get_version,
}


def get_option_from_release(release: ClientRelease, option: MatrixOptionKind) -> str:
    return MATRIX_OPTION_KIND_TO_GETTER[option](release)


def download_via_maven(
    repo: str, artifact_id: str, version: str, dst_folder: str, is_test_artifact=False
):
    dst_file_name = artifact_id + "-" + version
    if is_test_artifact:
        dst_file_name += "-tests"
    dst_file_name += ".jar"

    artifact = "com.hazelcast:" + artifact_id + ":" + version
    if is_test_artifact:
        artifact += ":jar:tests"

    dst = path.join(dst_folder, dst_file_name)
    if path.isfile(dst):
        print("Not downloading %s, because it already exists." % dst_file_name)
        return

    args = [
        "mvn",
        "-q",
        "dependency:get",
        "-DrepoUrl=" + repo,
        "-Dartifact=" + artifact,
        "-Ddest=" + dst,
    ]

    print("Downloading " + dst_file_name)
    p = subprocess.run(args, shell=IS_ON_WINDOWS)
    if p.returncode != 0:
        print("Failed to download " + dst_file_name)
        sys.exit(p.returncode)
