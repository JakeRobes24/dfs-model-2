# DFS Model 2.0 — Consensus & historical minutes (prototype v0.1)

Run: `pip install -r requirements.txt` then `streamlit run app.py`.

Inputs: reconciled contest/DAILY CSV with `fanduel_id,fanduel_name,salary,roster_eligibility,injury_flag,projected_minutes,projected_fd_points`; independent sources CSV `player,source,minutes,independent_group,observed_at`; optional historical CSV `player,season_mpg,last5_mpg,last10_mpg`.

## Evidence rules
- Independently sourced estimates count as agreement only when two independent groups are within four minutes. Duplicate syndication is grouped by `independent_group`.
- Consensus uses median of available independent estimates. If disagreement or single-source evidence exists, use history where available and mark confidence lower.
- Historical-only estimates use recent and season averages, and are flagged. With no other evidence, DAILY remains a *low-confidence, unverified fallback*, not a confirmed minutes projection.
- OUT in contest is excluded. Probable/questionable require manual injury checks and scenario handling before lock.
- Original DAILY points-per-minute is retained; adjusted points = that rate × adjusted minutes. This is a **scenario model**, not an independently validated fantasy projection.
- The optimizer tests all eligible players with defensible positive projections, not only those with third-party minutes; outputs confidence and provenance.

## Limitations / next development
- No automated injury feeds or web scraping, no live provider integration, no historical source data bundled. Upload independently obtained authorized data.
- Source consensus is not a guarantee of accuracy; correlated providers, freshness, role changes and minute caps need manual investigation.
- A missing DAILY projection cannot be converted to a defensible fantasy projection without additional scoring evidence. Reconcile and supply one before optimization.
- Add historical outcome tracking and calibrated source weights after enough real slates are collected.
- Add GPP ceilings/ownership and robust injury scenario optimization; current optimizer maximizes adjusted **mean** projection only.
- Do not enter lineups without contest status, news, and full eligibility verification.

## v0.2 additions (2026-11-20)
- `evidence.py` checks source minutes, source independence-group duplicates and undated evidence; the UI displays warnings. Undated does not automatically mean outdated.
- Optional scenario CSV `player,minutes_delta` recalculates adjusted minutes and FD points; scenarios are hypothetical, not live injury news.
- Optional post-slate source evaluation joins `player,source,minutes` forecasts to `player,actual_minutes` results and reports MAE/RMSE with sample sizes. We do not auto-reweight providers from tiny samples.
- `tests.py` validates legal nine-player optimization, out exclusions, fallback confidence, scenario changes and accuracy calculations.
- **Still not implemented:** verified external historical-game-log ingestion, live injuries, source APIs, ownership-based GPP ceiling simulation, or deployment. Historical averages require uploaded legitimate data; do not label DAILY fallback as independently verified.


## v0.3 coverage and history corrections
- `coverage.py` retains all 247 original contest entries by FanDuel ID; identifies the seven verified name aliases and separately reports truly missing scoring projections. It never treats an unmatched entry as an automatic fade.
- `nov20_complete_247_player_coverage.csv` reports matched, excluded OUT and missing scoring coverage; missing players remain in the audit and require a verified supplementary points/FPPM source before optimization.
- `historical.py` ingests actual player game logs supplied by the user or an authorized source, filters out the slate date and future games, and computes season/last-5/last-10 minute averages. No historical minutes have been invented or populated.
- Fixed `model.py` positional token handling for FanDuel G/F and F/C slots; tests now include full 247-row coverage and alias/historical checks.
- Historical source acquisition and live injuries are **not yet connected**. This is not a claim that all 247 players now have validated projections.

## v0.4 historical scoring bridge (2026-11-20)
- `history_bridge.py` computes FanDuel scoring from **real supplied pre-slate NBA box scores** (PTS + 1.2 REB + 1.5 AST + 3 STL + 3 BLK - TOV), historical minutes and fantasy points per minute.
- `bridge_missing` can supply a historical-only scoring projection for a previously unprojected player **only with >=3 actual completed game records**. Labels these low/medium confidence and never silently substitutes zero for missing data.
- Future or same-day games are excluded from historical data to prevent leakage.
- `test_history_bridge.py` tests this pipeline using explicitly **synthetic fixture records**; those synthetic rows are NOT imported into real November 20 projections.
- For 2026-27 historical logs, candidate external providers include the LineupExperts NBA Player Game Logs by Date API (requires authorized key) and a publicly documented Hugging Face game-log dataset. Neither was ingested here; the runtime has no external download connectivity. Do not claim 27 gaps are filled until authentic logs are supplied and matched.
- For real input use a CSV with columns: `player,game_date,minutes,pts,reb,ast,stl,blk,tov`. Call `summarize_logs(logs, slate_date)` and `bridge_missing(coverage, summary)`; resolve aliases explicitly, review statuses, and then run consensus/optimizer. Preserve FanDuel IDs.

## v0.5 external historical-data adapter (2026-11-20)
- `source_ingest.py` reads actual Hugging Face season Parquet game logs or FanDuel-oriented GitHub CSV game logs into the validated historical-scoring bridge. It does not download them or assert data was acquired.
- Optional Parquet dependency: `pip install pyarrow`. CSV ingestion uses existing pandas dependency.
- Historical inputs must contain complete player/date/minutes/PTS/REB/AST/STL/BLK/TOV rows. All slate-day and future records are excluded.
- `apply_verified_logs(coverage, '/path/to/authentic_logs.csv', slate_date='2026-11-20')` returns full-pool augmented coverage and historical summary. Run optimizer only after statuses and all adjusted projection assumptions are reviewed.
- `test_source_ingest.py` tests CSV conversion, one evidence-supported scoring fill, unresolved players and future-game leakage prevention with **synthetic fixtures only**.
- Verified public source documentation: https://huggingface.co/datasets/cbratkovics/nba-game-logs and https://github.com/xtheredshirtx/fanduel-player-data/tree/main/NBA . Verify rights and provider access before downloading or deploying.
- **No authentic game logs were downloaded in this run** (runtime outbound network connection failed). Hence the 27 missing scoring rows remain unresolved in the actual Nov. 20 audit, and no new fully supported four-lineup portfolio is claimed.

## v0.6 verified-data acquisition and full-pool audit
- `fetch_and_audit.py` can fetch the public 2026-27 historical game-log Parquet file in an environment with outbound internet access, or accept `--local-logs` for an authentic file downloaded separately.
- Run `python fetch_and_audit.py --coverage nov20_complete_247_player_coverage.csv --out audit_output` after installing requirements and pyarrow. Historical outputs include full-pool coverage, player history, still-unresolved scoring, and a coverage report.
- A synthetic integration test verifies missing scoring can be filled from three pre-slate logs while OUT players and slate-day rows are excluded.
- **Important:** This runtime cannot download the real external file, so real historical coverage has not yet been populated. Do not claim the missing 27 players were resolved. Source: https://huggingface.co/datasets/cbratkovics/nba-game-logs
- Historical-only minutes and fantasy points are evidence-based baselines, not guaranteed current rotation forecasts; review team roles, injuries, confirmed starts, and scenario uncertainty before optimizing.
