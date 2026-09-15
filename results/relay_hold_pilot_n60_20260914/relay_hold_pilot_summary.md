# 2026-09-14 relay hold pilot

Scenario: N60, speed 30 m/s, 60 s, traffic rate 2, range 200 m, seeds 4601-4603. GA uses full lightweight backbone repair plus relay hold rounds = 3.

| Method | PDR(%) | Routing load | Total control | Backbone control | CH churn | CH tenure | Mean cluster size | Path preservation | BS efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GA-MP-DCA relay hold | 19.2931 | 13.1961 | 5739.7 | 2258.7 | 0.4583 | 3.1169 | 3.2555 | 1.0000 | 1.0000 |
| MWMP-DCA baseline | 16.7359 | 15.3992 | 5809.7 | 2328.7 | 0.6076 | 2.1774 | 3.1525 | 0.0273 | 0.1727 |
| MDCS baseline | 18.6130 | 13.9629 | 5855.0 | 2374.0 | 0.5580 | 2.4242 | 3.0890 | 0.0260 | 0.1732 |
| TDC-MOPSO baseline | 20.8310 | 11.5390 | 5411.7 | 1930.7 | 0.3206 | 4.6919 | 3.8457 | 0.0703 | 0.2029 |

Decision: advance this branch to 5-seed 120 s validation. It beats MWMP-DCA and MDCS on PDR, routing load, and connected-backbone metrics, while remaining below TDC-MOPSO on raw PDR/load.
