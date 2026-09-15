# GA-MP-DCA Relay Hold Experiments (2026-09-15)

This repository contains the effective implementation and first-part experiment summaries for a FANET clustering/backbone study based on GA-MP-DCA.

## Effective Method

The current effective method is **GA-MP-DCA with lightweight connected-backbone repair and relay hold time**. Backbone relay nodes are separated from cluster heads: a relay (`BR`) helps maintain the CH-to-BS backbone but is not promoted to a cluster head. `BACKBONE_RELAY_HOLD_ROUNDS` keeps selected relay nodes active for several clustering rounds to reduce role oscillation.

Key parameters used in the formal experiments:

- `TLET_SMOOTHING_ALPHA = 0.35`
- `CH_ROTATION_WEIGHT_MARGIN = 0.10`
- `CH_ROTATION_STABILITY_MARGIN_BONUS = 0.05`
- `CH_ROTATION_STABLE_ROUNDS = 3`
- `BACKBONE_RELAY_HOLD_ROUNDS = 3`
- Communication range: `200 m`
- Traffic rate: `2`
- Formal simulation time: `120 s`

## Main Results

N60, speed 30 m/s, 10 seeds:

| Method | PDR(%) | Routing load | Path preservation | BS efficiency |
|---|---:|---:|---:|---:|
| GA-MP-DCA relay hold | 19.5951 | 26.9498 | 1.0000 | 1.0000 |
| MWMP-DCA | 16.2979 | 32.7896 | 0.0235 | 0.1360 |
| MDCS | 17.6333 | 30.4923 | 0.0209 | 0.1332 |
| TDC-MOPSO | 20.8366 | 23.8456 | 0.0580 | 0.1568 |

The method outperforms MWMP-DCA and MDCS on PDR and routing load, while preserving a fully connected backbone. TDC-MOPSO remains stronger on raw PDR/load in some N60 settings, but has much weaker backbone path preservation and BS reachability.

## Result Files

- `results/relay_hold_extension_n60_20260914_s4606_4610/relay_hold_10seed_combined_summary.md`
- `results/relay_hold_node_scale_ga_20260915/relay_hold_node_scale_summary.md`
- `results/relay_hold_speed_sweep_n60_20260915/relay_hold_speed_sweep_summary.md`
- `results/relay_hold_validation_n60_20260914/relay_hold_validation_summary.md`
- `results/experiment_progress_20260914_on_demand_failed.md`

Only key CSV summaries are included. Large figures, raw trial folders, temporary archives, and rejected raw-result directories are intentionally omitted.

## Tests

Validated on the server Python environment:

```bash
/root/miniconda3/envs/py310/bin/python -m py_compile utils/config.py topology/mwmp_dca/cluster_manager.py experiments/run_recent_baseline_pilot.py routing/mwmp_dca/mwmp_dca_routing.py
/root/miniconda3/envs/py310/bin/python -m unittest discover -s tests -p 'test_mwmp_dca.py'
```

The focused MWMP-DCA/GA-MP-DCA tests passed: 11/11.
