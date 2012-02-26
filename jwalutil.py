# Copyright 2011 James Ascroft-Leigh

import contextlib
import shutil
import string
import tempfile
import urllib

try:
    from cStringIO import StringIO
except Exception:
    from StringIO import StringIO

def trim(text, prefix="", suffix=""):
    assert text.startswith(prefix), (text, prefix)
    assert text.endswith(suffix), (text, suffix)
    assert len(text) >= len(prefix) + len(suffix), (text, prefix, suffix)
    return text[len(prefix):len(text)-len(suffix)]

def get1(items):
    items = list(items)
    assert len(items) == 1, items
    return items[0]

def read_lines(data, line_terminator="\r\n"):
    # For well behaved data that comes from a command line program.
    # Each line - even the last - should really have a \r\n
    # terminator.  Absence of any terminator indicates no lines at
    # all.  The unix utility "ls" bahaves like this, for example.
    # Note, though, that sometimes a different line terminator is
    # used.
    result = []
    i = 0
    while True:
        index = data.find(line_terminator, i)
        if index >= 0:
            result.append(data[i:index])
            i = index + len(line_terminator)
        else:
            assert index == -1, index
            if i < len(data) - 1:
                raise Exception("Trailing garbage %r in %r" % (data[i:], data))
        if i == len(data):
            break
    return result

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

@contextlib.contextmanager
def mkdtemp(*a, **kw):
    temp_dir_path = tempfile.mkdtemp(*a, **kw)
    try:
        yield temp_dir_path
    finally:
        shutil.rmtree(temp_dir_path)

def add_user_to_url(base_url, username, password):
    scheme, rest = base_url.split("://", 1)
    return "%s://%s:%s@%s" % (
        scheme,
        urllib.quote(username, safe=""),
        urllib.quote(password, safe=""),
        rest)
