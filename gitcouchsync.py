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
is then given a different document named after that branch.  These
documents are (or should be, assuming no rebasing) append-only objects
that are equivalent to a reflog.  No couchdb documents are ever
deleted.
"""

from __future__ import with_statement

from cStringIO import StringIO
from jwalutil import trim
from pprint import pformat
import contextlib
import json
import optparse
import pycurl as curl
import sys

def get(url):
    url = url.encode("ascii")
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.perform()
        return json.loads(out.getvalue())

def force_couchdb_put(couchdb_url, *documents):
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
    for branch in branches:
        data = get(git_url + "/git/refs/heads/" + branch["branch"])
        branch["commit"] = {"_id": "git-object-" + data["object"]["sha"],
                            "type": "git-commit",
                            "sha": data["object"]["sha"]}
        force_couchdb_put(couchdb_url, branch)
    force_couchdb_put(
        couchdb_url, 
        {"_id": "git-branches",
         "type": "git-branch-list",
         "branches": [{"branch": b["branch"],
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
