# Job Hunter — Phases 1, 2 & 3 (+ Workday, + RAG answers, + LLM dropdown mapping)

An automated job-application pipeline. This repo currently covers:

- **Phase 1 (Hunter):** scrapes job postings from public/internal ATS
  endpoints — Greenhouse, Lever, Ashby, and Workday — into Postgres/SQLite.
- **Phase 2 (Evaluator):** scores each posting against your resume with an
  LLM (Anthropic or OpenAI) and marks it approved or trashed.
- **Phase 3 (Executor):** opens an approved application in a real browser
  and pre-fills the fields it's confident about — including, optionally,
  RAG-drafted answers to cover letters/open-ended questions and LLM-picked
  dropdown options — grounded in your real stories and resume. It never
  submits — you review and click submit yourself. EEO/demographic and
  work-authorization questions are never sent to any LLM at all, regardless
  of what's configured.

---

## Quickstart: run Phase 1 → Phase 2 → Phase 3 end to end

This walks through the whole pipeline once, against real data, so you can
see actual jobs go from scraped → scored → approved before doing anything
else with the project.

**1. Install**

```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\Activate.ps1    # Windows PowerShell
# .venv\Scripts\activate.bat    # Windows cmd.exe
pip install -r requirements.txt
```

**2. Configure**

```bash
cp .env.example .env
```

Open `.env` and set:
- `GREENHOUSE_COMPANIES` / `LEVER_COMPANIES` / `ASHBY_COMPANIES` — start
  small, e.g. `GREENHOUSE_COMPANIES=stripe`. Find a slug by checking
  `boards.greenhouse.io/{slug}`, `jobs.lever.co/{slug}`, or
  `jobs.ashbyhq.com/{slug}` for a company you know uses that ATS.
- `WORKDAY_COMPANIES` (optional, and slower than the other three — see
  the Sources section below for its `tenant|wd_host|site` format)
- `LLM_PROVIDER` — `anthropic` or `openai`
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` — whichever matches
- Leave `DATABASE_URL` unset for now; it falls back to a local SQLite file
  (`job_hunter.db`) so you don't need Postgres running to test this.

**3. Add your resume**

```bash
cp resume.md.example resume.md
```

Replace the placeholder content with your real experience — plain text or
markdown, no special formatting needed.

**4. Run the Hunter**

```bash
python -m app.hunter
```

You should see one log line per company, like:

```
2026-08-12 10:02:11 INFO greenhouse  stripe               42 seen,  42 new
```

If you see `0 seen` for every company, the slug is probably wrong — check
step 2's URLs against the actual company career page.

**5. Check what landed in the database**

```bash
python -m app.inspect_jobs
```

This prints a count of jobs by status, plus the most recent ones. Right
now everything should show as `PENDING_EVALUATION`.

**6. Run the Evaluator**

```bash
python -m app.evaluator
```

One log line per job scored:

```
2026-08-12 10:05:44 INFO Senior Backend Engineer                score= 88 -> APPROVED_FOR_APPLY
```

This calls a real LLM API for every pending job, so cost and time scale
with however many companies/postings you configured in step 2 — that's
why step 2 says to start small.

**7. See what got approved**

```bash
python -m app.inspect_jobs --status APPROVED_FOR_APPLY
```

If nothing got approved, that's not necessarily a bug — it means nothing
scored above `APPROVAL_THRESHOLD` (default 85) against your resume. Try
lowering it in `.env` temporarily to see mid-range scores, or check the
Evaluator's log output for the reasoning behind a specific score.

**8. Set up your candidate profile**

```bash
cp candidate_profile.json.example candidate_profile.json
```

Fill in your real contact details. `resume_file_path` must point to an
actual PDF/DOCX file to upload — not `resume.md` from step 3, which is
plain text used only for LLM scoring.

**8b. (Optional) Add a story bank for cover letter / open-question drafting**

```bash
cp story_bank.json.example story_bank.json
```

Add 2-5 real stories from your own experience. Skip this step entirely if
you'd rather just write cover letters yourself — without this file, the
Executor simply leaves those fields blank for you, nothing breaks.

**9. Dry-run the Executor first**

```bash
python -m app.executor.runner --dry-run
```

This opens the oldest `APPROVED_FOR_APPLY` job's application page, reports
exactly what it *would* fill and what it would leave for you, and closes —
without touching a single field. Read the "Skipped" list carefully; that's
everything requiring your judgment (dropdowns, EEO/demographic questions,
work authorization, anything the classifier wasn't confident about).

**10. Run it for real**

```bash
python -m app.executor.runner
```

A visible Chromium window opens, fields get filled, a screenshot is saved
for your records, and the terminal pauses with the browser still open.
Review every field yourself — pay extra attention to anything marked
`AI DRAFT ... REVIEW BEFORE SUBMITTING` or `LLM PICK ... REVIEW BEFORE
SUBMITTING`, since that content is LLM-generated — answer whatever was
skipped, and click Submit yourself if it looks right. The tool never does
this for you. Press Enter in the terminal once you're done, and it'll ask
whether you actually submitted, updating the job's status accordingly.

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError` | Forgot to activate `.venv` or run `pip install -r requirements.txt` |
| Hunter: `0 seen` for a company | Wrong slug — re-check the company's actual career board URL |
| Hunter: `httpx.HTTPStatusError` | Company doesn't use that ATS, or the slug is wrong (404) |
| Evaluator: `FileNotFoundError` re: resume | Forgot step 3 (`cp resume.md.example resume.md`) |
| Evaluator: `ValueError` re: API key | `.env` has the wrong key set for your `LLM_PROVIDER`, or the key is blank |
| Evaluator runs but job stays `PENDING_EVALUATION` | Check the logged error — that job will retry next run automatically |
| Executor: `FileNotFoundError` re: candidate profile | Forgot step 8 (`cp candidate_profile.json.example candidate_profile.json`) |
| Executor: browser window doesn't appear | First run `python -m playwright install chromium` to download the browser binary |
| Executor fills fields incorrectly | The classifier is heuristic, not perfect — that's exactly why it pauses for your review instead of submitting automatically. Report the mismatch to yourself as a note to improve `app/executor/field_classifier.py` |
| Workday: `ValueError` re: 'tenant\|wd_host\|site' | Check the format in `WORKDAY_COMPANIES` — it needs all three pieces, pipe-separated |
| Workday: very slow Hunter run | Expected — per-job description fetching plus conservative delays add up fast for large companies. Set `WORKDAY_FETCH_DESCRIPTIONS=false` for a quicker listing-only pass |
| Workday: every job's description fetch returns `422 Unprocessable Entity` | Fixed in this version — some tenants' `externalPath` already includes a leading `/job/` segment, which combined with the URL template's own `/job` produced a doubled `.../job/job/...` path. If you're on an older copy, pull the latest `app/sources/workday.py`. |
| Greenhouse/Lever: `404 Not Found` even though the company definitely exists | The token often isn't the company's name — e.g. DoorDash's Greenhouse token is `doordashusa`, not `doordash`. Some companies have also switched ATS platforms entirely (Netflix moved off Lever). Verify by opening `boards.greenhouse.io/{slug}` or `jobs.lever.co/{slug}` directly in a browser before assuming your config is wrong. |
| Windows: `pytest` / `python` / `playwright` "is not recognized as the name of a cmdlet..." | Your virtual environment isn't activated in this shell, or the package genuinely isn't installed. Run `.venv\Scripts\Activate.ps1` (PowerShell) or `.venv\Scripts\activate.bat` (cmd.exe) first — you should see `(.venv)` appear in your prompt — then re-run `pip install -r requirements.txt`. If PowerShell refuses to run the activation script with an execution-policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first (affects only that terminal session). |
| `psycopg2.OperationalError: connection ... refused` on `localhost:5432` | No Postgres server is running, and `DATABASE_URL` is set (even to the placeholder in `.env.example`). Comment out `DATABASE_URL` in `.env` entirely to fall back to SQLite, or actually start a Postgres server (Docker: `docker run --name job-hunter-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=job_hunter -p 5432:5432 -d postgres:16-alpine`, then set `DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/job_hunter`) |

---

## Sources (Phase 1)

Four sources, each behind the same `JobSource` interface:

| Source | How it works |
|---|---|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` — public, no auth |
| Lever | `GET api.lever.co/v0/postings/{company}?mode=json` — public, no auth |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{board_name}` — public, no auth |
| Workday | Internal `CXS` JSON endpoint the tenant's own career site calls — see below |

For Greenhouse/Lever/Ashby, the company/board slug is whatever appears in
that company's public job board URL (e.g. `boards.greenhouse.io/stripe` →
slug is `stripe`).

**Workday needs three pieces, not one slug** — `tenant|wd_host|site` — since
there's no single fixed URL pattern across tenants. Find them by opening
the company's actual careers page:

```
https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
         ^^^^^^ ^^^                   ^^^^^^^^^^^^^^^^^^^^^^^^
         tenant  wd_host               site
```

→ `WORKDAY_COMPANIES=nvidia|wd5|NVIDIAExternalCareerSite`

Workday's list endpoint doesn't include full descriptions — getting one
costs a second request per job, which is why `WORKDAY_DETAIL_DELAY_SECONDS`
exists as an extra courtesy delay on top of `REQUEST_DELAY_SECONDS`. Many
Workday tenants run bot detection more aggressively than the other three
sources, so this adapter is deliberately slower.

No Postgres yet? Leave `DATABASE_URL` unset in `.env` — it falls back to a
local SQLite file (`job_hunter.db`).

Re-running the Hunter anytime is safe and idempotent — dedup is enforced
at the database level (`source` + `external_id`), so you won't get
duplicate rows. Fields like title/location/description refresh on
postings you've already seen; `status` never resets on a re-run, since
that belongs to the Evaluator, not the Hunter.

## Phase 2 reference — Evaluator

Scores every `PENDING_EVALUATION` job against your resume with an LLM and
marks it `APPROVED_FOR_APPLY` (score > threshold) or `TRASHED`.

**Supports both Anthropic and OpenAI** behind one interface
(`app/llm/base.py`) — same adapter pattern as the Hunter's sources. Switch
providers by changing `LLM_PROVIDER` in `.env`; no code changes needed.

`APPROVAL_THRESHOLD` (default 85) is exclusive — a job must score *above*
it to be approved, matching the original spec. Failed evaluations (bad API
response, network error) are left `PENDING_EVALUATION` so they retry on
the next run rather than silently disappearing.

## Phase 3 reference — Executor

Opens one `APPROVED_FOR_APPLY` job's application page in a real (visible,
non-headless by default) browser, classifies every form field it finds,
and fills the ones it's confident about:

- Name, email, phone, LinkedIn/GitHub/portfolio URLs, resume upload
- Cover letter / open-ended questions, **if** a story bank is configured
  (see the RAG section below) — otherwise left blank for you
- Dropdown (`<select>`) options the heuristic classifier can't place, via
  an LLM comparing your resume against the field's actual options — see
  "LLM dropdown mapping" below
- Deliberately **never** answers EEO/demographic questions (race, gender,
  veteran status, disability) or work-authorization questions — these are
  never even sent to an LLM, regardless of what's configured, because
  they're legally significant and belong to a human, not a guess
- Deliberately **never** clicks Submit — it pauses with the browser open
  and asks you to review and submit yourself

Run `--dry-run` first on anything you haven't tried before — it reports
exactly what would be filled without touching the page.

Made a mistake or applied outside the tool? Fix a job's status manually:

```bash
python -m app.mark_status --job-id 12 --status APPLIED
```

## RAG reference — cover letter / open-question answers

Optional. Without `story_bank.json`, the Executor just skips these
fields — nothing breaks if you never set this up.

**How it works:** a field's question text (e.g. "Describe a time you led a
project") is matched against your stories using TF-IDF cosine similarity —
not a real embedding model, deliberately. A story bank is small (a
handful of entries), so keyword-overlap retrieval works fine at that
scale, and it means no embedding API call and no model download; this
runs fully offline. The best-matching story is then handed to your
configured LLM (`LLM_PROVIDER` — same one Phase 2 uses) with instructions
to draft an answer using *only* details in that story, never inventing
facts.

Every RAG-drafted field is filled with the text prefixed in the terminal
report as `AI DRAFT from story '...' - REVIEW BEFORE SUBMITTING` — treat
these as a first draft, not a final answer.

## LLM dropdown mapping

Optional — automatically enabled whenever `resume.md` exists, since it
reuses the same resume text Phase 2 already loads. Handles `<select>`
dropdowns the heuristic classifier can't place (e.g. "Years of Python
experience?"), which the original spec called out as needing more than
keyword matching.

**Every dropdown goes through a hard safety gate before an LLM is ever
called**, checked in `app/executor/field_classifier.py`'s
`is_sensitive_dropdown()`: any field whose label mentions race, gender,
veteran status, disability, work authorization, visa sponsorship,
citizenship, or similar is **never sent to the LLM at all** — not just
never auto-filled, never even included in a request. This is enforced in
the caller (`fill_application`), not inside the mapper itself, so the
protection holds regardless of what mapper implementation is used.

For everything else, the LLM must pick one of the field's *actual*
options verbatim (enforced via JSON schema `enum`) or say `NONE` — it can
never invent a choice that isn't on the page. It also self-reports
confidence, and only a `high`-confidence pick gets auto-selected; anything
lower is left for you. Filled dropdowns show up in the terminal report as
`LLM PICK: '...' - REVIEW BEFORE SUBMITTING`.

## Inspecting the database

```bash
python -m app.inspect_jobs                          # summary + recent jobs
python -m app.inspect_jobs --status APPROVED_FOR_APPLY
python -m app.inspect_jobs --status TRASHED --limit 50
```

## Tests

```bash
pytest -v
```

88 tests, covering all four phases plus their integration:
- **Sources** — each adapter (including Workday's pagination and
  detail-fetch failure handling) against fixture data matching that
  provider's own documented response schema
- **DB / dedup** — upsert logic against an in-memory SQLite DB
- **LLM clients** — both providers' response parsing against realistic
  mocked SDK responses, plus a `StubLLMClient` for testing the Evaluator's
  threshold logic with zero API cost
- **Field classifier** — pure logic, including negative cases like making
  sure a "Company Name" field never gets filled with your own name
- **Executor DOM fill** — runs a real (headless) Chromium against a local
  HTML fixture in `tests/fixtures/`, so it verifies actual browser
  interaction without touching any live site. This needs a Chromium binary
  (`python -m playwright install chromium`) — if one isn't available, this
  file's tests skip cleanly rather than failing; everything else always
  runs.
- **RAG** — story bank loading, TF-IDF retrieval accuracy (verified
  against three genuinely distinct stories, not just "does it return
  something"), both providers' `draft_answer()` parsing, and the full
  retrieve-then-generate wiring in `AnswerService`
- **LLM dropdown mapping** — confidence/validity gating in isolation, both
  providers' `select_dropdown_option()` parsing, and — critically — a live
  browser test confirming a work-authorization dropdown is never sent to
  the mapper at all, not just never filled
- **Integration** — a single job pushed through the real `upsert_job()` →
  `evaluate_job()` → `fill_application()` functions each phase's CLI
  actually calls, proving the phases hand off to each other correctly and
  not just that each one works in isolation

No live network calls or live company sites are touched by any test.

## Project layout

```
app/
  config.py          # env-based settings
  db/
    models.py         # Job table + status enum
    session.py         # engine/session + init_db()
  sources/
    base.py            # RawJob schema + JobSource protocol
    greenhouse.py
    lever.py
    ashby.py
    workday.py          # tenant/wd_host/site + pagination + detail fetch
  llm/
    base.py             # EvaluationResult schema + LLMClient protocol
    prompts.py           # shared prompts + JSON schema, same for both providers
    openai_client.py
    anthropic_client.py
    factory.py            # picks provider based on LLM_PROVIDER env var
  rag/
    story_bank.py         # Story schema + loader
    retriever.py            # TF-IDF story retrieval, fully offline
    answer_service.py        # ties retriever + LLM draft_answer() together
  hunter.py             # orchestrates sources -> DB
  evaluator.py           # orchestrates DB -> LLM -> DB
  executor/
    candidate.py          # CandidateProfile schema + loader
    field_classifier.py    # pure logic: form field metadata -> FieldRole
    dropdown_mapper.py      # LLM dropdown-option selection, confidence-gated
    runner.py                 # Playwright orchestration, human-review pause
  inspect_jobs.py         # CLI to view job counts/status from the DB
  mark_status.py           # CLI to manually correct a job's status
resume.md.example
candidate_profile.json.example
story_bank.json.example
tests/
  fixtures/
    sample_application_form.html  # local form used to test the Executor
```

## Adding a new source

Implement the `JobSource` protocol in `app/sources/base.py` (one method:
`fetch_jobs(company_slug) -> list[RawJob]`), then add an instance to
`SOURCE_COMPANIES` in `app/hunter.py`. Nothing else needs to change —
the DB layer and (future) Evaluator only ever see the normalized
`RawJob`/`Job` shape.

## Next milestones

- **Radio buttons and multi-select checkboxes** — the dropdown mapper only
  handles `<select>` elements. Radio groups need different DOM extraction
  (the question text isn't associated with any single input the way a
  `<select>`'s options are), so this is a distinct piece of work, not a
  copy-paste of the dropdown logic.
- **Real embeddings for story retrieval** — TF-IDF works well at
  story-bank scale (a handful of entries) but would need a real embedding
  model if the story bank grows large or the matching needs to handle
  paraphrasing better than keyword overlap. `StoryRetriever` is the one
  class to swap.
- **Celery + Redis** for concurrent processing, once running one job at a
  time in each phase becomes the bottleneck.