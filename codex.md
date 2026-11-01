# Incremental Plaid ingestion with configurable runs

## Summary

Update `src/pipelines/api_ingestion/ingest_td_transactions.py` into a repeatable ingestion job that saves Plaid transactions and a sync checkpoint in DuckDB.

The current script fetches only one page, prints counts, and saves neither transactions nor the cursor. This change will store data in separate staging tables for validation before dashboard integration.

## Implementation

- Keep macOS Keychain credential storage and existing TD credential names. Load credentials once, validate them, and never log tokens.
- Use `/transactions/sync` without a cursor on the first run; subsequent runs use the saved cursor.
- Fetch every page until `has_more=false`, processing `added`, `modified`, and `removed` changes. Preserve page order.
- Commit transaction changes and the final cursor in one DuckDB transaction after all pages arrive. A failed run leaves the previous checkpoint intact.
- On `TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION`, discard buffered changes and restart from the run’s original cursor, as required by [Plaid’s sync documentation](https://plaid.com/docs/api/products/transactions/).
- Retry transient network, rate-limit, and server failures up to three times with exponential backoff; respect `Retry-After`. Authentication and Item errors stop the run with an actionable message.
- Allow only one writer per target database; report database lock conflicts clearly.

## Storage and run interface

Create two tables automatically without changing existing transaction tables:

- `plaid_sync_state`: environment, Item ID, cursor, and last successful sync time; keyed by environment and Item ID.
- `plaid_transactions`: environment, Item ID, transaction ID, account ID, date, amount, currency, description, pending status, pending transaction ID, raw JSON, removal status, and update time; keyed by environment, Item ID, and transaction ID.

Upsert added and modified transactions; mark removed transactions inactive. Retain pending records in staging and preserve Plaid’s original amount sign. Empty syncs are successful and may still advance the checkpoint.

Expose `run_ingestion(options)` for Python callers and an `argparse` CLI:

| Parameter | Default | Behavior |
|---|---|---|
| `--environment` | `production` | Select production or sandbox; isolate checkpoints by environment. |
| `--db-path` | `data/finance.db` | Resolve relative paths from the project root. |
| `--page-size` | `500` | Validate a value from 1–500. |
| `--dry-run` | Off | Fetch and summarize changes without creating or updating database state. |
| `--replay` | Off | Fetch from the beginning and idempotently reapply available history; never clear existing data first. |

Sandbox uses separately named Keychain credentials, with no production fallback. Resolve the Item ID through Plaid before selecting its checkpoint.

Example:

```bash
python src/pipelines/api_ingestion/ingest_td_transactions.py \
  --environment production \
  --page-size 500 \
  --dry-run
```

Return a structured summary containing mode, pages fetched, added/modified/removed counts, duration, and commit status. Print that summary for CLI users and exit nonzero on failure. Document setup and examples in the README.

## Tests and acceptance criteria

Use mocked Plaid responses and temporary DuckDB databases to verify:

- First run, multiple pages, and resume from the saved cursor.
- Repeated changes and replay produce no duplicate transaction rows.
- Modifications, removals, and pending-to-posted transitions update staging correctly.
- Pagination mutation restarts from the original cursor.
- API or database failure preserves both prior data and checkpoint.
- Dry run leaves the database unchanged, including when the database does not yet exist.
- Invalid parameters, missing credentials, environment isolation, and retry exhaustion behave as documented.

Acceptance: a second successful run requests changes from the prior checkpoint and commits only the resulting updates.

## Assumptions and boundaries

- Existing TD credentials reference an Item already enabled for Transactions; Link onboarding is outside this change.
- Runs are invoked manually or by an external scheduler. Webhooks and scheduling infrastructure are deferred.
- Custom parameters are operational controls; date-range backfills are excluded because sync is cursor based.
- Existing CSV ingestion and dashboard totals remain unchanged. At future dashboard integration, require a cutover date per account: CSV is authoritative before that date, Plaid from that date onward.
- Replay retrieves history Plaid currently makes available; it does not expand the Item’s historical coverage or automatically resolve historical CSV overlap.
