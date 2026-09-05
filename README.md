# AutoApply JobHunter — Phases 1–4

An automated job-application pipeline with a management dashboard. This
repo currently covers:

- **Phase 1 (Hunter):** scrapes job postings from public/internal ATS
  endpoints — Greenhouse, Lever, Ashby, Workday, SmartRecruiters, and
  Workable — into Postgres/SQLite.
- **Phase 2 (Evaluator):** a fast keyword pre-filter screens out obvious
  non-matches before any LLM call, then scores every remaining posting
  against your resume — via OpenAI, Anthropic, a local Ollama model, or
  Gemini, including a hybrid local+cloud mode — and marks it approved,
  held for review, or trashed.
- **Phase 3 (Executor):** opens an approved application in a real browser
  and pre-fills the fields it's confident about — including, optionally,
  RAG-drafted answers to cover letters/open-ended questions and LLM-picked
  dropdown options, grounded in your real stories and resume. It never
  submits — you review and click submit yourself. EEO/demographic and
  work-authorization questions are never sent to any LLM at all, regardless
  of what's configured.
- **Phase 4 (Dashboard):** an Angular UI over a FastAPI backend for
  reviewing pending/flagged jobs and triggering the Hunter, with
  Google/GitHub OAuth login and per-account data isolation.

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
- `GREENHOUSE_COMPANIES` / `LEVER_COMPANIES` / `ASHBY_COMPANIES` /
  `SMARTRECRUITERS_COMPANIES` / `WORKABLE_COMPANIES` — comma-separated
  slugs, start small, e.g. `GREENHOUSE_COMPANIES=stripe`. Find a slug by
  checking `boards.greenhouse.io/{slug}`, `jobs.lever.co/{slug}`,
  `jobs.ashbyhq.com/{slug}`, `api.smartrecruiters.com/v1/companies/{slug}/postings`,
  or `apply.workable.com/{slug}` for a company you know uses that ATS.
- `WORKDAY_COMPANIES` (optional, and slower than the others — see the
  Sources section below for its `tenant|wd_host|site` format)
- `LLM_PROVIDER` — `anthropic`, `openai`, `ollama`, `gemini`, or `hybrid`
  (see the LLM Providers section below for what each needs)
- Leave `DATABASE_URL` unset for now; it falls back to a local SQLite file
  (`job_hunter.db`) so you don't need Postgres running to test this.

**3. Add your resume**

```bash
cp resume.md.example resume.md
```

Replace the placeholder content with your real experience — plain text or
markdown, no special formatting needed. This is used for LLM scoring only,
separate from the PDF/DOCX you actually apply with (step 8).

**4. Run the Hunter**

```bash
python -m app.hunter
```

You should see one log line per company, like:

```
2026-08-12 10:02:11 INFO greenhouse  stripe               42 seen,  42 new
```

If you see `0 seen` for every company, the slug is probably wrong — check
step 2's URLs against the actual company career page. **One exception:**
Workable's widget API returns a valid `200` for almost any slug, even a
wrong one — it just returns a *different* company's real jobs instead of
an error. Open `apply.workable.com/{slug}` in a browser once per new
Workable company to confirm it's the one you meant, rather than trusting
the Hunter log alone.

**5. Check what landed in the database**

```bash
python -m app.inspect_jobs
```

This prints a count of jobs by status, plus the most recent ones. Right
now everything should show as `PENDING_EVALUATION`.

**6. Run the Evaluator**

```bash
python -m app.evaluator --limit 10
```

Always sanity-check on a small batch first — cost, time, and cloud quota
(if using `gemini`/`hybrid`) all scale with how many jobs you run against.
One log line per job:

```
2026-08-12 10:05:44 INFO Senior Backend Engineer                score= 88 -> APPROVED_FOR_APPLY
```

Once you're comfortable, drop `--limit` (or raise it) for the full queue.

**7. See what got approved**

```bash
python -m app.inspect_jobs --status APPROVED_FOR_APPLY
```

If nothing got approved, that's not necessarily a bug — it means nothing
scored above `APPROVAL_THRESHOLD` (default 85) against your resume. Try
lowering it in `.env` temporarily to see mid-range scores, or check the
Evaluator's log output / a job's `rationale` column for the reasoning
behind a specific score.

**8. Set up your candidate profile**

```bash
cp candidate_profile.json.example candidate_profile.json
```

Fill in your real contact details. `resume_file_path` must point to an
actual PDF/DOCX file that exists on disk — not `resume.md` from step 3.

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

**11. (Optional) Run the dashboard**

```bash
uvicorn app.api.main:app --reload   # backend, one terminal
cd dashboard && npm install && ng serve   # frontend, another terminal
```

Requires Google/GitHub OAuth credentials in `.env` — see `GUIDE.md` for
setup. Set `OWNER_EMAIL` and/or `OWNER_GITHUB_USERNAME` so your own login
resolves to the account new jobs are attributed to.

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError` | Forgot to activate `.venv` or run `pip install -r requirements.txt` |
| Hunter: `0 seen` for a company | Wrong slug — re-check the company's actual career board URL |
| Hunter: `httpx.HTTPStatusError` (404/401/422) | Fails fast now — permanent errors (wrong slug, bad tenant/site, missing auth) no longer burn a full retry budget. A 404 means the board doesn't exist under that slug; 422 on Workday often means a wrong `site` value |
| Evaluator: `FileNotFoundError` re: resume | Forgot step 3 (`cp resume.md.example resume.md`) |
| Evaluator: `ValueError` re: API key | `.env` has the wrong key set for your `LLM_PROVIDER`, or the key is blank |
| Evaluator runs but job stays `PENDING_EVALUATION` | Check the logged error — that job retries automatically, up to `MAX_EVAL_FAILURES` times before it's auto-trashed with an explanatory rationale |
| Evaluator: `429 RESOURCE_EXHAUSTED` from Gemini, repeated across many jobs | Daily free-tier quota exhausted (as low as 20 requests/day). The hybrid client detects this specifically (not a short rate-limit 429) and stops attempting further cloud calls for the rest of that run rather than wasting retries — those jobs simply retry on your next run once quota resets |
| Executor: `FileNotFoundError` re: candidate profile | Forgot step 8 (`cp candidate_profile.json.example candidate_profile.json`) |
| Executor: `FileNotFoundError` re: `resume_file_path` | The path in `candidate_profile.json` must point to a real PDF/DOCX that exists on disk — separate from `resume.md` |
| Executor: browser window doesn't appear | First run `python -m playwright install chromium` to download the browser binary |
| Executor: dry-run reports nothing in either Filled or Skipped | The job's `apply_url` likely points to a search/listing page rather than the actual application form — check what Hunter stored vs. what the real "Apply" link on the company's site is |
| Executor fills fields incorrectly | The classifier is heuristic, not perfect — that's exactly why it pauses for your review instead of submitting automatically |
| Workday: `ValueError` re: 'tenant\|wd_host\|site' | Check the format in `WORKDAY_COMPANIES` — it needs all three pieces, pipe-separated |
| Workday: very slow Hunter run | Expected — per-job description fetching plus conservative delays add up fast for large companies. Set `WORKDAY_FETCH_DESCRIPTIONS=false` for a quicker listing-only pass |
| Workable: a company's jobs look wrong | The Workable widget API returns `200` for almost any slug, including nonexistent ones — it silently returns an unrelated company's real jobs rather than erroring. Verify the slug by opening `apply.workable.com/{slug}` directly |
| SmartRecruiters: descriptions missing | Confirm `SMARTRECRUITERS_FETCH_DESCRIPTIONS=true` — the list endpoint doesn't include them, only the per-posting detail endpoint does |
| Greenhouse/Lever: `404 Not Found` even though the company definitely exists | The token often isn't the company's name — e.g. DoorDash's Greenhouse token is `doordashusa`, not `doordash`. Some companies have also switched ATS platforms entirely. Verify by opening the board URL directly before assuming your config is wrong |
| Windows: `pytest` / `python` / `playwright` "is not recognized..." | Your virtual environment isn't activated in this shell. Run `.venv\Scripts\Activate.ps1` (PowerShell) or `.venv\Scripts\activate.bat` (cmd.exe) — you should see `(.venv)` in your prompt |
| Evaluator (Ollama): `ConnectionError: Could not reach Ollama` | Ollama isn't running. Check for its tray icon, or start it manually with `ollama serve`. Confirm you've pulled the model set in `OLLAMA_MODEL` |
| Evaluator (Ollama): slow, or occasional job "timed out" | Expected on CPU-only hardware — see the Local LLM section below for realistic per-job timing. A small number of unexplained hangs on otherwise-clean content can happen; the 3-strikes failure counter contains the cost automatically rather than retrying forever |
| `psycopg2.OperationalError: connection ... refused` | No Postgres server running, and `DATABASE_URL` is set. Comment it out to fall back to SQLite, or start a real Postgres instance |

---

## Sources (Phase 1)

Six sources, each behind the same `JobSource` interface:

| Source | How it works |
|---|---|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true` — public, no auth |
| Lever | `GET api.lever.co/v0/postings/{company}?mode=json` — public, no auth |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{board_name}` — public, no auth |
| Workday | Internal `CXS` JSON endpoint the tenant's own career site calls — see below |
| SmartRecruiters | `GET api.smartrecruiters.com/v1/companies/{id}/postings` — list endpoint lacks descriptions, per-posting detail fetch toggled via `SMARTRECRUITERS_FETCH_DESCRIPTIONS` (mirrors Workday's pattern, including failure-isolation on a bad detail fetch) |
| Workable | `GET apply.workable.com/api/v1/widget/accounts/{slug}?details=true` — single call, full description included, same simplicity as Greenhouse/Lever/Ashby |

For Greenhouse/Lever/Ashby/SmartRecruiters, the company/board slug is
whatever appears in that company's public job board URL.

**Workday needs three pieces, not one slug** — `tenant|wd_host|site`:

```
https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
         ^^^^^^ ^^^                   ^^^^^^^^^^^^^^^^^^^^^^^^
         tenant  wd_host               site
```

→ `WORKDAY_COMPANIES=nvidia|wd5|NVIDIAExternalCareerSite`

Workday's list endpoint doesn't include full descriptions — getting one
costs a second request per job, which is why `WORKDAY_DETAIL_DELAY_SECONDS`
exists as an extra courtesy delay on top of `REQUEST_DELAY_SECONDS`. Many
Workday tenants run bot detection more aggressively than the other
sources, so this adapter is deliberately slower.

**All retryable HTTP calls across every source share one predicate**
(`app/sources/_retry.py`) distinguishing transient failures (429, 5xx,
network errors, and 403 — bot-management challenges that clear on retry)
from permanent ones (404, 401, 422) — permanent failures fail on the
first attempt instead of burning a full retry-with-backoff budget on a
misconfigured slug.

No Postgres yet? Leave `DATABASE_URL` unset in `.env` — it falls back to a
local SQLite file (`job_hunter.db`).

Re-running the Hunter anytime is safe and idempotent — dedup is enforced
at the database level (`source` + `external_id`).

## Phase 2 reference — Evaluator

Scores every `PENDING_EVALUATION` job against your resume and sorts it
into one of three outcomes, not two:

- **below `REVIEW_THRESHOLD`** → `TRASHED`
- **`REVIEW_THRESHOLD` to `APPROVAL_THRESHOLD`** → stays
  `PENDING_EVALUATION`, held in the dashboard's review queue for a human
- **above `APPROVAL_THRESHOLD`** → `APPROVED_FOR_APPLY`

Set `REVIEW_THRESHOLD=0` (or leave unset) to restore the original
hard-cutoff behavior with no review band.

### Fast pre-filter

Runs before any LLM call, in `app/evaluator.py`. Two independent checks,
either one trashes a job for free:
1. **Title match** against `EXCLUDE_TITLE_KEYWORDS` — a short, deliberately
   conservative list of unambiguous non-engineering roles (sales,
   recruiting, accounting, legal, HR, etc.)
2. **No signal at all** — neither the title nor the description contains a
   single entry from the broad `SKILL_KEYWORDS` list (languages,
   frameworks, cloud/devops, generic role signals). This is a "does this
   look like a tech job at all" check, not "does this match my exact
   stack" — that judgment stays with the LLM.

Both lists are tunable directly in `app/evaluator.py`, and are deliberately
biased toward false positives (an ambiguous job reaches the LLM) over
false negatives (a real match silently discarded with no human ever
seeing it).

### Failure handling

A job that fails evaluation (network issue, provider error, an
unexplained hang) retries automatically on the next run. After
`MAX_EVAL_FAILURES` (default 3) consecutive failures, it's auto-trashed
with an explanatory rationale rather than retrying forever — **except**
for cloud-quota exhaustion specifically, which is deliberately exempt
from this counter (see Gemini section below) since it's an external,
resets-on-its-own condition unrelated to the job itself.

```bash
python -m app.evaluator --limit 10
```

## LLM Providers

Five options behind one `LLMClient` interface (`app/llm/base.py`) — switch
by changing `LLM_PROVIDER` in `.env`, no code changes needed.

### Anthropic / OpenAI

Standard API-key setup — `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` or
`OPENAI_API_KEY`/`OPENAI_MODEL`.

### Local LLM (Ollama)

Free, private, no API key — trades cost for speed and (usually) some
answer quality versus a cloud provider.

**Setup:**
```bash
ollama pull llama3.1:8b
```
```dotenv
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
OLLAMA_KEEP_ALIVE=5m
```

**Honest, measured expectations on CPU-only hardware (no dedicated GPU):**
roughly 90–160 seconds per job is realistic, not 15–30 seconds — that's a
real measured range, not a worst case. If you have a dedicated NVIDIA/AMD
GPU, Ollama uses it automatically and speeds jump substantially; check
`ollama ps` while a request runs to confirm GPU vs. CPU usage (`100% CPU`
with no discrete GPU in your hardware means this is close to a hardware
ceiling, not a bug to chase).

`OLLAMA_KEEP_ALIVE` (default `5m`) matters more than it looks — setting it
to `0` forces a full model reload from disk before *every single request*,
which measurably adds to per-job time. `5m` keeps the model warm between
consecutive Evaluator jobs and only unloads once genuinely idle.

Structured output (the JSON score schema) is enforced via constrained
decoding, so you'll reliably get valid JSON regardless of model quality —
what depends on model quality is whether the score/reasoning is actually
*good*. Review outputs critically, especially at first; a small local
model's confidence doesn't always track its own stated reasoning (see
Hybrid mode below for how this project mitigates that).

### Gemini

Free tier (Flash-family models), no credit card needed — get a key at
https://aistudio.google.com/apikey. Model IDs and rate limits shift over
time; if `GEMINI_MODEL` starts 404ing, check https://ai.dev/rate-limit for
currently available models rather than trusting a name to stay valid
indefinitely.

**Free-tier daily quota is low** — as low as 20 requests/day for a given
model, measured directly for this project (published numbers online are
unreliable and conflict with each other). Once exhausted, every escalation
would otherwise burn a full retry-with-backoff cycle for nothing — this is
detected specifically (distinguished from a short-lived rate limit by
inspecting the error's quota-ID for a daily-scoped quota) and short-circuits
immediately instead, with zero further HTTP calls for the rest of that run.

**Moving to a paid tier:** just a `.env` change (`GEMINI_MODEL=` plus
billing enabled on the linked Google Cloud project) — no code change
needed. `gemini-3.1-flash-lite` is a real, current, low-cost option if
evaluating your queue size makes sense as an ongoing cost rather than a
free-tier constraint.

### Hybrid

```dotenv
LLM_PROVIDER=hybrid
HYBRID_LOCAL_PROVIDER=ollama
HYBRID_CLOUD_PROVIDER=gemini
```

Local model scores every job first (free/unlimited); **any score at or
above `REVIEW_THRESHOLD` gets a cloud second opinion** rather than being
trusted locally — this is deliberately stricter than "only the ambiguous
band between the two thresholds." Local scoring is only fully trusted for
a clear reject.

This exists because local small-model scoring, in real testing on this
project, produced confidently wrong high scores via more than one failure
mode — stating a disqualifying gap in its own reasoning and then scoring
85-100 anyway, and separately, confabulating an unsupported equivalence
with no admitted gap at all. Both landed above the review band, which
originally had no cloud check at all above it. Given the real cost of an
incorrect auto-approval (feeding a bad match into Phase 3), local scoring
is no longer trusted for anything except a confident reject.

## Inspecting the database

```bash
python -m app.inspect_jobs                          # summary + recent jobs
python -m app.inspect_jobs --status APPROVED_FOR_APPLY
python -m app.inspect_jobs --status TRASHED --limit 50
python -m app.mark_status --job-id 12 --status APPLIED   # manual correction
python -m app.flag_approved_for_review              # dry run
python -m app.flag_approved_for_review --apply      # bulk re-review, see script docstring
```

`flag_approved_for_review.py` is a one-off remediation tool, not part of
the regular pipeline — moves every `APPROVED_FOR_APPLY` job back to
`PENDING_EVALUATION` for human review. Useful after any change to
scoring logic you don't yet fully trust against already-approved jobs.

## Phase 3 reference — Executor

Opens one `APPROVED_FOR_APPLY` job's application page in a real (visible,
non-headless by default) browser, classifies every form field it finds,
and fills the ones it's confident about:

- Name, email, phone, LinkedIn/GitHub/portfolio URLs, resume upload
- Cover letter / open-ended questions, **if** a story bank is configured
- Dropdown (`<select>`) options the heuristic classifier can't place, via
  an LLM comparing your resume against the field's actual options
- Deliberately **never** answers EEO/demographic or work-authorization
  questions — checked structurally in the caller before any LLM is
  involved, not something every dropdown-mapper implementation has to
  remember to do right
- Deliberately **never** clicks Submit

**Known limitation:** the dropdown mapper only handles `<select>`
elements — radio buttons and checkboxes are always left for you. This
happens to cut in the safe direction, since EEO questions are often
radio-button-based in practice.

**Status as of this writing: code-complete, never yet run successfully
against a real live application end to end.** The one dry-run attempt so
far returned nothing in either the Filled or Skipped report, most likely
because the test job's `apply_url` pointed to a search/listing page
rather than an actual application form — not yet root-caused. Treat this
phase as needing real verification before trusting it against a job you
actually care about.

Run `--dry-run` first on anything you haven't tried before.

## RAG reference — cover letter / open-question answers

Optional. Without `story_bank.json`, the Executor just skips these
fields.

A field's question text is matched against your stories using TF-IDF
cosine similarity — not a real embedding model, deliberately: a story
bank is small, so keyword-overlap retrieval works fine at that scale, and
it runs fully offline with no extra API call. The best-matching story is
handed to your configured LLM with instructions to draft an answer using
*only* details in that story, never inventing facts.

Every RAG-drafted field is filled with text prefixed as
`AI DRAFT from story '...' - REVIEW BEFORE SUBMITTING`.

## LLM dropdown mapping

Automatically enabled whenever `resume.md` exists. Every dropdown goes
through a hard safety gate (`app/executor/field_classifier.py`'s
`is_sensitive_dropdown()`) before an LLM is ever called — any field
mentioning race, gender, veteran status, disability, work authorization,
visa, sponsorship, citizenship, or similar is never sent to the LLM at
all. Enforced in the caller, not inside the mapper, so the protection
holds regardless of mapper implementation.

For everything else, the LLM must pick one of the field's actual options
verbatim (enforced via JSON schema `enum`) or say `NONE`. Only a
`high`-confidence pick gets auto-selected. Filled dropdowns show up as
`LLM PICK: '...' - REVIEW BEFORE SUBMITTING`.

## Phase 4 — Dashboard & Auth

FastAPI backend (`app/api/`) + Angular dashboard (`dashboard/`), with
Google/GitHub OAuth login (`app/auth.py`, Authlib). One "owner" account —
identified by `OWNER_EMAIL` and/or `OWNER_GITHUB_USERNAME`, since GitHub
doesn't always return an email even with the right scope requested — is
the account newly scraped/evaluated jobs are attributed to; anyone else
who signs in gets a real account with an empty dashboard. Every job/hunter
API route is scoped to the current user; a job belonging to someone else
404s rather than leaking via 403.

`User.email` is nullable, with `(provider, provider_id)` as a fallback
identity — needed because a GitHub login with no public/returned email is
a real case, not a hypothetical one. See `GUIDE.md` for OAuth app setup.

## Tests

```bash
pytest -v
```

Run this for the current count — coverage spans all six sources
(including SmartRecruiters/Workable and the shared retry predicate), both
Evaluator paths (pre-filter, threshold logic, hybrid escalation and its
quota-exhaustion circuit breaker), the dashboard's Angular components, and
the auth/owner-resolution logic, on top of the original Phase 1–3 suite
(sources, DB/dedup, LLM client parsing, field classifier, Executor DOM
fill against a local HTML fixture, RAG retrieval, dropdown mapping's
sensitive-field exclusion, and cross-phase integration). No live network
calls or live company sites are touched by any test.

## Project layout

```
app/
  config.py
  db/
    models.py           # Job + User tables, status enum
    session.py
  sources/
    base.py
    _retry.py            # shared transient-vs-permanent retry predicate
    greenhouse.py
    lever.py
    ashby.py
    workday.py
    smartrecruiters.py
    workable.py
  llm/
    base.py               # LLMClient protocol, EvaluationResult, CloudQuotaExhaustedError
    prompts.py
    openai_client.py
    anthropic_client.py
    ollama_client.py
    gemini_client.py
    hybrid_client.py       # local-first, cloud-confirms anything >= review_threshold
    factory.py
  rag/
    story_bank.py
    retriever.py
    answer_service.py
  api/
    main.py
    deps.py
    schemas.py
    routes/
      auth.py
      hunter.py
      jobs.py
  auth.py                 # OAuth user resolution, owner bootstrapping
  hunter.py
  evaluator.py             # pre-filter + failure-give-up + orchestration
  executor/
    candidate.py
    field_classifier.py
    dropdown_mapper.py
    runner.py
  inspect_jobs.py
  mark_status.py
  flag_approved_for_review.py
dashboard/                 # Angular 21 frontend
resume.md.example
candidate_profile.json.example
story_bank.json.example
tests/
```

## Adding a new source

Implement the `JobSource` protocol in `app/sources/base.py` (one method:
`fetch_jobs(company_slug) -> list[RawJob]`), then add an instance to
`SOURCE_COMPANIES` in `app/hunter.py`. Nothing else needs to change.

## Next milestones

- **Full real-world Executor run** — genuinely never completed against a
  live application yet; the search-page-vs-form-URL question needs
  resolving first.
- **Radio buttons and multi-select checkboxes** — dropdown mapper only
  handles `<select>` elements.
- **Real embeddings for story retrieval** — TF-IDF works well at
  story-bank scale but would need a real embedding model if the bank
  grows large or needs to handle paraphrasing better than keyword overlap.
- **Local-model trust calibration** — hybrid mode currently trusts local
  scoring only for a clear reject; worth revisiting if a local model
  demonstrates reliable high-end scoring against known-good matches over
  more evidence than a single synthetic test.
- **Celery + Redis** for concurrent processing, once running one job at a
  time in each phase becomes the bottleneck.