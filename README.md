# frontier-pipeline

Workflow-graph pipeline for AI-agent GitHub curation and Friday frontier reports.

This package implements a scheduled research product that discovers AI-agent GitHub projects, curates them into an Obsidian-style wiki, and generates Friday frontier reports grounded in public investment-theme coverage.

See the [design spec](docs/superpowers/specs/2026-08-09-ai-agent-frontier-pipeline-design.md) for architecture, components, and implementation details.

## Secrets (GitHub Actions)

Configure these repository secrets for scheduled / `workflow_dispatch` runs:

| Secret | Purpose |
|--------|---------|
| `DASHSCOPE_API_KEY` | **Required.** Alibaba DashScope (Qwen) for live LLM nodes |
| `FRONTIER_GITHUB_TOKEN` | Optional PAT with `public_repo` (or `repo`) for higher GitHub Search API rate limits. If unset, Actions uses the built-in `GITHUB_TOKEN`. |

### Autonomous schedules

| Workflow | When (UTC) | What it does |
|----------|------------|--------------|
| `daily-ingest` | Every day 06:00 | Ingest AI-agent repos → update `wiki/` → commit |
| `friday-report` | Fridays 07:00 | Investment scan → frontier report → checker → publish HTML/MD → commit |

After pushing to GitHub: **Settings → Secrets and variables → Actions** → add `DASHSCOPE_API_KEY`, then open the **Actions** tab and enable workflows if prompted. Trigger a smoke run via **Actions → daily-ingest → Run workflow**.

## Local development

Copy `.env.example` to `.env` and set `DASHSCOPE_API_KEY`. The CLI loads `.env` automatically.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
frontier-pipeline bootstrap-wiki
frontier-pipeline run --graph graphs/daily_ingest.yaml --llm fake
frontier-pipeline run --graph graphs/daily_ingest.yaml --llm dashscope
```

Friday graph (offline):

```bash
frontier-pipeline run --graph graphs/friday_report.yaml --llm fake
```

Optional env: `TOP_N` limits GitHub ingest / invest-scan result counts (int).

## Schedules

| Workflow | Cron (UTC) |
|----------|------------|
| Daily ingest | `0 6 * * *` (06:00) |
| Friday report | `0 7 * * 5` (07:00 Friday) |

Friday `workflow_dispatch` accepts `live` (DashScope vs fake) and `top_n` (smoke limit; scheduled runs default `TOP_N=25`).

Default live provider is DashScope OpenAI-compatible mode (`qwen-plus` at `https://dashscope.aliyuncs.com/compatible-mode/v1`). Override with `FRONTIER_LLM_MODEL` / `FRONTIER_LLM_BASE_URL`. Anthropic remains available via `--llm anthropic`.

## Optional PDF export

`render_share` always writes self-contained `report.html`. Set `FRONTIER_PDF=1` and install Playwright (`pip install playwright && playwright install chromium`) to also emit `report.pdf`. If Playwright is unavailable, PDF generation is skipped without failing the run.
