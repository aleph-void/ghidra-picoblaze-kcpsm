#!/usr/bin/env bash
# P-code emulation test: test/emu-test.sh [--broken] [outdir]
# Runs every case of test/emu/cases3.txt (KCPSM3) and cases6.txt (KCPSM6): hand-computed
# expectations. With --broken it runs a copy of each with one deliberately wrong expectation and
# succeeds only if exactly that case fails.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/env.sh"
BROKEN=0
[[ ${1:-} == --broken ]] && { BROKEN=1; shift; }
OUTD=$(readlink -m "${1:-${TMPDIR:-/tmp}/picoblaze-emu}")
mkdir -p "$OUTD"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/pb-emu.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c 12288 /dev/zero > "$PROJ/zero.bin"
rc=0
for arch in 3 6; do
	LANG_ID=KCPSM$arch:BE:24:default
	CASES=$HERE/emu/cases$arch.txt
	if (( BROKEN )); then
		python3 "$HERE/emu/cases.py" --broken $arch >"$PROJ/broken$arch.txt"
		CASES=$PROJ/broken$arch.txt
	fi
	out=$OUTD/emu$arch.txt
	(( BROKEN )) && out=$OUTD/emu$arch-broken.txt
	mkdir -p "$PROJ/p$arch"
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ/p$arch" p -import "$PROJ/zero.bin" \
		-loader BinaryLoader -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
		-postScript PbEmuTest.java "$CASES" "$out" -deleteProject >"$PROJ/log$arch.txt" 2>&1 \
		|| { tail -40 "$PROJ/log$arch.txt" >&2; exit 1; }
	[[ -s $out ]] || { grep -E "ERROR|Exception" "$PROJ/log$arch.txt" | head -20 >&2; exit 1; }
	grep -v ^PASS "$out" || true
	if (( BROKEN )); then
		first=$(awk '/^case /{print $2; exit}' "$CASES")
		[[ $(grep -c ^FAIL "$out") == 1 ]] && grep -q "^FAIL $first:" "$out" \
			&& echo "KCPSM$arch: broken expectation detected ($first)" || rc=1
	else
		grep -q " 0 failed" "$out" || rc=1
	fi
done
exit $rc
