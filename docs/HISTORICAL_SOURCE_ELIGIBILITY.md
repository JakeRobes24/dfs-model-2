# Historical provider-calibration eligibility review (2026-11-25)

Read-only inspection of actual archive packets in the private history repository. This is a provenance audit, not new calibration results.

| Date / contest | Research rows | Outcome rows in packet | Eligibility for frozen source accuracy |
|---|---:|---:|---|
| Nov 18 / 136886 | 316 | 316 | Legacy archive lacks frozen capture and per-provider dated evidence; retrospective only |
| Nov 20 / 136961 | 247 | 0 | Legacy 33-stage research export, no current replay capture fields; official outcomes stored separately; retrospective only |
| Nov 24 main / 137128 | 105 | 105 | Morning capture 11:14:51 UTC qualifies under existing replay chronology; reviewed in NOV24_PROVIDER_ACCURACY.md |
| Nov 24 main earlier packet / 137128 | 105 | 0 | Same morning capture timestamp; not an independent date |
| Nov 24 After Hours / 137139 | 70 | 70 | Reconstructed pool marked timing unknown; do not treat as frozen evidence |

Nov 20 packet was too large for the file-content connector; retrieved its Git blob (6c313225e0dc4ef447fd47d13bbd355e24a4e52d) and inspected the complete JSON. The old archive is valuable, but timestamps in research notes are not substitutes for the current full-pool immutable pre-tip chronology.

Recovered source inventory from Nov 20 research CSV:
- MatchWiz: 98 player projected-minute rows with partial PTS/REB/AST stat evidence; source snapshot noted 09:25 ET. Not complete FD projections.
- TheCapper: 9 player projected-minute rows with independent projected box score references, not historical actuals.
- KeelStats: 138 Tonight projected-minute values; 247 rows carry the source link and 08:14 ET snapshot note. L10 minutes and starts are observed summaries, not Tonight forecasts.

These providers have been restored to the research registry as manual sources, with historical links distinguished from verified current access. Their current availability, data independence and calibration reliability have not been established. Keep older source data available for explicitly retrospective investigations. Do not fabricate timestamps, promote weights or duplicate a date to inflate sample size.

Archive references:
- [Nov 18 packet](https://github.com/JakeRobes24/dfs-model-2-history/blob/94fb8a84d1e4c8b9c480ade08aed07e0f771c3f0/incoming-app/2026-11-18/136886/4987d355107cfae2248987e0a4d7b186a7fd8f19068b60bdea8c2e62082cf855.json)
- [Nov 20 packet](https://github.com/JakeRobes24/dfs-model-2-history/blob/00ed90b1cc8108fd8e21cd6c7969b8be3ea7162a/incoming-app/2026-11-20/136961/c617feccd24e571821de590f05b8439c90c9939b314464e55e8c6592671e868b.json)
- [Nov 24 earlier main packet](https://github.com/JakeRobes24/dfs-model-2-history/blob/b8fb80f95aa00909d4497c5264962b957436c737/incoming-app/2026-11-24/137128/6dbd4f73ea88976a39046e89e4679749ea902186c23a5629d225002ed11ac7be.json)
- [Nov 24 After Hours packet](https://github.com/JakeRobes24/dfs-model-2-history/blob/f71815185cf4f404f80a765974769f79602ffa44/incoming-app/2026-11-24/137139/cbf58f7964a885564b2a1c7dc7cef470513d0c7922b41841cef37335f23f7fa7.json)

Next: inspect current public access for the recovered sources, then collect genuinely frozen forecasts on new slates. The archive loader and post-slate review remain read-only; no production or historical database mutation.
