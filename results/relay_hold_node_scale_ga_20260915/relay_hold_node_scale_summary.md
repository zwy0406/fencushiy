# 2026-09-15 relay hold node scale summary

Scenario: speed 30 m/s, 120 s, traffic rate 2, range 200 m. N20/N40 use seeds 4601-4605 for GA relay hold and historical baselines. N60 uses 10-seed GA relay hold and existing 5-seed baselines for scale reference.

| N | Method | Seeds | PDR(%) | Routing load | Total control | CH churn | CH tenure | Mean cluster size | Path preservation | BS efficiency |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | GA relay hold | 5 | 34.4953 | 22.2943 | 5345.8 | 0.2152 | 7.4770 | 1.5903 | 1.0000 | 1.0000 |
| 20 | MWMP-DCA | 5 | 19.9902 | 38.3053 | 5350.6 | 0.2681 | 5.9131 | 1.5881 | 0.2537 | 0.7278 |
| 20 | MDCS | 5 | 20.3349 | 37.8782 | 5431.8 | 0.2229 | 7.2455 | 1.5445 | 0.2453 | 0.7414 |
| 20 | TDC-MOPSO | 5 | 22.0501 | 33.7996 | 5238.6 | 0.0836 | 18.7217 | 1.6533 | 0.3151 | 0.7334 |
| 40 | GA relay hold | 5 | 39.0156 | 14.8959 | 8797.4 | 0.3596 | 4.2309 | 2.3704 | 1.0000 | 1.0000 |
| 40 | MWMP-DCA | 5 | 22.7372 | 25.8873 | 8905.4 | 0.4608 | 3.1852 | 2.3007 | 0.0690 | 0.3653 |
| 40 | MDCS | 5 | 23.4351 | 25.2583 | 8927.0 | 0.4514 | 3.2664 | 2.2994 | 0.0627 | 0.3595 |
| 40 | TDC-MOPSO | 5 | 27.7361 | 20.1208 | 8320.2 | 0.2107 | 7.7617 | 2.7000 | 0.1395 | 0.3880 |
| 60 | GA relay hold | 10 | 19.5951 | 26.9498 | 11838.2 | 0.4573 | 3.2065 | 3.0679 | 1.0000 | 1.0000 |
| 60 | MWMP-DCA | 5 | 16.5107 | 32.3414 | 11997.4 | 0.5735 | 2.4025 | 2.9649 | 0.0239 | 0.1395 |
| 60 | MDCS | 5 | 18.4321 | 29.0790 | 12040.2 | 0.5569 | 2.4792 | 2.9383 | 0.0222 | 0.1396 |
| 60 | TDC-MOPSO | 5 | 20.2360 | 24.4711 | 11107.4 | 0.3136 | 5.0228 | 3.6507 | 0.0594 | 0.1596 |

Decision: node-scale evidence is strong enough to keep relay hold as the first-part main method. N20 and N40 beat all baselines on PDR while preserving full backbone reachability; N60 beats MWMP-DCA and MDCS and remains close to TDC-MOPSO on PDR while dominating connected-backbone metrics.
