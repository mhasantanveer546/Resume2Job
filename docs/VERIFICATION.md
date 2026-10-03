# Verification — 3 October 2026

## Environment
Python 3.12.14, Linux, Chrome for Testing 154.0.8037.92. Runtime dependencies pinned in requirements.txt.

## Completed checks
- **34 pytest tests passed** in 1.14 seconds.
- **Desktop browser:** 1440 × 1000.
- **Mobile browser:** 390 × 844; no horizontal page overflow.
- **All nonlocal browser requests blocked:** zero external requests during the application flow.
- **No unexpected browser or JavaScript errors.** One intentionally invalid profile produced the expected HTTP 422, kept the editor open, and stopped the save/match chain.
- PDF upload -> editable profile -> preferences -> ranked jobs -> selected analysis -> all report tabs -> improvements -> report download -> cached analysis -> refresh/restore -> invalid input -> empty results -> deletion.
- Second candidate checked on mobile; paste-text fallback checked with HTML injection text, which was safely displayed as text.
- Fresh PDF-to-analysis browser flow: **1.721 seconds** in deterministic mode, including automation clicks and edits.
- Cached analysis reopen: **0.073 seconds**.
- Data: 180 unique jobs; 172 public records with original links; eight labeled synthetic roles. Required/preferred public skills are present in the source descriptions.
- Screenshots visually checked for landing, analysis and mobile action views.

## Test coverage
Five candidate personas; strong versus weak matches; score reproducibility and sum invariants; work-date overlap and education exclusion; aliases; strict preferences; seniority filtering; empty vocabulary; malformed, encrypted, oversized, overlong and textless PDFs; parser fallback; schema rejection; hallucinated credentials, metrics and employers; implied skill uncertainty; four-call advisor limit; resource retrieval; local-only LLM transport; model failure; embedding failure; upload and analysis API; owner isolation; expiry; cache invalidation; deletion; cross-origin write rejection; dataset integrity; CSV import.

## Not claimed as verified
- Actual Ollama model inference: no Ollama installation/model in this workspace. The endpoint adapter and agent protocol were tested with controlled responses; this does not establish real model quality or hardware performance.
- Optional sentence-transformers inference: fallback path tested, no embedding model downloaded.
- Windows/macOS launcher execution and Docker build: provided and reviewed, but this environment is Linux without Docker.
- Job availability or worldwide coverage: public data is a UK-focused snapshot, not live search. Automated requirement extraction needs human spot-checking.
- Free-form factual resume rewriting: intentionally restricted to formatting cleanup because arbitrary paraphrases cannot be proven truthful by a lexical verifier.
- The full PRD quality benchmark (10 real-world resumes and human top-five relevance judgments) has not been completed. Synthetic correctness tests are not a substitute for that evaluation.

A dependency emits one Starlette TestClient deprecation warning about httpx. It does not affect the app or test results.

## Repeat
```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m playwright install chromium
# Start the app in another terminal, then:
python tests/browser_flow.py
```
Set CHROME_PATH if using a separately installed browser. Screenshots are written to /tmp/r2j-screenshots by default; set R2J_SCREENSHOTS for a different location.
