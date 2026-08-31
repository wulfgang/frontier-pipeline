# AI Agent Frontier Pipeline — Design Spec

**Date:** 2026-08-09  
**Status:** Ready for user review  
**Approach:** Workflow-graph core + thin agents (Approach 1)  
**Language (implementation default):** Python 3.12+ for runner and nodes (fits Actions, schema validation, and LLM SDKs); graph definitions remain YAML.

## 1. Purpose

Build a scheduled research product that:

1. **Daily** discovers the latest and most popular GitHub projects related to AI agents.
2. **Curates** that information into a local Markdown/Obsidian-style **llm-wiki** (wiki bootstrap is a prerequisite before daily runs matter).
3. **Each Friday**, scans public web sources that proxy Bloomberg Tech–style coverage of AI investment activity.
4. **Generates a report** ranking which tracked GitHub projects sit on the frontier of current AI investment themes, with possible business cases grounded in the wiki + investment scan.
5. **Runs a checker agent** that verifies factual grounding, investment logic (hard fails), and pipeline integrity (soft checks).
6. Uses **graph engineering** as an **agent workflow graph** (orchestration DAG), not a knowledge graph, for v1.

**Primary consumer:** the repo owner. Outputs live as Markdown in the wiki plus shareable HTML/PDF.

**Runtime:** GitHub Actions cron; workflows commit wiki and report artifacts back to the repo.

## 2. Goals and non-goals

### Goals

- Declarative workflow graphs with a small runner and typed artifact handoffs.
- Obsidian-friendly Markdown wiki as the durable knowledge surface.
- Provider-agnostic LLM interface; default Anthropic Claude via `ANTHROPIC_API_KEY`.
- Friday report only published (HTML/PDF) when the checker hard-passes.
- Clear, testable contracts for node I/O and checker rules.

### Non-goals (v1)

- Bloomberg Terminal / official Bloomberg API access.
- A separate knowledge-graph database (entities/edges store).
- Heavy multi-agent frameworks (LangGraph/Crew as the orchestration core).
- Multi-tenant or team collaboration product surface.
- Guaranteeing complete or authoritative investment coverage from public web proxies.

## 3. Architecture

**Spine:** a declarative workflow graph (YAML). Nodes are agents/steps; edges are typed artifact handoffs. A **graph runner** loads the graph, executes ready nodes in topological order, writes artifacts, and records a run manifest for the checker.

**Two scheduled graphs:**

| Schedule | Graph | Flow |
|----------|--------|------|
| Daily | `daily_ingest` | `github_ingest` → `wiki_curate` → soft `pipeline_check` |
| Friday | `friday_report` | `invest_scan` → `frontier_report` → hard `checker` → `render_share` (only if hard-pass) |

**Repo layout:**

```text
wiki/                 # Obsidian-style llm-wiki (committed by Actions)
graphs/               # Workflow definitions (YAML)
src/                  # Runner, LLM provider interface, node implementations
artifacts/            # Run-scoped intermediates (gitignored; present in Actions workspace)
reports/              # Published Markdown + HTML/PDF
reports/drafts/       # Failed or pre-check drafts + check.json
tests/fixtures/       # Offline full-graph fixtures
.github/workflows/    # Cron + PR CI
docs/superpowers/     # Specs and plans
```

**LLM:** thin `Provider` interface (chat + structured output). Default: Claude. OpenAI (or others) swappable behind the same interface.

**Secrets:** `ANTHROPIC_API_KEY`, `GITHUB_TOKEN` (API rate limits + committing with permissions).

## 4. Components

### 4.1 Graph runner

- Load and validate graph YAML (unknown nodes, cycles, dangling edges → reject before run).
- Execute nodes when required inputs exist; fail fast on hard node errors.
- Persist per-node status and I/O paths to `artifacts/<run_id>/manifest.json`.
- Soft-check nodes may warn without aborting the graph.

### 4.2 Nodes (v1)

| Node | Responsibility | Primary outputs |
|------|----------------|-----------------|
| `github_ingest` | Query GitHub Search/API for AI-agent repos using topics (`ai-agents`, `llm-agents`, `autonomous-agents`, `agentic`) plus keyword fallbacks in name/description; rank by stars and recent activity; emit top-N repo cards per run (N configurable, default 25) | `repos.json` |
| `wiki_curate` | Upsert Markdown under wiki conventions; update indexes/links | `wiki/projects/*`, `wiki/themes/*`, `wiki/index.md` |
| `invest_scan` | Fetch public pages/RSS as Bloomberg Tech proxies: Bloomberg.com technology/AI articles when reachable, plus reputable secondary funding coverage (e.g. TechCrunch, VentureBeat) when Bloomberg content is paywalled; every card must keep `source_url` | `investments.json` |
| `frontier_report` | Join wiki + investment cards; rank frontier repos; draft business cases | `report.md`, `report.json` |
| `checker` | Grounding, investment logic (hard); pipeline integrity (soft) | `check.json` |
| `render_share` | Markdown → self-contained HTML; PDF generated from that HTML via a headless Chromium print step in Actions (HTML is the required share artifact; PDF is best-effort) | `reports/YYYY-MM-DD.html`, optional `.pdf` |
| `pipeline_check` | Soft integrity check for daily runs against manifest | warnings in manifest / job summary |

### 4.3 Wiki prerequisite (bootstrap)

Before relying on daily curation quality, seed:

- `wiki/index.md` — home / navigation
- Directories: `wiki/projects/`, `wiki/themes/`, `wiki/investments/`, `wiki/reports/`
- Short style guide (front-matter fields, linking rules, naming) that `wiki_curate` must follow

Bootstrap is a one-time (or rare) setup step, not part of the daily graph.

### 4.4 GitHub Actions

- **Daily workflow:** cron → run `daily_ingest` graph → commit wiki changes.
- **Friday workflow:** cron → run `friday_report` graph → commit reports/wiki on success; on hard-fail commit drafts + `check.json` and fail the job.
- **PR CI:** unit + schema + fixture integration tests.
- **Manual smoke:** `workflow_dispatch` optional live run with tight limits.
- Concurrency groups so daily and Friday do not clobber mid-commit.
- Commits only under `wiki/` and `reports/` (never force-push).

## 5. Data flow

### 5.1 Daily

1. `github_ingest` → `repos.json` (`id`, `url`, `stars`, `topics`, `summary`, `fetched_at`, …).
2. `wiki_curate` reads `repos.json` + existing `wiki/projects/*` → upserts project pages, theme stubs, index links.
3. Soft `pipeline_check` reads the run manifest → warns on missing pages/artifacts; does not block commit of successful curations.
4. Actions commits wiki updates with a dated message.

### 5.2 Friday

1. `invest_scan` → `investments.json` (`headline`, `themes`, `actors`, `source_url`, `date`, …).
2. `frontier_report` reads `investments.json` + relevant wiki pages → `report.md` + `report.json` (ranked projects, claims, citations).
3. `checker` reads draft + sources + manifest → `check.json`.
   - **Hard fail:** ungrounded claims, or business cases that do not follow from investment themes + wiki evidence.
   - **Soft fail:** missing optional pipeline steps / stale daily ingest.
4. **Hard-pass:** `render_share` → HTML (+ PDF); copy Markdown into `wiki/reports/`.
5. **Hard-fail:** commit `check.json` + draft under `reports/drafts/`; skip share render; fail Actions job for notification.

### 5.3 Artifact contract

Every node declares `inputs` / `outputs` in graph YAML. The runner starts a node only when required inputs exist on disk for that run.

## 6. Error handling

| Case | Behavior |
|------|----------|
| Transient HTTP/API/LLM errors | Retry with backoff (3 attempts), then mark node `failed` and stop the graph |
| Partial GitHub ingest | Keep successful cards; log failures in manifest; curate proceeds on available data |
| LLM empty/malformed structured output | One repair prompt; if still invalid vs schema → fail node |
| Checker hard fail | Skip `render_share`; leave draft + `check.json`; fail Actions job |
| Checker soft fail only | Proceed with render; warnings in report front-matter and job summary |
| Missing secrets | Fail fast at runner start with a clear message |
| Rate limits | Honor `Retry-After`; if still blocked, fail with quota reason (no silent empty wiki updates) |

## 7. Testing

**Unit:** graph runner (order, missing inputs, retries, manifest); pure transforms (repo card → Markdown); checker rules (grounded vs not; theme↔case mismatch; soft warnings).

**Contract:** JSON Schema (or equivalent) for `repos.json`, `investments.json`, `report.json`, `check.json`; graph YAML validation.

**Integration:** fixture-driven full daily and Friday graphs under `tests/fixtures/` (no live APIs by default).

**CI:** PRs run unit + contract + fixture integration. Schedules run production graphs; Friday hard-fails remain visible via Actions and committed `check.json`.

## 8. Graph YAML shape (illustrative)

```yaml
name: friday_report
nodes:
  - id: invest_scan
    uses: invest_scan
    outputs: [investments.json]
  - id: frontier_report
    uses: frontier_report
    inputs: [investments.json]
    outputs: [report.md, report.json]
  - id: checker
    uses: checker
    inputs: [report.md, report.json, investments.json]
    outputs: [check.json]
    on_hard_fail: stop
  - id: render_share
    uses: render_share
    inputs: [report.md, check.json]
    outputs: [report.html]
    requires_check: hard_pass
edges:
  - [invest_scan, frontier_report]
  - [frontier_report, checker]
  - [checker, render_share]
```

Exact field names may be refined during implementation as long as: declared I/O, topological execution, and checker gating of render remain.

## 9. Success criteria

- Wiki bootstrap exists and daily runs upsert AI-agent project pages without manual editing.
- Friday run produces a ranked frontier report with citations when sources and wiki evidence support it.
- Checker blocks share render on ungrounded or illogical investment→business-case leaps.
- Workflow graph is the explicit orchestration artifact (readable YAML + runner), not an opaque framework.
- PR CI passes offline; scheduled Actions can commit wiki/reports safely.

## 10. Implementation phasing (high level)

1. Repo skeleton, wiki bootstrap, LLM provider interface, graph runner + schemas.
2. Daily graph: `github_ingest` + `wiki_curate` + soft `pipeline_check` + Actions.
3. Friday graph: `invest_scan` + `frontier_report` + `checker` + `render_share` + Actions.
4. Hardening: retries, concurrency, fixture CI, manual live smoke workflow.

Detailed task breakdown belongs in the implementation plan (next step after this spec is approved).
