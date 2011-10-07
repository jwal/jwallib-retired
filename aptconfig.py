# Copyright 2011 James Ascroft-Leigh

"""\
%prog [options]
"""

import optparse
import sys

DEFAULT_CONFIG = {
        "mirror": "http://archive.ubuntu.com/",
        "distribution": "natty",
        "components": [
                "main",
                "universe",
                "restricted",
                "multiverse",
            ],
        "prefixes": [
                "deb",
                "deb-src",
            ],
        "extensions": [
                "",
                "-security",
                "-updates",
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
            for extension in extensions:
                assert " " not in extension, repr(extension)
                results.append("%(prefix)s %(mirror)s %(distribution)s %(component)s%(extension)s" % locals())
    return "".join("%s\r\n" % (l,) for l in results)

def main(argv):
    parser = optparse.OptionParser(__doc__)
    options, args = parser.parse_args(argv)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    print render_to_sources_list(DEFAULT_CONFIG)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
