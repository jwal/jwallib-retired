# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]
"""

import optparse
import requests
import sys
from posixpath import join
import posixpath
import email
import apt_pkg
from cStringIO import StringIO
from jwalutil import mkdtemp
from jwalutil import get1
from jwalutil import read_file
from jwalutil import write_file
from jwalutil import read_lines
from jwalutil import group_by
from jwalutil import trim
import os
from pprint import pformat
from process import call
import contextlib
import hashlib

BASE_URL = "http://changelogs.ubuntu.com/"

PORTS_MIRRORS = (
    ("http://archive.ubuntu.com/ubuntu/", 
     "http://ports.ubuntu.com/ubuntu-ports/"),
)

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
    try:
        result.raise_for_status()
    except Exception, e:
        #print get, args, kwargs
        raise
    return result


def get_release_file(base_url):
    for src, dst in [("", "")] + list(PORTS_MIRRORS):
        url = base_url
        if url.startswith(src):
            url = dst + trim(url, prefix=src)
        try:
            file_data = get(url).content
        except Exception, e:
            try:
                file_data_bz2 = get(url + ".bz2").content
            except Exception, e:
                try:
                    file_data_gz = get(url + ".gz").content
                except Exception, e:
                    continue
                else:
                    file_data = call(["gunzip"], 
                                     stdin_data=file_data_bz2,
                                     do_crlf_fix=False)
            else:
                file_data = call(["bzip2", "-d"], 
                                 stdin_data=file_data_bz2,
                                 do_crlf_fix=False)
                break
        else:
            break
    else:
        raise Exception("Failed to fetch %r including gz and "
                        "bz2 variants and ports mirror"
                        % (base_url,))
    return file_data

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
        meta_release_data = get(
            join(BASE_URL, "meta-release-development")).content
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
        seen_supported_non_lts = False
        for release in meta_release:
            branch = "ubuntu_codename_%s" % (release["Dist"],)
            is_lts = "LTS" in release["Version"]
            is_supported = release["Supported"] == "1"
            if is_supported and not is_lts:
                seen_supported_non_lts = True
            is_development = not is_supported and seen_supported_non_lts
            # print "  branch", branch
            # print "    is_supported", is_supported
            # print "    is_lts", is_lts
            # print "    is_development", is_development
            if not is_supported and not is_development:
                continue
            ok_branches.add(branch)
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
            release_data = get(release["Release-File"]).content
            new_sha1sums = get_release_sha1sums(release_data)
            write_file(release_path, release_data)
            release_gpg_data = get(release["Release-File"] + ".gpg").content
            release_gpg_path = os.path.join(hg_path, "Release.gpg")
            write_file(release_gpg_path, release_gpg_data)
            gpg(["--verify", release_gpg_path, release_path])
            for relpath in old_sha1sums:
                if relpath in new_sha1sums:
                    continue
                file_path = os.path.join(hg_path, relpath)
                call(["rm", "-rf", "--one-file-system", file_path])
            for relpath in new_sha1sums:
                if relpath in old_sha1sums:
                    if new_sha1sums[relpath] == old_sha1sums[relpath]:
                        continue
                if (relpath.endswith(".gz") 
                        and trim(relpath, suffix=".gz") in new_sha1sums):
                    continue
                if (relpath.endswith(".bz2") 
                        and trim(relpath, suffix=".bz2") in new_sha1sums):
                    continue
                file_path = os.path.join(hg_path, relpath)
                file_data = get_release_file(
                    posixpath.join(
                        posixpath.dirname(release["Release-File"]), relpath))
                sha1sum = hashlib.sha1(file_data).hexdigest()
                if sha1sum != new_sha1sums[relpath]:
                    raise Exception("sha1sum mismatch for %r: "
                                    "got %s expecting %s"
                                    % (url, sha1sum, new_sha1sums[relpath]))
                if not os.path.exists(os.path.dirname(file_path)):
                    os.makedirs(os.path.dirname(file_path))
                with open(file_path, "wb") as fh:
                    fh.write(file_data)
            hg(["addremove"])
            if len(read_lines(hg(["status"]))) > 0:
                hg(["commit", "-m", "Update from upstream"])
        for branch in branches:
            if branch == "default" or branch in ok_branches:
                continue
            hg(["update", "--clean", branch])
            hg(["commit", "--close-branch", 
                "-m", "Closing unsupported release"])

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
