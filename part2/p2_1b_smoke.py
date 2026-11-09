"""Run the fixed, 12-second P2-1B acceptance scenario on the integrated tree."""

import argparse
import csv
import json
from math import fsum, isclose
from pathlib import Path
from unittest.mock import patch

import simpy

from experiments.frozen_methods import FROZEN_METHODS
from part2.integration.deterministic_loop import DeterministicLoop, DeterministicSimulator
from part2.integration.movement_controller import MovementLimits
from utils import config


def packet_counts(rows):
    rows = list(rows)
    if len({row["packet_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate packet outcomes")
    delivered = sum(row["outcome"] == "delivered" for row in rows)
    if delivered != sum(bool(row["delivery_time"]) for row in rows):
        raise ValueError("delivery timestamp disagrees with outcome")
    return {"generated": len(rows), "delivered": delivered,
            "packet_delivery_ratio": delivered / len(rows) if rows else None}


def _csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    positions = [(500, 500, 150), (730, 500, 150), (470, 500, 150),
                 (420, 460, 150), (410, 550, 150), (340, 500, 150),
                 (240, 500, 150)]
    options = {k: v for k, v in FROZEN_METHODS["PROPOSED"].items()
               if k not in {"protocol", "cluster_algorithm"}}
    options.update(NUMBER_OF_DRONES=len(positions), USE_BASE_STATION=True,
                   BS_NODE_ID=0, BS_POSITION=positions[0], ROUTING_PROTOCOL="MWMP_DCA",
                   CLUSTER_ALGORITHM="MWMP_DCA", ENABLE_VISUALIZATION=False,
                   ENABLE_PLOTS=False, ENABLE_POI=False, TRACE_ONLY=False,
                   MOBILITY_TRACE_MODE="live", HETEROGENEOUS=False,
                   MOBILITY_MODEL="GaussMarkov3D", PACKET_DIAGNOSTICS=True,
                   ENABLE_CLUSTER_SNAPSHOT_LOGGING=False)
    with patch.multiple(config, **options), patch(
            "simulator.simulator.start_coords.get_random_start_point_3d",
            return_value=positions):
        env = simpy.Environment()
        channels = {i: simpy.Resource(env, capacity=1) for i in range(len(positions))}
        sim = DeterministicSimulator(2025, env, channels, len(positions),
                                     controlled_limits={1: MovementLimits(100, 20)},
                                     total_simulation_time=13_000_000)
        loop = DeterministicLoop(sim, 95)
        pois = {1: (750, 500, 150), 2: (835, 500, 150)}
        network, trajectories, coverage, routes = [], [], [], []
        for tick in range(1, 121):
            at = tick * 100_000
            if tick == 11:
                event = env.timeout(at - env.now)
                env.run(until=event)
                loop.decide({1: {1, 2}}, {1: (0.0, 100)}, 3_000_000)
                assert 1 in loop.assignments
            # Process all events at the physical tick and any same-time network epoch.
            env.run(until=at + 1)
            for drone in sim.drones:
                x, y, z = drone.coords
                trajectories.append(dict(time_us=at, node_id=drone.identifier,
                                         x_m=x, y_m=y, z_m=z, speed_mps=drone.speed))
            if tick < 10:
                continue
            state = loop.adapter.capture()
            result = loop.evaluate(pois)
            coverage.append(dict(time_us=state.time_us,
                                 geometric_coverage=len(result.geometric_ids) / len(pois),
                                 bs_reachable_coverage=len(result.effective_ids) / len(pois)))
            for nid, node in state.nodes.items():
                routes.append(dict(time_us=state.time_us, epoch=state.epoch, node_id=nid,
                                   route_available_now=node.route_available_now))
            if not network or network[-1]["epoch"] != state.epoch:
                network.append(dict(time_us=state.snapshot_time_us, epoch=state.epoch,
                                    clusters=dict(state.clusters), cluster_heads=state.cluster_heads,
                                    backbone_relays=state.backbone_relays,
                                    paths_to_bs=dict(state.paths_to_bs)))
        diag = sim.metrics.packet_diagnostics
        diag.export(output, env.now)
        outcome_file = output / "packet_outcomes.csv"
        pdr = packet_counts([])
        if outcome_file.exists():
            with outcome_file.open(newline="", encoding="utf-8") as stream:
                pdr = packet_counts(csv.DictReader(stream))
        assert pdr["generated"] == sim.metrics.datapacket_generated_num
        assert pdr["delivered"] == len(sim.metrics.datapacket_arrived)
        ledger = []
        for d in sim.drones:
            loss = d.initial_energy - d.residual_energy
            assert isclose(loss, fsum([d.propulsion_energy, d.communication_energy]), abs_tol=1e-6)
            assert isclose(d.communication_energy, d.data_energy + d.control_energy, abs_tol=1e-6)
            assert isclose(d.communication_energy, d.tx_energy + d.rx_energy, abs_tol=1e-6)
            ledger.append(dict(node_id=d.identifier, initial_j=d.initial_energy,
                               remaining_j=d.residual_energy, propulsion_j=d.propulsion_energy,
                               communication_j=d.communication_energy, data_j=d.data_energy,
                               control_j=d.control_energy, tx_j=d.tx_energy, rx_j=d.rx_energy,
                               error_j=loss - fsum([d.propulsion_energy, d.communication_energy])))
    _csv(output / "uav_trajectories.csv", trajectories)
    _csv(output / "coverage.csv", coverage)
    _csv(output / "route_available_now.csv", routes)
    _csv(output / "energy_ledger.csv", ledger)
    (output / "cluster_and_ch_changes.json").write_text(json.dumps(network, indent=2), encoding="utf-8")
    (output / "packet_delivery_ratio.json").write_text(json.dumps(pdr, indent=2), encoding="utf-8")
    assert len(network) == 12
    assert {r["route_available_now"] for r in routes if r["node_id"] == 1} == {True, False}
    return pdr


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(run(parser.parse_args().output))
