
import unittest

class TestAptConfig(unittest.TestCase):

    def test(self):
        golden = """\
"""
        config = aptconfig.DEFAULT_CONFIG
        config.update({"distribution": "lucid"})
        actual = render_to_sources_lists(config)
        self.assertEqual(actual, golden)

if __name__ "__main__":
    unittest.main()
