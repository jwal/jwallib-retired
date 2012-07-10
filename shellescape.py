import pipes

def shell_escape_arg(arg):
    return pipes.quote(arg)

def shell_escape(argv   ):
    if type(argv) is unicode:
        argv = argv.encode("utf-8")
    if type(argv) is str:
        argv = [argv]
    return " ".join(shell_escape_arg(a) for a in argv)

