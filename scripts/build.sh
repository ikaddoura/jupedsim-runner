#!/usr/bin/env bash
# Builds dist/jps-runner (one folder) for the current platform and smoke-tests it.
# Needs Python 3.11+ as $PYTHON (default: python3).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

# Fresh every time: a package left over from an earlier build would end up in the notices.
"$PYTHON" -m venv --clear .build-venv
VPY=.build-venv/bin/python
[ -x "$VPY" ] || VPY=.build-venv/Scripts/python.exe
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q -r requirements.txt -r requirements-build.txt -c constraints.txt

"$VPY" -m PyInstaller -y --log-level WARN --distpath dist --workpath build packaging/jps-runner.spec

# Notices for everything inside the bundle: every license file of every bundled package
# (GEOS inside shapely, HDF5 inside h5py, the native libraries of numpy and pillow, ...).
"$VPY" -I scripts/collect_licenses.py dist/jps-runner
cp LICENSE dist/jps-runner/LICENSE.txt
cp NOTICE.md dist/jps-runner/NOTICE.md

EXE=dist/jps-runner/jps-runner
[ -x "$EXE" ] || EXE=dist/jps-runner/jps-runner.exe
"$EXE" version
"$EXE" simulate examples/room_with_obstacle.json --seed 1 --out build/smoke.sqlite
