#!/usr/bin/env python

"""\
%prog [options] -- [UNITTEST_ARGS...]
"""

from __future__ import with_statement

from selenium import webdriver
from couchdblib import delete, couchapp
from couchdblib import get, put, post_new, put_update, url_quote, temp_view
from jwalutil import add_user_to_url, mkdtemp, monkey_patch_attr
import contextlib
import datetime
import optparse
import os
import posixpath
import subprocess
import sys
import time
import unittest
import urllib

class GitbrowserSeleniumTests(unittest.TestCase):

    source_path = NotImplemented
    couchdb_url = NotImplemented
    saucelabs_url = NotImplemented
    public_url = NotImplemented

    def _go_to_the_selenium_stage(self):
        desired_capabilities = webdriver.DesiredCapabilities.FIREFOX
        desired_capabilities["version"] = "6"
        desired_capabilities["platform"] = "XP"
        desired_capabilities["name"] = "Git Browser selenium tests"
        driver = webdriver.Remote(
            desired_capabilities=desired_capabilities,
            command_executor=self.saucelabs_url)
        try:
            driver.implicitly_wait(30)
            driver.get(self.public_url)
        finally:
            driver.quit()

    def _run_test(self):
        # Wipe out all git-related documents and the design document
        result = get(posixpath.join(self.couchdb_url, 
                                    "_design/test/_view/git-documents"))
        for item in result["rows"]:
            delete(posixpath.join(self.couchdb_url, url_quote(item["id"])))
        # Upload the gitbrowser to the couchdb design document
        gitbrowser_source_path = os.path.join(self.source_path, "gitbrowser")
        couchapp(posixpath.join(self.couchdb_url, "_design/gitbrowser"), 
                 gitbrowser_source_path)
        # Populate a test GIT repository
        with mkdtemp() as temp_dir:
            cwd_script = ["bash", "-c", 'cd "$1" && shift && exec "$@"', "-", 
                          temp_dir]
            subprocess.check_call(cwd_script + ["git", "init"])
        ## write file README
            git = cwd_script + ["env", 
                                "HOME=%s" % (temp_dir,),
                                "git"]
            subprocess.check_call(git + ["config", "user.name", "Tester"])
            subprocess.check_call(git + ["config", "user.email", 
                                         "fail@example.com"])
            path = os.path.join(temp_dir, "README")
            with open(path, "wb") as fh:
                fh.write("Initial version of text file\r\n")
            subprocess.check_call(git + ["add", path])
            subprocess.check_call(git + ["commit", "-m", 
                                         "Initial commit"])
        ## write file README
            with open(path, "wb") as fh:
                fh.write("Just a minimal git repository for testing\r\n")
            subprocess.check_call(git + ["add", path])
        ## write file binary 
            path = os.path.join(temp_dir, "binary-file")
            with open(path, "wb") as fh:
                fh.write("".join(chr(i) for i in range(2**8)))
            subprocess.check_call(git + ["add", path])
        ## write file subfolder/README 
            path = os.path.join(temp_dir, "subfolder", "README")
            os.makedirs(os.path.dirname(path))
            with open(path, "wb") as fh:
                fh.write("A file in a subfolder\r\n")
            subprocess.check_call(git + ["add", path])
            subprocess.check_call(git + ["commit", "-m", "Update"])
        # Copy the git repository to the couchdb
            sync_script = os.path.join(self.source_path, "gitcouchdbsync.py")
            subprocess.check_call(cwd_script + ["python", sync_script,
                                                self.couchdb_url])
        # Run selenium testing against the public URL
        self._go_to_the_selenium_stage()

    def test(self):
        # Clean up any partially aborted test runs
        def mark_aborted(doc):
            doc.update({"status": "aborted"})
        queue_url = posixpath.join(self.couchdb_url, "test-queue")
        queued_ids = set(i["_id"] for i in get(queue_url)["queue"])
        pending_map_func = """\
function (doc) {
  var prefix = "test-run-";
  if (doc._id.substr(0, prefix.length) == prefix) {
    if (doc.status == "pending") {
      emit(null, doc._id);
    }
  }
}
"""
        git_map_func = """\
function (doc) {
  var prefix  = "test-";
  if (doc._id.substr(0, prefix.length) != prefix) {
    emit(null, doc._id);
  }
}
"""
        design_doc = {
            "language": "javascript",
            "views": {
                "pending-tests": {
                    "map": pending_map_func,
                    }, 
                "git-documents": {
                    "map": git_map_func,
                    },
                },
            }
        put_update(posixpath.join(self.couchdb_url, "_design/test"),
                   lambda a=None: design_doc)
        result = get(posixpath.join(self.couchdb_url, 
                                    "_design/test/_view/pending-tests"))
        pending_ids = set(i["id"] for i in result["rows"])
        for missing_id in pending_ids - queued_ids:
            put_update(posixpath.join(self.couchdb_url, url_quote(missing_id)),
                       mark_aborted)
        # Add this test run to the queue on the shared database
        def now():
            return datetime.datetime.utcnow().isoformat() + "Z"
        document = {
            "request_time": now(),
            "start_time": "",
            "end_time": "",
            "status": "pending",
            }
        result = post_new(self.couchdb_url, document, 
                          id_template="test-run-%s")
        my_url = posixpath.join(self.couchdb_url, url_quote(result["id"]))
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
                    print "sleeping..."
                    time.sleep(5)
        finally:
        # Mark the test as completed
            put_update(queue_url, remove_from_queue)

def on_error_raise(message=""):
    raise Exception(message)

@contextlib.contextmanager
def setup_globals(options):
    source_path = os.path.dirname(os.path.abspath(__file__))
    couchdb_url = add_user_to_url(options.couchdb_url,
                                  options.couchdb_username,
                                  options.couchdb_password)
    saucelabs_url = add_user_to_url(options.saucelabs_url,
                                    options.saucelabs_username,
                                    options.saucelabs_password)
    with contextlib.nested(
        monkey_patch_attr(
            GitbrowserSeleniumTests, "source_path", source_path), 
        monkey_patch_attr(
            GitbrowserSeleniumTests, "couchdb_url", couchdb_url),
        monkey_patch_attr(
            GitbrowserSeleniumTests, "saucelabs_url", saucelabs_url),
        monkey_patch_attr(
            GitbrowserSeleniumTests, "public_url", options.public_url)):
        yield

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
                      default="http://localhost:5984/gitbrowser-testing")
    parser.add_option("--couchdb-username", dest="couchdb_username",
                      default="guessme")
    parser.add_option("--couchdb-password", dest="couchdb_password",
                      default="guessme")
    parser.add_option("--saucelabs-url", dest="saucelabs_url",
                      default="http://ondemand.saucelabs.com:80/wd/hub")
    parser.add_option("--saucelabs-username", dest="saucelabs_username",
                      default="guessme")
    parser.add_option("--saucelabs-password", dest="saucelabs_password",
                      default="guessme")
    parser.add_option("--public-url", dest="public_url",
                      default="http://gitbrowser-testing.declarative.co.uk/")
    parser.add_option("--no-clean-home", default=True, const=False,
                      action="store_const", dest="do_clean_home")
    options, args = parser.parse_args(argv)
    unittest_argv = [prog] + args
    with setup_globals(options):
        unittest.main(argv=unittest_argv)

if __name__ == "__main__":
    sys.exit(main(sys.argv[0], sys.argv[1:]))

