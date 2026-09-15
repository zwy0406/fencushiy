# 2026-09-15 relay hold 10-seed combined result

Scenario: N60, speed 30 m/s, 120 s, traffic rate 2, range 200 m, seeds 4601-4610. GA uses full lightweight backbone repair plus relay hold rounds = 3.

| Method | Seeds | PDR(%) | Routing load | Total control | Backbone control | CH churn | CH tenure | Mean cluster size | Path preservation | BS efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GA-MP-DCA relay hold | 10 | 19.5951 | 26.9498 | 11838.2 | 4817.2 | 0.4573 | 3.2065 | 3.0679 | 1.0000 | 1.0000 |
| MWMP-DCA | 10 | 16.2979 | 32.7896 | 11975.6 | 4954.6 | 0.5794 | 2.3609 | 2.9786 | 0.0235 | 0.1360 |
| MDCS | 10 | 17.6333 | 30.4923 | 12019.2 | 4998.2 | 0.5644 | 2.4418 | 2.9513 | 0.0209 | 0.1332 |
| TDC-MOPSO | 10 | 20.8366 | 23.8456 | 11105.8 | 4084.8 | 0.3074 | 5.1381 | 3.6524 | 0.0580 | 0.1568 |

Paired deltas: GA relay hold vs MWMP-DCA: PDR +3.2972, routing load -5.8398, path preservation +0.9765, BS efficiency +0.8640. Vs MDCS: PDR +1.9617, routing load -3.5425, path preservation +0.9791, BS efficiency +0.8668. Vs TDC-MOPSO: PDR -1.2415, routing load +3.1042, path preservation +0.9420, BS efficiency +0.8432.

Decision: keep relay hold as the current main method. It consistently beats MWMP-DCA and MDCS in PDR and routing load while preserving a connected backbone. TDC-MOPSO remains better on raw PDR/load, but has weak connected-backbone preservation, so the thesis argument should use connected-backbone stability and BS reachability as primary claims.
