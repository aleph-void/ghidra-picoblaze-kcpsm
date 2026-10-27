#!/usr/bin/env bash
# Fetch the Open PicoBlaze Assembler (opbasm 1.3.10, MIT, github.com/kevinpt/opbasm) at a pinned commit
# and, when a nim compiler is given in $NIM (and libpcre.so.1 is on LD_LIBRARY_PATH), build its simulator:
#   test/fetch-opbasm.sh <workdir>     prints OPBASM_SRC=<dir>, and OPBSIM=<file> when built
set -euo pipefail
W=$(readlink -m "${1:?workdir}")
mkdir -p "$W"
COMMIT=83ee54a126baa6b4e30b211c347c6b419b283009
SHA=${OPBASM_SHA256:-7e5be990f5f2338ec80a11ddfdb907fcaae014936daf1bfd5946a65b6f2950f7}
if [[ ! -d $W/opbasm-$COMMIT ]]; then
	curl -sfL -o "$W/opbasm.tar.gz" "https://github.com/kevinpt/opbasm/archive/$COMMIT.tar.gz"
	echo "$SHA  $W/opbasm.tar.gz" | sha256sum -c --quiet - || { echo "checksum mismatch for opbasm" >&2; exit 1; }
	tar xzf "$W/opbasm.tar.gz" -C "$W"
fi
echo "OPBASM_SRC=$W/opbasm-$COMMIT"
if [[ -n ${NIM:-} && ! -x $W/opbsim ]]; then
	# opbsim 1.3.10 lets ADDCY/SUBCY chain Z on PicoBlaze-3 too; the data sheet and opbasm's own
	# documentation say KCPSM3 does not. test/opbsim-pb3-z.patch fixes that in a copy of the sources.
	HERE=$(cd "$(dirname "$0")" && pwd)
	rm -rf "$W/opbasm-$COMMIT/sim_fix"
	cp -r "$W/opbasm-$COMMIT/sim" "$W/opbasm-$COMMIT/sim_fix"
	patch -s "$W/opbasm-$COMMIT/sim_fix/opbsim.nim" < "$HERE/opbsim-pb3-z.patch"
	(cd "$W/opbasm-$COMMIT/sim_fix" && "$NIM" c -d:release --hints:off -o:"$W/opbsim" opbsim.nim >/dev/null 2>&1) || true
fi
[[ -x $W/opbsim ]] && echo "OPBSIM=$W/opbsim"
exit 0
