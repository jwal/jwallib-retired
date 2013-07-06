# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]
"""

import optparse
import requests
import sys
from posixpath import join
import email
import apt_pkg
from cStringIO import StringIO
from jwalutil import mkdtemp
from jwalutil import get1
from jwalutil import read_file
from jwalutil import write_file
from jwalutil import read_lines
from jwalutil import group_by
import os
from pprint import pformat
from process import call
import contextlib

BASE_URL = "http://changelogs.ubuntu.com/"

def parse_control_file(data):
    result = []
    with mkdtemp() as temp_dir:
        meta_path = os.path.join(temp_dir, "data.txt")
        write_file(meta_path, data)
        tags = apt_pkg.TagFile(meta_path)
        r = tags.step()
        while r:
            result.append(dict(tags.section))
            r = tags.step()
    return result

def get(*args, **kwargs):
    result = requests.get(*args, **kwargs)
    result.raise_for_status()
    return result

@contextlib.contextmanager
def with_ubuntu_keyring():
    keyrings = [
        "/usr/share/keyrings/ubuntu-master-keyring.gpg",
        "/usr/share/keyrings/ubuntu-archive-keyring.gpg",
        ]

    def gpg(argv, **kwargs):
        return call(["gpg", "--homedir", temp_dir] + argv, **kwargs)

    with mkdtemp() as temp_dir:
        for keyring_path in keyrings:
            gpg(["--import", keyring_path])
        yield gpg

def get_release_sha1sums(release_data):
    sha1sums = {}
    release = get1(parse_control_file(release_data))
    for line in read_lines(release["SHA1"] + "\n"):
        sha1sum, size, relpath = line.split()
        sha1sums[relpath] = sha1sum
    return sha1sums

def ubuntu_to_hg(hg_path):

    def hg(argv, **kwargs):
        kwargs.setdefault("cwd", hg_path)
        kwargs.setdefault("do_print", True)
        return call(["hg"] + argv, **kwargs)

    with with_ubuntu_keyring() as gpg:
        meta_release_data = get(join(BASE_URL, "meta-release")).text
        meta_release = parse_control_file(meta_release_data)
        group_by(meta_release, lambda r: r["Dist"])
        if not os.path.exists(hg_path):
            os.makedirs(hg_path)
            hg(["init"])
        branches = set([a.split()[0] for a in read_lines(hg(["branches"]))])
        if "default" in branches:
            hg(["update", "--clean", "default"])
        meta_release_path = os.path.join(hg_path, "meta-release")
        write_file(meta_release_path, meta_release_data)
        hg(["addremove"])
        if len(read_lines(hg(["status"]))) > 0:
            hg(["commit", "-m", "Update from upstream"])
        ok_branches = set()
        for release in meta_release:
            branch = "ubuntu_%s" % (release["Dist"],)
            try:
                if branch not in branches:
                    hg(["update", "--clean", "default"])
                    hg(["branch", "--force", branch])
                else:
                    hg(["update", "--clean", branch])
                try:
                    hg(["merge", "default"])
                except Exception:
                    pass
                release_path = os.path.join(hg_path, "Release")
                old_sha1sums = {}
                if os.path.exists(release_path):
                    old_sha1sums = get_release_sha1sums(read_file(release_path))
                release_data = get(release["Release-File"]).text
                new_sha1sums = get_release_sha1sums(release_data)
                write_file(release_path, release_data)
                release_gpg_data = get(release["Release-File"] + ".gpg").text
                release_gpg_path = os.path.join(hg_path, "Release.gpg")
                write_file(release_gpg_path, release_gpg_data)
                gpg(["--verify", release_gpg_path, release_path])
                for relpath in old_sha1sums:
                    if relpath in new_sha1sums:
                        continue
                    # Delete file
                for relpath in new_sha1sums:
                    if relpath in old_sha1sums:
                        if new_sha1sums[relpath] == old_sha1sums[relpath]:
                            continue
                    # Fetch file and check sha1sum
                hg(["addremove"])
                if len(read_lines(hg(["status"]))) > 0:
                    hg(["commit", "-m", "Update from upstream"])
            except Exception, e:
                print e
                continue
            ok_branches.add(branch)
        for branch in branches:
            if branch == "default" or branch in ok_branches:
                continue
            hg(["update", "--clean", branch])
            hg(["commit", "--close-branch", "-m", "Closing failed branch"])

def main(argv):
    parser = optparse.OptionParser(__doc__)
    parser.add_option("--hg", dest="hg_path", default="ubuntuhg")
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    hg_path = os.path.abspath(options.hg_path)
    ubuntu_to_hg(hg_path)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
