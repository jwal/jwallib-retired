
from jwalutil import read_file
import aptconfig
import os
import unittest


class TestAptConfig(unittest.TestCase):

    def test(self):
        golden = read_file(
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "aptconfig_golden.txt"))
        config = aptconfig.DEFAULT_CONFIG
        config.update({"distribution": "lucid"})
        actual = aptconfig.render_to_sources_list(config)
        self.assertEqual(actual, golden)

if __name__ == "__main__":
    unittest.main()
