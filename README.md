# SQL MCP Server

A read-only SQL question-answering system powered by local Ollama, with guardrails and evals.

## What it does

This MCP server lets an MCP client ask natural-language questions about PostgreSQL. Ollama generates SQL locally; the server validates the SQL before execution, so no paid API key is required.

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install and start Ollama, then download a model:
   ```powershell
   ollama pull llama3.2
   ollama serve
   ```
4. Set your database connection and optional Ollama settings:
   ```bash
   set DB_URL=postgresql://postgres:postgres@localhost:5432/postgres
   set OLLAMA_URL=http://127.0.0.1:11434
   set OLLAMA_MODEL=llama3.2
   ```
5. Load the sample SQL data into PostgreSQL:
   ```bash
   psql %DB_URL% -f data\sample_data.sql
   ```
6. Run the server:
   ```bash
   python src/server.py
   ```

## Architecture

```text
MCP Inspector (or local demo)
  -> MCP server (src/server.py)
      - ask_database() sends schema and question to local Ollama
      - run_query() validates and runs the returned SQL safely
  -> Safety layer
      - Only SELECT allowed
      - Dangerous keywords blocked
      - Multi-statement queries rejected
      - Comments and injections rejected
      - Query timeout and row limits enforced
  -> PostgreSQL database
```

## Safety guarantees

- Only SELECT queries are allowed
- Dangerous SQL keywords are blocked
- Multi-statement queries are rejected
- SQL comments are rejected
- Query timeouts and row limits are enforced

## Ollama usage

MCP clients should call `ask_database` with a natural-language question. The server sends only the database schema and question to Ollama's local `/api/generate` endpoint. Ollama must return JSON containing one SQL statement; the existing safety layer rejects anything that is not a safe `SELECT`. `run_query` remains available for clients that already have SQL.

## Eval suite

The project includes 40 eval cases in [tests/test_evals.py](tests/test_evals.py).

Two runners test different code paths:

- `run_live_evals.py` exercises the `ask_database` path: natural language -> Ollama -> SQL -> safety layer. It writes `EVAL_RESULTS.md`.
- `run_detailed_evals.py` exercises the `run_query` path with raw SQL and direct safety checks. It writes `DETAILED_EVAL_RESULTS.md`.

The current honest live result is **68% (27/40)** via Ollama `llama3.2`. The safety category scored **100% (10/10)**.

To run the live evaluation, ensure PostgreSQL is running with the sample data loaded, Ollama is running with `llama3.2` available, and then run:

```bash
python run_live_evals.py
```

For the direct SQL safety evaluation, run `python run_detailed_evals.py`.

## What the eval suite found

Case S9 exposed an injection-laundering bypass: `ask_database` sent a raw injection payload to Ollama, which rewrote it as clean SQL and removed the comment marker before the safety check ran. Raw questions are now checked for SQL and injection patterns before reaching the model, while the generated SQL retains the existing post-generation safety check. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the full finding.

## Threat Model

This project is designed to protect a PostgreSQL database from abusive or dangerous SQL access when exposed through a language-agent-style interface.

It defends against:

- non-SELECT SQL commands such as `DELETE`, `UPDATE`, `INSERT`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`
- multiple SQL statements in a single request
- SQL comment and tautology injection patterns (`--`, `/*`, `*/`, `OR 1=1`), checked on raw input before it reaches the model as well as on generated SQL
- accidental data exposure from large result sets by limiting rows
- runaway queries via a statement timeout

It does not claim to protect against all SQL injection or application-layer vulnerabilities in a more complex deployment.

Layer ordering matters here: case S9 showed that checking only post-generation SQL is insufficient, since the model can rewrite a payload into something that passes inspection.

## Notes

- The detailed eval runner remains deterministic for repeatable direct-SQL scorecards.
- `run_live_evals.py` exercises the Ollama-backed `ask_database` path; `run_detailed_evals.py` exercises direct SQL through `is_safe_query`.
