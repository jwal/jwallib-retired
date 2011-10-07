# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]
"""

import optparse
import sys

def main(argv):
    parser = optparse.OptionParser(__doc__)
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
