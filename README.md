# PicoBlaze

Ghidra processor module for the Xilinx **PicoBlaze** 8-bit soft-core microcontroller, in its two
versions: KCPSM3 (Spartan-3/Virtex-II Pro, 10-bit program counter, 1K instructions) and KCPSM6
(Spartan-6/Virtex-6/7-series, 12-bit program counter, 4K instructions, register banks, more
instructions). Language IDs `KCPSM3:BE:24:default` and `KCPSM6:BE:24:default`.

Original work by CUB3D, proposed to Ghidra as
[pull request #7511](https://github.com/NationalSecurityAgency/ghidra/pull/7511) (Apache-2.0; the same
author also publishes it as CUB3D/ghidra-picoblaze). This fork keeps the PR's commit and adds the
Ghidra-Rare verification and fixes; `CREDITS.md` lists who did what and `GHIDRA-RARE.md` has the test
results, the known gaps and the notes on the reference tools.

## Install and use

Download the zip for your Ghidra version from the fork's Releases page (built for Ghidra 12.1.3,
12.1.4 and 12.2) and use *File > Install Extensions*.

Program memory is addressed in instructions: one address is one 18-bit instruction, stored as three
big-endian bytes, so the listing shows the addresses of the PicoBlaze assembler's listing and the
interrupt vector of a 1K KCPSM3 is `0x3FF`. A raw binary image is the program words in order, 3 bytes
each (`test/hex2bin.py` converts the `.hex` file that the Open PicoBlaze Assembler writes; the
Xilinx `.mem`/`.hex` text files need the same conversion). Import it with the *Raw Binary* loader
and the language `KCPSM3` or `KCPSM6`.

Memory model: `rom` (program, instruction addresses), `scratchpad` (STORE/FETCH), `port_in` and
`port_out` (INPUT reads and OUTPUT writes separate port spaces, as the two directions of a port id are
different signals), `stack_buffer` (the call stack). Registers `s0`-`sF`, KCPSM6 also the second bank
`s0_b`-`sF_b`; flags `Z`, `C`; `SP` is the call stack pointer.

## Differences from the PR

- Instruction addresses instead of byte offsets (the PR multiplied every address by 3, so `ISR` sat at
  `0xBDF`); `JUMP@`/`CALL@` and the return addresses are plain instruction addresses.
- KCPSM6 register banks work: `REGBANK A/B` sets a disassembly context that selects `s0`-`sF` or
  `s0_b`-`sF_b` for the instructions that follow, `STAR` writes the other bank.
- INPUT and OUTPUT are loads and stores of the `port_in`/`port_out` spaces instead of pcodeops;
  interrupt enable is a register (`INT_ENABLE`), `RETURNI` restores the flags the interrupt saved.
- Many instruction fixes (see `CREDITS.md`).

## Known limitations of the original, and what became of them

The PR's README is a single line. These come from the specification files' own comments, the PR
discussion and testing:

| Limitation | Status |
|---|---|
| "PC should be a 10-bit value with wraparound" (KCPSM3), "PC wraparound is not supported" (KCPSM6) | remaining: the program counter does not wrap at 10/12 bits (see GHIDRA-RARE.md) |
| Stack overflow is not checked (KCPSM6: a reset in hardware) | remaining; KCPSM3's stack wraps at 32 entries (31 in hardware) |
| `odd_parity` pcodeop for TEST/TESTCY (PR review) | already `popcount` in the PR |
| REGBANK, STAR were pcodeops: both banks aliased | fixed (context-selected register banks) |
| INPUT/OUTPUT/ENABLE/DISABLE/RETURNI were pcodeops | fixed (port spaces, `INT_ENABLE`, `Z_SAVED`/`C_SAVED`) |
| Wrong ADDCY, SUB, SUBCY, COMPARE encodings and flags (KCPSM3), signed borrow in KCPSM6, `STAR`, conditional `RETURN` of KCPSM6 | fixed |
| Addresses were byte offsets (x3), the interrupt vector `0xBDF`, no `PC` register for the emulator | fixed |
| KCPSM6 shares KCPSM3's compiler spec | fixed: separate `KCPSM6.cspec` |
| HWBUILD result, interrupt entry (saving flags and bank), scratchpad size selection | remaining (properties of the implementation / hardware) |
