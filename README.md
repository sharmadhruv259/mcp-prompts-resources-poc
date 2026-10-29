# MCP Playground — FastAPI, Groq & Model Context Protocol

A full-stack proof of concept demonstrating how AI agents can dynamically discover and interact with **MCP Tools, Resources, and Prompts** using Groq's native function-calling capabilities.

The application supports custom agent creation, configurable system prompts, automatic and manual MCP operation selection, execution tracking, and result caching.

The backend is built with **Python, FastAPI, FastMCP, and Groq**, while the frontend uses **Next.js, React, and TypeScript**.

No LangChain is required.

---

## 1. Project Overview

The MCP Playground demonstrates how the Model Context Protocol (MCP) can be integrated with configurable AI agents.

The system supports:

- Dynamic discovery of MCP Tools, Resources, and Prompts.
- Groq-based tool selection and execution.
- Creation and management of custom AI agents.
- Custom system instructions for each agent.
- Agent-specific MCP tool permissions.
- Automatic and manual operation selection.
- MCP execution logs displayed in the frontend.
- Caching of supported MCP operations.
- SQLite persistence for custom agent configurations.
- Multiple agents with different responsibilities.

The primary objective is to demonstrate MCP integration without relying on hardcoded keyword-based routing.

## 2. System Architecture

The project consists of two separate repositories.

### Backend

Repository: `mcp-prompts-resources-poc`

Responsible for:

- FastAPI endpoints.
- MCP server registration.
- MCP capability discovery.
- Groq agent orchestration.
- Function schema adaptation.
- MCP operation execution.
- Custom agent management.
- Result caching.

### Frontend

Repository: `mcp-playground-frontend`

Responsible for:

- Custom agent creation and selection.
- Agent configuration.
- Chat interface.
- Auto and Manual mode selection.
- MCP capability selection.
- Execution log visualization.
- Displaying agent responses and errors.

### Request Flow

```text
                    USER
                      |
                      v
               Next.js Frontend
                      |
                      v
                  FastAPI
                   api.py
                      |
             +--------+--------+
             |                 |
             v                 v
       Agent Registry       MCP Discovery
        (SQLite)                |
             |                  |
             +--------+---------+
                      |
                      v
                  agent.py
             Groq Orchestration
                      |
                      v
               tool_schemas.py
            Dynamic Schema Adapter
                      |
                      v
               Groq Function API
                      |
                      v
                Tool Selection
                      |
                      v
               MCP Dispatcher
                      |
                Cache Check
                      |
                      v
                MCP Client
                      |
                      v
                  server.py
                  FastMCP
                      |
           +----------+----------+
           |          |          |
           v          v          v
         Tools     Resources    Prompts
           |          |          |
           +----------+----------+
                      |
                      v
                MCP Results
                      |
                      v
                Groq Agent
                      |
                      v
                FastAPI Response
                      |
                      v
                Next.js Frontend
```

The backend uses an in-process MCP client connection, so the current application does not require a separately running MCP server process.

## 3. Backend Project Structure

```text
mcp-prompts-resources-poc/
│
├── api.py
├── agent.py
├── server.py
├── prompts.py
├── tool_schemas.py
├── client.py
│
├── constants/
│   ├── config.py
│   ├── instructions.py
│   └── paths.py
│
├── models/
│   └── agent_config.py
│
├── services/
│   ├── agent_registry.py
│   ├── mcp_cache.py
│   ├── mcp_discovery.py
│   └── mcp_dispatcher.py
│
├── data/
│   ├── requirements.md
│   ├── architecture.md
│   └── agents.db
│
├── tests/
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

### File Responsibilities

| File | Responsibility |
|---|---|
| `api.py` | Defines FastAPI endpoints for agents, chat, and MCP discovery |
| `agent.py` | Handles Groq calls, tool execution, and agent responses |
| `server.py` | Registers native MCP tools and resources |
| `prompts.py` | Defines reusable MCP prompts |
| `tool_schemas.py` | Generates Groq-compatible function definitions |
| `models/agent_config.py` | Defines custom agent configuration models |
| `services/agent_registry.py` | Manages agent persistence using SQLite |
| `services/mcp_discovery.py` | Discovers MCP tools, resources, and prompts |
| `services/mcp_dispatcher.py` | Executes MCP operations |
| `services/mcp_cache.py` | Manages cached MCP results |
| `constants/config.py` | Application and Groq configuration |
| `data/agents.db` | Stores custom agent configurations |

`client.py` and some constants modules remain subject to the planned backend cleanup. Their continued use should be verified before removal.

## 4. MCP Server

The MCP server is implemented using FastMCP.

It exposes three types of capabilities:

1. MCP Tools
2. MCP Resources
3. MCP Prompts

### 4.1 MCP Tools

The server exposes a native tool:

**`get_project_overview`**

Purpose: Retrieve an overview of the project.

The Groq-facing function name is prefixed as:

```text
mcp_tool__get_project_overview
```

The dispatcher removes the prefix before executing the native MCP tool.

### 4.2 MCP Resources

Resources expose project information that can be retrieved through the MCP client.

| Resource | URI | Source |
|---|---|---|
| Project Requirements | `project://requirements` | `data/requirements.md` |
| Project Architecture | `project://architecture` | `data/architecture.md` |

These resources allow agents to retrieve project information without embedding the document contents directly in the agent's system prompt.

Resource contents can be updated by editing the corresponding Markdown files.

### 4.3 MCP Prompts

The server exposes two reusable prompts.

**`summarize_project`**

Provides reusable instructions for generating project summaries.

**`explain_technical`**

Provides reusable instructions for explaining technical project information.

Prompt names and argument definitions are discovered from the MCP server.

## 5. Dynamic MCP Discovery and Groq Schemas

The application dynamically discovers MCP capabilities through `services/mcp_discovery.py`.

The discovered capabilities include:

- Native MCP tool names and input schemas.
- Available resource URIs.
- MCP prompt names and argument definitions.

`tool_schemas.py` converts this information into Groq-compatible function definitions.

### Available Groq Functions

| Function | Purpose |
|---|---|
| `mcp_tool__get_project_overview` | Execute the native MCP overview tool |
| `read_mcp_resource` | Retrieve an MCP resource |
| `get_mcp_prompt` | Retrieve reusable MCP prompt instructions |

The native MCP tool's input schema is obtained from discovery.

Resource URIs and prompt names are also discovered dynamically.

The schema adapter is responsible for translating MCP capabilities into the function format required by Groq. It is not intended to duplicate the MCP server's definitions.

## 6. Custom AI Agents

The application supports creating and managing multiple custom agents.

Each agent can have its own:

- Name.
- Description.
- System prompt.
- MCP tool access configuration.
- Allowed MCP tools.
- Cache settings.

Custom agent configurations are stored in SQLite.

### Example Agent 1: Project Assistant

**Purpose:** Provide general project information.

Typical responsibilities:

- Explain project requirements.
- Summarize architecture.
- Retrieve project resources.
- Provide project overviews.
- Retrieve reusable MCP prompts.

### Example Agent 2: Project Technical Analyst

**Purpose:** Provide technical analysis of the project.

Typical responsibilities:

- Analyze system architecture.
- Compare requirements and implementation design.
- Identify technical limitations.
- Explain system components.
- Recommend technical improvements based on project information.

### Agent Execution

When a user selects an agent:

1. The frontend sends the selected agent and user message to FastAPI.
2. The backend retrieves the agent configuration.
3. The agent's system instructions are applied.
4. Permitted MCP capabilities are prepared for Groq.
5. Groq selects relevant operations.
6. The backend executes selected MCP operations.
7. The results are returned to Groq.
8. The generated answer and execution information are returned to the frontend.

Agents share the same underlying MCP server but can have different instructions and native tool permissions.

## 7. Auto and Manual Modes

The frontend provides two operation-selection modes.

### Auto Mode

In Auto mode, Groq decides which available MCP operations are relevant to the user's question.

A single question may require multiple MCP operations.

Example:

```text
Use the project overview tool, read both
project resources, and explain the architecture.
```

The agent can request multiple operations before generating its final answer.

### Manual Mode

Manual mode allows the user to select permitted MCP operations.

In the current POC, Manual mode restricts available native MCP tools, but does not guarantee that Groq will call the selected operation.

Resource and prompt selection is not yet fully enforced in the same way.

This is a known limitation of the current implementation.

## 8. MCP Dispatcher

The MCP dispatcher is implemented in:

```text
services/mcp_dispatcher.py
```

It handles:

- Native MCP tool execution.
- MCP resource reading.
- MCP prompt retrieval.
- Argument handling.
- MCP operation errors.

The dispatcher provides a common execution layer between Groq's requested functions and the MCP client.

## 9. MCP Result Caching

The application includes a TTL-based cache in:

```text
services/mcp_cache.py
```

Caching can reduce repeated MCP retrieval operations.

The agent validates cacheable operations before using cached results.

The cache supports applicable resource and prompt retrieval operations.

Cache behavior depends on the selected agent configuration and the operation being executed.

## 10. Frontend Architecture

The frontend is implemented using Next.js, React, TypeScript, and Tailwind CSS.

### Project Structure

```text
mcp-playground-frontend/
│
├── app/
│   ├── page.tsx
│   ├── layout.tsx
│   └── globals.css
│
├── src/
│   ├── components/
│   │   ├── agents/
│   │   │   └── AgentForm.tsx
│   │   ├── chat/
│   │   │   └── ChatPanel.tsx
│   │   ├── execution/
│   │   │   └── ExecutionLog.tsx
│   │   ├── layout/
│   │   │   └── Sidebar.tsx
│   │   └── tools/
│   │       └── ToolSelector.tsx
│   │
│   ├── hooks/
│   │   ├── useAgents.ts
│   │   └── useMCPCapabilities.ts
│   │
│   ├── lib/
│   │   └── api.ts
│   │
│   ├── constants/
│   │   └── starters.ts
│   │
│   └── types/
│       ├── agents.ts
│       ├── chat.ts
│       ├── mcp.ts
│       └── tools.ts
│
├── package.json
├── .env.example
└── README.md
```

### Frontend Features

The interface contains three main panels.

**Left Panel — Agent and Tool Configuration**

- Select an existing agent.
- Create and configure custom agents.
- Switch between Auto and Manual modes.
- Select MCP operations.

**Center Panel — Chat**

- Enter questions.
- View AI-generated answers.
- Interact with the selected agent.

**Right Panel — Execution Log**

- View MCP operation execution.
- Inspect selected operations.
- View execution results and errors.
- Observe cache behavior when reported.

## 11. Backend API

The FastAPI application exposes the following endpoint groups.

| Endpoint | Purpose |
|---|---|
| `GET /api/mcp/capabilities` | Retrieve discovered MCP capabilities |
| `/api/agents` | Manage custom agent configurations |
| `POST /api/chat` | Execute a question using the selected agent |

The `/api/agents` group supports the application's agent-management operations.

For the complete generated API documentation, visit:

```text
http://127.0.0.1:8000/docs
```

## 12. Installation and Setup

### Prerequisites

- Python environment compatible with the backend dependencies.
- Node.js and npm.
- Groq API key.
- Git.

### 12.1 Backend Setup

Clone the backend repository and open its directory.

```bash
cd mcp-prompts-resources-poc
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Use a Groq model supported by your account and compatible with tool calling.

Start the FastAPI backend:

```bash
uvicorn api:app --reload
```

Backend address:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### 12.2 Frontend Setup

Open a separate terminal.

```bash
cd mcp-playground-frontend
```

Install dependencies:

```bash
npm install
```

Configure the frontend environment using the repository's `.env.example` file and the API base URL expected by `src/lib/api.ts`.

Start the frontend:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

Ensure the FastAPI backend is running before testing MCP operations from the frontend.

## 13. Running Backend Tests

The backend includes automated tests covering MCP integration, agent execution, schema handling, caching, and related functionality.

Run:

```bash
python -m pytest -q
```

The backend previously reached **63 passing tests**.

The test suite should be rerun after any changes to schema generation, MCP dispatching, agent execution, or API behavior.

## 14. End-to-End Testing

The final testing workflow covers two custom agents:

1. Project Assistant
2. Project Technical Analyst

### Project Assistant Tests

**Test 1: Native MCP Tool**

```text
Give me a complete overview of this project
using the available MCP tool.
```

Expected: The agent calls `get_project_overview`.

**Test 2: MCP Resource**

```text
What are the main requirements of this project?
```

Expected: The agent reads the requirements resource.

**Test 3: MCP Prompt**

```text
Retrieve the summarize_project MCP prompt
and show its instructions.
```

Expected: The agent retrieves the requested prompt.

### Project Technical Analyst Tests

**Test 1: Technical Architecture**

```text
Analyze the project's architecture and explain
its major technical components.
```

Expected: The agent reads the architecture resource.

**Test 2: Requirements Comparison**

```text
Compare the project requirements with the
architecture and identify potential gaps.
```

Expected: The agent retrieves relevant project information and provides a grounded comparison.

**Test 3: Multiple MCP Operations**

```text
Use the project overview tool, read both project
resources, and provide a technical analysis.
```

Expected: The agent requests multiple relevant MCP operations.

### Multi-Agent Testing

Test switching between Project Assistant and Project Technical Analyst.

Verify that:

- The correct agent configuration is selected.
- Each agent follows its own system prompt.
- Agent responses reflect their different responsibilities.
- Tool permissions remain agent-specific.
- Switching agents does not accidentally reuse the previous agent's configuration.

## 15. Out-of-Scope Handling

Custom agents are intended to answer questions relevant to their configured responsibilities.

Example out-of-scope question:

```text
What is the capital of France?
```

Desired response:

```text
Out of scope: This question is outside the selected
agent's responsibilities. Please ask a question
related to this agent's purpose or select a more
suitable agent.
```

This should be handled separately from genuine backend execution errors.

**Implementation status:** Strict out-of-scope enforcement is a planned improvement and should not be considered fully implemented until the backend changes and corresponding tests are completed.

System-prompt instructions alone do not guarantee that an LLM will reject every unrelated question.

## 16. Error Handling

The application should distinguish between:

- Unsupported or unavailable MCP operations.
- Invalid MCP arguments.
- Missing resources or prompts.
- Groq API failures.
- Agent execution failures.
- Out-of-scope user requests.

The frontend should display meaningful error messages.

For example, a genuine backend failure may be reported as:

```text
Backend error: Unable to execute the custom agent.
Check the backend logs.
```

Out-of-scope questions should instead receive an appropriate agent-level response.


The project uses the MCP server as the source of truth for available capabilities while adapting discovered definitions into the format required by Groq.

This provides a foundation for experimenting with MCP-enabled AI agents and extending the system with additional tools, resources, prompts, and agent configurations.
