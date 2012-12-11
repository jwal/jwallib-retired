# Copyright 2012 James Ascroft-Leigh

"""\
%prog [options]

A bit like Vagrant.
"""

from jwalutil import on_error_raise
from jwalutil import read_file
from process import call as call_no_print
from process import shell_escape
import aptconfig
import copy
import hashlib
import json
import lxml.etree
import optparse
import os
import shutil
import sys
import tempfile
import time

call = lambda *a, **kw: call_no_print(
    *a, **dict(kw.items() + [("do_print", True)]))

def force_rm(path):
    path = os.path.abspath(path)
    call_no_print(["sudo", "python", "-c", """
from __future__ import with_statement
assert __name__ == "__main__"
import sys
import os
import subprocess
import time
path, = sys.argv[1:]
while True:
    commands = []
    for proc in os.listdir("/proc"):
        if not proc.isdigit():
            continue
        try:
            root = os.readlink(os.path.join("/proc", proc, "root"))
        except Exception, e:
            print ":::", e
            continue
        if root == path or root.startswith(path + "/"):
            commands.append(["kill", "-KILL", proc])
            continue
        for fd in os.listdir(os.path.join("/proc", proc, "fd")):
            try:
                fdpath = os.readlink(os.path.join("/proc", proc, "fd", fd))
                if not fdpath.startswith("/"):
                    continue
                fdpath = os.path.join(root, fdpath[1:])
                if path == fdpath or fdpath.startswith(path + "/"):
                    commands.append(["kill", "-KILL", proc])
                    break
            except Exception, e:
                print ":::", e
    to_unmount = []
    with open("/proc/mounts", "rb") as fh:
        for mount in fh:
            src, dst, rst = mount.split(" ", 2)
            if dst == path or dst.startswith(path + "/"):
                to_unmount.append(dst)
    to_unmount.sort(reverse=True)
    for mpath in to_unmount:
        commands.append(["umount", mpath])
    if len(commands) == 0:
        break
    commands.append(["rm", "-rf", "--one-file-system", path])
    all_good = True
    for command in commands:
        try:
            subprocess.check_call(command)
        except Exception, e:
            print ":::", e
            all_good = False
    if not all_good:
        time.sleep(0.1)
""", path])
    call(["sudo", "rm", "-rf", "--one-file-system", path])


def get_vm_state(vm_name, on_no_state=on_error_raise):
    assert " " not in vm_name, vm_name
    out = call_no_print(["virsh", "--connect", "lxc://", "list", "--all"])
    out = out.split("\r\n")
    assert out[0].split() == ["Id", "Name", "State"], out
    assert out[1] == "-" * 52, out
    out = out[2:]
    for line in out:
        if line == "":
            continue
        parts = line.split()
        id, name, state = parts[0], parts[1], " ".join(parts[2:])
        if name != vm_name:
            continue
        return state
    return on_no_state("No state found for vm: %s" % (vm_name,))

def get_ssh_argv(config):
    return ["ssh", "-i", config["ssh_key_path"],
            "-oHostKeyAlias=basebox", 
            "-oHashKnownHosts=no",
            "-t",
            "-q",
            "-oUserKnownHostsFile=" + config["host_key_path"] + ".known",
            "sysadmin@192.168.122.200"]

def prepare(config):

    def flush_cache():
        if config["do_write_project_cache"]:
            call_no_print(
                ["mkdir", "-p", os.path.dirname(config["project_cache_path"])])
            with open(config["project_cache_path"], "wb") as fh:
                fh.write(json.dumps(config["project_cache"]))

    flush_cache()
    root_path = os.path.join(config["project_dir"], "root")
    flush_cache()
    if not os.path.exists(root_path):
        force_rm(root_path)
        mnt_path = config["mnt_path"]
        force_rm(mnt_path)
        call(["mkdir", "-p", root_path])
        call(["mkdir", "-p", mnt_path])
        call(["sudo", "mount", "--bind", root_path, mnt_path])
        call(["sudo", "debootstrap", config["ubuntu-codename"], mnt_path], 
             stdout=None, stderr=None, stdin=None)
        for relpath in ["proc", "dev", "dev/pts", "sys"]:
            src = os.path.join("/", relpath)
            dst = os.path.join(mnt_path, relpath)
            call(["sudo", "mkdir", "-p", dst])
            call(["sudo", "mount", "--bind", src, dst])
        resolvconf = os.path.join(mnt_path, "run/resolvconf/resolv.conf")
        force_rm(resolvconf)
        call(["sudo", "cp", "/etc/resolv.conf", resolvconf])
        call(["sudo", "bash", "-c", 'echo "$1" > "$2"', "-", 
              aptconfig.BLANK_SOURCES, 
              os.path.join(mnt_path, "etc/apt/sources.list")])
        base_sources_config = copy.deepcopy(aptconfig.DEFAULT_CONFIG)
        base_sources_config["distribution"] = config["ubuntu-codename"]
        base_sources = aptconfig.render_to_sources_list(base_sources_config)
        call(["sudo", "bash", "-c", 'echo "$1" > "$2"', "-", 
              base_sources, 
              os.path.join(mnt_path, "etc/apt/sources.list.d/base.list")])
        call(["sudo", "chroot", mnt_path, "apt-get", "update"], stdout=None)
        call(["sudo", "chroot", mnt_path, "apt-get", "remove", "--yes",
              "cloud-init"], stdout=None)
        call(["sudo", "chroot", mnt_path, "apt-get", "install", "--yes",
              "language-pack-en"], stdout=None)
        call(["sudo", "chroot", mnt_path, "apt-get", "install", "--yes",
              "openssh-server"], stdout=None)
        call(["sudo", "chroot", mnt_path, "adduser", "--gecos", "", 
              "--disabled-password", "--uid", "1000", "sysadmin"], stdout=None)
        call(["sudo", "mv", os.path.join(mnt_path, "home", "sysadmin"), 
              os.path.join(config["project_dir"], "home")])
        call(["sudo", "chroot", mnt_path, "adduser", "sysadmin", 
              "adm"], stdout=None)
        call(["sudo", "chroot", mnt_path, "adduser", "sysadmin", 
              "sudo"], stdout=None)
        call(["sudo", "chroot", mnt_path, "bash", "-c", 
              "rm -rf /etc/ssh/ssh_host_*"])
        call(["sudo", "chroot", mnt_path, "dpkg-reconfigure", 
              "openssh-server"], stdout=None)
        call(["cp", os.path.join(mnt_path, "etc", "ssh", 
                                 "ssh_host_ecdsa_key.pub"), 
              config["host_key_path"]])
        call(["bash", "-c", 'echo basebox $(cat "$1") > "$2"', "-",
              config["host_key_path"], config["host_key_path"] + ".known"])
        force_rm(config["ssh_key_path"])
        call(["ssh-keygen", "-P", "", "-f", config["ssh_key_path"]])
        for home_path in [os.path.join(mnt_path, "root"),
                          os.path.join(config["project_dir"], "home")]:
            
            ak_path = os.path.join(home_path, ".ssh", "authorized_keys")
            call(["sudo", "mkdir", "-p", os.path.dirname(ak_path)])
            force_rm(ak_path)
            call(["sudo", "cp", config["ssh_key_path"] + ".pub", ak_path])
            if os.path.basename(home_path) != "root":
                call(["sudo", "chown", "-R", "1000:1000", 
                      os.path.dirname(ak_path)])
        call(["sudo", "bash", "-c", 'echo "$1" > "$2"', "-",
              """\
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
  address 192.168.122.200
  netmask 255.255.255.0
  network 192.168.122.0
  gateway 192.168.122.1
  dns-nameservers 192.168.122.1
""", os.path.join(mnt_path, "etc", "network", "interfaces")])
        nopasswd_path = os.path.join(
            mnt_path, "etc", "sudoers.d", "sudo-nopasswd")
        call(["sudo", "bash", "-c", 'echo "$1" > "$2"', "-",
              """\
%sudo ALL=(ALL:ALL) NOPASSWD: ALL
""", nopasswd_path])
        call(["sudo", "chmod", "0440", nopasswd_path])
        #### Run chef here?
        force_rm(mnt_path)
    ssh_argv = get_ssh_argv(config)
    if get_vm_state(config["vm_name"], on_no_state=lambda m: None) != "running":
        mnt_path = config["mnt_path"]
        force_rm(mnt_path)
        call(["mkdir", "-p", mnt_path])
        call(["sudo", "mount", "--bind", root_path, mnt_path])
        home_rw = os.path.join(config["project_dir"], "home")
        call(["mkdir", "-p", home_rw])
        home_mnt = os.path.join(mnt_path, "home", "sysadmin")
        force_rm(home_mnt)
        call(["sudo", "mkdir", "-p", home_mnt])
        call(["sudo", "mount", "--bind", home_rw, home_mnt])
        call(["virsh", "--connect", "lxc://", "destroy", config["vm_name"]],
             do_check=False)
        while True:
            if get_vm_state(config["vm_name"], 
                            on_no_state=lambda m: "shut off") == "shut off":
                break
            time.sleep(0.1)
        call(["virsh", "--connect", "lxc://", "undefine", config["vm_name"]],
             do_check=False)
        definition = """\
<domain type="lxc">
  <name>TEMPLATE: name</name>
  <memory>524288</memory>
  <os>
    <type arch="x86_64">exe</type>
    <init>/sbin/init</init>
  </os>
  <vcpu>2</vcpu>
  <clock offset="utc"/>
  <on_poweroff>destroy</on_poweroff>
  <on_reboot>restart</on_reboot>
  <on_crash>destroy</on_crash>
  <devices>
    <emulator>/usr/lib/libvirt/libvirt_lxc</emulator>
    <filesystem type="mount">
      <source dir="TEMPLATE: root_dir"/>
      <target dir="/"/>
    </filesystem>
    <interface type="bridge">
      <source bridge="virbr0"/>
    </interface>
    <console type="pty">
      <target port="0"/>
    </console>
  </devices>
</domain>
"""
        xml = lxml.etree.fromstring(definition)
        for match in xml.xpath(".//name"):
            match.text = config["vm_name"]
        for match in xml.xpath(".//filesystem//source"):
            match.attrib["dir"] = mnt_path
        xml_path = os.path.join(config["project_dir"], "libvirt.xml")
        call(["bash", "-c", 'echo "$1" > "$2"', "-",
              lxml.etree.tostring(xml), xml_path])
        call(["virsh", "--connect", "lxc://", "define", xml_path])
        call(["virsh", "--connect", "lxc://", "start", config["vm_name"]])
        print "~~~", " ".join(shell_escape(a) for a in ssh_argv)
    while True:
        rc = []
        call_no_print(ssh_argv + ["true"], do_check=False, handle_rc=rc.append)
        rc = rc[0]
        if rc == 0:
            break
        time.sleep(0.1)

def basebox(config, argv):
    prepare(config)
    ssh_argv = get_ssh_argv(config)
    exec_argv = ssh_argv + [" ".join(shell_escape(a) for a in argv)]
    os.execvp(exec_argv[0], exec_argv)

def expand_config(config):
    config.setdefault("system_root", os.path.join(config["home"], ".basebox"))
    config.setdefault(
        "objcache", os.path.join(config["system_root"], "objcache"))
    config.setdefault("tmp", os.path.join(config["system_root"], "tmp"))
    config.setdefault("base_image", {})
    config["base_image"].setdefault(
        "url", ("http://cloud-images.ubuntu.com/"
                "quantal/current/quantal-server-cloudimg-amd64-disk1.img"))
    config.setdefault(
        "project_key", hashlib.sha1(config["project_path"]).hexdigest())
    config.setdefault(
        "project_cache_path", os.path.join(
            config["system_root"], "projects", config["project_key"], 
            "cache.json"))
    if os.path.exists(config["project_cache_path"]):
        with open(config["project_cache_path"], "rb") as fh:
            config.setdefault("project_cache", json.loads(fh.read()))
    else:
        config.setdefault("project_cache", {})
    config.setdefault("do_write_project_cache", True)
    config.setdefault("project_dir", 
                      os.path.join(config["system_root"], "projects", 
                                   config["project_key"]))
    project_dir = config["project_dir"]
    config.setdefault("img_path", os.path.join(project_dir, "disk.img"))
    config.setdefault("mnt_path", os.path.join(project_dir, "mnt"))
    config.setdefault(
        "host_key_path", os.path.join(project_dir, "ssh_host_ecdsa_key.pub"))
    config.setdefault("ssh_key_path", os.path.join(project_dir, "ssh_key"))
    config.setdefault("nbd", "nbd0")
    config.setdefault("vm_name", "basebox" + config["project_key"])
    config.setdefault("ubuntu-codename", "quantal")

def find_config_path(on_not_found=on_error_raise):
    basename = "basebox.json"
    pwd = os.path.abspath(".")
    start_pwd = pwd
    while True:
        candidate = os.path.join(pwd, basename)
        if os.path.isfile(candidate):
            return candidate
        if os.path.dirname(pwd) == pwd:
            return on_not_found("Failed to find %r starting at %r"
                                % (basename, start_pwd))
        pwd = os.path.dirname(pwd)

def main(argv):
    parser = optparse.OptionParser(__doc__)
    parser.add_option("--tear-down", dest="tear_down_dir")
    parser.add_option("--show-config", dest="do_show_config",
                      action="store_const", const=True, default=False)
    parser.add_option("--show-ssh-cmd", dest="do_show_ssh_cmd",
                      action="store_const", const=True, default=False)
    parser.allow_interspersed_args = False
    options, args = parser.parse_args(argv)
    if len(args) == 0:
        args = ["bash"]
    if options.tear_down_dir is not None:
        force_rm(options.tear_down_dir)
        return
    config_path = find_config_path(on_not_found=parser.error)
    config = json.loads(read_file(config_path))
    config.setdefault("project_path", os.path.dirname(config_path))
    config.setdefault("cwd", os.path.abspath("."))
    config.setdefault("home", os.path.abspath(os.path.expanduser("~")))
    expand_config(config)
    if options.do_show_config:
        print json.dumps(config, indent=2, sort_keys=True)
        return
    if options.do_show_ssh_cmd:
        ssh_argv = get_ssh_argv(config)
        print "~~~", " ".join(shell_escape(a) for a in ssh_argv)
        return
    basebox(config, args)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
