# Historical archive recovery and asymmetric NFL interval replay

November 27 development checkpoint. The private evidence branch's README identifies the workload CSV as a ZIP member, not a standalone repository file. Reassembled evidence.part00, evidence.part01 and evidence.part02 in order; size matched 100034 bytes, and the ZIP member's CRC-32 and uncompressed length matched. The independent JavaScript replay read 3412 archived player-games, reproduced the original 452 rushing and 967 receiving holdouts and matched the previously documented original and symmetric calibration summaries to rounding. The JavaScript runtime did not provide SHA-256, so this replay did not independently verify the README's SHA-256. The added Python replay utility enforces both published SHA-256 hashes; its real-archive execution remains pending. No private player-level data copied into the model repository.

Same six held-out weeks (6–11), after the 50-player warmup, equal-week means. Nominal central coverage 80%; nominal miss budget 10% each tail.

| Yardage | Method | Holdouts | Coverage | Below | Above | Width | Interval score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Rushing | Original | 381 | 52.92% | 28.35% | 18.73% | 38.15 | 107.90 |
| Rushing | Symmetric | 381 | 79.72% | 9.18% | 11.10% | 62.60 | 94.24 |
| Rushing | Asymmetric | 381 | 82.59% | 9.93% | 7.48% | 68.32 | 95.36 |
| Receiving | Original | 822 | 46.51% | 31.68% | 21.81% | 39.67 | 120.79 |
| Receiving | Symmetric | 822 | 79.47% | 8.71% | 11.82% | 64.71 | 101.34 |
| Receiving | Asymmetric | 822 | 79.79% | 10.20% | 10.01% | 69.92 | 100.81 |

Asymmetric improved receiving interval score in five of six weeks, with a modest 0.53 equal-week improvement; it worsened rushing interval score overall and widened both intervals. Keep symmetric as the rushing research leader and asymmetric as a receiving challenger, not a promoted policy. Conditional on matched played rows; no untouched holdout, full fantasy-point or lineup correlation validation. NBA rate challenge still requires locating the original row-level role archive; the cross-sport ZIP has an NBA summary, not the complete row-level history.

Reproduce using `python nfl_archive_replay.py evidence.part00 evidence.part01 evidence.part02` with the original authorized private evidence files. No Friday slate files required; no MLB or live scoring changes.
