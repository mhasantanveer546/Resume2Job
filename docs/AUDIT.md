# Resume2Job audit and implementation decisions

## Baseline
The supplied ZIP contained four Python modules, an Alpine/Tailwind CDN page, SQLite session storage, eight synthetic jobs, a 26-skill vocabulary, CSV importer and 12 tests. The deterministic match/gap architecture and single FastAPI deployment were worth retaining.

## Conflicts resolved
The PRD suggests cloud free-tier providers and CDN frontend assets. The current instruction requires local-first, no paid AI APIs and offline operation, so runtime cloud AI is blocked and frontend assets are local vanilla JavaScript/CSS. A one-time public job snapshot is included; the app itself never calls a job API.

## Findings and repairs
| Area | Original state | Delivered change |
|---|---|---|
| PDF handling | Missing fallback/encryption preflight | Size, signature, page and encryption checks; pdfplumber plus PyMuPDF; text fallback UI |
| Profile | Only skills/year edits | All six profile sections editable, validated and normalized |
| Experience | Education dates counted; overlap double-counted; fixed current year | Work sections only, month-aware merged intervals, actual current date; uncertain estimates exposed |
| Matching | Extra skills disagreed with analysis; ignored mode/level/location; rounded total mismatch | Consistent profile merge, filters, configurable weights, exact rounded component sum |
| Similarity | Refit against filtered jobs each call; min-max promoted weak results | Cached corpus index and raw cosine; optional local embeddings; edits drive query text |
| Data | Eight synthetic roles only | 180 records, including 172 public API snapshot records and labeled demo roles |
| Taxonomy | 26 skills | 366 categorized skills with explicit aliases |
| Qualification | No actual education gap reporting | Requirement, candidate evidence and review/unknown status |
| Grounding | Arbitrary model education/year claims; quote removed required gap | Exact quotes, deterministic years, implication stays unconfirmed |
| Advisor | Free prose could invent candidate facts | Four-call cap; retrieved tools; model may select only approved recommendation IDs |
| RAG | No learning retrieval | Local chunk index with tags/TF-IDF; citations; advisor resource tool |
| Rewrite | Only novel known skills rejected | Conservative formatting-only acceptance; factual paraphrases rejected |
| Caching | Skills/years signature only | Whole profile/preferences/job/config/model version; edits invalidate; refresh restores profile |
| Privacy | Global DB connection; no expiry; UUID alone | Owner cookie plus UUID, per-operation connections, 24h expiry, secure delete, local-only AI |
| UI | CDN dependency; partial editor; error chains continued | Offline assets, guarded sequential saves, recovery, stepper/actions, export, responsive UI |
| Packaging | Unpinned dependencies; env not loaded | Tested pins, dotenv, launchers, Dockerfile, troubleshooting, fixtures |

## Functional coverage
F1–F11 are implemented with deterministic fallbacks and optional local LLM stages. F12 is deliberately limited to safe formatting edits; free paraphrasing is not claimed. F13 text report export and F14 deletion are included. F15 live search and F16–F18 comparison, full resume document generation and bookmarks remain out of scope.

## Risks still requiring judgment
- Public jobs are a UK-focused snapshot; automated skill extraction can confuse a mentioned technology with a requirement. Each record links to the original and is labeled as needing review. This is not a manually reviewed global vacancy index.
- Local model quality/speed depends on user hardware. No specific model is silently downloaded. Real model inference is distinct from deterministic fallback and mocked protocol tests.
- Work-date parsing is heuristic, particularly for unusual layouts, undated roles and graduation dates embedded in mixed sections. The editor is the quality gate.
- Qualification equivalence cannot safely be reduced to keyword matching. The app surfaces evidence for review instead of declaring a degree equivalent.
- The API uses synchronous bounded analysis requests, not a queue/polling service. Suitable for a local hackathon, not a production multi-user service.
- Retention cleanup runs on startup and storage access. A stopped application cannot run cleanup; the next start does so.

## First implementation phase and sequence
1. Fix extraction, scoring, contracts, session storage and evidence boundaries.
2. Connect local retrieval and bounded agent calls.
3. Finish offline UI, real dataset snapshot and launchers.
4. Verify API regressions, browser flow, error recovery and packaging.
