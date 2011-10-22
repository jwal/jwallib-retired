
SYMBOLIC_TYPES = (
    ("directory", "d", "040"),
    ("regular file", "-", "100"),
    ("symbolic link", "l", "120"),
    ("unknown strange file", "m", "160"),
    )

MODE_CONSTANTS = (
    ("S_IFMT", int("0170000", 8)),
    ("S_IFSOCK", int("0140000", 8)),
    ("S_IFLINK", int("0120000", 8)),
    ("S_IFREG", int("0100000", 8)),
    ("S_IFBLK", int("0060000", 8)),
    ("S_IFDIR", int("0040000", 8)),
    ("S_IFCHR", int("0020000", 8)),
    ("S_IFIFO", int("0010000", 8)),
    ("S_ISUID", int("0004000", 8)),
    ("S_ISGID", int("0002000", 8)),
    ("S_ISVTX", int("0001000", 8)),
    ("S_IRWXU", int("00700", 8)),
    ("S_IRUSR", int("00400", 8)),
    ("S_IWUSR", int("00200", 8)),
    ("S_IXUSR", int("00100", 8)),
    ("S_IRWXG", int("00070", 8)),
    ("S_IRGRP", int("00040", 8)),
    ("S_IWGRP", int("00020", 8)),
    ("S_IXGRP", int("00010", 8)),
    ("S_IRWXO", int("00007", 8)),
    ("S_IROTH", int("00004", 8)),
    ("S_IWOTH", int("00002", 8)),
    ("S_IXOTH", int("00001", 8)),
    )

def octal_to_symbolic_mode(octal_string, check_reversible=True):
    # type_bits = int(octal_string, 8) & dict(MODE_CONSTANTS)["S_IFMT"]
    # for name, field in MODE_CONSTANTS:
    #     if name == "S_IFMT" or field & dict(MODE_CONSTANTS)["S_IFMT"] == 0:
    #         continue
    #     if field & type_bits > 0:
    #         print name, bin(field), bin(type_bits), bin(field & type_bits)
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
