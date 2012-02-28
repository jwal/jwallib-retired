# Copyright 2011 James Ascroft-Leigh

from cStringIO import StringIO
from jwalutil import trim
import subprocess

def call(argv, **kwargs):
    # print "~~~", argv
    do_wait = kwargs.pop("do_wait", True)
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.STDOUT)
    rc = kwargs.pop("check_rc", 0)
    do_check = kwargs.pop("do_check", True)
    do_crlf_fix = kwargs.pop("do_crlf_fix", True)
    print "@@@", argv
    try:
        child = subprocess.Popen(argv, **kwargs)
    except Exception, e:
        raise Exception("Failed to spawn child process %r: %s" % (argv, e))
    if do_wait:
        stdout, stderr = child.communicate()
        if do_check:
            if child.returncode != rc:
                raise Exception("""\
Child process error:
  returncode=%r
  argv=%r
  stdout...
%s
""" % (child.returncode, argv, stdout))
        if do_crlf_fix and stdout is not None:
            # print "@@@", repr(stdout)
            stdout = stdout.replace("\r\n", "\n").replace("\n", "\r\n")
        # print "###", repr(stdout)
        return stdout
    else:
        return child
