# 2026-09-15 relay hold speed sweep summary

Scenario: N60, 120 s, traffic rate 2, range 200 m, seeds 4601-4605. Speeds: 20 and 40 m/s. GA uses full lightweight backbone repair plus relay hold rounds = 3.

| Speed | Method | Seeds | PDR(%) | Routing load | Total control | CH churn | CH tenure | Mean cluster size | Path preservation | BS efficiency |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | GA relay hold | 5 | 18.2963 | 27.1949 | 11759.8 | 0.4083 | 3.6560 | 3.1215 | 1.0000 | 1.0000 |
| 20 | MWMP-DCA | 5 | 16.3745 | 30.5961 | 11837.4 | 0.5358 | 2.6384 | 3.0688 | 0.0252 | 0.1235 |
| 20 | MDCS | 5 | 19.9694 | 25.2498 | 11919.0 | 0.5034 | 2.8536 | 3.0150 | 0.0231 | 0.1190 |
| 20 | TDC-MOPSO | 5 | 20.7235 | 22.5320 | 11010.2 | 0.2710 | 5.8973 | 3.7462 | 0.0606 | 0.1412 |
| 40 | GA relay hold | 5 | 20.0276 | 32.8017 | 11903.0 | 0.5228 | 2.6722 | 3.0251 | 1.0000 | 1.0000 |
| 40 | MWMP-DCA | 5 | 16.0866 | 41.2197 | 12017.8 | 0.6346 | 2.0776 | 2.9952 | 0.0230 | 0.1460 |
| 40 | MDCS | 5 | 16.6989 | 39.8389 | 12009.8 | 0.6116 | 2.1915 | 2.9957 | 0.0214 | 0.1424 |
| 40 | TDC-MOPSO | 5 | 20.5781 | 29.8766 | 11151.4 | 0.3505 | 4.4445 | 3.6095 | 0.0612 | 0.1819 |

Key deltas: at 20 m/s, GA beats MWMP-DCA on PDR by +1.9217 and routing load by -3.4011, but trails MDCS/TDC-MOPSO on raw PDR; at 40 m/s, GA beats MWMP-DCA by +3.9410 PDR and MDCS by +3.3288 PDR, and is close to TDC-MOPSO (-0.5505 PDR) while preserving full backbone reachability. At both speeds, GA keeps path preservation and BS efficiency at 1.0, while the baselines remain below 0.182 BS efficiency.

Decision: speed stress evidence supports the thesis claim under high mobility, especially at 40 m/s. The final first-part narrative should emphasize connected-backbone stability and BS reachability, with PDR/load gains over MWMP-DCA and MDCS and near-TDC raw PDR at high speed.
