#!/usr/bin/env python

"""\
%prog [options] -- [UNITTEST2_ARGS...]
"""

from couchdblib import (get, put, post_new, put_update, url_quote, temp_view,
                        delete)
from jwalutil import add_user_to_url
import datetime
import optparse
import os
import posixpath
import subprocess
import sys
import time
import unittest2
import urllib

class GitbrowserSeleniumTests(unittest2.TestCase):

    source_dir = NotImplemented
    couchdb_url = NotImplemented

    def _run_test(self):
        # Wipe out all git-related documents and the design document
        map_func = """\
function (doc) {
  if (doc._id.substr(0, 4) == "git-") {
    emit(null, doc._id);
  }
}
"""
        result = temp_view(posixpath.join(self.couchdb_url, "_temp_view"),
                           {"map": map_func})
        for item in result["rows"]:
            delete(posixpath.join(self.couchdb_url, url_quote(item["id"])))
        # Populate a test GIT repository
        # Copy the git repository to the couchdb
        # Upload the gitbrowser to the couchdb design document
        # Run selenium testing against the public URL

    def test(self):
        def now():
            return datetime.datetime.utcnow().isoformat() + "Z"
        # Add this test run to the queue on the shared database
        document = {
            "request_time": now(),
            "start_time": "",
            "end_time": "",
            "status": "pending",
            }
        result = post_new(self.couchdb_url, document, 
                          id_template="test-run-%s")
        my_url = posixpath.join(self.couchdb_url, url_quote(result["id"]))
        queue_url = posixpath.join(self.couchdb_url, "test-queue")
        def append_to_queue(queued):
            queued.setdefault("queue", []).append(
                {"_id": result["id"],
                 "request_time": document["request_time"],
                 })
        def remove_from_queue(queued):
            queue = queued.get("queue", [])
            queue = [e for e in queue if e.get("_id") != result["id"]]
            queued["queue"] = queue
        put_update(queue_url, append_to_queue)
        try:
            while True:
                queue = get(queue_url)
                for i, entry in enumerate(queue.get("queue", [])):
                    if entry["_id"] == result["id"]:
                        my_index = i
                        break
                else:
                    raise Exception("I seem to have been un queued")
        # Is there a non-expired entry in the queue ahead of mine?
                if my_index == 0:
                    def mark_running(job):
                        job.update(
                            {"status": "running",
                             "start_time": now()})
                    status = "aborted"
                    def mark_stopped(job):
                        job.update(
                            {"status": status,
                             "stop_time": now()})
        # Mark the test as running 
                    put_update(my_url, mark_running)
                    try:
                        try:
                            self._run_test()
                        except AssertionError:
                            status = "failed"
                            raise
                        except Exception:
                            status = "error"
                            raise
                        else:
                            status = "passed"
                            return
                    finally:
                        put_update(my_url, mark_stopped)
                else:
        # Set a timout for the next time to check, if necessary
                    time.sleep(5)
        finally:
        # Mark the test as completed
            put_update(queue_url, remove_from_queue)

def on_error_raise(message=""):
    raise Exception(message)

def setup_globals_and_home(options, on_error=on_error_raise):
    home_path = os.path.abspath(options.home_dir)
    container_git_path = os.path.join(home_path, ".git")
    if not options.force_in_git and os.path.exists(container_git_path):
        return on_error("Home directory seems to be a git repository, "
                        "are you sure about this? %r" % (container_git_path,))
    if options.do_clean_home:
        subprocess.check_call(["rm", "-rf", "--one-file-system", home_path])
    if options.source_dir is None:
        source_path = os.path.join(home_path, "git", "jwallib")
    else:
        source_path = os.path.abspath(options.source_dir)
    if not os.path.exists(source_path):
        subprocess.check_call(["git", "clone", options.git_url, source_path])
    cwd_script = ["bash", "-c", 'cd "$1" && shift && exec "$@"', "-", 
                  source_path]
    couchdb_url = add_user_to_url(options.couchdb_url,
                                  options.couchdb_username,
                                  options.couchdb_password)
    # subprocess.check_call(cwd_script + ["python", "gitcouchdbsync.py", 
    #                                     couchdb_url])
    virtualenv_path = os.path.join(home_path, "couchapp_env")
    virtualenv_activate = os.path.join(virtualenv_path, "bin", "activate")
    env_script = ["bash", "-c",
                  'source "$1" && shift && exec "$@"', "-",
                  virtualenv_activate]
    if not os.path.exists(virtualenv_path):
        subprocess.check_call(["virtualenv", virtualenv_path])
        subprocess.check_call(env_script + ["pip", "install", "couchapp"])
    # subprocess.check_call(env_script + cwd_script 
    #                       + ["python", "selfcouchapp.py",
    #                          "--app-subdir", "gitbrowser",
    #                          couchdb_url])
    GitbrowserSeleniumTests.source_path = source_path
    GitbrowserSeleniumTests.couchdb_url = couchdb_url

def main(prog, argv):
    parser = optparse.OptionParser(prog=prog)
    parser.add_option("--home-dir", dest="home_dir",
                      default=".")
    parser.add_option("--source-dir", dest="source_dir")
    parser.add_option("--git-url", dest="git_url",
                      default="https://github.com/jwal/jwallib")
    parser.add_option("--force-in-git", dest="force_in_git",
                      action="store_const", const=True, default=False)
    parser.add_option("--couchdb-url", dest="couchdb_url",
                      default="https://jwal.cloudant.com/gitbrowser-testing")
    parser.add_option("--couchdb-username", dest="couchdb_username",
                      default="guessme")
    parser.add_option("--couchdb-password", dest="couchdb_password",
                      default="guessme")
    parser.add_option("--no-clean-home", default=True, const=False,
                      action="store_const", dest="do_clean_home")
    options, args = parser.parse_args(argv)
    unittest_argv = [prog] + args
    setup_globals_and_home(options, on_error=on_error_raise)
    unittest2.main(argv=unittest_argv)

if __name__ == "__main__":
    sys.exit(main(sys.argv[0], sys.argv[1:]))
