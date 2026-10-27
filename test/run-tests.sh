#!/usr/bin/env bash
# PicoBlaze module tests:
#   1. both .slaspec files compile
#   2. p-code emulator cases (test/emu/cases3.txt, cases6.txt: hand-computed results from the user guides)
#      on KCPSM3 and KCPSM6, and copies with one deliberately wrong expectation, which must be the
#      only failure
#   3. every-entry decode test (CoverageCheck.java, two seeds, both languages)
#   4. decode differential: all 262144 18-bit words through Ghidra and the Open PicoBlaze Assembler
#      (round trip both ways, test/roundtrip.py)
#   5. semantic differential: random programs run in the Open PicoBlaze Simulator and in the p-code
#      emulator (test/fuzz_gen.py + PbEmuTest.java)
#   6. with --real <workdir>: test/real-binaries.sh (opbasm's own test programs, import checks)
#
#   test/run-tests.sh [--real <workdir>] [outdir]
#
# Environment: GHIDRA_INSTALL_DIR (Ghidra 12.1.x/12.2 whose Ghidra/Processors/PicoBlaze is, or links to,
# this module directory), JAVA_HOME (JDK 21+; 25 for 12.2). Steps 4-6 need the Open PicoBlaze Assembler
# (OPBASM_SRC=<checkout>; --real fetches it), steps 5 and 6 its simulator (OPBSIM=<opbsim>, built with nim
# and libpcre.so.1 on LD_LIBRARY_PATH; NIM=<nim> lets --real build it). Steps whose tool is missing
# are skipped. TMPDIR must not contain a path component starting with a dot.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
source "$HERE/env.sh"
REAL=
if [[ ${1:-} == --real ]]; then
	REAL=$(readlink -m "$2")
	shift 2
fi
OUT=$(readlink -m "${1:-${TMPDIR:-/tmp}/picoblaze-tests}")
mkdir -p "$OUT"
rc=0
if [[ -n $REAL ]]; then
	eval "$("$HERE/fetch-opbasm.sh" "$REAL")"
	export OPBASM_SRC
	[[ -z ${OPBSIM:-} ]] || export OPBSIM
fi

echo "== 1. compile"
for s in "$MOD"/data/languages/*.slaspec; do
	"$GHIDRA_INSTALL_DIR/support/sleigh" "$s" >"$OUT/sleigh.log" 2>&1 || { tail -20 "$OUT/sleigh.log"; rc=1; }
	grep -E "ERROR" "$OUT/sleigh.log" && rc=1
done
ls -l "$MOD"/data/languages/*.sla | awk '{print "   " $5, $9}'

echo "== 2. emulator"
"$HERE/emu-test.sh" "$OUT/emu" || rc=1
"$HERE/emu-test.sh" --broken "$OUT/emu" || rc=1
grep -h -E "emulation \(" "$OUT/emu/emu3.txt" "$OUT/emu/emu6.txt" | sed 's/^/   /'

echo "== 3. every-entry decode test"
head -c 64 /dev/zero >"$OUT/zero.bin"
for l in KCPSM3 KCPSM6; do
	for seed in 1 2; do
		PB_GHIDRA_SETTINGS="${TMPDIR:-/tmp}/picoblaze-settings-$l$seed" \
			"$HERE/ghidra-script.sh" raw $l:BE:24:default "$OUT/zero.bin" CoverageCheck.java "$OUT/cov_${l}_$seed.txt" 256 "$seed" &
	done
done
wait
for l in KCPSM3 KCPSM6; do
	tot=$(sed -n 's/^coverage: \([0-9]*\) constructors.*/\1/p' "$OUT/cov_${l}_1.txt")
	un=$( (cat "$OUT"/cov_${l}_*.txt | grep '^unreached' || true) | sort | uniq -c | awk '$1==2' | wc -l)
	echo "   $l: $((tot - un))/$tot constructors reached"
	(cat "$OUT"/cov_${l}_*.txt | grep '^unreached' || true) | sort | uniq -c | awk '$1==2 {print "   " $0}'
	((un == 0)) || rc=1
done

if [[ -n ${OPBASM_SRC:-} ]]; then
	echo "== 4. decode round trip against the Open PicoBlaze Assembler"
	for a in pb3 pb6; do python3 "$HERE/roundtrip.py" $a "$OUT/rt_$a" | sed 's/^/   /' || rc=1; done
else
	echo "== 4. skipped (set OPBASM_SRC or use --real)"
fi
if [[ -n ${OPBASM_SRC:-} && -n ${OPBSIM:-} ]]; then
	echo "== 5. random programs: Open PicoBlaze Simulator vs p-code emulator"
	for a in 3 6; do
		python3 "$HERE/fuzz_gen.py" pb$a ${FUZZ_COUNT:-300} $((100 + a)) "$OUT/fuzz$a" | sed 's/^/   /'
		"$HERE/real-emu.sh" "$OUT/fuzz$a/cases.txt" "$OUT/fuzz$a" KCPSM$a:BE:24:default | tail -n 3 | sed 's/^/   /' || rc=1
	done
else
	echo "== 5. skipped (needs OPBASM_SRC and OPBSIM)"
fi
if [[ -n $REAL ]]; then
	echo "== 6. real code"
	"$HERE/real-binaries.sh" "$REAL" || rc=1
fi
((rc == 0)) && echo "all tests passed" || echo "FAILURES"
exit $rc
