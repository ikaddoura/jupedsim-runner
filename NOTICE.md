# jps-runner — notices

The runner's own code (`runner_main.py`, build scripts) is MIT-licensed, see `LICENSE.txt`.

This binary bundles third-party software under its own licenses; the full texts are in
`THIRD_PARTY_LICENSES.txt`. Among them:

| Component | License | Source |
|---|---|---|
| JuPedSim (`jupedsim`, incl. `libjupedsim`) | LGPL-3.0-or-later | https://github.com/PedestrianDynamics/jupedsim |
| jupedsim-scenarios | MIT | https://github.com/PedestrianDynamics/jupedsim-scenarios |
| GEOS (inside `shapely`) | LGPL-2.1 | https://github.com/libgeos/geos |
| Python | PSF-2.0 | https://www.python.org |
| numpy, scipy, pandas, shapely, pedpy, h5py, matplotlib, Pillow, … | BSD/MIT/PSF-style | see `THIRD_PARTY_LICENSES.txt` |

The LGPL libraries are shipped unmodified as separate files in `_internal/`. You may replace them
with your own builds of the same version; the runner loads whatever is in that folder. On macOS a
replaced library must be re-signed (`codesign --force --sign - <file>`) and the folder's quarantine
attribute removed for macOS to load it.

The Qt/PySide6 and VTK packages that `pip install jupedsim` installs for JuPedSim's visualizer are
**not** part of this binary.
