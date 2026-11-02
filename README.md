# jupedsim-runner

A standalone command-line build of [JuPedSim](https://www.jupedsim.org) pedestrian simulations:
one folder per platform, no Python installation needed. It wraps the `jps-scenarios` CLI of
[jupedsim-scenarios](https://github.com/PedestrianDynamics/jupedsim-scenarios) with PyInstaller.

> This is an independent packaging of JuPedSim. It is **not affiliated with or endorsed by** the
> JuPedSim project or Forschungszentrum Jülich. For JuPedSim itself — documentation, citation,
> support — see [jupedsim.org](https://www.jupedsim.org).

Applications use it at arm's length: they write a scenario JSON, start `jps-runner` as a separate
process, and read the trajectory SQLite it writes.

## Download

Releases carry one archive per platform: `macos-arm64` and `macos-x86_64` (signed, notarized
`.dmg`), `windows-x86_64` (`.zip`), `linux-x86_64` (`.tar.gz`). Unpack it anywhere and keep the
folder together — `jps-runner` loads its libraries from `_internal/` next to it.

## Usage

```bash
jps-runner version
jps-runner simulate scenario.json --out trajectory.sqlite [--seed 42] [--dt 0.01] [--every-nth-frame 10]
```

`version` prints one JSON line with the runner, `jupedsim` and `jupedsim-scenarios` versions.

`simulate` prints one JSON line on stdout (logs go to stderr) with `status` (`completed` /
`timeout`), `message`, `evacuation_time`, `total_agents`, `agents_evacuated`, `agents_remaining`,
`frame_rate` and `sqlite_file`. Exit code 0: everyone left; 3: the maximum simulation time was
reached with persons still inside — the trajectory is **kept**, so the jam can be inspected; 2: the
scenario could not be set up (bad input, more persons than a start area holds, I/O error) — one
`error: …` line on stderr, no traceback. (`jps-scenarios run` deletes the trajectory on a timeout; that is why `simulate`
exists.) All subcommands of `jps-scenarios` (`run`, `sweep`, `report`) work as well.

The input is the scenario JSON of jupedsim-scenarios (the format the
[JuPedSim web editor](https://github.com/PedestrianDynamics/jupedsim-web-community) exports), with
the geometry embedded as `walkable_area_wkt`; see `examples/room_with_obstacle.json`. The output is
JuPedSim's trajectory SQLite (`trajectory_data`, `metadata`, `geometry`, `frame_data`).

**Element ids must carry the type prefix** the loader dispatches on: `jps-distributions_<n>`,
`jps-exits_<n>`, `jps-checkpoints_<n>`, `jps-waypoints_<n>`, `jps-waiting_polygons_<n>`. A start
area with any other id loads fine, but nobody moves and the run ends in a timeout.

The first run after unpacking takes up to a minute (matplotlib builds its font cache once, in
`~/.cache/jps-runner`, overridable with `JPS_RUNNER_CACHE`); later runs start in about a second.

## Versions

| runner | jupedsim | jupedsim-scenarios |
|---|---|---|
| 0.1.1 | 1.4.2 | 0.9.0 |
| 0.1.0 | 1.4.2 | 0.9.0 |

`requirements.txt` pins the two, `constraints.txt` pins everything underneath. Bump them together
and tag a new release; the scenario format is still alpha upstream.

## Building

```bash
PYTHON=python3.12 scripts/build.sh
```

Builds `dist/jps-runner/`, writes `THIRD_PARTY_LICENSES.txt` and a `licenses/` folder into it
(every license file of every bundled package, via `scripts/collect_licenses.py`), and smoke-tests it
on the example. CI (`.github/workflows/build.yml`) does the same on all four platforms; a `v*` tag creates a
draft release with the Windows and Linux archives.

### macOS release (maintainer, local)

CI builds are only ad-hoc signed; macOS kills them when they arrive with a quarantine attribute (a
browser download), also when another program starts them. Per release, on a Mac of each architecture
(or from the CI artifact of that architecture, unpacked into `dist/jps-runner`):

```bash
DEVELOPER_ID="Developer ID Application: <Name> (<TEAMID>)" NOTARY_PROFILE=<profile> \
  scripts/sign-and-notarize-macos.sh 0.1.0 arm64
```

Then attach `dist/jps-runner-0.1.0-macos-arm64.dmg` to the draft release and publish it.

## License

The runner's own code is MIT, see [LICENSE](LICENSE). The binaries bundle third-party software
under its own licenses, among them JuPedSim (LGPL-3.0-or-later) and GEOS (LGPL-2.1), shipped as
unmodified, replaceable files — see [NOTICE.md](NOTICE.md). "JuPedSim" is the name of the
Forschungszentrum Jülich project; it is used here only to say what this program runs.
