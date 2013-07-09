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
        with open(meta_path, "wb") as fh:
            fh.write(data)
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

def ubuntu_to_hg(hg_path, username):

    def hg(argv, **kwargs):
        kwargs.setdefault("cwd", hg_path)
        kwargs.setdefault("do_print", True)
        prefix = ["hg"]
        if username is not None and argv[0] in ("commit", "ci"):
            prefix.extend(["--config", "ui.username=%s" % (username,)])
        return call(prefix + argv, **kwargs)

    with with_ubuntu_keyring() as gpg:
        meta_release_data = get(
            join(BASE_URL, "meta-release-development")).content
        meta_release = parse_control_file(meta_release_data)
        group_by(meta_release, lambda r: r["Dist"])
        if not os.path.exists(hg_path):
            os.makedirs(hg_path)
            hg(["init"])
        branches = set([a.split()[0] for a in read_lines(hg(["branches"]))])
        ok_branches = set()
        seen_supported_non_lts = False
        for release in meta_release:
            branch = "ubuntu_codename_%s" % (release["Dist"],)
            is_lts = "LTS" in release["Version"]
            is_supported = release["Supported"] == "1"
            if is_supported and not is_lts:
                seen_supported_non_lts = True
            is_development = not is_supported and seen_supported_non_lts
            if not is_supported and not is_development:
                continue
            ok_branches.add(branch)
            done = set()
            if branch not in branches:
                hg(["update", "--clean", "--rev", "00"])
                hg(["branch", "--force", branch])
            else:
                hg(["update", "--clean", branch])
            hg(["--config", "extensions.purge=", "purge", "--all"])
            release_gpg_path = os.path.join(hg_path, "Release.gpg")
            release_path = os.path.join(hg_path, "Release")
            old_sha1sums = {}
            release_gpg_data = get(release["Release-File"] + ".gpg").content
            if os.path.exists(release_gpg_path):
                if release_gpg_data == read_file(release_gpg_path):
                    continue
                release_data = read_file(release_path)
                old_sha1sums = get_release_sha1sums(release_data)
                old_sha1sums["Release"] = hashlib.sha1(
                    release_data).hexdigest()
                old_sha1sums["Release.gpg"] = hashlib.sha1(
                    release_gpg_data).hexdigest()
                # for relpath in sorted(old_sha1sums):
                #     if posixpath.dirname(relpath) == "Index":
                #         index_data = read_file(os.path.join(hg_path, relpath))
                #         child_sha1sums = get_release_sha1sums(index_data)
                #         for relpath2 in sorted(child_sha1sums):
                #             relpath3 = posixpath.join(
                #                 posixpath.dirname(relpath), relpath2)
                #             old_sha1sums[relpath3] = child_sha1sums[relpath2]
            release_data = get(release["Release-File"]).content
            with open(release_gpg_path, "wb") as fh:
                fh.write(release_gpg_data)
            done.add("Release")
            with open(release_path, "wb") as fh:
                fh.write(release_data)
            done.add("Release.gpg")
            gpg(["--verify", release_gpg_path, release_path])
            new_sha1sums = get_release_sha1sums(release_data)
            new_sha1sums["Release.gpg"] = hashlib.sha1(
                release_gpg_data).hexdigest()
            new_sha1sums["Release"] = hashlib.sha1(
                release_data).hexdigest()
            # for relpath in sorted(new_sha1sums):
            #     if posixpath.basename(relpath) == "Index":
            #         if new_sha1sums[relpath] == old_sha1sums.get(relpath):
            #             index_data = read_file(os.path.join(hg_path, relpath))
            #         else:
            #             index_data = get(
            #                 posixpath.join(
            #                     posixpath.dirname(release["Release-File"]),
            #                     relpath)).content
            #             sha1sum = hashlib.sha1(index_data).hexdigest()
            #             if sha1sum != new_sha1sums[relpath]:
            #                 raise Exception("sha1sum mismatch for %r: "
            #                                 "got %s expecting %s"
            #                                 % (url, sha1sum, 
            #                                    new_sha1sums[relpath]))
            #             index_path = os.path.join(hg_path, relpath)
            #             if not os.path.exists(os.path.dirname(index_path)):
            #                 os.makedirs(os.path.dirname(index_path))
            #             with open(index_path, "wb") as fh:
            #                 fh.write(index_data)
            #         done.add(relpath)
            #         child_sha1sums = get_release_sha1sums(index_data)
            #         for relpath2 in sorted(child_sha1sums):
            #             relpath3 = posixpath.join(
            #                 posixpath.dirname(relpath), relpath2)
            #             new_sha1sums[relpath3] = child_sha1sums[relpath2]
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
                if relpath in done:
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
    parser.add_option("--username", dest="username")
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    hg_path = os.path.abspath(options.hg_path)
    ubuntu_to_hg(hg_path, username=options.username)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
