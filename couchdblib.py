# Simplle utility functions for interacting with a CouchDB database.
# The pycurl library is used for simple network (HTTP/S) protocol
# handling.

from __future__ import with_statement

from jwalutil import StringIO
from pprint import pformat
from process import call
import contextlib
import json
import os
import posixpath
import pycurl as curl
import urllib
import uuid

### URL quoting
# The default safe characters in the standard library's
# `urllib.quote()` function is not safe for all uses.  This function
# is more like JavaScript's `encodeURIComponent()`.
def url_quote(part):
    return urllib.quote(part, safe="")

### Simple document fetching
# 
# Allows normal size documents to be fetched using a single line
# function call.  Assumes that the return document is JSON.
def get(url):
    url = url.encode("ascii")
    with contextlib.closing(curl.Curl()) as c:
        c.setopt(c.URL, url)
        out = StringIO()
        c.setopt(c.WRITEFUNCTION, out.write)
        c.perform()
        return json.loads(out.getvalue())

### Simple document uploading
# 
# Allows a JSON-like object to be uploaded to a particular document
# URL in the CouchDB.
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

### Delete a document
#
# To delete a document the HTTP DELETE method is used.  A delete of a
# specifif revision can be specified in which case the document will
# only be deleted when that revision is the latest version.  The
# default is to delete the latest revision.
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

### Posting a new document
# 
# The couchdb documentation suggests that the POST HTTP method should
# be avoided so this function emulates it by allocating a UUID and
# trying to PUT to it until it finds one that isn't already used.
def post_new(url, document, id_template="%s"):
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
    
### Updating a document
#
# CouchDB documents can be updated using the PUT method but the API
# returns an error (unless overridden) for changes that are made
# concurrently i.e. without referencing the current version of the
# document in their PUT.  This helper function allows an update_func
# function to repeatedly attempt to apply changes to a document until
# those changes can be succesfully committed to the database.  The
# func will be called each time a conflict is detected, each time with
# a different version of the document as input.
# 
# A simple example for the update_func can be to just return a new
# replacement document.  In this case the function is effectvely a
# forced replacement of the named document.
# 
# Ideally this function would use a randomized binary exponential
# backoff for PUT attempts but at the moment it just tries as quickly
# as it can.
def put_update(url, update_func):
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
            old_rev = old_doc.pop("_rev", None)
            if old_rev is None:
                raise Exception("Failed to get existing document "
                                "_rev from %s:\n%s" % (url, pformat(old_doc)))
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

### Uploading a CouchApp
# 
# Calls through to the command line program `couchapp` to generate a
# CouchDB design document from a directory structure.  The design
# document is uploaded to the given URL.
def couchapp(url, local_path):
    url = url.encode("ascii")
    local_path = os.path.abspath(local_path)
    design_json = call(["couchapp", "push", "--export"],
                        stderr=None, cwd=local_path)
    # Strangely it seems to print a line before the design document
    design_json = design_json[design_json.find("{"):]
    put_update(url, lambda a=None: json.loads(design_json))

