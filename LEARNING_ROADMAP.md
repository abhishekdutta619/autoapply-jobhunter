# Job Hunter — Learning Roadmap

A running log of what each phase of this project actually teaches, so the
goal stays "understand this deeply" and not just "get it running." Update
this file as we build Phase 2, 3, and Workday.

---

## Phase 0 — Planning & Feasibility (before any code)

This phase wasn't code, but it's the part that keeps the whole project out
of trouble later. Worth treating as seriously as the engineering.

- [ ] **Reading a platform's Terms of Service before scraping it.** The
      difference between "public data reachable via a documented API" and
      "data behind active anti-bot enforcement" isn't a technical
      distinction — it's a legal/policy one, and it's why we ruled out
      LinkedIn/Naukri scraping but not Greenhouse/Lever/Ashby.
- [ ] **Architecture-first thinking.** Deciding the Hunter/Evaluator/Executor
      split *before* writing code — three independently-failing stages
      instead of one script that dies on the first bad job.
- [ ] **Verifying documentation instead of assuming.** When I wasn't fully
      sure of Ashby's or Lever's exact response fields, I looked them up
      rather than guessing — worth building as a habit for any API
      integration, not just this one.

**Try it yourself:** pick any two websites you use daily and check their
`robots.txt` (`site.com/robots.txt`) and Terms of Service for what they say
about automated access. Most people never look.

---

## Phase 1 — The Hunter

### 1. Configuration & environment management
- [ ] Why config (DB URLs, company lists) lives in environment variables,
      not hardcoded in source — `python-dotenv` + `.env`
- [ ] Sensible defaults for local dev (SQLite fallback) vs. real deployment
      (Postgres)

**Try it:** add a new setting yourself — e.g. `MAX_JOBS_PER_COMPANY` — and
wire it through `app/config.py` into `hunter.py`.

### 2. HTTP clients & third-party APIs
- [ ] Making GET requests with `httpx`, passing query params, setting
      timeouts
- [ ] `response.raise_for_status()` and what HTTP status codes actually mean
- [ ] Public/unauthenticated vs. authenticated API endpoints

**Try it:** add a new field to `RawJob` (e.g. `employment_type`) and
populate it from Greenhouse's job metadata.

### 3. Resilience & retries
- [ ] Why network calls fail transiently (timeouts, momentary 5xx errors)
- [ ] `tenacity`'s retry decorator and **exponential backoff** — why backing
      off matters more than retrying immediately
- [ ] Politeness: the `time.sleep()` between requests and why hammering a
      free public API is a bad idea even when it's technically allowed

**Try it:** point `GreenhouseSource().fetch_jobs("this-company-does-not-exist")`
at a bad slug and watch the retry attempts in the logs before it gives up.

### 4. Data modeling & validation
- [ ] `pydantic.BaseModel` for typed, validated data (`RawJob`)
- [ ] `str | None` optional typing
- [ ] Why a **normalized intermediate schema** matters — every adapter
      speaks a different dialect, but everything downstream only ever sees
      `RawJob`

### 5. Databases & ORMs
- [ ] SQLAlchemy 2.0 declarative models — `Mapped[]`, `mapped_column()`
- [ ] Engine vs. `Session` vs. `sessionmaker`
- [ ] Using a Python `Enum` to represent a state machine (`JobStatus`)
- [ ] `UniqueConstraint` — enforcing dedup at the database level, not just
      in application code
- [ ] Timezone-aware datetimes (`DateTime(timezone=True)`) — a classic
      source of real-world bugs when skipped
- [ ] The **upsert pattern**: select first, then decide insert vs. update —
      and why the Hunter updates a job's title/description on re-scrape but
      never touches its `status`, since that belongs to later phases

**Try it:** open a Python shell, `from app.db.session import get_session`,
and write a `select()` query yourself to list every job currently in the DB.

### 6. Software design patterns
- [ ] `Protocol`-based interfaces (structural typing) — `JobSource`
- [ ] The **adapter pattern** — one interface, four implementations
      (Greenhouse/Lever/Ashby/Workday)
- [ ] Separation of concerns — `config` / `db` / `sources` / orchestration
      as distinct modules
- [ ] Why this design means adding Workday later touches *zero* lines in
      Phase 2 or 3

### 7. Testing
- [ ] `pytest` basics — fixtures, assertions
- [ ] Mocking external calls with `unittest.mock.patch` so tests are
      deterministic and don't depend on a live network or rate limits
- [ ] In-memory SQLite (`sqlite:///:memory:`) for fast, isolated DB tests
- [ ] Testing against **fixture data that matches documented schemas**,
      rather than hitting live APIs in every test run

**Try it:** write one more test — assert that if Greenhouse returns a job
with no `location` key at all, `RawJob.location` ends up `None` instead of
crashing.

### 8. Project hygiene
- [ ] Pinning dependencies in `requirements.txt`
- [ ] `.env.example` as documentation-as-code
- [ ] README-driven project structure
- [ ] Python package layout (`__init__.py`, module boundaries)

---

## Suggested study order (not just run order)

1. Read `app/sources/base.py` + `app/sources/greenhouse.py` together — the
   smallest complete slice of the whole pipeline.
2. Run `pytest -v` and actually read what each assertion is proving.
3. Trace one call through `hunter.py` by hand: `fetch_jobs()` → `RawJob` →
   `upsert_job()` → a row in `jobs`.
4. Modify one adapter end-to-end yourself (pick a new field: add it to
   `RawJob`, the DB model, the adapter parsing, and a test).
5. Only then move on to Phase 2.

---

## Phase 2 — The Evaluator

### 1. Structured output from an LLM
- [ ] Why free-text LLM responses are unreliable for code to parse, and how
      **structured outputs** (OpenAI's `response_format: json_schema`,
      Anthropic's forced `tool_choice`) solve that — the model is
      constrained to emit exactly the schema you define
- [ ] Writing a JSON Schema by hand (`RESULT_SCHEMA` in `app/llm/prompts.py`)
      and reusing the *same* schema across two different providers' APIs

**Try it:** loosen `RESULT_SCHEMA` to also require a `red_flags: list[str]`
field, update `EvaluationResult` to match, and see both clients still work
without touching `evaluator.py`.

### 2. Provider abstraction (same pattern as Phase 1, on purpose)
- [ ] `LLMClient` Protocol + two concrete implementations — exactly the
      adapter pattern from `JobSource`, applied to a different problem
- [ ] A **factory function** (`get_llm_client()`) that reads config and
      returns the right implementation — the orchestrator never branches
      on provider itself
- [ ] Why this is the second time you've seen this pattern in one project —
      once you recognize it, you'll start seeing where else it applies

### 3. Prompt design
- [ ] Separating a **system prompt** (stable instructions/role) from a
      **user prompt** (per-request content) — and putting the actual score
      threshold discipline ("be strict," "don't reward keyword-matching")
      in the system prompt, not left implicit
- [ ] Keeping prompt-building logic in one shared module so both providers
      are judged on identical instructions — a fair A/B comparison if you
      ever want to compare them

### 4. Operational resilience for LLM calls
- [ ] Why a failed evaluation should leave a job's status untouched
      (`PENDING_EVALUATION`) rather than guessing or crashing the whole
      run — same "isolate failures per item" idea as the Hunter's
      per-company try/except
- [ ] Rate/cost awareness: sleeping between LLM calls isn't just courtesy
      like the Hunter — it's now real money per request

**Try it:** temporarily break your API key and run the Evaluator — confirm
the job stays `PENDING_EVALUATION` instead of silently being marked
`TRASHED`.

### 5. Testing LLM-dependent code without hitting a real API
- [ ] Mocking SDK response objects with `SimpleNamespace` to mirror the
      real client's attribute structure (`response.choices[0].message`,
      `response.content[0].input`) without needing the actual API
- [ ] A **stub client** (`StubLLMClient`) implementing the same Protocol as
      the real ones — lets you test `evaluate_job`'s threshold logic with
      zero network calls and zero API cost
- [ ] Why this matters even more here than in Phase 1: LLM calls cost
      money and are non-deterministic, so tests *must* avoid the real API

---

## Phase 3 — The Executor

### 1. Browser automation
- [ ] Playwright's sync API — `launch()`, `new_page()`, `goto()`,
      `fill()`, `set_input_files()`
- [ ] Headed vs. headless browsers, and why this project defaults to
      **headed** — a human physically watching and clicking Submit is a
      deliberate safety choice, not just a debugging convenience
- [ ] `page.evaluate()` to run JavaScript inside the page and pull
      structured data back into Python — the `EXTRACT_FIELDS_JS` snippet
      that tags every field with a stable index for later re-selection

**Try it:** open `tests/fixtures/sample_application_form.html` directly in
your own browser and view-source it alongside `EXTRACT_FIELDS_JS` — trace
by hand which DOM attributes each field would produce.

### 2. Separating "pure logic" from "hard to test" glue code
- [ ] `field_classifier.py` (regex/heuristic decisions, zero I/O) vs.
      `runner.py` (Playwright calls, `input()`, DB writes) — the classifier
      is trivially unit-testable; the runner mostly isn't, and doesn't need
      to be once the logic it calls is proven
- [ ] Why this split matters even more here than in Phase 1/2: browser
      automation is slow and flaky to test directly, so pushing decisions
      into a pure function you *can* test cheaply is worth the extra file

### 3. Testing browser interaction without a live site
- [ ] A local HTML fixture (`tests/fixtures/sample_application_form.html`)
      instead of hitting any real company's application page — deterministic,
      fast, and never at risk of triggering anti-bot defenses
- [ ] `file://` URLs as a legitimate way to point a browser at test content
- [ ] Designing a **negative test case on purpose** — the "Company Name"
      decoy field exists specifically to catch a plausible bug (matching
      "name" too loosely) that a purely positive test suite would miss

**Try it:** add a new decoy field to the fixture — e.g. "School Name" —
and confirm it's correctly left blank without writing any new classifier
code first. If it fails, that's a real bug the test suite just caught for
you.

### 4. Deliberately conservative automation design
- [ ] Why the Executor **never** answers EEO/demographic or
      work-authorization questions, even though it technically could guess
      — this is a legal/ethical boundary, not a technical limitation
- [ ] Why it **never** clicks Submit — the human-in-the-loop pause
      (`input()` blocking with the browser still open) is the single most
      important design decision in this phase
- [ ] "Skip rather than guess" as a default posture — every classifier
      function returning `None` for anything it's not confident about,
      rather than picking its best guess

### 5. Structured local data vs. free text
- [ ] Why `candidate_profile.json` (structured) and `resume.md` (free
      text) are two separate files serving two different consumers — the
      Executor needs exact field values, the Evaluator's LLM needs prose
      it can reason over
- [ ] Loading and validating structured config the same way as Phase 1/2
      (`load_candidate_profile()` mirrors `load_resume()`'s
      fail-fast-with-a-helpful-message pattern)

---

## Workday — the fourth source

Built after Phase 3 rather than alongside Greenhouse/Lever/Ashby on
purpose — see Phase 1's "Why these three sources" reasoning for why it
needed to be its own milestone rather than a same-day fourth adapter.

### 1. Working with an undocumented internal API
- [ ] The difference between a **documented public API** (Greenhouse,
      Lever, Ashby) and an **internal endpoint inferred from how a site's
      own frontend behaves** (Workday's "CXS" system) — same public data,
      meaningfully more fragile to build against
- [ ] Why verifying field names against real, documented examples (rather
      than guessing) mattered even more here — an undocumented API has no
      spec to fall back on if you get it wrong

### 2. Modeling a genuinely different identifier shape
- [ ] Why `WorkdayCompany` (tenant + wd_host + site) exists instead of
      reusing the single-string `company_slug` the other three sources use
      — `parse_company_slug()` gives a clear error message when the shape
      is wrong, rather than a cryptic failure three calls later
- [ ] `@dataclass(frozen=True)` for a small immutable value type — a
      lighter-weight tool than a full Pydantic model when you don't need
      validation, just a clean structured value

### 3. Pagination
- [ ] Offset-based pagination: loop, accumulate, stop when a page is empty
      or the running offset reaches the reported total
- [ ] A **safety cap** (`MAX_PAGES`) on top of the natural stopping
      condition — defensive code for a total you don't fully trust from an
      undocumented API

### 4. The N+1 problem, deliberately made visible and controllable
- [ ] Why Workday's list endpoint not including full descriptions forces a
      second request *per job* — a classic **N+1 query problem**, here
      showing up in API calls instead of a database
- [ ] Making that cost a first-class, visible setting
      (`WORKDAY_FETCH_DESCRIPTIONS`) instead of hiding it — the user should
      be able to trade off completeness against speed/request volume on
      purpose, not by accident
- [ ] A second, tighter rate-limit knob (`WORKDAY_DETAIL_DELAY_SECONDS`)
      layered on top of the per-company one from Phase 1 — not every
      source needs the same level of caution

### 5. Partial failure at a finer grain
- [ ] Phase 1's Hunter already isolated failures per *company*; this
      adapter isolates them per *job* — one listing's detail fetch failing
      returns that job with `description_html=None` instead of dropping it
      (or the whole company's run) entirely
- [ ] Testing that failure path directly rather than only testing the
      happy path

**Try it:** temporarily lower `MAX_PAGES` to `2` in `app/sources/workday.py`
and run the Hunter against a large company — confirm it stops cleanly at
40 jobs instead of continuing indefinitely, and that nothing downstream
breaks from getting a partial result.

---

## RAG — cover letter / open-question answers

### 1. What "RAG" actually means, stripped of hype
- [ ] **R**etrieval (find the relevant source material) then
      **A**ugmented **G**eneration (hand it to an LLM as grounding) - two
      separate, separately-testable steps, not one black box
- [ ] Why grounding matters here specifically: without a real story to
      point at, an LLM asked "describe a time you led a project" will
      confidently invent one - the system prompt's "use ONLY details in
      the story" instruction exists because that failure mode is the
      default, not an edge case

### 2. Retrieval without an embedding model
- [ ] TF-IDF (term frequency-inverse document frequency) + cosine
      similarity as a legitimate, lightweight retrieval method - not
      "real" semantic search, but genuinely sufficient at small scale
      (a few stories, not a few thousand documents)
- [ ] Why this was the right tradeoff here: no embedding API call, no
      model download, fully offline, deterministic to test - versus a
      vector DB (Chroma/Qdrant, as the original spec named) that would add
      real value only once the story bank is large enough for
      keyword-overlap to start missing things
- [ ] `StoryRetriever` is isolated behind one class specifically so this
      tradeoff can be revisited later without touching anything else

**Try it:** add a fourth story to `story_bank.json.example` that shares
vocabulary with an existing one (e.g. two stories both mentioning
"leadership") and see whether `best_match()` still picks the right one for
a targeted question. If it doesn't, you've just found TF-IDF's actual
limit at your story bank's current size - that's the signal to consider
real embeddings, not a guess.

### 3. Reusing infrastructure instead of duplicating it
- [ ] `draft_answer()` was added to the *same* `LLMClient` Protocol and the
      *same* two adapters from Phase 2, instead of building a separate
      "RAG LLM client" - one provider connection, two capabilities
- [ ] The difference in how the two methods are called: `evaluate_match()`
      forces structured JSON output (a score needs to be parsed reliably);
      `draft_answer()` deliberately does NOT (free text is the actual
      desired output, and forcing structure here would just add a
      pointless wrapper object)

### 4. Making an optional feature truly optional
- [ ] `_build_answer_service()` catches a missing story bank and returns
      `None` rather than crashing the whole Executor - RAG is additive,
      not a hard dependency
- [ ] `fill_application()`'s `answer_service=None` default means every
      existing Phase 3 test kept passing unchanged when this feature was
      added - a sign the interface was extended safely rather than
      reworked

### 5. Flagging AI-generated content for human review, visibly
- [ ] Every RAG-drafted field's report line is prefixed
      `AI DRAFT ... REVIEW BEFORE SUBMITTING` rather than looking identical
      to a name or email field that was filled with certainty - the
      distinction between "we know this value" and "we generated this
      value" is preserved all the way to what the human reads

---

## LLM dropdown mapping

### 1. Constraining an LLM to a fixed set of choices
- [ ] JSON Schema's `enum` constraint used to make it structurally
      impossible for the model to invent an option that isn't on the page
      - `build_dropdown_schema()` builds this schema fresh per field,
      since the valid choices are different every time
- [ ] The difference between *constraining what the model can say* (schema
      enum) and *trusting what it says* (`DropdownMapper` still checks
      `selected_option in options` defensively afterward) - belt and
      suspenders, not either/or

### 2. Self-reported confidence as a second gate
- [ ] Asking the model to rate its own confidence, then only acting on
      `high` - `medium` and `low` are both treated as "don't know," not
      partial credit
- [ ] Why this matters more here than in Phase 2's scoring: a wrong resume
      score just produces a bad `TRASHED`/`APPROVED` call you can review
      via `inspect_jobs`; a wrong dropdown answer gets submitted into an
      actual application under the candidate's name

### 3. A safety boundary enforced structurally, not by convention
- [ ] `is_sensitive_dropdown()` is checked in `runner.py`, the *caller* of
      `DropdownMapper`, not inside the mapper itself - so the EEO/work-
      authorization protection holds no matter what mapper implementation
      gets passed in later, rather than depending on every future
      implementation remembering to check
- [ ] The protection is "never sent to the LLM," not "never auto-filled" -
      a subtle but real difference. Even asking a third-party API to help
      answer a sensitive question is avoided, not just avoiding acting on
      the answer
- [ ] The test that actually proves this
      (`test_sensitive_dropdown_is_never_sent_to_the_mapper`) asserts on
      the *stub mapper's call log*, not just the DOM outcome - proving the
      call never happened, not just that its result wasn't used

**Try it:** add a new sensitive pattern to `_SENSITIVE_DROPDOWN_PATTERNS`
in `field_classifier.py` (pick something plausible, like "marital status"),
add a matching decoy field to the test fixture, and write the test that
proves it's blocked - same shape as the existing work-authorization test.

### 4. Extending a Protocol without breaking existing implementations
- [ ] `select_dropdown_option()` was added as a *third* method on the same
      `LLMClient` Protocol used since Phase 2 - both concrete adapters had
      to implement it, but nothing about `evaluate_match()` or
      `draft_answer()` changed
- [ ] Optional parameters with `None` defaults
      (`dropdown_mapper: DropdownMapper | None = None`) kept every earlier
      Phase 3 test passing unchanged - the same safe-extension pattern
      used when RAG was added

---

## Coming next — worth pre-reading

- [ ] Radio button and multi-select checkbox handling — structurally
      different from `<select>` dropdowns (a radio group's question text
      isn't associated with any single input the way a `<select>`'s
      options are), so this is new DOM-extraction work, not a copy of the
      dropdown mapper
- [ ] Real embedding models, if/when TF-IDF's keyword-overlap retrieval
      starts missing matches as a story bank grows
- [ ] Async task queues (Celery + Redis) — not needed yet, but coming once
      running one job at a time in each phase becomes the bottleneck
