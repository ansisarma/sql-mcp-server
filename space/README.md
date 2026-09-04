# HuggingFace Space

**Live: https://huggingface.co/spaces/Anshul174/sql-mcp-guardrails**

The deployed Space is a **static** HTML page, not a Gradio app. Two reasons:

1. HuggingFace now requires a paid PRO plan for Gradio and Docker Spaces. Static
   Spaces are free.
2. Gradio-Lite (Gradio in the browser via Pyodide) was tried first and fails to
   boot: its current build resolves `huggingface-hub>=0.33.5`, which has no pure
   Python wheel for Pyodide.

So the deployed page ports the three guardrail functions to JavaScript. It loads
instantly, costs nothing, and never sleeps. Behaviour was checked case by case
against the Python and matches, including eval case S9.

## Files here

| File | Status |
|---|---|
| `index.html` | **What is actually deployed.** Static page, JS port of the guardrails. |
| `app.py` | Gradio version. Kept for reference — needs a PRO Space, or run it locally with `python space/app.py`. |
| `guardrails.py` | Pure-Python guardrails, imported by `app.py`. Verbatim from `src/server.py`. |
| `requirements.txt` | For the Gradio version only. |

## Keeping them in sync

The guardrail logic now exists in three places: `src/server.py` (authoritative),
`space/guardrails.py` (Python copy), and the JS in `index.html`. If you change a
safety rule, change all three. Extracting the rules into one shared module and
generating the JS from it is the cleaner fix if this grows.
