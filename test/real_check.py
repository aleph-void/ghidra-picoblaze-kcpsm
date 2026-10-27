#!/usr/bin/env python3
"""Ghidra's disassembly of a real program image against the program: every instruction Ghidra
listed (PbRealCheck.java listing "<word address> <bytes> <text>") is assembled again by opbasm and
must produce the same 18-bit word as the image holds at that address; the image is read from the
opbasm hex file.
  real_check.py <pb3|pb6> <listing.txt> <image.hex>
Prints the number of instructions checked and the differences; exit status 1 when there are any."""
import os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
from pb_text import to_opbasm
arch, lst, hexf = sys.argv[1:4]
image = [int(l, 16) for l in open(hexf) if l.strip()]
rows = []
for l in open(lst):
    a, b, t = l.rstrip('\n').split(' ', 2)
    rows.append((int(a, 16), t))
env = dict(os.environ, PYTHONPATH=os.environ['OPBASM_SRC'])
bad = []
step = 1024 if arch == 'pb3' else 4096
for i in range(0, len(rows), step):
    chunk = rows[i:i + step]
    with tempfile.TemporaryDirectory() as d:
        open(d + '/r.psm', 'w').write('\n'.join(to_opbasm(t) for _, t in chunk) + '\n')
        r = subprocess.run([sys.executable, '-m', 'opbasm', '-3' if arch == 'pb3' else '-6', '-x', '-i', d + '/r.psm', '-n', 'r',
                            '-o', d], capture_output=True, text=True, env=env)
        if r.returncode:
            print('opbasm failed:', (r.stdout + r.stderr).strip().splitlines()[-1]); sys.exit(1)
        got = [int(l, 16) for l in open(d + '/r.hex') if l.strip()]
    for (a, t), w in zip(chunk, got):
        if a >= len(image) or image[a] != w:
            bad.append((a, t, w, image[a] if a < len(image) else None))
print(f'{len(rows)} instructions listed by Ghidra, {len(bad)} differ from the image')
for a, t, w, im in bad[:10]:
    print(f'   {a:03x} {t!r}: assembles to {w:05x}, image has {im if im is None else "%05x" % im}')
sys.exit(1 if bad else 0)
