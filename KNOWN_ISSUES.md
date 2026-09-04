# Known Issues

This project is intentionally lightweight and designed for safe read-only SQL queries.
The following limitations are known and worth documenting honestly.

## Current Limitations

- Complex JOIN queries may struggle
  - The built-in query inference and test mapping are simple and may not correctly express multi-table relationships in every case.

- ORDER BY is not fully supported
  - Some tests and natural-language questions assume ordered results, but the current server returns rows without a consistent ordering guarantee unless the SQL explicitly includes `ORDER BY`.

- Timeout behavior edge cases
  - The server imposes a PostgreSQL `statement_timeout`, but long or malformed queries may still return partial errors or connection-level failures instead of clean diagnostics.

- Local model only, no hosted API
  - SQL generation runs through Ollama on localhost. This is deliberate: no API key, no per-query cost, and the database schema never leaves the machine. The trade-off is that accuracy is bounded by whatever local model is installed, and `llama3.2` is the weakest link in the 68% score.
  - `run_detailed_evals.py` deliberately bypasses the model and tests `is_safe_query` directly, so the safety scorecard stays deterministic regardless of which model is loaded.

- Limited schema coverage
  - The eval suite is built around the `customers` and `orders` tables only, so any query outside those tables is intentionally rejected or reported as missing.

## Injection via LLM laundering (found and fixed)

The eval suite caught a real bypass. Case S9 passed a classic injection
payload to `ask_database` as its natural-language question. Because
`ask_database` sends the question to a local model to generate SQL, the
model rewrote the payload into syntactically clean SQL and stripped the
`--` comment. The safety check then ran against the model's cleaned
output rather than the original input, found nothing wrong, and returned
customer rows.

The guardrail logic was correct; it was inspecting the wrong string.
Sanitizing after the model is insufficient in any LLM-in-the-loop system,
because the model normalizes the attack into something that looks
legitimate. Raw input is now validated before it reaches the model, with
the post-generation check retained as a second layer.
