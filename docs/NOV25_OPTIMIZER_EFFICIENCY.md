# November 25 optimizer efficiency experiment

## Input and method

Read the immutable Nov 24 main contest 137128 morning research packet from the private history repo (commit 13531c97ba4fdfc28962f9cb4cac38118dd74280). It contains 105 contest rows, 85 eligible and 79 eligible with positive usable adjusted FD points. Extracted only the exact 79 optimizable rows (player ID suffix, team, salary, eligibility, unrounded adjusted points). Reproduced the existing MILP constraints in a local harness (SciPy 1.17.0): four sequential candidates with maximum pairwise overlap seven, plus the leading roster's strongest distinct alternative, salary cap 60000, maximum four players per team, unique player IDs and exact slots. Each solve proved optimal. No actual outcomes were used for optimization.

Tested three row orderings (original, seeded permutations 1 and 2). These are repeatability checks on a single slate, not three independent slates. Wall time includes matrix construction and five solves; it excludes public research, website rendering, archive access and network latency.

## Results

| Ordering | Original nine slots, s | Explicit UTIL ordering, s | Compact UTIL capacity, s |
|---|---:|---:|---:|
| Original | 3.9832 | 3.3099 | 2.6574 |
| Seed 1 | 2.9672 | 3.9672 | 3.2908 |
| Seed 2 | 3.6162 | 3.7822 | 2.6902 |

The explicit-ordering experiment had separately timed baseline runs of 4.1039, 2.9972 and 3.5644 s. Its median time was worse than that baseline; rejected. Compact UTIL reduced median local time from 3.6162 to 2.6902 s (~25.6%), although one ordering was slower. Identical player sets for all five rosters in all three comparisons. Objective differences were at most floating point rounding (~1e-8). Rounded projected scores: 329.28, 328.19, 327.77, 327.18; leading distinct rival 328.19.

## Implementation decision

The two unlocked UTIL assignments are interchangeable. Combine them into one row with demand two and one binary assignment variable per eligible player. Every legal distinct-player assignment to the original two UTIL slots maps to one compact solution and vice versa. Salary, team limits, overlap, excluded roster, and objective constraints are unchanged. Fixed/closed slot workflows retain the explicit nine-slot formulation; no changes to late-swap slot placement. Added a mixed-position regression comparing the two formulations. No scoring or production change.

The local harness reproduced the constraints, rather than importing the repository module. New implementation CI is required. Broader real-slate benchmarks and staging end-to-end timings remain outstanding; do not extrapolate the local speed result to every slate.
