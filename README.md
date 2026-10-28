
# MCP Prompts & Resources POC — Groq Tool-Calling Agent

A lightweight Python proof of concept demonstrating how an AI agent can automatically discover, select, and retrieve MCP Resources and MCP Prompts using Groq's native tool-calling capabilities.

The application runs in the terminal without LangChain, a frontend, or a database.

## 1. Project Overview

This project demonstrates how the Model Context Protocol (MCP) can be integrated with an AI agent to retrieve project information and reusable prompt instructions dynamically.

The system contains three main components:

- **MCP Server:** Exposes project Resources and Prompts.
- **MCP Client:** Connects to the server and performs MCP operations.
- **Groq AI Agent:** Understands user questions, selects relevant tools, retrieves information, and generates answers.

The agent uses Groq's native function calling rather than hardcoded keyword-based routing.

## 2. Project Structure

```text
mcp-prompts-resources-poc/
│
├── server.py
├── client.py
├── agent.py
│
├── data/
│   ├── requirements.md
│   └── architecture.md
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

### File Responsibilities

| File | Responsibility |
|------|----------------|
| `server.py` | Defines MCP Resources and Prompts |
| `client.py` | Connects to MCP server and provides interactive CLI |
| `agent.py` | Manages Groq tool calling and agent execution |
| `requirements.md` | Contains sample project requirements |
| `architecture.md` | Contains sample technical architecture |
| `.env` | Stores Groq API configuration |

## 3. MCP Resources

Resources expose information that MCP clients can retrieve.

Our server provides two resources:

### Resource 1: Project Requirements

**URI:** `project://requirements`

Reads information from:

`data/requirements.md`

Contains:
- Project overview
- Functional requirements
- Features
- Constraints
- Future considerations

### Resource 2: Project Architecture

**URI:** `project://architecture`

Reads information from:

`data/architecture.md`

Contains:
- System architecture
- Frontend and backend technologies
- Document processing
- Embeddings and vector storage
- LLM integration
- Technical constraints

Resources can be updated by editing the Markdown files without modifying the agent's tool schemas.

## 4. MCP Prompts

Prompts are reusable instructions exposed by the MCP server.

Our server provides two prompts:

### Prompt 1: summarize_project

**Name:** `summarize_project`

Purpose: Generate a concise project summary for a specified audience.

Example audiences:
- Manager
- Developer

### Prompt 2: explain_technical

**Name:** `explain_technical`

Purpose: Generate a detailed technical explanation for a specified audience.

Example audiences:
- Manager
- Developer

The agent selects an appropriate prompt based on the user's request.

## 5. Groq AI Agent

The Groq AI Agent is implemented in `agent.py`.

Its responsibilities include:

1. Discover available MCP Resources and Prompts.
2. Register corresponding function-calling schemas with Groq.
3. Send the user question to Groq.
4. Inspect Groq's tool-call requests.
5. Execute the requested operations through the MCP client.
6. Return retrieved information to Groq.
7. Generate a final response using the retrieved context.

### Available Agent Tools

The agent exposes two Groq function-call adapters:

**Tool 1: read_mcp_resource**

```python
read_mcp_resource(uri: str)
```

Retrieves a resource from the MCP server.

Example:

```text
read_mcp_resource("project://requirements")
```

**Tool 2: get_mcp_prompt**

```python
get_mcp_prompt(name: str, audience: str)
```

Retrieves prompt instructions from the MCP server.

Example:

```text
get_mcp_prompt("explain_technical", "developer")
```

These are Groq-callable Python functions that interact with MCP. They are not separate MCP Tools exposed by the server.

## 6. System Architecture

```text
                  USER
                    |
                    v
                client.py
             Interactive CLI
                    |
                    v
                agent.py
              Groq AI Agent
                    |
                    v
          Groq Tool-Calling API
                    |
                    v
             Tool Selection
                    |
           +--------+--------+
           |                 |
           v                 v
  read_mcp_resource    get_mcp_prompt
           |                 |
           +--------+--------+
                    |
                    v
                MCP Client
                    |
              stdio transport
                    |
                    v
                server.py
                MCP Server
                    |
           +--------+--------+
           |                 |
           v                 v
       Resources           Prompts
           |                 |
    requirements.md     summarize_project
    architecture.md     explain_technical
           |                 |
           +--------+--------+
                    |
                    v
              Tool Results
                    |
                    v
               Groq Agent
                    |
                    v
               AI Response
```

### Important Distinction

MCP provides a standardized mechanism to expose and retrieve Resources and Prompts.

Groq handles reasoning, tool selection, and response generation.

Python executes the function calls and communicates with the MCP server.

## 7. Installation

### Prerequisites

- Python 3.11 or higher recommended
- Groq API key
- Virtual environment

### Step 1: Create Virtual Environment

```bash
python3 -m venv .venv
```

### Step 2: Activate Virtual Environment

Linux/macOS:

```bash
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install mcp groq python-dotenv
```

Alternatively, if `requirements.txt` is configured:

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Never commit your `.env` file to GitHub.

## 8. Running the Application

Run:

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
