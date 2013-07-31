# A set of miscellaneous functions that seem to make a lot of sense to
# me but that aren't available in the python standard library.

from __future__ import with_statement

import contextlib
import datetime
import re
import shutil
import string
import tempfile
import urllib

### StringIO
# 
# It is a common pattern to use cStringIO when available but to
# fall-back on the pure-python implementation when that isn't
# available, like when using jython.  This provides a name that can be
# imported that picks the best implementation.
try:
    from cStringIO import StringIO
except Exception:
    from StringIO import StringIO

### Trim
#
# You often come across structured strings with a specific prefix or
# suffix to indicate a type or a category.  A common example is
# filename extensions.  If you need to fetch the base string with the
# prefix or suffix removed then, for safety and clarity, you should
# first check that the expected prefix or suffix is actually present.
def trim(text, prefix="", suffix=""):
    assert text.startswith(prefix), (text, prefix)
    assert text.endswith(suffix), (text, suffix)
    assert len(text) >= len(prefix) + len(suffix), (text, prefix, suffix)
    return text[len(prefix):len(text)-len(suffix)]


### Get1
#
# When you are using a standardized query language but only expect a
# single result it makes sense to check that you did in fact get a
# result and didn't find abiguous results.  Examples:
#    
#    my_url = get1(sql("select value "
#                      "from settings"
#                      " where key = 'my_url'"))
# 
#    hostname = get1(
#      iface.xpath("ancestor::host/@name"))
def get1(items):
    items = list(items)
    assert len(items) == 1, items
    return items[0]

### Read file
#
# Wouldn't it be nice to read the contents of a file with a single
# line statement?  In newer version of python this is possible but
# frowned upon because putting the read() method call after the colon
# for the with statement (on the same line) is ugly.
def read_file(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")

def write_file(path, data):
    with open(path, "wb") as fh:
        return fh.write(data.encode("utf-8"))

### Read lines
#
# Most well-bahaved command line programs emit their output as a
# single result per line and each line is terminated by a newline
# sequence.  Even the last line should have the terminator so that an
# entry for the empty string can be distinguished from no entries at
# all.  An example utility that behaves like this is the unix utility
# `ls`.
# 
# The line terminator defaults to `\r\n` a.k.a. CRLF a.k.a. U+000D
# U+000A to be consistent with Internet standards such as HTTP.  In
# practise many invocations of this will need to override the line
# terminator to be `\n`.
def read_lines(data, line_terminator=None):
    if "\r\n" in data:
        line_terminator = "\r\n"
    else:
        line_terminator = "\n"
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

### Is text?
# 
# Really, source code should be 7bit clean, should not use special
# characters (even tab).  Why not tab?  Because it is often rendered
# inconsistently with a variable number of spaces used.  Why CRLF line
# termination?  Because that is consistent with Internet standards
# such as HTTP.  Why ASCII only?  So there is no need to do encoding
# detection.
#
# Eventually the world will move on and this function will not be
# necessary.
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

### mkdtemp
#
# A contextmanager for easily working with temporary directories.
@contextlib.contextmanager
def mkdtemp(*a, **kw):
    temp_dir_path = tempfile.mkdtemp(*a, **kw)
    try:
        yield temp_dir_path
    finally:
        shutil.rmtree(temp_dir_path)

### maybe_with
#
# This is used for the main() function in command line scripts.  The
# common pattern is to open a file specified on the command line, if
# specified, but to fall back on the already open sys.stdout handle
# otherwise.  Example:
#
#    out_fh = stdout if options.out_path is None else None
#    with maybe_with(out_fh, lambda: open(options.out_path, "wb")) as fh:
#      print >>>fh, "Hello world"
@contextlib.contextmanager
def maybe_with(param, cm):
    if param is None:
        with cm() as result:
            yield result
    else:
        yield param

### Monkey patching
# 
# Context manager for monkey patching.  It sets or replaces a named
# attribute of the given object with a defined value.  After the
# context exits the attribute is returned to its original state.  A
# special marker object called undefined is used to detect when the
# attribute was originally missing. By using identity `is` comparison
# with this local-scoped undefined `object()` there is no chance that
# the attribute could actually take this value.
@contextlib.contextmanager
def monkey_patch_attr(obj, attr, value):
    undefined = object()
    orig = getattr(obj, attr, undefined)
    setattr(obj, attr, value)
    try:
        yield
    finally:
        if orig is undefined:
            delattr(obj, attr)
        else:
            setattr(obj, attr, orig)

### Add user to url
# 
# If the username and password are stored in a separate file from the
# actual URL then this can be used to construct a working URL.
def add_user_to_url(base_url, username, password):
    scheme, rest = base_url.split("://", 1)
    return "%s://%s:%s@%s" % (
        scheme,
        urllib.quote(username, safe=""),
        urllib.quote(password, safe=""),
        rest)

### Group by
# 
# For ad-hoc analysis of data structures in python.  Similar to the
# `itertools.group()` function but is simpler for smaller datasets
# that don't need to be streamed.
# 
# By default the key is assumed to be unique so that a simple
# key-value mapping is emitted.  The alternative is to emit a key to
# list mapping.
def group_by(items, key_getter=lambda i: i.id, unique=True):
    result = {}
    for item in items:
        key = key_getter(item)
        result.setdefault(key, []).append(item)
    if unique:
        for key in result:
            result[key] = get1(result[key])
    return result


### Error handlers
#
#### On error, raise
# 
# This is for scripts that have a `main()` function separate from a
# logic function.  The logic function can be imported invoked as a
# library call but wishes to raise an exception when used incorrectly.
# When called from the `main()` function, the usage error should be
# reported via `sys.exit()` or via `parser.error()`.  Such logic
# functions can therefore take an error callback defaulting to this
# function.
def on_error_raise(message):
    raise Exception(message)


#### On error, return None
 
# Sometimes the failure mode is known to be safe to ignore by the
# caller.  Such callers may wish to pass this function to override
# certain error handlers.  Can you tell that I don't like catching
# exceptions?
def on_error_return_none(message):
    return None
    
    
### Parsing ISO8601 timestamps
ISO8601 = re.compile("""\
^(?P<yearsign>[+-]?)
(?P<year>\d+)
((?P<yearmonthsep>[-]?)
 (?P<month>\d{2})
 ((?P<monthdaysep>[-]?)
  (?P<day>\d{2})
  ((?P<datetimesep>[T ]?)
   (?P<hour>\d{2})
   ((?P<hourminutesep>[:]?)
    (?P<minute>\d{2})
    ((?P<minutesecondsep>[:]?)
     (?P<second>\d{2})
     ((?P<secondpointsep>[,.]?)(?P<secondpoint>\d+))?
     ((?P<specialoffset>[Z])
     |((?P<offsetsign>[+-])(?P<offsethour>\d{2})
     (?P<offsersep>[:]?)(?P<offsetminute>\d{2}?)
))?)?)?)?)?)?$
""",
                     re.VERBOSE)
def parse_iso8601_to_utc_seconds(timestamp):
    match = ISO8601.match(timestamp)
    if match is None:
        raise Exception("Unable to parse: %s" % (timestamp,))
    parsed = match.groupdict()
    if parsed["specialoffset"] == "Z":
        offset = datetime.timedelta(seconds=0)
    else:
        offsetminute = (0 if not parsed["offsetminute"] 
                        else int(parsed["offsetminute"]))
        offsethour = int(parsed["offsethour"])
        offsetsign = {"+": 1, "-": -1}[parsed["offsetsign"]]
        offset = offsetsign * datetime.timedelta(
            hours=offsethour, minutes=offsetminute)
    base = datetime.datetime(
        *[int(parsed[a]) for a in
          ["year", "month", "day", "hour", "minute", "second"]])
    return base - offset
        

# Copyright 2011 James Ascroft-Leigh

