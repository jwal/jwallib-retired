import jwalutil
import unittest

class TestISO8601(unittest.TestCase):

    def runTest(self):
        cases = [
#            ("1970-01-01T00:00:00.0Z",),
            ("1970-01-01T00:00:00.0+0515",),
            ]
        for case in cases:
            print jwalutil.parse_iso8601_to_utc_seconds(case[0])
            
if __name__ == "__main__":
    unittest.main()

# Copyright 2011 James Ascroft-Leigh

