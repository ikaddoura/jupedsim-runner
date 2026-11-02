"""Entry point of the jps-runner binary: the jupedsim-scenarios CLI, plus `version`, `simulate` and `analyse`."""

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

RUNNER_VERSION = "0.2.0"


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


def _first_crossings(data, coordinates):
    """Frame at which each person first crosses the line segment, in either direction.

    pedpy's compute_n_t misses a person whose position falls exactly on the line in one frame (seen
    with grid-aligned starts: 149 of 150 counted). Here a point on the line counts as "not yet on the
    positive side", so the side changes exactly once whichever way the person goes.
    """
    import numpy as np

    (ax, ay), (bx, by) = coordinates[0], coordinates[-1]
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    frames = []
    for _, p in data.groupby("id", sort=False):
        x = p["x"].to_numpy()
        y = p["y"].to_numpy()
        if len(x) < 2 or length2 == 0:
            continue
        s = dx * (y - ay) - dy * (x - ax)          # which side of the line (cross product)
        side = s > 0
        idx = np.nonzero(side[1:] != side[:-1])[0]
        for i in idx:
            denom = s[i] - s[i + 1]
            f = s[i] / denom if denom != 0 else 0.0
            px, py = x[i] + f * (x[i + 1] - x[i]), y[i] + f * (y[i + 1] - y[i])
            u = ((px - ax) * dx + (py - ay) * dy) / length2
            if -1e-9 <= u <= 1 + 1e-9:              # within the segment, not its extension
                frames.append(int(p["frame"].iloc[i + 1]))
                break
    return frames


def _analyse(argv: list[str]) -> int:
    """Flow over measurement lines (own crossing count), density and speed in measurement areas (PedPy), over time.

    Input: the trajectory SQLite of `simulate`, and a JSON
    {"lines": [{"id", "coordinates": [[x, y], [x, y]]}], "areas": [{"id", "coordinates": [[x, y], ...]}],
     "speed_window_s": 1.0}.
    Output (--out): JSON {"frame_rate", "lines": [{"id", "time": [...], "cumulative": [...]}],
    "areas": [{"id", "time": [...], "density": [...], "speed": [...]}]} — speed is null in frames
    where nobody with a known speed is inside. Exit 0 on success, 2 on bad input.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="jps-runner analyse")
    parser.add_argument("trajectory")
    parser.add_argument("measurements")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        import numpy as np
        import pandas as pd
        import pedpy
        import shapely

        spec = json.loads(pathlib.Path(args.measurements).read_text(encoding="utf-8"))
        traj = pedpy.load_trajectory_from_jupedsim_sqlite(trajectory_file=pathlib.Path(args.trajectory))
        fps = float(traj.frame_rate)
        result = {"frame_rate": fps, "lines": [], "areas": []}

        data_all = traj.data[["id", "frame", "x", "y"]].sort_values(["id", "frame"])
        all_frames = np.arange(int(data_all["frame"].min()), int(data_all["frame"].max()) + 1)
        for line in spec.get("lines", []):
            crossing_frames = _first_crossings(data_all, line["coordinates"])
            counts = np.zeros(len(all_frames), dtype=int)
            for f in crossing_frames:
                counts[int(f) - int(all_frames[0]):] += 1
            result["lines"].append({
                "id": line["id"],
                "time": [round(f / fps, 3) for f in all_frames],
                "cumulative": [int(v) for v in counts],
            })

        areas = spec.get("areas", [])
        if areas:
            # Individual speed over a window of speed_window_s; at the ends of a track over what there is.
            step = max(1, int(round(float(spec.get("speed_window_s", 1.0)) * fps / 2)))
            speed = pedpy.compute_individual_speed(
                traj_data=traj, frame_step=step, speed_calculation=pedpy.SpeedCalculation.BORDER_ADAPTIVE)
            data = traj.data[["id", "frame", "x", "y"]]
            frames = np.arange(int(data["frame"].min()), int(data["frame"].max()) + 1)
            for area in areas:
                polygon = shapely.Polygon(area["coordinates"])
                density = pedpy.compute_classic_density(
                    traj_data=traj, measurement_area=pedpy.MeasurementArea(area["coordinates"]))
                density = density.set_index("frame")["density"].reindex(frames, fill_value=0.0)
                # Mean speed of those inside with a known speed; pedpy's own mean refuses tracks it
                # has no speed for (very short ones), so it is averaged here.
                inside = data[shapely.contains_xy(polygon, data["x"].to_numpy(), data["y"].to_numpy())]
                joined = inside.merge(speed[["id", "frame", "speed"]], on=["id", "frame"], how="inner")
                mean = joined.groupby("frame")["speed"].mean().reindex(frames)
                result["areas"].append({
                    "id": area["id"],
                    "time": [round(f / fps, 3) for f in frames],
                    "density": [round(float(v), 4) for v in density.to_numpy()],
                    "speed": [None if pd.isna(v) else round(float(v), 4) for v in mean.to_numpy()],
                })

        pathlib.Path(args.out).write_text(json.dumps(result), encoding="utf-8")
        print(json.dumps({"status": "completed", "lines": len(result["lines"]), "areas": len(result["areas"]),
                          "out": str(pathlib.Path(args.out).resolve())}))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if sys.argv[1:2] == ["analyse"]:
        sys.exit(_analyse(sys.argv[2:]))
    if sys.argv[1:2] == ["version"]:
        sys.exit(_version())
    if sys.argv[1:2] == ["simulate"]:
        sys.exit(_simulate(sys.argv[2:]))
    from jupedsim_scenarios.cli import main

    sys.exit(main())
