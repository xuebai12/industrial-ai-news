# Industrial AI Pipeline Runbook

## Standard local run

```bash
python main.py --output email --skip-dynamic --skip-llm-filter --output-dir output
```

## Manual run (scheduled disabled)

```bash
./.venv/bin/python main.py --output both --output-dir output --log-format json
./.venv/bin/python ops_dashboard.py --output-dir output --days 7
```

Current mode:

- no scheduler entrypoint is used
- dispatch is triggered manually only
- `run_scheduled_dispatch.sh` now exits with a disabled notice

For strict mode in automation:

```bash
python main.py --output both --strict --log-format json --output-dir output
```

## Artifacts

- `output/run-summary-YYYY-MM-DD.json`: run metrics and stage outcomes.
- `output/error-YYYY-MM-DD.json`: structured error report when run fails.
- `output/ops-dashboard.md`: latest 7-run operational dashboard.
- `output/ops-dashboard.json`: machine-readable dashboard payload.
- `logs/run-YYYY-MM-DD.log`: launch script log stream.

## Failure categories

- `CONFIG`: missing required env vars for selected output mode.
- `SCRAPE`: source fetching/parsing stage failure.
- `FILTER`: relevance filtering failure.
- `LLM`: analysis call or parsing failure.
- `DELIVERY`: email/markdown/notion delivery stage failure.

Notion-specific categories inside delivery logs:

- `AUTH`: token/permission issue.
- `SCHEMA`: database property mismatch.
- `RATE_LIMIT`: Notion throttling.
- `API` / `UNKNOWN`: other provider or client errors.

## Common SOP

1. Open latest `run-summary-*.json` and check `exit_reason`.
2. If failed, open `error-*.json` and inspect `failures[*]`.
3. Open `ops-dashboard.md` for trend view and alert checks.
4. For Notion errors:
   - `AUTH`: verify `NOTION_API_KEY` integration access.
   - `SCHEMA`: compare DB property names with service mappings.
   - `RATE_LIMIT`: rerun later or reduce batch size.
5. For SMTP errors:
   - verify `SMTP_HOST/PORT/USER/PASS/EMAIL_TO`.
   - test with `--output markdown` to isolate mail transport.
6. For model errors:
   - switch to `--mock` for pipeline smoke validation.
   - verify provider key and model availability.

## Validation commands

```bash
ruff check .
mypy main.py src
pytest -q
```
