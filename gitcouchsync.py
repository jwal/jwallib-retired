# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options] GIT_URL COUCHDB_URL

I copy objects from GIT_URL and put them into COUCHDB_URL.  I cannot
copy them in the other direction yet.

At the moment, I rely on using the GitHub (JSON) API to Git
repositories as documented on http://developer.github.com/v3/.
i.e. your GIT URL will be parsed from something like
https://github.com/:user/:repo to
https://api.github.com/repos/:user/:repo .

A special couchdb document called branches is fully mutable and is
updated from the list of branches in the git repository.  Each branch
is then given a different document named after that branch.  Are also
fully mutable - there is no equivalent to the reflog yet.  No couchdb
documents are ever deleted.  Other documents are for the commits,
blobs and trees and, in theory, are immutable.

Objects of type blob, commit and tree are not necessarily copied in a
particular order.  The dependencies (referenced objects) of these may
therefore not be present in the target database before the referring
object is created.  All dependencies are fetched as part of this
synchronization unless specified using a (as yet unsupported) config
option.  The objects of type branch and branches are updated once
their immediately referenced objects are known to be present.
"""

from __future__ import with_statement

from cStringIO import StringIO
from hashlib import sha1
from jwalutil import trim
from pprint import pformat
import base64
import contextlib
import json
import optparse
import posixpath
import pycurl as curl
import string
import sys

FUNNY_SHAS = tuple([
        sha1("blob 0\0").hexdigest(),
        "0" * 40,
    ])

def get(url):
    url = url.encode("ascii")
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.perform()
        return json.loads(out.getvalue())

def is_text(candidate):
    try:
        candidate = candidate.encode("ascii")
    except:
        return False
    if not all(a in string.printable for a in candidate):
        return False
    not_allowed = "\t\x0b\x0c"
    if any(a in not_allowed for a in candidate):
        return False
    if any("\n" in a for a in candidate.split("\r\n")):
        return False
    return True

def parse_octal_chmod_code(octal_string):
    result = []
    if octal_string[:-3] == "040":
        result.append("d")
    elif octal_string[:-3] == "100":
        result.append("-")
    else:
        raise NotImplementedError(octal_string)
    parts = [int(x) for x in octal_string[-3:]]
    for part in parts:
        result.append("r" if (part & 0x4) > 0 else "-")
        result.append("w" if (part & 0x2) > 0 else "-")
        result.append("x" if (part & 0x1) > 0 else "-")
    return "".join(result)

def fetch_all(seeds, git_url, couchdb_url):
    to_fetch = set(tuple(s) for s in seeds)
    fetched = set(FUNNY_SHAS)
    while len(to_fetch) > 0:
        kind, sha = to_fetch.pop()
        if sha not in fetched:
            url = git_url + "/git/" + kind + "s/" + sha
            data = get(url)
            if kind == "commit":
                document = {
                    "_id": "git-" + kind + "-" + sha,
                    "type": "git-" + kind,
                    "sha": sha,
                    "author": data["author"],
                    "committer": data["committer"],
                    "message": data["message"],
                    "tree": {
                        "type": "git-tree",
                        "id_": "git-tree-" + data["tree"]["sha"],
                        "sha": data["tree"]["sha"],
                        },
                    "parents": [],
                    }
                for p in sorted(data["parents"], key=lambda x: x["sha"]):
                    ref = {"type": "git-commit",
                           "sha": p["sha"],
                           "_id": "git-commit-" + p["sha"]}
                    document["parents"].append(ref)
                    to_fetch.add(("commit", p["sha"]))
                to_fetch.add(("tree", document["tree"]["sha"]))
            elif kind == "tree":
                document = {
                    "_id": "git-" + kind + "-" + sha,
                    "type": "git-" + kind,
                    "sha": sha,
                    "children": [],
                    }
                for c in sorted(data["tree"], key=lambda x: x["sha"]):
                    ref = {"type": "git-" + c["type"],
                           "sha": c["sha"],
                           "_id": "git-" + c["type"] + "-" + c["sha"],
                           "basename": c["path"],
                           "mode": parse_octal_chmod_code(c["mode"])}
                    document["children"].append(ref)
                    to_fetch.add((c["type"], c["sha"]))
            elif kind == "blob":
                document = {
                    "_id": "git-" + kind + "-" + sha,
                    "type": "git-" + kind,
                    "sha": sha,
                    }
                if "content" not in data:
                    raise Exception("Not a blob? %r %r %s"
                                    % (kind, sha, pformat(data)))
                blob = base64.b64decode(data["content"])
                if is_text(blob):
                    document["encoding"] = "raw"
                    document["raw"] = blob
                else:
                    document["encoding"] = "base64"
                    document["base64"] = base64.b64encode(blob)
            else:
                raise NotImplementedError(kind)
            force_couchdb_put(couchdb_url, document)
        fetched.add(sha)

def force_couchdb_put_all_or_nothing(couchdb_url, *documents):
    document = {"all_or_nothing": True, "docs": documents}
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, couchdb_url + "/_bulk_docs")
        out = StringIO()
        input = json.dumps(document)
        c.setopt(c.WRITEFUNCTION, out.write)
        c.setopt(c.POST, True)
        c.setopt(c.POSTFIELDS, input)
        c.setopt(c.HTTPHEADER, ["content-type: application/json"])
        # c.setopt(c.VERBOSE, True)
        c.perform()
        result = json.loads(out.getvalue())
        assert all(a.get("error") is None for a in result), result

def put(url, document):
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.setopt(c.UPLOAD, True)
        c.setopt(c.READFUNCTION, StringIO(json.dumps(document)).read)
        c.perform()
        return json.loads(out.getvalue())

def force_couchdb_put_with_rev(couchdb_url, *documents):
    for document in documents:
        doc_url = posixpath.join(couchdb_url, document["_id"]).encode("ascii")
        i = 0
        while True:
            if i % 1000 == 0 and i != 0:
                print i, "The race is on!"
            old_doc = get(doc_url)
            if old_doc.get("error") == "not_found":
                if put(doc_url, document).get("error") is None:
                    break
            else:
                assert old_doc.get("error") is None, old_doc
                rev = old_doc.pop("_rev")
                if document == old_doc:
                    break
                else:
                    d2 = dict(document)
                    d2["_rev"] = rev
                    if put(doc_url, d2).get("error") is None:
                        break
            i += 1
                

force_couchdb_put = force_couchdb_put_with_rev

def git_to_couch(git_url, couchdb_url):
    github_prefix = "https://github.com/"
    github_api_prefix = "https://api.github.com/repos/"
    if not git_url.startswith(github_prefix):
        raise NotImplementedError("Sorry, I currently rely on github to "
                                  "convert GIT objects into JSON.  Try a "
                                  "GIT_URL like %s:user/:repo ."
                                  % (github_prefix,))
    git_url = github_api_prefix + trim(git_url, prefix=github_prefix)
    branches = list(sorted({"branch": b["name"],
                            "type": "git-branch",
                            "_id": "git-branch-" + b["name"]}
                           for b in get(git_url + "/branches")))
    to_fetch = set()
    for branch in branches:
        data = get(git_url + "/git/refs/heads/" + branch["branch"])
        branch["commit"] = {"_id": "git-object-" + data["object"]["sha"],
                            "type": "git-commit",
                            "sha": data["object"]["sha"]}
        to_fetch.add(("commit", data["object"]["sha"]))
    fetch_all(to_fetch, git_url, couchdb_url)
    for branch in branches:
        force_couchdb_put(couchdb_url, branch)
    force_couchdb_put(
        couchdb_url, 
        {"_id": "git-branches",
         "type": "git-branches",
         "branches": [{"branch": b["branch"],
                       "type": "git-branch",
                       "_id": b["_id"]} 
                      for b in branches]})

def main(argv):
    parser = optparse.OptionParser(__doc__)
    parser.add_option("--once", dest="mode", action="store_const",
                      const="once", default="once")
    parser.add_option("--poll", dest="mode", action="store_const",
                      const="poll", default="once")
    parser.add_option("--poll-interval", dest="poll_interval",
                      type=int, default=60*60, 
                      help="unit: seconds, default: hourly")
    options, args = parser.parse_args(argv)
    if len(args) == 0:
        parser.error("Missing: GIT_URL")
    git_url = args.pop(0)
    if len(args) == 0:
        parser.error("Missing: COUCHDB_URL")
    couchdb_url = args.pop(0)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    if options.mode == "once":
        git_to_couch(git_url, couchdb_url)
    elif options.mode == "poll":
        while True:
            git_to_couch(git_url, couchdb_url)
            time.sleep(options.poll_interval)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
