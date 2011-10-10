
SYMBOLIC_TYPES = (
    ("directory", "d", "040"),
    ("regular file", "-", "100"),
    ("symbolic link", "l", "120"),
    )

def octal_to_symbolic_mode(octal_string, check_reversible=True):
    result = []
    result.append(
        dict((e[2], e[1]) for e in SYMBOLIC_TYPES)[octal_string[:-3]])
    parts = [int(x) for x in octal_string[-3:]]
    for part in parts:
        result.append("r" if (part & 0x4) > 0 else "-")
        result.append("w" if (part & 0x2) > 0 else "-")
        result.append("x" if (part & 0x1) > 0 else "-")
    result = "".join(result)
    if check_reversible:
        octal = symbolic_to_octal_mode(result, check_reversible=False)
        assert (octal == octal_string), (octal_string, octal, result)
    return result

def symbolic_to_octal_mode(symbolic_string, check_reversible=True):
    result = []
    result.append(
        dict((e[1], e[2]) for e in SYMBOLIC_TYPES)[symbolic_string[0]])
    for i in range(3):
        triple = symbolic_string[3*i + 1:3*i+4]
        code = 0
        if "r" in triple:
            code += 4
        if "w" in triple:
            code += 2
        if "x" in triple:
            code += 1
        result.append(str(code))
    result = "".join(result)
    if check_reversible:
        symbolic = octal_to_symbolic_mode(result, check_reversible=False)
        assert (symbolic == symbolic_string), (symbolic_string, symbolic, 
                                               result)
    return result
