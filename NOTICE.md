# jps-runner — notices

The runner's own code (`runner_main.py`, build scripts) is MIT-licensed, see `LICENSE.txt`.

This binary bundles third-party software under its own licenses. The full texts are in
`THIRD_PARTY_LICENSES.txt` and, one folder per package, in `licenses/`. Among them:

| Component | Version | License | Source of exactly this version |
|---|---|---|---|
| JuPedSim (`jupedsim`, incl. `libjupedsim`) | 1.4.2 | LGPL-3.0-or-later | https://github.com/PedestrianDynamics/jupedsim/tree/v1.4.2 |
| GEOS (`libgeos`, `libgeos_c`, inside `shapely`) | 3.14.1 | LGPL-2.1 | https://github.com/libgeos/geos/tree/3.14.1 |
| HDF5 (`libhdf5`, inside `h5py`) | 2.0.0 | BSD-style (The HDF Group) | https://github.com/HDFGroup/hdf5 |
| jupedsim-scenarios | 0.9.0 | MIT | https://github.com/PedestrianDynamics/jupedsim-scenarios |
| Python | 3.12 | PSF-2.0 | https://www.python.org |
| numpy, scipy, pandas, shapely, pedpy, h5py, matplotlib, Pillow, … | see file | BSD/MIT/PSF-style | see `THIRD_PARTY_LICENSES.txt` |

The executable itself is built with PyInstaller, whose bootloader license (GPL-2.0 with an exception)
allows distributing the resulting program under any license.

The versions above are those of release 0.1.1 (mac arm64 build); `THIRD_PARTY_LICENSES.txt` in each
download lists the exact versions of that build.

The source archives of the LGPL components in exactly these versions (`jupedsim-<version>.tar.gz`,
`geos-<version>.tar.bz2`, with `SOURCES.sha256`) are attached to every release next to the
binaries: https://github.com/ikaddoura/jupedsim-runner/releases

The LGPL libraries are shipped unmodified as separate files in `_internal/`. You may replace them
with your own builds of the same version; the runner loads whatever is in that folder. On macOS a
replaced library must be re-signed (`codesign --force --sign - <file>`) and the folder's quarantine
attribute removed for macOS to load it.

The Qt/PySide6 and VTK packages that `pip install jupedsim` installs for JuPedSim's visualizer are
**not** part of this binary.
