"""Entry point of the jps-runner binary: the jupedsim-scenarios CLI, plus `version` and `simulate`."""

import json
import os
import pathlib
import sys

# PyInstaller's matplotlib hook points MPLCONFIGDIR at a fresh temp dir on every start,
# which rebuilds the font cache (~10 s) per run; pedpy imports matplotlib at module level.
# A one-folder bundle has stable paths, so a persistent cache directory is safe.
_cache = pathlib.Path(os.environ.get("JPS_RUNNER_CACHE", pathlib.Path.home() / ".cache" / "jps-runner"))
(_cache / "matplotlib").mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(_cache / "matplotlib")
os.environ.setdefault("MPLBACKEND", "Agg")

RUNNER_VERSION = "0.1.1"


def _version() -> int:
    from importlib.metadata import version

    print(json.dumps({
        "runner": RUNNER_VERSION,
        "jupedsim": version("jupedsim"),
        "jupedsim_scenarios": version("jupedsim-scenarios"),
    }))
    return 0


def _simulate(argv: list[str]) -> int:
    """Like `run`, but keeps the trajectory when the run times out with persons left inside.

    `jps-scenarios run` deletes the SQLite on a timeout; that is exactly the run a user wants to
    look at (where did it jam?). Exit codes: 0 all evacuated, 3 timed out (trajectory written),
    2 the scenario could not be set up (bad input, too many persons for a start area, I/O error).
    """
    import argparse

    from jupedsim_scenarios import load_scenario, run_scenario

    parser = argparse.ArgumentParser(prog="jps-runner simulate")
    parser.add_argument("scenario")
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--dt", type=float, default=None)
    parser.add_argument("--every-nth-frame", type=int, default=10)
    args = parser.parse_args(argv)

    scenario_path = pathlib.Path(args.scenario).resolve()
    try:
        scenario = load_scenario(str(scenario_path))
        result = run_scenario(
            scenario,
            seed=args.seed,
            dt=args.dt,
            every_nth_frame=args.every_nth_frame,
            output_path=args.out,
        )
    except Exception as exc:  # noqa: BLE001
        # jupedsim-scenarios raises a bare Exception for a start area that cannot hold its persons
        # (and other setup failures). A traceback tells a user nothing; one line and exit 2 does.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "scenario": str(scenario_path),
        "seed": result.seed,
        "model_type": scenario.model_type,
        "status": result.metrics.get("status"),
        "message": result.metrics.get("message"),
        "evacuation_time": result.evacuation_time,
        "total_agents": result.total_agents,
        "agents_evacuated": result.agents_evacuated,
        "agents_remaining": result.agents_remaining,
        "frame_rate": result.metrics.get("frame_rate"),
        "sqlite_file": str(pathlib.Path(args.out).resolve()),
    }))
    return 0 if result.success else 3


if __name__ == "__main__":
    if sys.argv[1:2] == ["version"]:
        sys.exit(_version())
    if sys.argv[1:2] == ["simulate"]:
        sys.exit(_simulate(sys.argv[2:]))
    from jupedsim_scenarios.cli import main

    sys.exit(main())
