#!/usr/bin/env bash
# Real PicoBlaze code: test/real-binaries.sh <workdir>
#  1. fetches the Open PicoBlaze Assembler (opbasm, MIT, github.com/kevinpt/opbasm at a pinned commit,
#     SHA-256 checked) and, if NIM names a nim compiler, builds its simulator opbsim (needs libpcre.so.1)
#  2. assembles opbasm's own test programs (test/asm/*.psm4: arithmetic, shifts, stack, conditionals,
#     ...) for KCPSM3 and KCPSM6, runs them in opbsim, and runs the same code in the p-code emulator:
#     registers, scratchpad and the error count the program reports must be identical
#  3. imports every program into Ghidra (auto-analysis), reports instructions/functions/bookmarks/
#     decompile failures, and assembles Ghidra's disassembly again with opbasm: the words must equal
#     the image.
# Environment: GHIDRA_INSTALL_DIR; OPBSIM (the simulator, default: opbsim on PATH or built into
# <workdir>/opbsim when NIM is set to a nim binary); m4 for the .psm4 sources.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/env.sh"
W=$(readlink -m "${1:?workdir}")
mkdir -p "$W"
rc=0
eval "$("$HERE/fetch-opbasm.sh" "$W")"
export OPBASM_SRC
[[ -z ${OPBSIM:-} ]] || export OPBSIM
command -v "${OPBSIM:-opbsim}" >/dev/null || { echo "opbsim not found: set OPBSIM (or NIM to build it)"; exit 1; }
for arch in pb3 pb6; do
	lang=KCPSM${arch#pb}:BE:24:default
	echo "== $arch: opbasm test programs, simulator vs p-code emulator"
	python3 "$HERE/real_gen.py" $arch "$OPBASM_SRC" "$W/$arch" | sed 's/^/   /'
	"$HERE/real-emu.sh" "$W/$arch/real-$arch.txt" "$W/$arch" $lang | tail -n 4 | sed 's/^/   /' || rc=1
	echo "== $arch: import and analysis"
	for hex in "$W/$arch"/*.hex; do
		n=$(basename "$hex" .hex)
		python3 "$HERE/hex2bin.py" "$hex" "$W/$arch/$n.bin"
		P=$(mktemp -d "${TMPDIR:-/tmp}/pb-real.XXXXXX")
		"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$P" p -import "$W/$arch/$n.bin" -loader BinaryLoader \
			-processor $lang -scriptPath "$HERE" \
			-postScript PbRealCheck.java "$W/$arch/$n.sum" "$W/$arch/$n.lst" "$W/$arch/$n.dec" 120 -deleteProject >"$P/log.txt" 2>&1 \
			|| { tail -30 "$P/log.txt"; rc=1; }
		rm -rf "$P"
		printf '   %-18s %s | %s | %s\n' "$n" "$(grep -E '^instructions:' "$W/$arch/$n.sum" | sed 's/  (.*//')" \
			"$(grep -E '^functions:' "$W/$arch/$n.sum" | sed 's/  (.*//')" "$(grep -E '^decompile:' "$W/$arch/$n.sum" | sed 's/ (of.*//')"
		grep -q "bad-instruction bookmarks: 0" "$W/$arch/$n.sum" || { echo "     bad-instruction bookmarks"; rc=1; }
		grep -q "error bookmarks: 0" "$W/$arch/$n.sum" || { echo "     error bookmarks"; rc=1; }
		grep -q " 0 failed, 0 timed out" "$W/$arch/$n.sum" || { echo "     decompile failures"; rc=1; }
		python3 "$HERE/real_check.py" $arch "$W/$arch/$n.lst" "$hex" | sed 's/^/     opbasm: /' || rc=1
	done
done
exit $rc
