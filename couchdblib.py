from __future__ import with_statement

from jwalutil import StringIO
from process import call
import contextlib
import json
import os
import posixpath
import pycurl as curl
import urllib
import uuid

def url_quote(part):
    return urllib.quote(part, safe="")

def get(url):
    url = url.encode("ascii")
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.perform()
        return json.loads(out.getvalue())

def put(url, document):
    url = url.encode("ascii")
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.setopt(c.UPLOAD, True)
        c.setopt(c.READFUNCTION, StringIO(json.dumps(document)).read)
        c.perform()
        return json.loads(out.getvalue())

def temp_view(url, view):
    url = url.encode("ascii")
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.setopt(c.POST, True)
        c.setopt(c.HTTPHEADER, ["Content-Type: application/json"])
        c.setopt(c.POSTFIELDS, json.dumps(view))
        c.perform()
        return json.loads(out.getvalue())

def delete(url, rev=None):
    url = url.encode("ascii")
    if rev is None:
        rev = get(url)["_rev"]
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        c.setopt(c.CUSTOMREQUEST, "DELETE")
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.setopt(c.HTTPHEADER, ["If-Match: %s" % (json.dumps(rev),)])
        c.perform()
        result = json.loads(out.getvalue())
        if not result.get("ok", False):
            raise Exception(result)

def post_new(url, document, id_template="%s"):
    # The couchdb documentation suggests that POST should be avoided,
    # so emulate it by allocating a UUID and trying to PUT to it until
    # it finds one that isn't already used.
    i = 0
    while True:
        if i % 1000 == 0 and i != 0:
            print i, "The race is on!"
        candidate = posixpath.join(
            url, url_quote(id_template % (uuid.uuid4(),)))
        candidate = candidate.encode("ascii")
        with contextlib.closing(curl.Curl()) as c:
            c.setopt(c.URL, candidate)
            out = StringIO()
            c.setopt(c.WRITEFUNCTION, out.write)
            c.setopt(c.UPLOAD, True)
            c.setopt(c.READFUNCTION, StringIO(json.dumps(document)).read)
            c.perform()
            result = json.loads(out.getvalue())
            if "id" in result:
                return result
            if result.get("error") != "conflict":
                raise Exception(result)
        i += 1
    

def put_update(url, update_func):
    # Couchdb documents can be updated but the API returns an error
    # (unless overridden) for changes that are made concurrently
    # i.e. without referencing the current version of the document in
    # their PUT.  This helper function allows an update_func function
    # to repeatedly attempt to apply changes to a document until those
    # changes can be succesfully committed to the database.  The func
    # will be called each time a conflict is detected, each time with
    # a different version of the document as input.  Ideally this
    # function would use a randomized binary exponential backoff for
    # PUT attempts but at the moment it just tries as quickly as it
    # can.
    url = url.encode("ascii")
    i = 0
    while True:
        if i % 1000 == 0 and i != 0:
            print i, "The race is on!"
        old_doc = get(url)
        if (old_doc.get("error") == "not_found" 
            and old_doc.get("reason") in ("missing", "deleted")):
            old_doc = {}
            old_rev = None
        else:
            assert old_doc.get("error") is None, old_doc
            old_rev = old_doc["_rev"]
            old_rev = old_doc.pop("_rev")
        new_doc = update_func(old_doc)
        # The update_func can choose to mutate the document in place
        # or to return a replacement document
        if new_doc is None:
            new_doc = old_doc
        # The update_func can choose to leave out the _rev attribute
        # or to populate it with the correct value from the input.
        if old_rev is None:
            assert "_rev" not in new_doc, new_doc
        else:
            if "_rev" in new_doc:
                assert new_doc["_rev"] == old_rev, (old_rev, new_doc["_rev"])
            else:
                new_doc = dict(new_doc)
                new_doc["_rev"] = old_rev
        result = put(url, new_doc)
        if result.get("error") is None:
            new_doc["_rev"] = result["rev"]
            new_doc["_id"] = result["id"]
            return new_doc
        i += 1

def couchapp(url, local_path):
    url = url.encode("ascii")
    local_path = os.path.abspath(local_path)
    call(["couchapp", "push", local_path, url])
