## Encoding to C-style identifiers
# 
# A C-style identifier is used in many programming contexts and
# protocols.  They are also compatible (as a subset) with many other
# contexts.  The characters allowed in a C-style identifier are
# restricted so that they can be embedded in a larger text document or
# snippet with a clear start and end point.
#
# If you are generating source code or protocol text but taking
# user-entered strings for parameters then it is sometimes necessary
# to use the user-entered strings to form identifiers.  To prevent
# namespace collisions it is necessary to ensure that the C-style
# identifer generation is reversible and deterministic.
#
# This library implements an example of this that attempts to maintain
# some readability in the generated identifiers.
#
# Example:
#
#      "Hello, world!" |-> _Hello_world___48656C6C6F2C20776F726C6421
# 
# The encoded identifier is formed of two parts separated by a double
# underscore.  The first character is always an underscore.  The first
# part is the human friendly part.  The second part is a base16
# encoding of the original string after encoding to utf-8.  It is this
# second part that ensures the identifiers do not collide and are
# reversible.
"""\
%prog [options] SOME_STRING
"""

import base64
import optparse
import string
import sys

def encode_as_c_identifier(any_string, check_reversible=True):
    any_string = any_string.encode("utf8")
    pretty_part = ["_"]
    for char in any_string:
        if char.lower() in string.lowercase + string.digits + "_":
            pretty_part.append(char)
        else:
            if pretty_part[-1] != "_":
                pretty_part.append("_")
    pretty_part = "".join(pretty_part)[:64] + "__"
    base16_part = base64.b16encode(any_string)
    result = pretty_part + base16_part
    if check_reversible:
        reversed = decode_from_c_identifier(result, check_reversible=False)
        assert reversed == any_string, (any_string, reversed, result)
    return result

def decode_from_c_identifier(encoded, check_reversible=True):
    a, b = encoded.rsplit("__", 1)
    result = base64.b16decode(b)
    if check_reversible:
        reversed = encode_as_c_identifier(result, check_reversible=False)
        assert reversed == encoded, (encoded, reversed, result)
    return result

def main(argv):
    parser = optparse.OptionParser(__doc__)
    parser.add_option("--reverse", dest="func", action="store_const",
                      default="encode_as_c_identifier", 
                      const="decode_from_c_identifier")
    parser.add_option("--encoding", dest="encoding", default="utf-8")
    options, args = parser.parse_args(argv)
    if len(args) == 0:
        parser.error("Missing: SOME_STRING")
    some_string = args.pop(0)
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    if options.func == "encode_as_c_identifier":
        print encode_as_c_identifier(some_string.decode(options.encoding))
    elif options.func == "decode_from_c_identifier":
        print decode_from_c_identifier(some_string).encode(options.encoding)
    else:
        raise NotImplementedError(options.func)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


# Copyright 2011 James Ascroft-Leigh

