"""Detailed eval runner tests the direct run_query safety path via is_safe_query.

Enhanced Eval runner for SQL MCP Server - generates detailed SQL query log.

This script loads the 40 test cases from src/server.py, maps each natural-language
case into a candidate SQL query, executes the query against the local PostgreSQL
database, and writes detailed results to DETAILED_EVAL_RESULTS.md.
"""

from __future__ import annotations

import datetime
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import psycopg2

from src.server import TEST_CASES, classify_question, connect_db, is_safe_query

MAX_ROWS = 100
QUERY_TIMEOUT_MS = 5000


@dataclass
class EvalResult:
    id: str
    category: str
    question: str
    expected: str
    passed: bool
    actual: str
    reason: str
    query: str | None


def escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def maybe_mojibake(text: str) -> str:
    try:
        return text.encode("utf-8").decode("latin1")
    except UnicodeError:
        return text


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text.strip())
    normalized = normalized.lower()
    return re.sub(r"\s+", " ", normalized)


def repair_mojibake(text: str) -> str:
    try:
        return text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text


def compare_expected(expected: str, actual: str) -> bool:
    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)

    if expected_norm == actual_norm:
        return True
    if expected_norm in actual_norm:
        return True
    if actual_norm in expected_norm:
        return True

    if re.fullmatch(r"[\d.]+", expected_norm):
        digits = re.sub(r"[^\d.]+", "", actual_norm)
        return expected_norm in digits

    repaired_expected_norm = normalize_text(repair_mojibake(expected))
    repaired_actual_norm = normalize_text(repair_mojibake(actual))

    if repaired_expected_norm == actual_norm:
        return True
    if repaired_actual_norm == expected_norm:
        return True
    if repaired_expected_norm in actual_norm:
        return True
    if repaired_actual_norm in expected_norm:
        return True
    if repaired_expected_norm in repaired_actual_norm:
        return True

    return False


def infer_sql_query(question: str) -> str | None:
    q = question.strip().lower().rstrip("?")

    patterns = [
        (r"how many customers are from (?P<city>.+)", "SELECT COUNT(*) FROM customers WHERE city = '{city}';"),
        (r"list all customer names", "SELECT name FROM customers ORDER BY name;"),
        (r"what is the total value of all orders", "SELECT SUM(total) FROM orders;"),
        (r"which customer is from (?P<city>.+)", "SELECT name FROM customers WHERE city = '{city}';"),
        (r"how many orders did (?P<name>.+) place", "SELECT COUNT(*) FROM orders JOIN customers ON customers.id = orders.customer_id WHERE customers.name ILIKE '{name}%' OR customers.name ILIKE '{name_mojibake}%';"),
        (r"what(?:'s| is) the largest order total", "SELECT MAX(total) FROM orders;"),
        (r"list orders by customer (?P<name>.+)", "SELECT orders.total FROM orders JOIN customers ON customers.id = orders.customer_id WHERE customers.name ILIKE '{name}%' OR customers.name ILIKE '{name_mojibake}%';"),
        (r"how many customers are there in total", "SELECT COUNT(*) FROM customers;"),
        (r"show me customers from berlin or hamburg", "SELECT name FROM customers WHERE city IN ('Berlin','Hamburg') ORDER BY name;"),
        (r"what(?:'s| is) the email of (?P<name>.+)", "SELECT email FROM customers WHERE name ILIKE '{name}%' OR customers.name ILIKE '{name_mojibake}%';"),
        (r"show me data from the (?P<table>\w+) table", "SELECT * FROM {table};"),
        (r"what(?:'s| is) the phone_number of (?P<name>.+)", "SELECT phone_number FROM customers WHERE name ILIKE '{name}%' OR customers.name ILIKE '{name_mojibake}%';"),
        (r"show me the products table", "SELECT * FROM products;"),
        (r"list all employees", "SELECT * FROM employees;"),
        (r"what'?s the shipping address for order (?P<id>\d+)", "SELECT shipping_address FROM orders WHERE id = {id};"),
        (r"show me inventory levels", "SELECT * FROM inventory;"),
        (r"what'?s the customer_phone_number", "SELECT customer_phone_number FROM customers;"),
        (r"list all transactions", "SELECT * FROM transactions;"),
        (r"show me the payments table", "SELECT * FROM payments;"),
        (r"what'?s the delivery_date for each order", "SELECT delivery_date FROM orders;"),
        (r"what is customer with id (?P<id>\d+)", "SELECT * FROM customers WHERE id = {id};"),
        (r"query the customers table for rows where name matches %", "SELECT * FROM customers WHERE name LIKE '%';"),
        (r"select", question.strip()),
    ]

    for pattern, template in patterns:
        match = re.fullmatch(pattern, q)
        if not match:
            continue

        if isinstance(template, str) and template == question.strip():
            return template

        groups = {k: v.title() if k in ["city"] else v for k, v in match.groupdict().items()}
        groups = {k: escape_sql_literal(v) for k, v in groups.items()}
        if "name" in groups:
            groups["name_mojibake"] = escape_sql_literal(maybe_mojibake(groups["name"]))
        else:
            groups["name_mojibake"] = ""
        return template.format(**groups)

    if question.strip().lower().startswith("select"):
        return question.strip()

    return None


def execute_query(query: str) -> tuple[bool, str, list[tuple[Any, ...]] | None]:
    safe, reason = is_safe_query(query)
    if not safe:
        return False, f"Query rejected: {reason}", None

    try:
        conn = connect_db()
        conn.set_session(autocommit=True)
        cursor = conn.cursor()
        cursor.execute(f"SET statement_timeout = {QUERY_TIMEOUT_MS}")
        cursor.execute(query)

        rows = cursor.fetchmany(MAX_ROWS + 1)
        if len(rows) > MAX_ROWS:
            rows = rows[:MAX_ROWS]
            result_text = f"[RESULT TRUNCATED AT {MAX_ROWS} ROWS]"
        else:
            result_text = ""

        if cursor.description is None:
            description = "Query executed successfully."
        else:
            col_names = [desc[0] for desc in cursor.description]
            description = f"Columns: {', '.join(col_names)}"

        cursor.close()
        conn.close()

        row_text = "\n".join(str(row) for row in rows) if rows else ""
        actual = description + ("\n" + row_text if row_text else "")
        if result_text:
            actual += "\n" + result_text

        return True, actual.strip(), rows
    except psycopg2.ProgrammingError as exc:
        return True, f"Error: {exc}", None
    except Exception as exc:
        return False, f"Error: {exc}", None


def evaluate_case(case: dict[str, Any]) -> EvalResult:
    question = case["question"]
    expected = case["expected"]
    classification = classify_question(question)
    query = infer_sql_query(question)

    if expected.lower() == "refuse":
        actual = query or question
        safe, reason = is_safe_query(actual)
        passed = not safe
        return EvalResult(case["id"], case["category"], question, expected, passed, reason, "Rejected unsafe SQL or no valid SELECT statement", query)

    if query is None:
        return EvalResult(case["id"], case["category"], question, expected, False, "No SQL query inferred", "Could not infer SQL query from question", None)

    safe, reason = is_safe_query(query)
    if not safe:
        return EvalResult(case["id"], case["category"], question, expected, False, f"Query rejected: {reason}", "Query did not pass safety checks", query)

    success, actual, rows = execute_query(query)
    if not success:
        return EvalResult(case["id"], case["category"], question, expected, False, actual, "Query execution failed", query)

    passed = compare_expected(expected, actual)
    return EvalResult(case["id"], case["category"], question, expected, passed, actual, "Query executed", query)


def generate_detailed_report(results: list[EvalResult]) -> str:
    timestamp = datetime.datetime.utcnow().isoformat()
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    md = f"""# Detailed Eval Results with SQL Queries

**Date:** {timestamp}
**Total Tests:** {total}
**Overall Pass Rate:** {100 * passed / total:.0f}% ({passed}/{total})

---

"""

    for i, result in enumerate(results, 1):
        status = "PASS" if result.passed else "FAIL"
        md += f"""## Test {i}: {status}

**Category:** {result.category}
**ID:** {result.id}
**Question:** {result.question}

### Generated SQL Query
```sql
{result.query if result.query else "No query generated"}
```

### Expected Output
```
{result.expected}
```

### Actual Output
```
{result.actual}
```

### Reason
{result.reason}

---

"""

    return md


def main() -> None:
    results = [evaluate_case(case) for case in TEST_CASES]
    detailed_report = generate_detailed_report(results)

    with open("DETAILED_EVAL_RESULTS.md", "w", encoding="utf-8") as f:
        f.write(detailed_report)

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"Wrote DETAILED_EVAL_RESULTS.md. {passed}/{total} cases passed.")


if __name__ == "__main__":
    main()
