# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]

Couchapp is a tool for building CouchDB _design documents based on a
standardized filesystem layout.  I think the idea is that normally a
software project is developed as a set of JavaScript/HTML/CSS files
etc on a filesystem and so there are more tools for editing these
kinds of documents in this location instead of when they are packaged
_design documents.

gitcouchdbsync.py is a script for copying git version control
documents (blobs, trees and commits) into a CouchDB database.  The
purpose is to (eventually) allow replication and synchronization of
versions of software without needing to use annoying commands like git
push and git fetch.

selfcouchapp.py is a script that combines these two utilities so that
the _design document follows the latest revision of a couchapp managed
project.  After you run "git commit" the gitcouchdbsync.py process
pushes this into a CouchDB and then the selfcouchapp.py script,
subscribed to _changes, notices that the branch has been updated.  It
will copy down the latest files for that branch and use couchapp to
replace the specified _design document.

In the "self" mode, you can configure the selfcouchapp.py script to
follow all branches in the git repository.  When a new branch is
created a _design document is created for it and when a branch is
deleted the _design document is also deleted.  During development, I
will be using this feature and working on a topic branch for my new
feature development, testing my changes in the same couchdb that
contains the stable and topic branches and both design documents.
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
