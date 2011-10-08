
def trim(string, prefix="", suffix=""):
    assert string.startswith(prefix), (string, prefix)
    assert string.endswith(suffix), (string, suffix)
    assert len(string) >= len(prefix) + len(suffix), (string, prefix, suffix)
    return string[len(prefix):len(string)-len(suffix)]

