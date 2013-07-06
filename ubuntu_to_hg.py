# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]
"""

import optparse
import requests
import sys
from posixpath import join
import email
import apt_pkg
from cStringIO import StringIO
from jwalutil import mkdtemp
from jwalutil import write_file
import os
from pprint import pformat

BASE_URL = "http://changelogs.ubuntu.com/"

def parse_control_file(data):
    result = []
    with mkdtemp() as temp_dir:
        meta_path = os.path.join(temp_dir, "data.txt")
        write_file(meta_path, data)
        tags = apt_pkg.TagFile(meta_path)
        r = tags.step()
        while r:
            result.append(dict(tags.section))
            r = tags.step()
    return result

def ubuntu_to_hg():
    meta_release_response = requests.get(join(BASE_URL, "meta-release"))
    meta_release = parse_control_file(meta_release_response.text)
    print pformat(meta_release)

def main(argv):
    parser = optparse.OptionParser(__doc__)
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    ubuntu_to_hg()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
