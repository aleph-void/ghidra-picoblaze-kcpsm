#!/usr/bin/env python3
"""Compare Ghidra slot disassembly (DumpSlots.java) with a reference (slotdis = GNU libopcodes,
or MAME unidasm converted to the same "<offset> <len> <text>" form).

  compare.py <ghidra.txt> <reference.txt> [--explain explain.py] [--show N]

exact    = same length and identical text (case and blanks ignored)
semantic = same length and the same instruction after numbers are compared as 32-bit values
           (objdump prints some absolute addresses sign-extended to 64 bits, and immediates in
           decimal or hex depending on the form)
Every other slot is a difference. Differences are grouped into classes keyed by the opcode
prefix and both mnemonics; an optional explain module maps a class to an explanation (a
confirmed reference-tool bug, an encoding the reference rejects, ...). Exit status 1 when an
unexplained difference remains."""
import importlib.util, re, sys
from collections import defaultdict

def load(path):
    res = {}
    for line in open(path, errors='replace'):
        p = line.rstrip('\n').split(' ', 2)
        if len(p) < 2:
            continue
        off, n = int(p[0], 16), int(p[1])
        text = p[2].strip() if len(p) > 2 else ''
        res[off] = (n, text)
    return res

INVALID = re.compile(r'^(\(bad\)|unknown\b|bad$|\?|\.byte|db\s|invalid)|\.word|[ ,]\?(,|$)', re.I)

def is_invalid(n, text):
    return n == 0 or bool(INVALID.search(text.strip()))

NUM = re.compile(r'(?<![\w])(-?)(0x[0-9a-f]+|\d+)(?![\w])')

MASK = 0xffffffff

def norm(text, values):
    t = re.sub(r'\s+', ' ', text.lower().strip())
    t = re.sub(r'\s*,\s*', ',', t)
    t = re.sub(r'\s*([()\[\]+])\s*', r'\1', t)
    if not values:
        return t
    def num(m):
        g = m.group(2)
        v = int(g, 16) if g.startswith('0x') else int(g, 10)
        if m.group(1):
            v = -v
        return '#%x' % (v & MASK)
    return NUM.sub(num, t)

def main():
    args = sys.argv[1:]
    explain = None
    show = 3
    if '--explain' in args:
        i = args.index('--explain')
        spec = importlib.util.spec_from_file_location('explain', args[i + 1])
        explain = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(explain)
        del args[i:i + 2]
    if '--bits' in args:
        global MASK
        i = args.index('--bits')
        MASK = (1 << int(args[i + 1])) - 1
        del args[i:i + 2]
    if '--show' in args:
        i = args.index('--show')
        show = int(args[i + 1])
        del args[i:i + 2]
    gh, ref = load(args[0]), load(args[1])
    data = open(args[2], 'rb').read() if len(args) > 2 else None
    exact = sem = both_bad = 0
    classes = defaultdict(list)
    explained = defaultdict(int)
    for off in sorted(ref):
        rn, rt = ref[off]
        gn, gt = gh.get(off, (0, 'MISSING'))
        rbad, gbad = is_invalid(rn, rt), is_invalid(gn, gt)
        if rbad and gbad:
            both_bad += 1
            continue
        if not rbad and not gbad and rn == gn:
            if norm(rt, False) == norm(gt, False):
                exact += 1
                continue
            if norm(rt, True) == norm(gt, True):
                sem += 1
                continue
        rm = 'INVALID' if rbad else rt.split(' ')[0].lower()
        gm = 'INVALID' if gbad else gt.split(' ')[0].lower()
        why = explain.classify(off, rn, rt, gn, gt, data) if explain else None
        if why:
            explained[why] += 1
            continue
        key = (rm, gm)
        classes[key].append((off, rn, rt, gn, gt))
    total = len(ref)
    diff = sum(len(v) for v in classes.values())
    print(f'slots {total}  exact {exact}  semantic {sem}  both-invalid {both_bad}  '
          f'explained {sum(explained.values())}  unexplained {diff}')
    agree = exact + sem + both_bad
    print(f'agreement {100.0 * agree / total:.3f}% (exact+semantic+both-invalid)')
    for why, n in sorted(explained.items(), key=lambda x: -x[1]):
        print(f'  explained {n:7d}  {why}')
    for key, items in sorted(classes.items(), key=lambda x: -len(x[1])):
        print(f'  DIFF {len(items):6d}  ref={key[0]}  ghidra={key[1]}')
        for off, rn, rt, gn, gt in items[:show]:
            hb = data[off:off + 8].hex() if data else ''
            print(f'      {off:08x} {hb}  ref[{rn}] {rt}  |  ghidra[{gn}] {gt}')
    sys.exit(1 if diff else 0)

if __name__ == '__main__':
    main()
