#!/usr/bin/env python3
"""Round trip of every 18-bit word through Ghidra and the Open PicoBlaze Assembler (opbasm, MIT):
  roundtrip.py <pb3|pb6> <outdir>
Ghidra decodes all 262144 words (four chunks of 65536, the size of the rom space); every word it
accepts is turned back into assembly source and assembled by opbasm, which must produce the same
word. A word that Ghidra accepts and opbasm rejects, or assembles to another word, is a difference.
Needs GHIDRA_INSTALL_DIR, OPBASM_SRC (an opbasm checkout) and the test scripts' environment."""
import os, re, struct, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
from pb_text import to_opbasm
arch, outd = sys.argv[1:3]
lang = {'pb3': 'KCPSM3:BE:24:default', 'pb6': 'KCPSM6:BE:24:default'}[arch]
os.makedirs(outd, exist_ok=True)
env = dict(os.environ, PYTHONPATH=os.environ['OPBASM_SRC'])
# 1. Ghidra's decoding of the four chunks
procs = []
for k in range(4):
    b = f'{outd}/chunk{k}.bin'
    open(b, 'wb').write(b''.join(struct.pack('>I', w)[1:] for w in range(k << 16, (k + 1) << 16)))
    e = dict(os.environ, PB_GHIDRA_SETTINGS=f'{outd}/settings{k}')
    procs.append(subprocess.Popen([here + '/ghidra-slots.sh', lang, b, '3', f'{outd}/gh{k}.txt'], env=e))
for p in procs:
    assert p.wait() == 0
valid = {}
for k in range(4):
    for l in open(f'{outd}/gh{k}.txt'):
        off, n, text = l.rstrip('\n').split(' ', 2)
        if text != 'BAD':
            valid[(k << 16) + int(off, 16) // 3] = text
print(f'{arch}: Ghidra accepts {len(valid)} of 262144 words')
# 2. assemble the source of the accepted words in chunks; one instruction per line
maxinst = 1024 if arch == 'pb3' else 4096
words = sorted(valid)
skipped = 0
if arch == 'pb3':
    # the assembler limits the scratchpad address of FETCH/STORE to 00-3F (64 bytes); the hardware ignores
    # the upper bits and Ghidra decodes (and masks) them
    import re as _re
    keep = []
    for w in words:
        m = _re.match(r'(FETCH|STORE) s.,0x([0-9a-f]+)$', valid[w])
        if m and int(m.group(2), 16) >= 0x40:
            skipped += 1
        else:
            keep.append(w)
    words = keep
    print(f'{arch}: {skipped} FETCH/STORE words with an address above 3F are not assembler input (explained)')
bad = []
same = 0
i = 0
while i < len(words):
    chunk = words[i:i + maxinst]
    i += maxinst
    src = f'{outd}/rt.psm'
    open(src, 'w').write('\n'.join(to_opbasm(valid[w]) for w in chunk) + '\n')
    r = subprocess.run([sys.executable, '-m', 'opbasm', '-3' if arch == 'pb3' else '-6', '-x', '-i', src, '-n', 'rt',
                        '-o', outd], capture_output=True, text=True, env=env)
    if r.returncode:
        # find the offending lines: assemble them one by one
        for w in chunk:
            open(src, 'w').write(to_opbasm(valid[w]) + '\n')
            r1 = subprocess.run([sys.executable, '-m', 'opbasm', '-3' if arch == 'pb3' else '-6', '-x', '-i', src,
                                 '-n', 'rt', '-o', outd], capture_output=True, text=True, env=env)
            if r1.returncode:
                bad.append((w, valid[w], 'rejected: ' + (r1.stdout + r1.stderr).strip().splitlines()[-1][:80]))
            else:
                got = int(open(outd + '/rt.hex').readline(), 16)
                if got == w: same += 1
                else: bad.append((w, valid[w], 'assembled to %05x' % got))
        continue
    hx = [int(l, 16) for l in open(outd + '/rt.hex') if l.strip()][:len(chunk)]
    for w, got in zip(chunk, hx):
        if got == w: same += 1
        else: bad.append((w, valid[w], 'assembled to %05x' % got))
print(f'{arch}: {same} words round-trip exactly, {len(bad)} differ')
from collections import Counter
cls = Counter((t.split(' ')[0], why.split(':')[0] if why.startswith('rej') else 'other word') for _, t, why in bad)
for (m, why), n in cls.most_common(30):
    ex = next((w, t, y) for w, t, y in bad if t.split(' ')[0] == m)
    print(f'   {n:6d} {m:12s} {why:10s} e.g. {ex[0]:05x} {ex[1]} -> {ex[2]}')

# (opbasm also assembles STAR sX,kk as opcode 0x17; it is not in the KCPSM6 documentation and
# opbsim stops with "Invalid opcode" on it, so it is not decoded and not enumerated here.)
# 3. the other direction: everything the assembler produces must be decoded by Ghidra into the
# same instruction. The source lines enumerate the assembler's instruction set (all register and
# constant operands, all addresses, all conditions); the expected text is built with them.
from pb_text import canon
items = []
pb6 = arch == 'pb6'
two = ['add', 'addcy', 'and', 'compare', 'fetch', 'input', 'load', 'or', 'output', 'store', 'sub', 'subcy', 'test', 'xor']
if pb6:
    two += ['comparecy', 'testcy']
scr = 256 if pb6 else 64
for m in two:
    for x in range(16):
        for y in range(16):
            items.append((f'{m} s{x:X}, s{y:X}', f'{m} s{x:X},s{y:X}'))
        for k in range(scr if m in ('fetch', 'store') else 256):
            items.append((f'{m} s{x:X}, {k:02X}', f'{m} s{x:X},{k}'))
for m in ['sl0', 'sl1', 'slx', 'sla', 'rl', 'sr0', 'sr1', 'srx', 'sra', 'rr'] + (['hwbuild'] if pb6 else []):
    for x in range(16):
        items.append((f'{m} s{x:X}', f'{m} s{x:X}'))
naddr = 4096 if pb6 else 1024
for m in ('jump', 'call'):
    for a in range(naddr):
        items.append((f'{m} {a:03X}', f'{m} {a}'))
        for c in ('z', 'nz', 'c', 'nc'):
            items.append((f'{m} {c}, {a:03X}', f'{m} {c},{a}'))
for c in ('', 'z', 'nz', 'c', 'nc'):
    items.append((f'return {c}'.strip(), f'return {c}'.strip()))
for m in ('returni', 'enable', 'disable'):
    for a in (('enable', 'disable') if m == 'returni' else ('interrupt',)):
        items.append((f'{m} {a}', f'{m} {a}'))
if pb6:
    for m in ('regbank',):
        for a in 'ab':
            items.append((f'regbank {a}', f'regbank {a}'))
    for x in range(16):
        for y in range(16):
            items.append((f'star s{x:X}, s{y:X}', f'star s{x:X},s{y:X}'))
            items.append((f'jump@ (s{x:X}, s{y:X})', f'jump@ (s{x:X},s{y:X})'))
            items.append((f'call@ (s{x:X}, s{y:X})', f'call@ (s{x:X},s{y:X})'))
        for k in range(256):
            items.append((f'load&return s{x:X}, {k:02X}', f'load&return s{x:X},{k}'))
    for k in range(256):
        for p in range(16):
            items.append((f'outputk {k:02X}, {p:X}', f'outputk {k},{p}'))
ghtext = {w: canon(t) for w, t in valid.items()}
miss = []
ok2 = 0
for i in range(0, len(items), maxinst):
    chunk = items[i:i + maxinst]
    src = f'{outd}/rev.psm'
    open(src, 'w').write('\n'.join(a for a, _ in chunk) + '\n')
    r = subprocess.run([sys.executable, '-m', 'opbasm', '-3' if arch == 'pb3' else '-6', '-x', '-i', src, '-n', 'rev',
                        '-o', outd], capture_output=True, text=True, env=env)
    if r.returncode:
        print('assembler failed on the enumerated chunk:', (r.stdout + r.stderr).strip().splitlines()[-3:])
        sys.exit(1)
    hx = [int(l, 16) for l in open(outd + '/rev.hex') if l.strip()][:len(chunk)]
    for (a, want), w in zip(chunk, hx):
        got = ghtext.get(w)
        if got == canon(want):
            ok2 += 1
        else:
            miss.append((a, w, got))
print(f'{arch}: {ok2} of {len(items)} assembler instructions decode to the same instruction in Ghidra, {len(miss)} differ')
for a, w, got in miss[:10]:
    print(f'   {a!r} = {w:05x}: Ghidra {got!r}')
sys.exit(1 if (bad or miss) else 0)
