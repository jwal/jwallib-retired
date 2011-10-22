# Copyright 2011 James Ascroft-Leigh

import base64
import string

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

