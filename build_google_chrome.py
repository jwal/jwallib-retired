# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]

I build Google Chrome (well, maybe the open source Chromium) based on
a custom webkit git repository.  The build takes place in a virtual
environment using Linux Container namespace isolation.
"""

from process import call
import basebox
import optparse
import sys
import os

def chrome_build():
    temp_dir = "/var/tmp/chrome-build"
    config = {"system_root": os.path.join(temp_dir, "bb-sys"),
              "home": os.path.expanduser("~"),
              "project_path": os.path.join(temp_dir, "proj"),
              "cwd": os.path.join(temp_dir, "cwd"),
              "ubuntu-codename": "precise",
              "vm_name": "chromebuild",
              }
    basebox.expand_config(config)
    basebox.prepare(config)

    def bbcall(argv, **kwargs):
        kwargs.setdefault("do_print", True)
        argv = basebox.get_ssh_argv(config) + list(argv)
        return call(argv, **kwargs)
    # bbcall(["bash"], stdout=None, stderr=None, stdin=None)
    bbcall(["bash", "-c", """\
set -x
set -e

git --version || (sudo apt-get update && sudo apt-get install --yes git)
ls git/depot_tools >/dev/null || ( git clone https://git.chromium.org/chromium/tools/depot_tools.git git/depot_tools && echo 'export PATH="$HOME/git/depot_tools:$PATH"' >> ~/.env )
ls ~/git/jwallib || git clone https://github.com/jwal/jwallib ~/git/jwallib
python ~/git/jwallib/aptconfig.py '{"components":["multiverse"]}' | sudo tee /etc/apt/sources.list.d/multiverse.list
sudo apt-get update
source "$HOME/.env"
ls ~/.gclient >/dev/null || gclient config https://git.chromium.org/chromium/src.git --git-deps
cat > "$HOME/.gclient" << 'EOF'
solutions = [
  { "name"        : "src",
    "url"         : "https://git.chromium.org/chromium/src.git",
    "deps_file"   : ".DEPS.git",
    "managed"     : True,
    "custom_deps" : {
      "src/third_party/WebKit/LayoutTests": None,
      "src/content/test/data/layout_tests/LayoutTests": None,   
      "src/chrome_frame/tools/test/reference_build/chrome": None,
      "src/chrome_frame/tools/test/reference_build/chrome_win": None,
      "src/chrome/tools/test/reference_build/chrome": None,
      "src/chrome/tools/test/reference_build/chrome_linux": None,
      "src/chrome/tools/test/reference_build/chrome_mac": None,
      "src/chrome/tools/test/reference_build/chrome_win": None,
    },
    "safesync_url": "",
  },
]
EOF
gclient sync --nohooks
./src/build/install-build-deps.sh
gclient sync
"""], stdout=None, stderr=None, stdin=None)

def main(argv):
    parser = optparse.OptionParser(__doc__)
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    chrome_build()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
