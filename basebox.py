# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]

A bit like Vagrant.
"""

from jwalutil import on_error_raise
from jwalutil import read_file
import json
import optparse
import os
import sys
from process import call as call_no_print
import tempfile
import shutil
import hashlib

call = lambda *a, **kw: call_no_print(
    *a, **dict(kw.items() + [("do_print", True)]))

def basebox(config):
    sha1sum = config["base_image"].get("sha1sum")
    if sha1sum is None:
        sha1sum = config["project_cache"].get("base_image_sha1sum")
    objpath = None
    if sha1sum is not None:
        objpath = os.path.join(config["objcache"], sha1sum)
        if not os.path.exists(objpath):
            objpath = None
    if objpath is None:
        call(["mkdir", "-p", config["tmp"]])
        tmp_path = tempfile.mkdtemp(dir=config["tmp"])
        try:
            tmp_img = os.path.join(tmp_path, "download")
            call(["wget", "-O", tmp_img, config["base_image"]["url"]],
                 stdout=None)
            tmp_sha1sum = call(["sha1sum", tmp_img]).split()[0]
            if sha1sum is not None and sha1sum != tmp_sha1sum:
                raise Exception("Checksum mismatch:\n"
                                "  url %r\n"
                                "  expected %r\n"
                                "  got %r" % (config["base_image"]["url"],
                                              sha1sum, tmp_sha1sum))
            objpath = os.path.join(config["objcache"], tmp_sha1sum)
            call(["chmod", "a-wx", tmp_img])
            call(["mkdir", "-p", os.path.dirname(objpath)])
            call(["mv", tmp_img, objpath])
            config["project_cache"]["base_image_sha1sum"] = tmp_sha1sum
        finally:
            shutil.rmtree(tmp_path)
    print "@@@", objpath

def expand_config(config):
    config.setdefault("system_root", os.path.join(config["home"], ".basebox"))
    config.setdefault(
        "objcache", os.path.join(config["system_root"], "objcache"))
    config.setdefault("tmp", os.path.join(config["system_root"], "tmp"))
    config.setdefault("base_image", {})
    config["base_image"].setdefault(
        "url", ("http://cloud-images.ubuntu.com/"
                "quantal/current/quantal-server-cloudimg-amd64-disk1.img"))
    config.setdefault(
        "project_key", hashlib.sha1(config["project_path"]).hexdigest())
    config.setdefault(
        "project_cache_path", os.path.join(
            config["system_root"], "projects", config["project_key"], 
            "cache.json"))
    if os.path.exists(config["project_cache_path"]):
        with open(config["project_cache_path"], "rb") as fh:
            config.setdefault("project_cache", json.loads(fh.read()))
    else:
        config.setdefault("project_cache", {})
    config.setdefault("do_write_project_cache", True)

def find_config_path(on_not_found=on_error_raise):
    basename = "basebox.json"
    pwd = os.path.abspath(".")
    start_pwd = pwd
    while True:
        candidate = os.path.join(pwd, basename)
        if os.path.isfile(candidate):
            return candidate
        if os.path.dirname(pwd) == pwd:
            return on_not_found("Failed to find %r starting at %r"
                                % (basename, start_pwd))
        pwd = os.path.dirname(pwd)

def main(argv):
    parser = optparse.OptionParser(__doc__)
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    config_path = find_config_path(on_not_found=parser.error)
    config = json.loads(read_file(config_path))
    config.setdefault("project_path", os.path.dirname(config_path))
    config.setdefault("cwd", os.path.abspath("."))
    config.setdefault("home", os.path.abspath(os.path.expanduser("~")))
    expand_config(config)
    basebox(config)
    if config["do_write_project_cache"]:
        call_no_print(
            ["mkdir", "-p", os.path.dirname(config["project_cache_path"])])
        with open(config["project_cache_path"], "wb") as fh:
            fh.write(json.dumps(config["project_cache"]))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
