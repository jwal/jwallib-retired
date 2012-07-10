# A simple utility that clones a git repository but also commits any
# uncommitted changes from the original into the clone.  This is used
# for development of the Git Browser where it is useful to see how the
# browser will display certain content before committing it to the
# main repository.  It is also used, as a library, from the continuous
# integration script to that tests can be run before commit.

"""\
%prog [options]
"""

from jwalutil import on_error_raise
import optparse
import os
import subprocess
import sys

### Finding the git directory
#
# Simulates the way the actual git command locates the root directory
# of the repository.  It searches for the .git folder in the current
# directory and moves up one level if it is not there.  This is
# repeated until it find the repository root or until it fails by
# finding the filesystem root.
def find_git_dir(start_dir=".", on_missing=on_error_raise):
    start_dir = os.path.abspath(start_dir)
    candidate = start_dir
    while True:
        candidate_git = os.path.join(candidate, ".git")
        if os.path.exists(candidate_git):
            return candidate
        if os.path.dirname(candidate) == candidate:
            return on_missing("Unable to find a git repository: %s"
                              % (start_dir,))
        candidate = os.path.dirname(candidate)


def git_clone(git_url, dest_path):
    if os.path.exists(dest_path):
        return
    subprocess.check_call(["git", "clone", git_url, dest_path])


def git_status(git_path):
    child = subprocess.Popen(["git", "status", "--porcelain"],
                             cwd=git_path, stdout=subprocess.PIPE)
    stdout, stderr = child.communicate()
    assert child.returncode == 0, git_path
    return [x for x in stdout.rstrip("\n").split("\n") if x != ""]


def git_generate_patch(git_path):
    child = subprocess.Popen(["git", "diff", "HEAD"],
                             cwd=git_path, stdout=subprocess.PIPE)
    stdout, stderr = child.communicate()
    assert child.returncode == 0, git_path
    return stdout


def git_apply_patch(patch, git_path):
    child = subprocess.Popen(["git", "apply", "-"],
                             cwd=git_path, stdin=subprocess.PIPE)
    stdout, stderr = child.communicate(patch)
    assert child.returncode == 0, git_path


def git_commit(git_path, message="Autocommit", username="root",
               email="fail@example.com"):
    subprocess.check_call(["git", "-c", "user.name=%s" % (username,),
                           "-c", "user.email=%s" % (email,),
                           "commit", "-am", message], cwd=git_path)


def git_dev_commit(dev_repo, dest_repo):
    if dest_repo.startswith(dev_repo):
        raise Exception("Dev repo %r within dest repo %r"
                        % (dev_repo, dest_repo))
    if dev_repo.startswith(dest_repo):
        raise Exception("Dest repo %r within dev repo %r"
                        % (dest_repo, dev_repo))
    git_clone(dev_repo, dest_repo)
    # TODO: Also commit untracked files?
    if len(git_status(dev_repo)) > 0:
        print git_status(dev_repo)
        patch = git_generate_patch(dev_repo)
        print patch
        # TODO: Reset to the revision in the dev_repo first
        git_apply_patch(patch, dest_repo)
        git_commit(dest_repo)


def main(argv):
    parser = optparse.OptionParser(__doc__)
    parser.add_option("--dev-repo", default=None, dest="dev_repo")
    parser.add_option("--dest-repo", default=None, dest="dest_repo")
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    dev_repo = options.dev_repo or find_git_dir()
    dest_repo = options.dest_repo or os.path.abspath(".")
    git_dev_commit(dev_repo, dest_repo)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# Copyright 2012 James Ascroft-Leigh
