# Ghidra-Rare notes: PicoBlaze

Verification of the PicoBlaze module (Ghidra pull request #7511: KCPSM3 and KCPSM6) to the Ghidra-Rare bar
([docs/VERIFICATION.md](https://github.com/aleph-void/Ghidra-Rare/blob/main/docs/VERIFICATION.md)).
Credits and the list of changes are in `CREDITS.md`; `README.md` has the memory model and the
limitation table.

- Language IDs: `KCPSM3:BE:24:default` and `KCPSM6:BE:24:default` (the PR's). They do not collide with
  Ghidra's languages or with another module here.
- Built and tested with Ghidra 12.1.3, 12.1.4 and 12.2 (`tools/build-module.sh --standard`).
- `KCPSM3.sla` and `KCPSM6.sla` are about 6 KB each.

## Running the tests

```
GHIDRA_INSTALL_DIR=<ghidra with this directory in Ghidra/Processors/PicoBlaze> test/run-tests.sh [--real <workdir>] [outdir]
```

Steps 1-3 (compile, emulator cases, every-entry test) need only Ghidra and Python. The decode
round trip needs the Open PicoBlaze Assembler (`OPBASM_SRC=<opbasm checkout>`), the random-program
differential and the real-code run also its simulator (`OPBSIM`). `--real <workdir>` fetches opbasm at
a pinned commit and builds the simulator when `NIM=<nim>` is set and `libpcre.so.1` is on
`LD_LIBRARY_PATH`; the simulator is built from a patched copy (see *Reference tool notes*).

## Results

| Area | Result |
|---|---|
| Decode | **Round trip against opbasm over all 262144 18-bit words** (`test/roundtrip.py`): Ghidra accepts 65193 (KCPSM3) and 119739 (KCPSM6) words; each is turned back into assembly and assembled by opbasm, which produces the same word (65193/65193 and 119739/119739; 6144 KCPSM3 `STORE`/`FETCH` words with an address above 3F are not assembler input, see below). In the other direction every instruction opbasm can produce (all register and constant operands, all 1K/4K addresses, all conditions: 65193 and 119739 assembler instructions) decodes to the same instruction in Ghidra. Every other word is undefined in the module. `reached/total` constructors: **59/59** (KCPSM3), **77/77** (KCPSM6). |
| Semantics | 58 (KCPSM3) + 69 (KCPSM6) emulator cases (`test/emu/cases3.txt`, `cases6.txt`; the machine code is assembled by opbasm, every expectation was worked out by hand from the user guides: flags of every ALU instruction including the KCPSM6 chained Z of ADDCY/SUBCY/TESTCY/COMPARECY and its absence in KCPSM3, all shifts and rotates with carry in, scratchpad direct/indirect, separate input and output ports, jumps and calls of every condition, conditional returns, nested calls and the stack contents, RETURNI restoring the saved flags, LOAD&RETURN, JUMP@/CALL@, register banks and STAR, OUTPUTK); a copy of each file with one wrong expectation reports exactly that case ("broken expectation detected"). **Random-program differential against the Open PicoBlaze Simulator**: 500 + 500 random programs (register-bank sections, calls and returns, forward jumps, scratchpad, ports) run in the simulator and in Ghidra's p-code emulator end with the same registers (both banks), scratchpad and flags (KCPSM3: 500/500, KCPSM6: 500/500). |
| Real code | opbasm's own test suite (`test/asm/*.psm4`: arithmetic, 16-bit arithmetic, bit fields, carry flag, conditionals, control structures, memory operations, shifts and rotates, stack and swap macros; MIT, pinned commit, fetched by `test/real-binaries.sh`), assembled for both cores; the programs check themselves and report an error count at port FF. In the simulator and in the p-code emulator they end with the same registers, scratchpad and error count (see the script's output; programs that need the simulator's counter, loopback or ROM peripherals or interrupts are skipped, since the model has no such hardware). Auto-analysis of every program: 0 bad-instruction bookmarks, 0 error bookmarks, 0 decompile failures; Ghidra's disassembly assembled again by opbasm gives the image word at every address. |
| Spec files | `KCPSM3.cspec`/`KCPSM6.cspec` (the PR's KCPSM6 used KCPSM3's), pspec with the program counter, entry and interrupt vector symbols (instruction addresses) and the port spaces as volatile; no ELF/DWARF/loader (there is no PicoBlaze binary format; see *Unverified*). |

### Doesn't work

- **Program counter wrap-around.** The PC of the hardware has 10 (KCPSM3) or 12 (KCPSM6) bits and wraps;
  a Ghidra address space is a whole number of bytes, so the PC does not wrap and instruction addresses
  above 0x3FF/0xFFF exist.
- **KCPSM6 stack overflow** (a hardware reset) is not checked; the KCPSM3 stack pointer wraps at 32
  entries (31 in hardware).
- **Interrupt entry.** The hardware saves Z, C and the register bank when it takes an interrupt; that
  is not an instruction. `RETURNI` restores Z and C from the registers `Z_SAVED`/`C_SAVED`; the
  bank in force after `RETURNI` is the context of the code that follows it.
- **Register banks across calls and interrupts.** The bank is a disassembly-time context set by
  `REGBANK`; a subroutine that is called from both banks, or an interrupt service routine entered in
  bank B, is decoded for the bank that reached it first (default A).
- **HWBUILD** loads the hardware build number of the implementation (a pcodeop; the value is not in the
  program).
- **Scratchpad size.** KCPSM6 implementations have 64, 128 or 256 bytes (address bits ignored by the
  hardware); the model has 256 and does not mask. KCPSM3 masks to 64.
- Register-form instructions whose unused low operand nibble is not zero, undefined shift codes and
  `STAR sX,kk` (opcode 0x17: opbasm assembles it, the simulator stops with "Invalid opcode") are not
  decoded.

### Unverified

- Real silicon and the Xilinx tools (KCPSM3/KCPSM6 assemblers, Xilinx `.mem` and `.hex` files) were
  not used; the module follows the user guides and agrees with opbasm/opbsim.
- Real firmware images from products (none under a free license was available): the opbasm test
  programs and the random programs are the real-code evidence.
- Interrupt behaviour on hardware, timing.

### Reference tool notes

- opbsim 1.3.10 lets `ADDCY`/`SUBCY` chain the zero flag in PicoBlaze-3 mode too (the data sheet and
  opbasm's own documentation say KCPSM3 does not: "On PicoBlaze-3 the Z flag disregards the previous
  state of Z"). 5 of 500 random KCPSM3 programs differed because of it; the differential uses the
  simulator built with `test/opbsim-pb3-z.patch`, which makes `--pb3` follow the documentation.
- opbasm limits the KCPSM3 `STORE`/`FETCH` address to 00-3F; the hardware ignores the upper two bits and
  the module masks them.
- opbasm assembles `STAR sX, kk` (opcode 0x17), which opbsim rejects as an invalid opcode and the
  KCPSM6 documentation does not list.
- opbsim's default scratchpad has 64 bytes in KCPSM6 mode; `-s:256` is used so that it matches the model.
