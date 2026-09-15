# 2026-09-14 relay hold validation, N60 speed30

Scenario: N60, speed 30 m/s, 120 s, traffic rate 2, range 200 m, seeds 4601-4605. GA uses full lightweight backbone repair plus relay hold rounds = 3.

| Method | PDR(%) | Routing load | Total control | Backbone control | CH churn | CH tenure | Mean cluster size | Path preservation | BS efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GA-MP-DCA relay hold | 19.1707 | 27.5131 | 11854.6 | 4833.6 | 0.4568 | 3.2169 | 3.0569 | 1.0000 | 1.0000 |
| MWMP-DCA | 16.5107 | 32.3414 | 11997.4 | 4976.4 | 0.5735 | 2.4025 | 2.9649 | 0.0239 | 0.1395 |
| MDCS | 18.4321 | 29.0790 | 12040.2 | 5019.2 | 0.5569 | 2.4792 | 2.9383 | 0.0222 | 0.1396 |
| TDC-MOPSO | 20.2360 | 24.4711 | 11107.4 | 4086.4 | 0.3136 | 5.0228 | 3.6507 | 0.0594 | 0.1596 |

Paired deltas, relay hold GA minus baseline: +2.6601 PDR and -4.8283 routing load vs MWMP-DCA; +0.7386 PDR and -1.5658 routing load vs MDCS; -1.0652 PDR and +3.0420 routing load vs TDC-MOPSO. Backbone path preservation is +0.9761/+0.9778/+0.9406 against MWMP-DCA/MDCS/TDC-MOPSO.

Decision: keep relay hold as the current effective branch. It meets the formal gate against MWMP-DCA and MDCS while preserving a connected backbone. It does not beat TDC-MOPSO on raw PDR/load, so the paper argument should emphasize connected-backbone stability and BS reachability, not raw delivery alone.
