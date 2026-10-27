#!/usr/bin/env python3
"""Emulator cases for the PicoBlaze module. Each case is assembly (assembled once with opbasm, the
Open PicoBlaze Assembler; the machine code is kept in cases6.txt/cases3.txt, so the test needs no
tools), initial registers/memory, and results worked out by hand from the KCPSM3 and KCPSM6 user
guides (UG129 / UG129 for KCPSM6) and checked against nothing else.

  cases.py --assemble        regenerate cases6.txt and cases3.txt (needs opbasm: set OPBASM_SRC)
  cases.py --broken <arch>   print casesN.txt with one expectation made wrong
Programs start at rom:0 and run until the label __end__ (the part before a "---" line); code after
a "---" line is placed at address 0x40 (subroutines). Flags are the registers Z and C."""
import os, re, subprocess, sys, tempfile

# (name, variants, asm, set, expect) ; variants: '36' both, '6' KCPSM6 only, '3' KCPSM3 only.
# expect may be a dict, or a dict per variant {'3': {...}, '6': {...}} for differences.
CASES = [
 ('add_carry', '36', 'load s0, FF\n add s0, 01', {}, {'s0': 0, 'C': 1, 'Z': 1}),
 ('add_no_carry', '36', 'load s0, 10\n add s0, 20', {'C': 1, 'Z': 1}, {'s0': 0x30, 'C': 0, 'Z': 0}),
 ('add_reg', '36', 'load s1, 80\n load s2, 80\n add s1, s2', {}, {'s1': 0, 'C': 1, 'Z': 1}),
 ('addcy_adds_carry', '36', 'load s0, 05\n addcy s0, 02', {'C': 1}, {'s0': 8, 'C': 0, 'Z': 0}),
 ('addcy_carry_out', '36', 'load s0, FF\n addcy s0, 00', {'C': 1, 'Z': 1}, {'s0': 0, 'C': 1, 'Z': 1}),
 ('add16_zero_chain', '36', 'load s0, FF\n load s1, FF\n add s0, 01\n addcy s1, 00', {}, {'s0': 0, 's1': 0, 'C': 1, 'Z': 1}),
 ('add16_nonzero_low', '36', 'load s0, FE\n load s1, FF\n add s0, 01\n addcy s1, 01',
  {}, {'3': {'s0': 0xff, 's1': 0, 'C': 1, 'Z': 1}, '6': {'s0': 0xff, 's1': 0, 'C': 1, 'Z': 0}}),
 ('sub_borrow', '36', 'load s0, 03\n sub s0, 05', {}, {'s0': 0xfe, 'C': 1, 'Z': 0}),
 ('sub_equal', '36', 'load s0, 05\n sub s0, 05', {'C': 1}, {'s0': 0, 'C': 0, 'Z': 1}),
 ('sub_reg', '36', 'load s0, 10\n load s1, 01\n sub s0, s1', {}, {'s0': 0x0f, 'C': 0, 'Z': 0}),
 ('subcy_takes_borrow', '36', 'load s0, 05\n subcy s0, 02', {'C': 1}, {'s0': 2, 'C': 0, 'Z': 0}),
 ('subcy_borrow_out', '36', 'load s0, 00\n subcy s0, FF', {'C': 1, 'Z': 1}, {'s0': 0, 'C': 1, 'Z': 1}),
 ('sub16', '36', 'load s0, 00\n load s1, 01\n sub s0, 01\n subcy s1, 00',
  {}, {'3': {'s0': 0xff, 's1': 0, 'C': 0, 'Z': 1}, '6': {'s0': 0xff, 's1': 0, 'C': 0, 'Z': 0}}),
 ('compare_less', '36', 'load s0, 05\n compare s0, 07', {}, {'s0': 5, 'C': 1, 'Z': 0}),
 ('compare_equal', '36', 'load s0, 07\n compare s0, 07', {'C': 1}, {'s0': 7, 'C': 0, 'Z': 1}),
 ('compare_greater_reg', '36', 'load s0, 09\n load s1, 07\n compare s0, s1', {'C': 1}, {'C': 0, 'Z': 0}),
 ('comparecy_borrow', '6', 'load s0, 05\n load s1, 05\n compare s0, s1\n comparecy s0, 05', {'C': 1, 'Z': 0},
  {'C': 0, 'Z': 1}),
 ('comparecy_with_carry', '6', 'load s0, 05\n comparecy s0, 05', {'C': 1, 'Z': 1}, {'C': 1, 'Z': 0}),
 ('test_even_parity', '36', 'load s0, 81\n test s0, 81', {}, {'s0': 0x81, 'Z': 0, 'C': 0}),
 ('test_odd_parity', '36', 'load s0, 07\n test s0, FF', {}, {'s0': 7, 'Z': 0, 'C': 1}),
 ('test_zero', '36', 'load s0, F0\n test s0, 0F', {'C': 1}, {'Z': 1, 'C': 0}),
 ('testcy_parity_includes_carry', '6', 'load s0, 01\n testcy s0, 01', {'C': 1, 'Z': 1}, {'Z': 0, 'C': 0}),
 ('testcy_z_chain', '6', 'load s0, 01\n testcy s0, 00', {'C': 0, 'Z': 0}, {'Z': 0, 'C': 0}),
 ('and_clears_c', '36', 'load s0, F3\n and s0, 0F', {'C': 1}, {'s0': 3, 'C': 0, 'Z': 0}),
 ('or_zero', '36', 'load s0, 00\n or s0, 00', {'C': 1}, {'s0': 0, 'C': 0, 'Z': 1}),
 ('xor_reg', '36', 'load s0, AA\n load s1, FF\n xor s0, s1', {}, {'s0': 0x55, 'C': 0, 'Z': 0}),
 ('sl0', '36', 'load s0, 81\n sl0 s0', {}, {'s0': 2, 'C': 1, 'Z': 0}),
 ('sl0_zero', '36', 'load s0, 80\n sl0 s0', {}, {'s0': 0, 'C': 1, 'Z': 1}),
 ('sl1', '36', 'load s0, 81\n sl1 s0', {'Z': 1}, {'s0': 3, 'C': 1, 'Z': 0}),
 ('slx', '36', 'load s0, 81\n slx s0', {}, {'s0': 3, 'C': 1, 'Z': 0}),
 ('sla_carry_in', '36', 'load s0, 81\n sla s0', {'C': 1}, {'s0': 3, 'C': 1, 'Z': 0}),
 ('sla_no_carry_in', '36', 'load s0, 81\n sla s0', {'C': 0}, {'s0': 2, 'C': 1}),
 ('rl', '36', 'load s0, 81\n rl s0', {'C': 0}, {'s0': 3, 'C': 1, 'Z': 0}),
 ('sr0', '36', 'load s0, 81\n sr0 s0', {}, {'s0': 0x40, 'C': 1, 'Z': 0}),
 ('sr1', '36', 'load s0, 01\n sr1 s0', {'Z': 1}, {'s0': 0x80, 'C': 1, 'Z': 0}),
 ('srx', '36', 'load s0, 81\n srx s0', {}, {'s0': 0xc0, 'C': 1, 'Z': 0}),
 ('sra_carry_in', '36', 'load s0, 80\n sra s0', {'C': 1}, {'s0': 0xc0, 'C': 0}),
 ('sra_no_carry_in', '36', 'load s0, 81\n sra s0', {'C': 0}, {'s0': 0x40, 'C': 1}),
 ('rr', '36', 'load s0, 81\n rr s0', {'C': 0}, {'s0': 0xc0, 'C': 1, 'Z': 0}),
 ('sr0_zero', '36', 'load s0, 01\n sr0 s0', {}, {'s0': 0, 'C': 1, 'Z': 1}),
 ('store_fetch_const', '36', 'load s0, 5A\n store s0, 05\n fetch s1, 05', {}, {'scratchpad:5': 0x5a, 's1': 0x5a}),
 ('store_fetch_indirect', '36', 'load s0, 77\n load s1, 12\n store s0, s1\n fetch s2, s1', {}, {'scratchpad:12': 0x77, 's2': 0x77}),
 ('store_address_masked_kcpsm3', '3', 'load s0, 99\n store s0, 3F', {}, {'scratchpad:3f': 0x99}),
 ('output_input_const', '36', 'load s0, C3\n output s0, 20\n input s1, 21', {'port_in:21': 0x42}, {'port_out:20': 0xc3, 's1': 0x42}),
 ('output_input_reg', '36', 'load s0, 11\n load s1, 30\n output s0, s1\n input s2, s1', {'port_in:30': 0x22}, {'port_out:30': 0x11, 's2': 0x22}),
 ('outputk', '6', 'outputk 5A, 3', {}, {'port_out:3': 0x5a}),
 ('jump_taken_z', '36', 'load s0, 00\n compare s0, 00\n jump z, L1\n load s1, 11\nL1: load s2, 22', {}, {'s1': 0, 's2': 0x22}),
 ('jump_not_taken_z', '36', 'load s0, 01\n compare s0, 00\n jump z, L1\n load s1, 11\nL1: load s2, 22', {}, {'s1': 0x11, 's2': 0x22}),
 ('jump_nc', '36', 'load s0, 01\n compare s0, 00\n jump nc, L1\n load s1, 11\nL1: load s2, 22', {}, {'s1': 0, 's2': 0x22}),
 ('jump_c_not_taken', '36', 'load s0, 01\n compare s0, 00\n jump c, L1\n load s1, 11\nL1: load s2, 22', {}, {'s1': 0x11}),
 ('jump_backward_loop', '36', 'load s0, 05\n load s1, 00\nL1: add s1, 02\n sub s0, 01\n jump nz, L1', {}, {'s0': 0, 's1': 10}),
 ('call_return', '36', 'load s0, 01\n call sub\n add s0, 10\n---\naddress 40\nsub: add s0, 02\n return', {}, {'s0': 0x13, 'SP': 0}),
 ('call_pushes_next_address', '36', 'load s0, 01\n call sub\n load s1, 01\n---\naddress 40\nsub: load s5, 07\n return', {},
  {'SP': 0, 'stack_buffer:0/2': 2, 's1': 1}),
 ('call_z_taken', '36', 'load s0, 00\n compare s0, 00\n call z, sub\n---\naddress 40\nsub: load s5, 77\n return', {}, {'s5': 0x77, 'SP': 0}),
 ('call_z_not_taken', '36', 'load s0, 01\n compare s0, 00\n call z, sub\n---\naddress 40\nsub: load s5, 77\n return', {}, {'s5': 0, 'SP': 0}),
 ('return_c_taken', '36', 'call sub\n load s6, 66\n---\naddress 40\nsub: load s0, 00\n compare s0, 01\n return c\n load s5, 55\n return',
  {}, {'s5': 0, 's6': 0x66, 'SP': 0}),
 ('return_nc_not_taken', '36', 'call sub\n load s6, 66\n---\naddress 40\nsub: load s0, 00\n compare s0, 01\n return nc\n load s5, 55\n return',
  {}, {'s5': 0x55, 's6': 0x66, 'SP': 0}),
 ('nested_calls', '36', 'call a1\n---\naddress 40\na1: call b1\n add s0, 01\n return\nb1: add s0, 10\n return', {'s0': 0}, {'s0': 0x11, 'SP': 0}),
 ('returni_restores_flags_enable', '36', 'call isr\n---\naddress 40\nisr: returni enable', {'Z_SAVED': 1, 'C_SAVED': 0, 'Z': 0, 'C': 1},
  {'Z': 1, 'C': 0, 'INT_ENABLE': 1, 'SP': 0}),
 ('returni_disable', '36', 'call isr\n---\naddress 40\nisr: returni disable', {'INT_ENABLE': 1, 'Z_SAVED': 0, 'C_SAVED': 1}, {'INT_ENABLE': 0, 'C': 1, 'SP': 0}),
 ('enable_interrupt', '36', 'enable interrupt', {}, {'INT_ENABLE': 1}),
 ('disable_interrupt', '36', 'disable interrupt', {'INT_ENABLE': 1}, {'INT_ENABLE': 0}),
 ('load_and_return', '6', 'call sub\n load s6, 66\n---\naddress 40\nsub: load&return s5, 42', {}, {'s5': 0x42, 's6': 0x66, 'SP': 0}),
 ('jump_indirect', '6', 'load s0, 00\n load s1, 44\n jump@ (s0, s1)\n load s2, 11\n---\naddress 44\nload s3, 33\n jump __end__', {}, {'s2': 0, 's3': 0x33}),
 ('jump_indirect_uses_low_nibble', '6', 'load s0, F0\n load s1, 44\n jump@ (s0, s1)\n load s2, 11\n---\naddress 44\nload s3, 33\n jump __end__', {}, {'s2': 0, 's3': 0x33}),
 ('call_indirect', '6', 'load s0, 00\n load s1, 50\n call@ (s0, s1)\n load s6, 66\n---\naddress 50\nload s5, 55\n return', {}, {'s5': 0x55, 's6': 0x66, 'SP': 0}),
 ('regbank_switch', '6', 'load s0, 11\n regbank b\n load s0, 22\n regbank a', {}, {'s0': 0x11, 's0_b': 0x22}),
 ('star_writes_other_bank', '6', 'load s1, 5A\n star s2, s1', {}, {'s2': 0, 's2_b': 0x5a}),
 ('star_from_bank_b', '6', 'regbank b\n load s1, 6B\n star s2, s1\n regbank a', {}, {'s1_b': 0x6b, 's2': 0x6b, 's2_b': 0}),
 ('flags_survive_load', '36', 'load s0, 05\n sub s0, 06\n load s1, 77', {}, {'C': 1, 'Z': 0}),
]

def assemble(asm, arch):
    text = asm.replace('---', '__end__:') if '---' in asm else asm + '\n__end__:'
    # normalise: 'address' lines and labels as given
    lines = []
    for l in text.split('\n'):
        lines.append(l.rstrip())
    with tempfile.TemporaryDirectory() as d:
        open(d + '/c.psm', 'w').write('\n'.join(lines) + '\n')
        env = dict(os.environ, PYTHONPATH=os.environ['OPBASM_SRC'])
        r = subprocess.run([sys.executable, '-m', 'opbasm', '-3' if arch == '3' else '-6', '-x', '-i', d + '/c.psm',
                            '-n', 'c', '-o', d], capture_output=True, text=True, env=env)
        if r.returncode:
            raise SystemExit('opbasm failed for %r:\n%s' % (asm, r.stdout + r.stderr))
        words = [l.strip() for l in open(d + '/c.hex') if l.strip()]
        log = open(d + '/c.log').read()
        m = re.search(r'^\s*\*?\s+__end__\s+([0-9A-F]+)\s+\S*c\.psm', log, re.M)
        end = int(m.group(1), 16)
    last = max((i for i, w in enumerate(words) if int(w, 16)), default=0)
    return words[:last + 1], end

def render(arch, broken=False):
    out = ['# generated by test/emu/cases.py; do not edit']
    first = True
    for name, var, asm, st, ex in CASES:
        if arch not in var or 'PLACEHOLDER' in asm:
            continue
        if isinstance(ex, dict) and set(ex) <= {'3', '6'} and ex:
            ex = ex[arch]
        words, end = assemble(asm, arch)
        out.append('case ' + name)
        out.append('#   ' + asm.replace('\n', ' ; '))
        out.append('code ' + ' '.join(words))
        out.append('end %x' % end)
        out.append('steps 2000')
        for k, v in st.items():
            out.append('set %s 0x%x' % (k, v))
        for k, v in ex.items():
            if broken and first:
                v ^= 1
                first = False
            out.append('expect %s 0x%x' % (k, v))
        out.append('end')
    return '\n'.join(out) + '\n'

if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    if '--assemble' in sys.argv:
        for a in '36':
            open(here + '/cases%s.txt' % a, 'w').write(render(a))
    elif '--broken' in sys.argv:
        a = sys.argv[sys.argv.index('--broken') + 1]
        txt = open(here + '/cases%s.txt' % a).read().split('\n')
        for i, l in enumerate(txt):
            if l.startswith('expect '):
                p = l.split()
                txt[i] = 'expect %s %s' % (p[1], hex(int(p[2], 0) ^ 1))
                break
        sys.stdout.write('\n'.join(txt))
