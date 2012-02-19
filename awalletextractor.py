#!/usr/bin/env python
"""\
%prog [options] IN_FILE OUT_FILE
"""

try:
    from Crypto.Hash import SHA256, SHA
    from Crypto.Cipher import AES, Blowfish, DES3
except ImportError, e:
    raise ImportError("Try 'sudo apt-get install python-crypto': %s" % (e,))
import optparse
import os
import sys
import getpass

ALGORITHMS = (
    (AES, (
            256,
            # 192,
            # 128,
            )),
    # (Blowfish, (
    #         256,
    #         192,
    #         )),
    # (DES3, (
    #         112,
    #         168,
    #         )),
    )

CIPHER_MODES = (
    # "CBC",
    # "CFB",
    # "OFB",
    "ECB",
    )

SHA_REPEATS = tuple(
    list(range(15))
    + list(range(95, 105))
    + list(range(995, 1005))
    + list(range(9995, 10005))
    )

digesters = (
    "digest",
    "hexdigest",
    )

testers = (
    (0, None),
    (512, None),
    (0, 512 + 32),
    (512, 512 + 32),
    (512, 512 + (len("TRUE") * 8)),
    (0, 512 + (len("TRUE") * 8)),
    )

MAGIC_MARKER = "TRUE"

def awallet_extract(crypt_data, password):
    salt = crypt_data[:512 // 8]
    print "decrypting..."
    for seek, stop in testers:
        print "  seek=%r stop=%r" % (seek, stop)
        assert (seek // 8) * 8 == seek, seek
        if stop is None:
            ciphertext = crypt_data[seek:]
        else:
            assert (stop // 8) * 8 == stop, stop
            ciphertext = crypt_data[seek:stop]
        # assert salt + ciphertext == crypt_data
        for initial_key in [salt + password, password + salt]:
            print "    initial_key=%r" % (SHA.new(initial_key).hexdigest(),)
            for initial_digester in digesters:
                print "      initial_digester=%r" % (initial_digester,)
                for digester in digesters:
                    print "        digester=%r" % (digester,)
                    digest = getattr(SHA256.new(initial_key), initial_digester)()
                    for repeat_count in SHA_REPEATS:
                        print "          repeat_count=%r" % (repeat_count,)
                        for i in range(repeat_count):
                            digest = SHA256.new(digest).digest()
                        full_key = digest
                        for algorithm, keysizes in ALGORITHMS:
                            print "            algorithm=%r" % (algorithm.__name__,)
                            for keysize in keysizes:
                                print "              keysize=%r" % (keysize,)
                                assert len(full_key) * 8 >= keysize, \
                                    (len(full_key) * 8, keysize)
                                assert (keysize // 8) * 8 == keysize, keysize
                                key = full_key[:keysize // 8]
                                for cipher_mode in CIPHER_MODES:
                                    
                                    print "                cipher_mode=%r" % (cipher_mode,)
                                    mode_param = getattr(algorithm, "MODE_" + cipher_mode)
                                    cipher = algorithm.new(key, mode_param)
                                    plaintext = cipher.decrypt(crypt_data)
                                    # print repeat_count, algorithm, keysize, mode_param, repr(plaintext[:32]) + "..."
                                    # print ".",
                                    if MAGIC_MARKER in plaintext:
                                        print "@@@@@ got it?"
                                        return plaintext
    raise Exception("Failed to decrypt, was the password wrong?")

def main(argv):
    parser = optparse.OptionParser(__doc__)
    options, args = parser.parse_args(argv)
    if len(args) == 0:
        parser.error("Missing: IN_FILE")
    in_path = os.path.abspath(args.pop(0))
    if len(args) == 0:
        parser.error("Missing: OUT_FILE")
    out_path = os.path.abspath(args.pop(0))
    if len(args) > 0:
        parser.error("Unexpected: %r" % (args,))
    password = getpass.getpass()
    with open(in_path, "rb") as in_fh:
        data = awallet_extract(in_fh.read(), password)
    with open(out_path, "wb") as out_fh:
        out_fh.write(data)  

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
