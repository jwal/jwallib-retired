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

def chrome_build(argv=None):
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
        argv = basebox.get_ssh_argv(config, argv)
        return call(argv, **kwargs)

    the_script = """\
set -x
set -e

git --version || (sudo apt-get update && sudo apt-get install --yes git)
git config --global user.name "Example person"
git config --global user.email "fail@example.com"
git config --global core.autocrlf false
git config --global core.filemode false

ls git/depot_tools >/dev/null || ( git clone https://git.chromium.org/chromium/tools/depot_tools.git git/depot_tools && echo 'export PATH="$HOME/git/depot_tools:$PATH"' >> ~/.env && echo 'export GYP_GENERATORS="ninja"' >> "$HOME/.env" )
ls ~/git/jwallib || git clone https://github.com/jwal/jwallib ~/git/jwallib
python ~/git/jwallib/aptconfig.py '{"components":["multiverse"]}' | sudo tee /etc/apt/sources.list.d/multiverse.list
sudo apt-get update
sudo apt-get install --yes git-svn
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
# sudo env DEBIANFRONTEND=Noninteractive bash -c '( source /usr/share/debconf/confmodule && db_set msttcorefonts/accepted-mscorefonts-eula true )'
sudo apt-get install --yes ttf-mscorefonts-installer # Get the question out of the way early
echo N | sudo ./src/build/install-build-deps.sh
gclient sync

cd src
pwd  # Make sure you are in the src directory!
git svn init --prefix=origin/ -T trunk/src https://src.chromium.org/chrome
git config svn-remote.svn.rewriteUUID 0039d316-1c4b-4281-b951-d872f2087c98
git config svn-remote.svn.rewriteRoot svn://svn.chromium.org/chrome
git config svn-remote.svn.fetch trunk/src:refs/remotes/origin/git-svn
git svn fetch
# workaround for git-svn rewriteUUID bug
ln .git/svn/refs/remotes/origin/git-svn/.rev_map.4ff67af0-8c30-449e-8e8b-ad334ec8d88c .git/svn/refs/remotes/origin/git-svn/.rev_map.0039d316-1c4b-4281-b951-d872f2087c98

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
    "safesync_url": "http://chromium-status.appspot.com/lkgr",
  },
]
EOF
gclient sync

cd "$HOME/src"
rm -rf out/Debug out/Release
./build/gyp_chromium
ninja -C out/Release chrome

#rm -rf ~/Desktop/chrome/ && mkdir -p ~/Desktop/chrome/ && cp -r chrome chrome.pak locales resources obj/chrome/browser/themes *.pak ~/Desktop/chrome
"""
    bbcall(["bash", "-c", 'cat > "$HOME/thescript.sh"'],
           do_print=True, stdin_data=the_script)
    argv = argv or ["bash", "thescript.sh"]
    bbcall(argv, stdout=None, stderr=None, stdin=None)

def main(argv):
    parser = optparse.OptionParser(__doc__)
    parser.add_option("--shell", dest="mode",
                      action="store_const", const="shell", default="build")
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    if options.mode == "build":
        chrome_build()
    elif options.mode == "shell":
        chrome_build(argv=["bash"])
    else:
        raise NotImplementedError(options.mode)
        

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
