# MCP Prompts & Resources POC

Minimal MCP demo using two static resource URIs and two parameterized prompts. The MCP client discovers capabilities and combines resource text with a prompt for an optional Groq response.

## Requirements

- Python 3.11 or newer
- Groq API key (optional: needed only for live LLM output)

## Setup (Linux/macOS)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python client.py
```

This works without Groq and demonstrates MCP discovery, resource reading and prompt retrieval.

To enable live generation:

```bash
export GROQ_API_KEY="your_key_here"
python client.py
```

`GROQ_MODEL` defaults to `llama-3.3-70b-versatile` and can be changed with an environment variable.

## Optional MCP Inspector

```bash
npx -y @modelcontextprotocol/inspector
```

Connect using `stdio`, command set to your virtual environment's **absolute** Python path, and arguments set to the **absolute** path of `server.py`. Alternatively, with `uv` installed run `uv run mcp dev server.py`.

## Demo notes

- Resources: `project://requirements` and `project://architecture`.
- Prompts: `summarize_project` and `explain_technical`.
- To demonstrate updated context, modify `data/requirements.md` and run `python client.py` again.
- To demonstrate another resource/prompt combination, change the URI and prompt selected in `client.py`.
- No frontend, database, vector index, or production deployment.
