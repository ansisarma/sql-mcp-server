"""
Verbatim copy of the three pure guardrail functions from src/server.py.

The Space needs these without pulling in psycopg2 and the mcp package, which
src/server.py imports at module level. Nothing here is new logic — if you change
a rule in src/server.py, change it here too.
"""

import re
from typing import Any


def is_safe_query(query: str) -> tuple[bool, str]:
    """Check whether a query is safe to run."""
    query_upper = query.strip().upper()

    if not query_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed"

    if ";" in query.rstrip(";"):
        return False, "Multiple statements not allowed"

    dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE", "COPY"]
    for keyword in dangerous:
        if keyword in query_upper:
            return False, f"Query contains forbidden keyword: {keyword}"

    if query_upper.strip() == "SELECT":
        return False, "Incomplete SELECT query"

    if "--" in query or "/*" in query or "*/" in query:
        return False, "Query contains suspicious SQL comment patterns"

    return True, "OK"


def has_unsafe_sql_intent(question: str) -> bool:
    """Reject destructive natural-language requests before model generation."""
    question_upper = question.upper()
    dangerous = r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY)\b"
    return re.search(dangerous, question_upper) is not None or "CALL THE FUNCTION" in question_upper


def classify_question(question: str) -> dict[str, Any]:
    """Classify a natural-language question as database, non-database, or ambiguous."""
    q = question.strip().lower()
    if not q:
        return {"category": "ambiguous", "reason": "empty_question"}

    if q == "select":
        return {"category": "ambiguous", "reason": "incomplete_query"}

    if q in {"show me information", "show me data", "show me something"}:
        return {"category": "ambiguous", "reason": "too_vague"}

    if any(token in q for token in ["weather", "joke", "who are you", "hack", "hello", "what is the capital", "tell me a"]):
        return {"category": "non_database", "reason": "off_topic"}

    if len(q.split()) <= 1:
        return {"category": "ambiguous", "reason": "too_vague"}

    database_keywords = [
        "customer",
        "customers",
        "order",
        "orders",
        "table",
        "data",
        "database",
        "list",
        "count",
        "how many",
        "who",
        "what is",
        "which",
        "from",
        "where",
        "email",
        "name",
        "city",
        "total",
        "value",
    ]

    if any(keyword in q for keyword in database_keywords):
        return {"category": "database", "reason": "looks_like_database_request"}

    return {"category": "ambiguous", "reason": "too_vague"}
