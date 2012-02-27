# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options] [GIT_COUCHDB] [DESIGN_COUCHDB]

Couchapp is a tool for building CouchDB _design documents based on a
standardized filesystem layout.  I think the idea is that normally a
software project is developed as a set of JavaScript/HTML/CSS files
etc on a filesystem and so there are more tools for editing these
kinds of documents in this location instead of when they are packaged
_design documents.

gitcouchdbsync.py is a script for copying git version control
documents (blobs, trees and commits) into a CouchDB database.  The
purpose is to (eventually) allow replication and synchronization of
versions of software without needing to use annoying commands like git
push and git fetch.

selfcouchapp.py is a script that combines these two utilities so that
the _design document follows the latest revision of a couchapp managed
project.  After you run "git commit" the gitcouchdbsync.py process
pushes this into a CouchDB and then the selfcouchapp.py script,
subscribed to _changes, notices that the branch has been updated.  It
will copy down the latest files for that branch and use couchapp to
replace the specified _design document.

In the "self" mode, you can configure the selfcouchapp.py script to
follow all branches in the git repository.  When a new branch is
created a _design document is created for it and when a branch is
deleted the _design document is also deleted.  During development, I
will be using this feature and working on a topic branch for my new
feature development, testing my changes in the same couchdb that
contains the stable and topic branches and both design documents.
"""

from __future__ import with_statement

from couchdblib import get, couchapp
from jwalutil import mkdtemp
from posixutils import symbolic_to_octal_mode
from pprint import pformat
import base64
import optparse
import os
import posixpath
import pycurl as curl
import sys
import time
import urllib

def write_file(path, data):
    with file(path, "wb") as fh:
        fh.write(data)

def blob_to_fs(git_couchdb_url, file_path, blob):
    blob_data = get(posixpath.join(git_couchdb_url, blob))
    if blob_data["encoding"] == "raw":
        write_file(file_path, blob_data["raw"])
    elif blob_data["encoding"] == "base64":
        write_file(file_path, base64.b64decode(blob_data["base64"]))
    else:
        raise NotImplementedError(blob_data)

def tree_to_fs(git_couchdb_url, local_dir, tree):
    os.mkdir(local_dir)
    tree_data = get(posixpath.join(git_couchdb_url, tree))
    for entry in tree_data["children"]:
        out_path = os.path.join(local_dir, entry["basename"])
        if entry["child"]["type"] == "git-tree":
            tree_to_fs(git_couchdb_url, out_path, entry["child"]["_id"])
        elif entry["child"]["type"] == "git-blob":
            blob_to_fs(git_couchdb_url, out_path, entry["child"]["_id"])
        else:
            raise NotImplementedError(entry)
        mode = symbolic_to_octal_mode(entry["mode"])
        # os.chmod(out_path, int(mode, 8) & 0xfff)

def sync_batch(git_couchdb_url, design_couchdb_url, branch, app_subdir):
    if branch is None:
        branches = [
            b["_id"] for b in get(
                posixpath.join(git_couchdb_url, "git-branches"))["branches"]]
    else:
        # TODO: Should really look for branches with this name using
        # an index
        branches = ["git-branch-" + branch]
    with mkdtemp() as temp_dir:
        for branch in branches:
            basename = urllib.quote(branch, safe="")
            local_dir = os.path.join(temp_dir, basename)
            commit = get(posixpath.join(git_couchdb_url, 
                                        branch))["commit"]["_id"]
            tree = get(posixpath.join(git_couchdb_url, 
                                      commit))["tree"]["_id"]
            if app_subdir != ".":
                # TODO: Support multi-level sub_dir
                assert "/" not in app_subdir, app_subdir
                for child in get(posixpath.join(git_couchdb_url, 
                                                tree))["children"]:
                    if child["basename"] == app_subdir:
                        assert child["child"]["type"] == "git-tree", child
                        tree = child["child"]["_id"]
                        break
                else:
                    raise Exception("Missing child %r" % (app_subdir,))
            existing = get(posixpath.join(design_couchdb_url, 
                                          "_design/%s" % (basename,)))
            if existing.get("couchapp_git_tree_id") == tree:
                continue
            print "Updating %r..." % (branch,)
            tree_to_fs(git_couchdb_url, local_dir, tree)
            write_file(os.path.join(local_dir, "couchapp_git_tree_id"),
                       tree)
            if os.path.exists(os.path.join(local_dir, "_id")):
                os.unlink(os.path.join(local_dir, "_id"))
            couchapp(design_couchdb_url, local_dir)
            print "...done %r" % (branch,)
            

def main(argv):
    parser = optparse.OptionParser(__doc__)
    parser.add_option("--poll", dest="mode", action="store_const",
                      const="poll", default="once")
    parser.add_option("--poll-interval", dest="poll_interval",
                      type=int, default=60*60, 
                      help="unit: seconds, default: hourly")
    parser.add_option("--app-subdir", dest="app_subdir",
                      default=".")
    parser.add_option("--branch", dest="branch", default=None) 
    options, args = parser.parse_args(argv)
    if len(args) == 0:
        git_couchdb = "http://localhost:5984/jwallib"
    else:
        git_couchdb = args.pop(0)
    if len(args) == 0:
        design_couchdb = git_couchdb
    else:
        design_couchdb = args.pop(0)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    if options.mode == "once":
        sync_batch(git_couchdb, design_couchdb, options.branch, 
                   options.app_subdir)
    elif options.mode == "poll":
        while True:
            sync_batch(git_couchdb, design_couchdb, options.branch,
                       options.app_subdir)
            time.sleep(options.poll_interval)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
