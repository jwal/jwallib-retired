# Copyright 2011 James Ascroft-Leigh

try:
    from cStringIO import StringIO
except Exception:
    from StringIO import StringIO

def trim(string, prefix="", suffix=""):
    assert string.startswith(prefix), (string, prefix)
    assert string.endswith(suffix), (string, suffix)
    assert len(string) >= len(prefix) + len(suffix), (string, prefix, suffix)
    return string[len(prefix):len(string)-len(suffix)]

def get1(items):
    items = list(items)
    assert len(items) == 1, items
    return items[0]

def read_lines(data):
    if data == "":
        return []
    return list(trim(a, suffix="\r\n") for a in StringIO(data)
                if a != "")

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

