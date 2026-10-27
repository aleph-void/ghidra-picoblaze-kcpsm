#!/usr/bin/env python3
"""Find the first instruction after which Ghidra and opbsim disagree on a generated program:
  bisect.py <pb3|pb6> <program.psm> <outdir>
Cuts the program after every instruction (labels still referenced later are kept out of the
prefix), appends the flag capture and the final loop, and writes cases like fuzz_gen.py does."""
import json, os, re, subprocess, sys
arch, prog, outd = sys.argv[1:4]
pb6 = arch == 'pb6'
os.makedirs(outd, exist_ok=True)
env = dict(os.environ, PYTHONPATH=os.environ['OPBASM_SRC'])
lines = open(prog).read().split('\n')
cut = next(i for i, l in enumerate(lines) if l.startswith('load sE, 00'))
head = lines[:cut]
rest = lines[cut:]
subs = [l for l in rest if True]
endidx = next(i for i, l in enumerate(rest) if l.startswith('end:'))
tail = rest[endidx + 1:]                  # the subroutines
cap = rest[:endidx + 1]
cases = open(f'{outd}/cases.txt', 'w')
labels_defined = set()
for k in range(1, len(head) + 1):
    pre = head[:k]
    refs = set(re.findall(r'\bL\d+\b', '\n'.join(pre)))
    defs = set(re.findall(r'^(L\d+):', '\n'.join(pre), re.M))
    if refs - defs:
        continue
    src = '\n'.join(pre + cap + tail) + '\n'
    open(f'{outd}/b.psm', 'w').write(src)
    r = subprocess.run([sys.executable, '-m', 'opbasm', '-6' if pb6 else '-3', '-i', f'{outd}/b.psm', '-n', 'b', '-o', outd], capture_output=True, text=True, env=env)
    if r.returncode: continue
    subprocess.run([sys.executable, '-m', 'opbasm', '-6' if pb6 else '-3', '-x', '-i', f'{outd}/b.psm', '-n', 'b', '-o', outd], capture_output=True, text=True, env=env)
    words = [l.strip() for l in open(f'{outd}/b.hex') if l.strip()]
    sim = subprocess.run([os.environ['OPBSIM'], '--pb6' if pb6 else '--pb3', f'-m:{outd}/b.mem', '-L:20000', '-j',
                          '-i:' + json.dumps({'00': [int(x) for x in os.environ.get('PORTS', '0').split(',')] if False else [0]*256})],
                         capture_output=True, text=True)
    st = json.loads(sim.stdout[sim.stdout.index('{'):])
    endaddr = next(i for i, w in enumerate(words) if int(w, 16) == (0x22000 if pb6 else 0x34000) + i)
    last = max(i for i, w in enumerate(words) if int(w, 16))
    cases.write(f'case cut{k}_{pre[-1].strip().replace(" ", "_").replace(",", "")}\ncode {" ".join(words[:last + 1])}\nend {endaddr:x}\nsteps 20000\n')
    for i, v in enumerate(st['regs_a']):
        cases.write(f'expect s{i:X} {v}\n')
    cases.write('end\n')
cases.close()
