import asyncio
import json
import unittest
from unittest.mock import patch

from src.server import TEST_CASES, call_tool, classify_question, generate_sql_with_ollama, has_unsafe_sql_intent, is_safe_query


class EvalSuiteTests(unittest.TestCase):
    def test_eval_suite_contains_40_cases(self):
        self.assertEqual(len(TEST_CASES), 40)

    def test_each_case_has_expected_fields(self):
        for case in TEST_CASES:
            self.assertIn("id", case)
            self.assertIn("category", case)
            self.assertIn("question", case)
            self.assertIn("expected", case)
            self.assertIn("explanation", case)

    def test_safety_checks_reject_dangerous_queries(self):
        safe, reason = is_safe_query("SELECT * FROM customers")
        self.assertTrue(safe)
        self.assertEqual(reason, "OK")

        for query in [
            "DELETE FROM customers",
            "DROP TABLE customers",
            "UPDATE customers SET email = 'x'",
            "INSERT INTO customers VALUES (1)",
            "ALTER TABLE customers ADD COLUMN password VARCHAR(100)",
            "SELECT * FROM customers; DROP TABLE customers;",
            "SELECT * FROM customers WHERE email = 'x' OR 1=1 --",
        ]:
            safe, _ = is_safe_query(query)
            self.assertFalse(safe)

    def test_classify_question_handles_database_and_non_database_requests(self):
        database_result = classify_question("How many customers are from Berlin?")
        self.assertEqual(database_result["category"], "database")

        non_database_result = classify_question("What's the weather?")
        self.assertEqual(non_database_result["category"], "non_database")

        vague_result = classify_question("customers")
        self.assertEqual(vague_result["category"], "ambiguous")

    @patch("src.server.urllib.request.urlopen")
    def test_ollama_response_is_parsed_as_sql(self, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"response": json.dumps({"sql": "SELECT COUNT(*) FROM customers"})}).encode()
        query = generate_sql_with_ollama("How many customers are there?", "customers.id (integer)")
        self.assertEqual(query, "SELECT COUNT(*) FROM customers")

    def test_unsafe_intent_is_rejected_before_ollama(self):
        self.assertTrue(has_unsafe_sql_intent("DROP TABLE customers"))
        self.assertTrue(has_unsafe_sql_intent("Call the function that deletes old orders"))
        self.assertFalse(has_unsafe_sql_intent("How many customers are there?"))

    def test_ask_database_rejects_raw_sql_and_injection_patterns(self):
        questions = [
            "SELECT * FROM customers WHERE email = 'admin' OR 1=1 --",
            "' OR '1'='1",
            "SELECT * FROM customers",
            "UNION SELECT email FROM customers",
        ]

        for question in questions:
            with self.subTest(question=question):
                response = asyncio.run(call_tool("ask_database", {"question": question}))
                text = "\n".join(item.text for item in response)
                self.assertIn("rejected", text.lower())


if __name__ == "__main__":
    unittest.main()
