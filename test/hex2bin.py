#!/usr/bin/env python3
"""opbasm .hex (one 18-bit word per line, 5 hex digits) -> binary image, 3 big-endian bytes per word
(the form the PicoBlaze language loads: one address per instruction).   hex2bin.py <in.hex> <out.bin>"""
import sys
words = [int(l, 16) for l in open(sys.argv[1]) if l.strip()]
open(sys.argv[2], 'wb').write(b''.join(w.to_bytes(3, 'big') for w in words))
