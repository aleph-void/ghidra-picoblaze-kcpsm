# Credits

## Upstream

- Source: Ghidra pull request [#7511](https://github.com/NationalSecurityAgency/ghidra/pull/7511),
  "Add Xilinx PicoBlaze KCPSM3 and KCPSM6 processors", head commit
  `6c87402c22115cab7b5b243682d83994e252d817` (opened 2025-02-15, not merged). The same author
  publishes the module as [CUB3D/ghidra-picoblaze](https://github.com/CUB3D/ghidra-picoblaze)
  (Apache-2.0; its single commit `b44cab4`, "KCPSM6 fixes", is older in design: it still uses an
  `odd_parity` pcodeop that the PR replaced by `popcount` on LukeSerne's review).
- Author: CUB3D (GitHub `@CUB3D`, commit author "CUB3D"). Review comments: LukeSerne.
- License: Apache-2.0 (a Ghidra contribution; the text is in `LICENSE`).

## Other sources used

- Xilinx UG129 (PicoBlaze 8-bit embedded microcontroller user guide, KCPSM3) and the KCPSM6 user
  guide (in the form the PR cites: archived copy of the Auburn University course notes of kcpsm6.pdf):
  instruction set and flag behaviour.
- Open PicoBlaze Assembler and Simulator (opbasm/opbsim 1.3.10, Kevin Thibedeau, MIT,
  github.com/kevinpt/opbasm, pinned commit `83ee54a`): run as black-box oracles; the instruction
  encodings of its documentation and its test programs (`test/asm`) are used as test input.

## What Ghidra-Rare changed

All changes are commits on top of the PR's files, branch `ghidra-rare`:

1. Stand-alone extension build: `build.gradle`, `extension.properties`, `LICENSE`, `.gitignore`; the
   Ghidra-tree `build.gradle` and the generator files (`buildLanguage.xml`, `sleighArgs.txt`) removed.
2. Specification files rewritten after testing against the assembler and the simulator:
   - `rom` addressed in instructions (`wordsize=3`), `PC` register, `stack_buffer` of 12-bit entries,
     separate `port_in`/`port_out` spaces, `INT_ENABLE`, `Z`/`C` flags as registers;
   - KCPSM3: opcodes of the register forms of ADDCY/SUBCY/SUB/COMPARE/TEST/XOR/..., ADD/ADDCY/SUB/
     SUBCY/COMPARE/TEST flags, SR/SL group, conditional RETURN/JUMP/CALL fields, STORE/FETCH mask;
   - KCPSM6: all opcodes checked against the assembler (`STAR` 0x16, conditional `RETURN`, `OUTPUTK`),
     SUB/SUBCY/COMPARE(CY) carry is the unsigned borrow (the PR used `sborrow`), `TESTCY`, register
     banks via context, `LOAD&RETURN`, `JUMP@`/`CALL@`;
   - `KCPSM6.cspec`, pspec entry/interrupt symbols as instruction addresses, volatile port spaces.
3. `README.md`, `GHIDRA-RARE.md`, this file, `test/`.
