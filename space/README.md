---
title: SQL MCP Server Guardrail Demo
emoji: 🛡
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: Read-only SQL guardrails for language agents, with the injection bypass the eval suite caught
---

# SQL MCP Server — guardrail demo

The guardrail layer from a read-only SQL MCP server. An MCP client asks a
natural-language question, a local Ollama model turns it into SQL, and the
server validates that SQL before it reaches PostgreSQL.

There is no database and no model in this Space. It runs the guardrail
functions on their own so the accept/reject decisions are visible.

Safety category scores 10/10. Full eval run: 68% (27/40) with `llama3.2`.

Source: https://github.com/ansisarma/sql-mcp-server
