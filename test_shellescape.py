
from itertools import combinations_with_replacement
from shellescape import shell_escape
import subprocess
import unittest


class ShellEscapeTest(unittest.TestCase):

    def test_tricky_strings(self):
        cases = [
            ("", "''"),
            ("Hello world", "'Hello world'"),
            ("this_is_a_test", "this_is_a_test"),
            ("Hi!", "'Hi!'"),
            ("bash -c 'rm -rf /'", '\'bash -c \'"\'"\'rm -rf /\'"\'"\'\''),
            ("~", "'~'"),
            ("$HOME", "'$HOME'"),
            ("xeyes &", "'xeyes &'"),
            ("\\", "'\\'"),
            ("\\\\", "'\\\\'"),
            ]
        for case, expected in cases:
            argv = ["bash", "-c", 'echo -n %s' % (shell_escape(case),)]
            child = subprocess.Popen(argv, stdout=subprocess.PIPE)
            stdout, stderr = child.communicate()
            assert child.returncode == 0, repr(argv)
            self.assertEqual(stdout, case)
            self.assertEqual(shell_escape(case), expected)

    def test_all_3_char_strings(self):
        # To reduce the search space we assume that all bytes > 128 are 
        # treated the same way as byte 128.  We also assume that all letters
        # and digits are treated the same way.
        bytes = range(1, 66) + range(90, 98) + range(122, 129)
        chars = "".join(chr(b) for b in bytes)
        assert "a" in chars
        assert "A" in chars
        assert chr(128) in chars
        for length in range(3):
            for case in combinations_with_replacement(chars, length):
                case = "".join(case)
                argv = ["bash", "-c", 'echo -n %s' % (shell_escape(case),)]
                child = subprocess.Popen(argv, stdout=subprocess.PIPE)
                stdout, stderr = child.communicate()
                assert child.returncode == 0, repr(argv)
                self.assertEqual(stdout, case)

if __name__ == "__main__":
    unittest.main()

