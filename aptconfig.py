# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options] [JSON_CONFIG]
"""

import json
import optparse
import sys

DEFAULT_CONFIG = {
        "mirror": "http://archive.ubuntu.com/",
        "distribution": "natty",
        "components": [
                "main",
                "universe",
                "restricted",
                # "multiverse",
            ],
        "prefixes": [
                "deb",
                "deb-src",
            ],
        "extensions": [
                "",
                "-security",
                "-updates",
                # "-proposed",
                # "-backports",
            ],
    }

def render_to_sources_list(config):
    mirror = config["mirror"]
    assert " " not in mirror, repr(mirror)
    distribution = config["distribution"]
    assert " " not in distribution, repr(distribution)
    results = []
    for prefix in config["prefixes"]:
        assert " " not in prefix, repr(prefix)
        for component in config["components"]:
            assert " " not in component, repr(component)
            for extension in config["extensions"]:
                assert " " not in extension, repr(extension)
                results.append("%(prefix)s %(mirror)s %(distribution)s %(component)s%(extension)s" % locals())
    return "".join("%s\r\n" % (l,) for l in results)

def main(argv):
    parser = optparse.OptionParser(__doc__)
    options, args = parser.parse_args(argv)
    custom_json = json.dumps({})
    if len(args) > 0:
        custom_json = args.pop(0)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    default_json = json.dumps(DEFAUT_CONFIG)
    defaults = json.loads(default_json)
    custom = json.loads(custom_json)
    for key, value in defaults.items():
        custom.setdefault(key, value)
    print render_to_sources_list(custom)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
