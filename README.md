# MCP Playground — FastAPI, Groq & Model Context Protocol

![Python](https://img.shields.io/badge/Python-FastAPI-009688?logo=fastapi&logoColor=white)
![MCP](https://img.shields.io/badge/Protocol-MCP-6366F1)
![Groq](https://img.shields.io/badge/LLM-Groq-F55036)
![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite&logoColor=white)

A full-stack proof of concept demonstrating how AI agents can dynamically discover and interact with **MCP Tools, Resources, and Prompts** using Groq's native function-calling capabilities.

The application supports **authenticated users with role-based access**, custom agent creation with an **approval workflow**, configurable system prompts, automatic and manual MCP operation selection, execution tracking, result caching, and administrative management of users and MCP tools.

The backend is built with **Python, FastAPI, FastMCP, and Groq**, while the frontend uses **Next.js, React, and TypeScript**.

No LangChain is required.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Backend Project Structure](#3-backend-project-structure)
4. [Authentication and Roles](#4-authentication-and-roles)
5. [MCP Server](#5-mcp-server)
6. [Dynamic MCP Discovery and Groq Schemas](#6-dynamic-mcp-discovery-and-groq-schemas)
7. [Default Assistant and Custom AI Agents](#7-default-assistant-and-custom-ai-agents)
8. [Agent Approval Workflow](#8-agent-approval-workflow)
9. [Auto and Manual Modes](#9-auto-and-manual-modes)
10. [MCP Dispatcher](#10-mcp-dispatcher)
11. [MCP Result Caching](#11-mcp-result-caching)
12. [Tool Management](#12-tool-management)
13. [Frontend Overview](#13-frontend-overview)
14. [Backend API](#14-backend-api)
15. [Installation and Setup](#15-installation-and-setup)
16. [Running Backend Tests](#16-running-backend-tests)
17. [End-to-End Testing](#17-end-to-end-testing)
18. [Out-of-Scope Handling](#18-out-of-scope-handling)
19. [Error Handling](#19-error-handling)
20. [Known Limitations](#20-known-limitations)
21. [Conclusion](#21-conclusion)

---

## 1. Project Overview

The MCP Playground demonstrates how the Model Context Protocol (MCP) can be integrated with configurable AI agents.

The system supports:

- Dynamic discovery of MCP Tools, Resources, and Prompts.
- Groq-based tool selection and execution.
- Token-based authentication with User, Manager, and Admin roles.
- A **Default Assistant** for general chat without MCP tools.
- Creation and management of custom AI agents.
- An approval workflow (Draft, Pending, Approved, Rejected) reviewed by Admins and Managers.
- Custom system instructions for each agent.
- Agent-specific MCP tool permissions.
- Automatic and manual operation selection.
- MCP execution logs displayed in the frontend.
- Caching of supported MCP operations.
- Administrative management of users, managers, and MCP tools.
- SQLite persistence for agents, users, and tool settings.

The primary objective is to demonstrate MCP integration without relying on hardcoded keyword-based routing.

## 2. System Architecture

The project consists of two separate repositories.

### Backend

Repository: `mcp-prompts-resources-poc`

Responsible for:

- FastAPI endpoints.
- Authentication, tokens, and role-based permissions.
- User, manager, and tool management.
- MCP server registration.
- MCP capability discovery.
- Groq agent orchestration and the Default Assistant.
- Function schema adaptation.
- MCP operation execution.
- Custom agent management and approval status.
- Result caching.

### Frontend

Repository: `mcp-playground-frontend`

Responsible for:

- Sign-in and role-based views.
- Custom agent creation, submission, and selection.
- Chat interface.
- Auto and Manual mode selection.
- MCP capability selection.
- Execution log visualization.
- Admin and Manager dashboards.

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
                      v
             Auth Dependencies
        (token verification + role checks)
                      |
          +-----------+-----------+
          |                       |
          v                       v
   Default Assistant        Agent Registry
   (no MCP tools)             (SQLite)
          |                       |
          |                       v
          |                MCP Discovery
          |                       |
          |                       v
          |                   agent.py
          |              Groq Orchestration
          |                       |
          |                       v
          |                tool_schemas.py
          |             Dynamic Schema Adapter
          |                       |
          |                       v
          |                Groq Function API
          |                       |
          |                       v
          |                Tool Selection
          |                       |
          |                       v
          |                MCP Dispatcher
          |                       |
          |                 Cache Check
          |                       |
          |                       v
          |                  MCP Client
          |                       |
          |                       v
          |                   server.py
          |                    FastMCP
          |                       |
          |            +----------+----------+
          |            |          |          |
          |            v          v          v
          |          Tools     Resources   Prompts
          |            |          |          |
          |            +----------+----------+
          |                       |
          +-----------+-----------+
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
├── api.py                          # FastAPI application and core endpoints
├── agent.py                        # Groq calls, tool execution, agent responses
├── server.py                       # FastMCP tools and resources
├── prompts.py                      # Reusable MCP prompts
├── tool_schemas.py                 # Groq-compatible function definitions
├── client.py
│
├── auth/
│   ├── routes.py                   # Authentication routes
│   ├── tokens.py                   # Access token creation and verification
│   ├── dependencies.py             # FastAPI dependencies (current user)
│   ├── permissions.py              # Role-based permission checks
│   ├── admin_routes.py             # Admin-only routes
│   ├── user_management_routes.py   # User and manager account management
│   └── tool_management_routes.py   # MCP tool management
│
├── constants/
│   ├── config.py                   # Application and Groq configuration
│   ├── instructions.py
│   ├── paths.py
│   └── system_prompts.py           # System prompt templates
│
├── models/
│   └── agent_config.py             # Agent configuration models
│
├── services/
│   ├── agent_registry.py           # Agent persistence and approval status
│   ├── default_assistant.py        # General chat without MCP tools
│   ├── mcp_cache.py                # TTL-based MCP result cache
│   ├── mcp_discovery.py            # MCP capability discovery
│   ├── mcp_dispatcher.py           # MCP operation execution
│   ├── tool_registry.py            # Registered tools and availability
│   └── user_service.py             # User account operations
│
├── scripts/
│   └── bootstrap_admin.py          # Creates the first administrator account
│
├── data/
│   ├── requirements.md             # Source for project://requirements
│   ├── architecture.md             # Source for project://architecture
│   └── agents.db                   # SQLite database
│
├── backups/
├── tests/
│
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── .env.example
├── .env
├── .gitignore
└── README.md
```

### File Responsibilities

| File | Responsibility |
|---|---|
| `api.py` | Defines FastAPI endpoints and registers the route modules |
| `agent.py` | Handles Groq calls, tool execution, and agent responses |
| `server.py` | Registers native MCP tools and resources |
| `prompts.py` | Defines reusable MCP prompts |
| `tool_schemas.py` | Generates Groq-compatible function definitions |
| `auth/routes.py` | Authentication endpoints |
| `auth/tokens.py` | Creates and verifies access tokens |
| `auth/dependencies.py` | Resolves the current user for protected endpoints |
| `auth/permissions.py` | Enforces role-based access |
| `auth/admin_routes.py` | Admin-only endpoints |
| `auth/user_management_routes.py` | Manages User and Manager accounts |
| `auth/tool_management_routes.py` | Manages MCP tool descriptions and availability |
| `models/agent_config.py` | Defines custom agent configuration models |
| `services/agent_registry.py` | Manages agent persistence and approval status using SQLite |
| `services/default_assistant.py` | Handles general chat when no custom agent is selected |
| `services/mcp_discovery.py` | Discovers MCP tools, resources, and prompts |
| `services/mcp_dispatcher.py` | Executes MCP operations |
| `services/mcp_cache.py` | Manages cached MCP results |
| `services/tool_registry.py` | Tracks registered tools and their availability |
| `services/user_service.py` | Creates, updates, and looks up user accounts |
| `constants/config.py` | Application and Groq configuration |
| `constants/system_prompts.py` | System prompt templates |
| `scripts/bootstrap_admin.py` | Creates the initial administrator account |
| `data/agents.db` | Stores custom agent configurations |

`client.py` and some constants modules remain subject to the planned backend cleanup. Their continued use should be verified before removal.

## 4. Authentication and Roles

The backend uses token-based authentication. Protected endpoints verify the access token and the caller's role before running.

### Roles

| Capability | User | Manager | Admin |
|---|:---:|:---:|:---:|
| Chat with the Default Assistant or approved agents | ✅ | ✅ | ✅ |
| Create, edit, and delete agents; submit them for approval | ✅ | ✅ | ✅ |
| Review, approve, and reject submitted agents | — | ✅ | ✅ |
| Manage regular User accounts | — | ✅ | ✅ |
| Manage Manager accounts | — | — | ✅ |
| Manage MCP tools (descriptions and availability) | — | — | ✅ |

Permissions are enforced on the backend. The frontend hides restricted sections, but access is never decided by the frontend alone.

### Creating the First Administrator

Run the bootstrap script once after setting up the environment:

```bash
python -m scripts.bootstrap_admin
```

The initial administrator can then create Manager and User accounts from the Admin dashboard.

## 5. MCP Server

The MCP server is implemented using FastMCP.

It exposes three types of capabilities:

1. MCP Tools
2. MCP Resources
3. MCP Prompts

### 5.1 MCP Tools

The server exposes native tools, such as:

**`get_project_overview`**

Purpose: Retrieve an overview of the project.

Native tools are discovered dynamically. Their Groq-facing function names are prefixed, for example:

```text
mcp_tool__get_project_overview
```

The dispatcher removes the prefix before executing the native MCP tool.

### 5.2 MCP Resources

Resources expose project information that can be retrieved through the MCP client.

| Resource | URI | Source |
|---|---|---|
| Project Requirements | `project://requirements` | `data/requirements.md` |
| Project Architecture | `project://architecture` | `data/architecture.md` |

These resources allow agents to retrieve project information without embedding the document contents directly in the agent's system prompt.

Resource contents can be updated by editing the corresponding Markdown files.

### 5.3 MCP Prompts

The server exposes two reusable prompts.

**`summarize_project`**

Provides reusable instructions for generating project summaries.

**`explain_technical`**

Provides reusable instructions for explaining technical project information.

Prompt names and argument definitions are discovered from the MCP server.

## 6. Dynamic MCP Discovery and Groq Schemas

The application dynamically discovers MCP capabilities through `services/mcp_discovery.py`.

The discovered capabilities include:

- Native MCP tool names and input schemas.
- Available resource URIs.
- MCP prompt names and argument definitions.

`tool_schemas.py` converts this information into Groq-compatible function definitions.

### Available Groq Functions

| Function | Purpose |
|---|---|
| `mcp_tool__<tool_name>` | Execute a native MCP tool (for example, `mcp_tool__get_project_overview`) |
| `read_mcp_resource` | Retrieve an MCP resource |
| `get_mcp_prompt` | Retrieve reusable MCP prompt instructions |

Each native tool's input schema is obtained from discovery. Resource URIs and prompt names are also discovered dynamically.

The schema adapter translates MCP capabilities into the function format required by Groq. It is not intended to duplicate the MCP server's definitions.

## 7. Default Assistant and Custom AI Agents

### Default Assistant

When no custom agent is selected, requests are handled by the **Default Assistant** (`services/default_assistant.py`). It answers general questions through Groq and does not execute MCP tools.

### Custom Agents

The application supports creating and managing multiple custom agents.

Each agent can have its own:

- Name.
- Description.
- System prompt.
- MCP tool access configuration.
- Allowed MCP tools.
- Cache settings.
- Approval status.

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

When a user selects an approved agent:

1. The frontend sends the selected agent and user message to FastAPI with the user's access token.
2. The backend verifies the token and retrieves the agent configuration.
3. The agent's system instructions are applied.
4. Permitted MCP capabilities are prepared for Groq.
5. Groq selects relevant operations.
6. The backend executes selected MCP operations.
7. The results are returned to Groq.
8. The generated answer and execution information are returned to the frontend.

Agents share the same underlying MCP server but can have different instructions and native tool permissions.

## 8. Agent Approval Workflow

Custom agents must be approved before they can run.

```text
  Create / Edit            Submit for Approval           Review
  ┌────────┐             ┌──────────────┐          ┌──────────────┐
  │ Draft  │ ──────────► │   Pending    │ ───────► │   Approved   │
  └────────┘             └──────────────┘    │     └──────────────┘
                                             │     ┌──────────────┐
                                             └───► │   Rejected   │
                                                   └──────────────┘
```

| Status | Meaning |
|---|---|
| Draft | Saved but not yet submitted for review |
| Pending | Waiting for Admin or Manager approval |
| Approved | Available for selection and execution |
| Rejected | Declined by a reviewer |

Admins and Managers review submissions from the **Agent Reviews** section of their dashboard.

## 9. Auto and Manual Modes

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

## 10. MCP Dispatcher

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

## 11. MCP Result Caching

The application includes a TTL-based cache in:

```text
services/mcp_cache.py
```

Caching can reduce repeated MCP retrieval operations.

The agent validates cacheable operations before using cached results.

The cache supports applicable resource and prompt retrieval operations.

Cache behavior depends on the selected agent configuration and the operation being executed.

## 12. Tool Management

Admins can manage the registered MCP tools through `auth/tool_management_routes.py` and `services/tool_registry.py`, using the **Tool Management** section of the Admin dashboard.

Admins can:

- View registered MCP tools.
- Edit tool descriptions.
- Enable or disable operations.

Tool management is restricted to the Admin role. Managers cannot access it.

## 13. Frontend Overview

The frontend is implemented using Next.js, React, TypeScript, and Tailwind CSS. It is maintained in the separate `mcp-playground-frontend` repository, which documents its project structure, components, and UI in detail.

The interface contains three main panels.

**Left Panel — Agents, Tools, and Account**

- Select the Default Assistant or an approved agent.
- Create and configure custom agents, and submit them for approval.
- View Draft, Pending, and Rejected agents.
- Switch between Auto and Manual modes.
- Browse available MCP tools.
- Sign in or out.

**Center Panel — Chat**

- Enter questions.
- View AI-generated answers rendered as Markdown.
- Interact with the Default Assistant or the selected agent.

**Right Panel — Execution Log**

- View MCP operation execution.
- Inspect selected operations.
- View execution results and errors.
- Observe cache behavior when reported.

Admins and Managers also have dashboards for user management, agent reviews, and (Admin only) manager and tool management.

## 14. Backend API

The FastAPI application exposes the following endpoint groups.

| Endpoint | Purpose |
|---|---|
| `GET /api/mcp/capabilities` | Retrieve discovered MCP capabilities |
| `/api/agents` | Manage custom agent configurations and submit them for approval |
| `POST /api/chat` | Execute a question using the Default Assistant or the selected agent |

Authentication, agent review, user management, and tool management endpoints are provided by the route modules in the `auth/` package.

For the complete generated API documentation, including all authentication and admin routes, visit:

```text
http://127.0.0.1:8000/docs
```

## 15. Installation and Setup

### Prerequisites

- Python environment compatible with the backend dependencies.
- Node.js and npm (for the frontend).
- Groq API key.
- Git.

### 15.1 Backend Setup

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

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Set at least:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Add any authentication settings listed in `.env.example`. Use a Groq model supported by your account and compatible with tool calling.

Create the first administrator account:

```bash
python -m scripts.bootstrap_admin
```

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

### 15.2 Frontend Setup

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

### 15.3 Docker

A `Dockerfile` is included for containerized runs.

```bash
docker build -t mcp-playground-backend .
docker run --env-file .env -p 8000:8000 mcp-playground-backend
```

## 16. Running Backend Tests

The backend includes automated tests covering MCP integration, agent execution, schema handling, caching, authentication, and related functionality.

Run:

```bash
python -m pytest -q
```

Rerun the test suite after any changes to authentication, schema generation, MCP dispatching, agent execution, or API behavior.

## 17. End-to-End Testing

The final testing workflow covers two custom agents:

1. Project Assistant
2. Project Technical Analyst

Before testing, sign in and make sure both agents are in the **Approved** state.

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

### Authentication and Approval Testing

- Calling a protected endpoint without a valid token is rejected.
- A Manager cannot reach Admin-only endpoints (manager management, tool management).
- A Draft or Pending agent cannot run until it is approved.
- A Rejected agent cannot run.
- Disabling a tool as an Admin removes it from the available operations.

## 18. Out-of-Scope Handling

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

## 19. Error Handling

The application should distinguish between:

- Unauthenticated or unauthorized requests.
- Unsupported or unavailable MCP operations.
- Invalid MCP arguments.
- Missing resources or prompts.
- Groq API failures.
- Agent execution failures.
- Out-of-scope user requests.

The frontend displays meaningful error messages.

For example, a genuine backend failure may be reported as:

```text
Backend error: Unable to execute the custom agent.
Check the backend logs.
```

Out-of-scope questions should instead receive an appropriate agent-level response.


## 20. Conclusion

The project uses the MCP server as the source of truth for available capabilities while adapting discovered definitions into the format required by Groq.

Together with token-based authentication, role-based permissions, an agent approval workflow, and administrative tool management, this provides a foundation for experimenting with MCP-enabled AI agents and extending the system with additional tools, resources, prompts, and agent configurations.
