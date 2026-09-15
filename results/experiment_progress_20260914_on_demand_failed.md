# 2026-09-14 on-demand backbone repair pilot

Scenario: N60, speed 30 m/s, 60 s, traffic rate 2, range 200 m, seeds 4601-4603.

| Method | PDR(%) | Routing load | Total control | Backbone control | CH churn | CH tenure | Mean cluster size | Path preservation | BS efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GA-MP-DCA on-demand repair | 15.0798 | 16.8816 | 5739.7 | 2258.7 | 0.4583 | 3.1169 | 3.2555 | 0.8979 | 1.0000 |
| MWMP-DCA | 16.7359 | 15.3992 | 5809.7 | 2328.7 | 0.6076 | 2.1774 | 3.1525 | 0.0273 | 0.1727 |
| MDCS | 18.6130 | 13.9629 | 5855.0 | 2374.0 | 0.5580 | 2.4242 | 3.0890 | 0.0260 | 0.1732 |
| TDC-MOPSO | 20.8310 | 11.5390 | 5411.7 | 1930.7 | 0.3206 | 4.6919 | 3.8457 | 0.0703 | 0.2029 |

Decision: do not expand this branch. It improves path preservation and BS efficiency over the baselines and keeps routing load below 30, but PDR is lower than MWMP-DCA, MDCS, and TDC-MOPSO. It also loses the full lightweight relay variant path-preservation value of 1.0.

Next direction: keep the full repair path advantage, but improve long-run PDR through CH selection and relay stability. Candidate next tests: relay hold time, load/density penalty for CH candidates, or a TDC-MOPSO-style multi-objective CH selector combined with lightweight backbone repair.
