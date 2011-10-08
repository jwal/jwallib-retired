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

A special couchdb document called git-branches is fully mutable and is
updated from the list of branches in the git repository.  Each branch
is then given a different document named after that branch
e.g. git-branch-:branch.  These branch document are also fully mutable
- and there is no equivalent to the reflog yet.  No couchdb documents
are ever deleted.  Other documents for the commits, blobs and trees
are, in theory, are immutable.

Objects are copied in dependency order i.e. the presence of an object
implied that, recursively, the objects it refers to are also present.
This is an assumption that the synchronizer relies upon in order to do
incremental copies.
"""

# Implementation note: The replication in dependency order requires a
# long stack of dependencies to be maintained.  The length of this
# stack is (according to my intuition) of the order of the length of
# the commit history multiplied by the average number of files and
# directories in the repository over time.  If the length of this
# stack becomes a burden then it can safely be discarded as long as
# the root element (the list of branches) is retained.  By also
# retaining the bottom most element you will eventually get everything
# pulled.
# 
# assert MAX_PULL_STACK_LENGTH > 10, MAX_PULL_STACK_LENGTH
# if len(pull_stack) > MAX_PULL_STACK_LENGTH:
#     pull_stack[:] = [pull_stack[0]] + [pull_stack[-1]]

from __future__ import with_statement

from cStringIO import StringIO
from collections import namedtuple
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
import time

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
    if not all(len(a) < 80 for a in candidate.split("\r\n")):
        return False
    return True

SYMBOLIC_TYPES = (
    ("directory", "d", "040"),
    ("regular file", "-", "100"),
    ("symbolic link", "l", "120"),
    )

def octal_to_symbolic_mode(octal_string, check_reversible=True):
    result = []
    result.append(
        dict((e[2], e[1]) for e in SYMBOLIC_TYPES)[octal_string[:-3]])
    parts = [int(x) for x in octal_string[-3:]]
    for part in parts:
        result.append("r" if (part & 0x4) > 0 else "-")
        result.append("w" if (part & 0x2) > 0 else "-")
        result.append("x" if (part & 0x1) > 0 else "-")
    result = "".join(result)
    if check_reversible:
        octal = symbolic_to_octal_mode(result, check_reversible=False)
        assert (octal == octal_string), (octal_string, octal, result)
    return result

def symbolic_to_octal_mode(symbolic_string, check_reversible=True):
    result = []
    result.append(
        dict((e[1], e[2]) for e in SYMBOLIC_TYPES)[symbolic_string[0]])
    for i in range(3):
        triple = symbolic_string[3*i + 1:3*i+4]
        code = 0
        if "r" in triple:
            code += 4
        if "w" in triple:
            code += 2
        if "x" in triple:
            code += 1
        result.append(str(code))
    result = "".join(result)
    if check_reversible:
        symbolic = octal_to_symbolic_mode(result, check_reversible=False)
        assert (symbolic == symbolic_string), (symbolic_string, symbolic, 
                                               result)
    return result

def resolve_document(git_url, docref):
    document = docref_to_dict(docref)
    kind = docref.kind
    id = docref.id
    if kind == "branches":
        source_url = git_url + "/branches"
    elif kind == "branch":
        source_url = git_url + "/git/refs/heads/" + docref.name
    elif kind in ("tree", "commit", "blob"):
        source_url = git_url + "/git/" + kind + "s/" + docref.name
    else:
        raise NotImplementedError(docref)
    data = get(source_url.encode("ascii"))
    if kind == "branches":
        document["branches"] = []
        for branch in data:
            document["branches"].append(
                {"branch": branch["name"],
                 "type": "git-branch",
                 "_id": "git-branch-" + branch["name"]})
    elif kind == "branch":
        document["commit"] = docref_to_dict(
            ShaDocRef("commit", data["object"]["sha"]))
    elif kind == "commit":
        document.update(
            {"author": data["author"],
             "committer": data["committer"],
             "message": data["message"],
             "tree": docref_to_dict(ShaDocRef("tree", 
                                              data["tree"]["sha"])),
             "parents": [],
             })
        for p in sorted(data["parents"], key=lambda x: x["sha"]):
            document["parents"].append(docref_to_dict(ShaDocRef("commit",
                                                                p["sha"])))
    elif kind == "tree":
        document["children"] = []
        for c in sorted(data["tree"], key=lambda x: x["sha"]):
            ref = {"child": docref_to_dict(ShaDocRef(c["type"], c["sha"])),
                   "basename": c["path"],
                   "mode": octal_to_symbolic_mode(c["mode"])}
            document["children"].append(ref)
    elif kind == "blob":
        if "content" not in data:
            if docref == ShaDocRef("blob", sha1("blob 0\0").hexdigest()):
                data = {"content": base64.b64encode("")}
            else:
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
    return document

DocRef = namedtuple("DocRef", ["id", "kind", "name"])

def BranchDocref(branch):
    branch = unicode(branch)
    return DocRef("git-branch-" + branch, "branch", branch)

def ShaDocRef(kind, sha):
    kind = unicode(kind)
    sha = unicode(sha)
    assert kind in ("tree", "blob", "commit"), kind
    return DocRef("git-" + kind + "-" + sha, kind, sha)

def id_to_docref(id):
    most = trim(id, prefix="git-")
    if most == "branches":
        return BRANCHES_DOCREF
    kind, name = most.split("-", 1)
    assert kind in ("branch", "tree", "commit", "blob"), repr(id)
    return DocRef(id, kind, name)

BRANCHES_DOCREF = DocRef(u"git-branches", u"branches", None)

def docref_to_dict(docref):
    if docref.kind == "branch":
        return {"_id": docref.id,
                "type": "git-" + docref.kind,
                "branch": docref.name}
    elif docref.kind == "branches":
        assert docref.name is None, docref
        return {"_id": docref.id,
                "type": "git-" + docref.kind}
    elif docref.kind in ("tree", "commit", "blob"):
        return {"_id": docref.id,
                "type": "git-" + docref.kind,
                "sha": docref.name}
    else:
        raise NotImplementedError(docref)

def dict_to_docref(document):
    id = document["_id"]
    kind = trim(document["type"], prefix="git-")
    if kind == "branches":
        return BRANCHES_DOCREF
    elif kind == "branch":
        return BranchDocref(document["branch"])
    elif kind in ("tree", "commit", "blob"):
        return ShaDocRef(trim(document["type"], prefix="git-"), 
                         document["sha"])
    else:
        raise NotImplementedError(document)

def find_dependencies(document):
    kind = trim(document["type"], prefix="git-")
    if kind == "branches":
        for branch in document["branches"]:
            yield dict_to_docref(branch)
    elif kind == "branch":
        yield dict_to_docref(document["commit"])
    elif kind == "commit":
        for parent in document["parents"]:
            yield dict_to_docref(parent)
        yield dict_to_docref(document["tree"])
    elif kind == "blob":
        pass
    elif kind == "tree":
        for child in document["children"]:
            yield dict_to_docref(child["child"])
    else:
        raise NotImplementedError(document)

BIG_NUMBER = 100000
SMALL_NUMBER = BIG_NUMBER // 2
assert BIG_NUMBER > SMALL_NUMBER, (BIG_NUMBER, SMALL_NUMBER)
assert SMALL_NUMBER > 0, SMALL_NUMBER

MUTABLE_TYPES = ("branches", "branch")

def fetch_all(git_url, couchdb_url, seeds):
    to_fetch = list(seeds)
    push = lambda x: to_fetch.append(x)
    pop = lambda: to_fetch.pop()
    def priority_sort_key(docref):
        priority_items = ["commit", "tree"]
        i = dict((a, idx) for (idx, a) in enumerate(priority_items)).get(
            docref.kind, len(priority_items))
        return (i, docref.name, docref)
    def multipush(many, limit=None):
        for i, item in enumerate(reversed(
                sorted(many, key=priority_sort_key))):
            if limit is not None and i > limit:
                break
            push(item)
    multipush(seeds)
    mutable_buffer = {}
    local_buffer = {}
    fetched = set()
    for match in get(couchdb_url + "/_all_docs")["rows"]:
        docref = id_to_docref(match["id"])
        if docref.kind not in MUTABLE_TYPES:
            fetched.add(docref)
    while len(to_fetch) > 0:
        docref = pop()
        if docref not in fetched:
            document = local_buffer.get(docref)
            if document is None:
                print "get", len(to_fetch), docref
                document = resolve_document(git_url, docref)
                local_buffer[docref] = document
                if docref.kind in ("branches", "branch"):
                    mutable_buffer[docref] = document
            local_dependencies = set(find_dependencies(document)) - fetched
            if len(local_dependencies) == 0:
                force_couchdb_put(couchdb_url, document)
                del local_buffer[docref]
                fetched.add(docref)
                print "put", len(to_fetch), docref
            else:
                push(docref)
                multipush(local_dependencies)
        if len(local_buffer) > BIG_NUMBER:
            local_buffer.clear()
            local_buffer.update(mutable_buffer)
        assert BIG_NUMBER > 15
        if len(to_fetch) > BIG_NUMBER:
            to_keep = to_fetch[:-SMALL_NUMBER]
            to_fetch[:] =  []
            multipush(seeds)
            multipush(to_keep)
            if len(to_fetch) > BIG_NUMBER:
                print "ouch, lots of seeds?"
            assert len(to_fetch) > 0

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
            if (old_doc.get("error") == "not_found" 
                and old_doc.get("reason") == "missing"):
                result = put(doc_url, document)
                if result.get("error") is None:
                    break
            else:
                assert old_doc.get("error") is None, old_doc
                rev = old_doc.pop("_rev")
                if document == old_doc:
                    break
                else:
                    d2 = dict(document)
                    d2["_rev"] = rev
                    result = put(doc_url, d2)
                    if result.get("error") is None:
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
    fetch_all(git_url, couchdb_url, [BRANCHES_DOCREF])

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
