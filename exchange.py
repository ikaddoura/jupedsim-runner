"""Passenger exchange at vehicle doors: boarding persons wait until the alighting persons are out.

The scenario format of jupedsim-scenarios has only a fixed waiting time per checkpoint, counted from each
person's arrival. A real exchange releases the waiting persons on an event: when the last alighting
person of a door (or of the whole vehicle) has passed it. That needs code in the step loop, which is
what this module adds. It reads the optional top-level key ``mobilitystudio_exchange`` of the scenario
JSON (the loader ignores keys it does not know)::

    "mobilitystudio_exchange": {
      "version": 1,
      "release": "per_door",                     # or "whole_vehicle"
      "doors": [
        {
          "id": "door_1",
          "alighting_checkpoint": "jps-checkpoints_0",   # passed = through the door
          "hold_checkpoints": ["jps-checkpoints_1", "jps-checkpoints_2"],
          "alighting_distributions": ["jps-distributions_0"]
        }
      ]
    }

Who is who is read from each person's route, as the loader's direct steering holds it:

* **boarding** persons of a door have one of its hold checkpoints on their route. These are waiting
  checkpoints (waiting time above 0) beside the door. While the door is not released, a person who
  has arrived in one waits there; on the release the wait ends at once.
* **alighting** persons of a door have its alighting checkpoint on their route but none of its hold
  checkpoints. One is out once they have passed that checkpoint (or have left the simulation).

A door is released when every alighting person of it has entered the simulation (the flows of the
listed distributions have spawned all their persons, or their time window is over) and none of them
is still before the alighting checkpoint. ``whole_vehicle`` releases all doors at the same moment,
when that holds for every door. With no alighting persons a door is released at once. A release is
never taken back.
"""

from __future__ import annotations

from typing import Any

KEY = "mobilitystudio_exchange"
FEATURE = "exchange_v1"
RELEASES = ("per_door", "whole_vehicle")

# How long a held person "waits" — longer than any simulation; replaced by the release time.
_HOLD_SECONDS = 1.0e9
# A timed flow that has not spawned all its persons is given up this long after its end time.
_SPAWN_GRACE_SECONDS = 1.0


class _Door:
    def __init__(self, spec: dict[str, Any]):
        self.id = str(spec.get("id", ""))
        self.alighting_checkpoint = spec.get("alighting_checkpoint")
        self.hold = set(spec.get("hold_checkpoints") or [])
        self.alighting_distributions = set(spec.get("alighting_distributions") or [])
        self.released_at: float | None = None


class PassengerExchange:
    """Holds the boarding persons of a running ``ScenarioRunner``; call :meth:`before_step` before every step."""

    def __init__(self, spec: dict[str, Any], raw: dict[str, Any], runner):
        if not isinstance(spec, dict):
            raise ValueError(f"{KEY} must be an object")
        if spec.get("version") != 1:
            raise ValueError(f"{KEY} version {spec.get('version')!r} is not supported (this runner reads version 1)")
        self.release = spec.get("release", "per_door")
        if self.release not in RELEASES:
            raise ValueError(f"{KEY}: release must be one of {', '.join(RELEASES)}, not {self.release!r}")
        checkpoints = raw.get("checkpoints") or {}
        distributions = raw.get("distributions") or {}
        self.doors: list[_Door] = []
        for d in spec.get("doors") or []:
            door = _Door(d)
            if door.alighting_checkpoint not in checkpoints:
                raise ValueError(f"{KEY}: door {door.id!r} names the checkpoint "
                                 f"{door.alighting_checkpoint!r}, which is not in the scenario")
            for cp in door.hold:
                if cp not in checkpoints:
                    raise ValueError(f"{KEY}: door {door.id!r} waits in {cp!r}, which is not in the scenario")
                if float(checkpoints[cp].get("waiting_time", 0.0)) <= 0:
                    raise ValueError(f"{KEY}: door {door.id!r} waits in {cp!r}, which has no waiting time;"
                                     " a waiting place needs a waiting time above 0")
            for dist in door.alighting_distributions:
                if dist not in distributions:
                    raise ValueError(f"{KEY}: door {door.id!r} names the distribution {dist!r}, which is not in the scenario")
            self.doors.append(door)
        self._runner = runner
        self._role: dict[int, tuple[_Door, str] | None] = {}
        self._passed: set[int] = set()
        self._held: set[int] = set()

    # -- what the runner reports ----------------------------------------------

    def summary(self) -> dict[str, Any]:
        return {
            "release": self.release,
            "doors": [{"id": d.id, "released_at": None if d.released_at is None else round(d.released_at, 2)}
                      for d in self.doors],
        }

    # -- the step hook ----------------------------------------------------------

    def before_step(self) -> None:
        runner = self._runner
        now = float(runner.simulation.elapsed_time())
        wait_info: dict[int, dict[str, Any]] = runner._agent_wait_info
        alive = {int(a.id) for a in runner.simulation.agents()}

        pending = {id(d): 0 for d in self.doors}
        boarding: list[tuple[int, _Door, dict[str, Any]]] = []
        for agent_id, info in wait_info.items():
            if agent_id not in alive or info.get("mode") != "path":
                continue
            role = self._role_of(agent_id, info)
            if role is None:
                continue
            door, kind = role
            if kind == "boarding":
                boarding.append((agent_id, door, info))
                continue
            if agent_id not in self._passed and (
                    info.get("current_origin") == door.alighting_checkpoint or info.get("state") == "done"):
                self._passed.add(agent_id)
            if agent_id not in self._passed:
                pending[id(door)] += 1

        ready = {id(d): self._all_spawned(d, now) and pending[id(d)] == 0 for d in self.doors}
        if self.release == "whole_vehicle":
            if all(ready.values()):
                for d in self.doors:
                    if d.released_at is None:
                        d.released_at = now
        else:
            for d in self.doors:
                if d.released_at is None and ready[id(d)]:
                    d.released_at = now

        for agent_id, door, info in boarding:
            waiting_here = info.get("state") == "waiting" and info.get("current_target_stage") in door.hold
            if door.released_at is None:
                if waiting_here:
                    info["wait_until"] = now + _HOLD_SECONDS
                    self._held.add(agent_id)
            elif agent_id in self._held:
                self._held.discard(agent_id)
                if waiting_here:
                    info["wait_until"] = now

    def _role_of(self, agent_id: int, info: dict[str, Any]):
        if agent_id in self._role:
            return self._role[agent_id]
        stages = set()
        for origin, choices in (info.get("path_choices") or {}).items():
            stages.add(origin)
            stages.update(target for target, _ in choices)
        stages.add(info.get("current_target_stage"))
        role = None
        for d in self.doors:
            if stages & d.hold:
                role = (d, "boarding")
                break
        if role is None:
            for d in self.doors:
                if d.alighting_checkpoint in stages:
                    role = (d, "alighting")
                    break
        self._role[agent_id] = role
        return role

    def _all_spawned(self, door: _Door, now: float) -> bool:
        info = self._runner._spawning_info
        flows = info.get("flow_distributions", []) or []
        counters = info.get("agent_counter_per_source", []) or []
        numbers = info.get("num_agents_per_source", []) or []
        for i, flow in enumerate(flows):
            if flow.get("dist_key") not in door.alighting_distributions:
                continue
            if i < len(counters) and i < len(numbers) and counters[i] < numbers[i] \
                    and now <= float(flow.get("end_time", 0.0)) + _SPAWN_GRACE_SECONDS:
                return False
        # Distributions placed at once are all inside since the start.
        return True


def run(scenario, spec: dict[str, Any], *, seed, dt, every_nth_frame, output_path):
    """``run_scenario`` with the exchange hook; returns (ScenarioResult, PassengerExchange)."""
    from jupedsim_scenarios.runner import ScenarioRunner

    with ScenarioRunner(scenario, seed=seed, dt=dt, every_nth_frame=every_nth_frame,
                        output_path=output_path) as runner:
        exchange = PassengerExchange(spec, scenario.raw, runner)
        end = scenario.max_simulation_time
        # The loop of ScenarioRunner.run_until, with the hook before every step.
        while runner.elapsed_time < end and runner._should_continue():
            exchange.before_step()
            runner.step()
        return runner.result(), exchange
