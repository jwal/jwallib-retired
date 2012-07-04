# Copyright 2012 James Ascroft-Leigh

"""\
%prog [options]
"""

from jwalutil import on_error_raise
import optparse
import os
import subprocess
import sys


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
