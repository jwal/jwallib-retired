
import awalletextractor
import os
import unittest


class AwalletExtractorTest(unittest.TestCase):

    def DISABLED__test(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        input_path = os.path.join(base_path, "awalletextractor_example.crypt")
        with open(input_path, "rb") as fh:
            crypt_data = fh.read()
        print awalletextractor.awallet_extract(crypt_data, "guessme")

if __name__ == "__main__":
    unittest.main()
