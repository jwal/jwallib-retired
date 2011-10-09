
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
