
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

Expected startup output:

```text
========================================
          MCP AI ASSISTANT
========================================
Connected successfully.
Ask a question about the project.
Type 'exit' to quit.
```

The MCP client starts the server using stdio and establishes the connection automatically.

## 9. Agent Execution Example

User question:

```text
Summarize the project's requirements for my manager.
```

Example output:

```text
AGENT ACTIVITY
----------------------------------------

[1] Reading: Project Requirements
    Tool: read_mcp_resource
    Status: Completed

[2] Getting Instructions: Summarize Project
    Tool: get_mcp_prompt
    Audience: manager
    Status: Completed

AI RESPONSE
----------------------------------------

The project aims to build a document
assistant that allows employees to upload
PDF documents and ask questions.

Key requirements include:
- PDF upload
- Document-based question answering
- Source references
- Handling missing information

----------------------------------------
Sources: Requirements
Prompt: Summarize Project
========================================
```

The actual wording and tool-call order may vary.

## 10. Test Cases

The system supports two Resources and two Prompts.

We can test all four possible combinations.

### Case 1: Requirements + Summary

**Question:**

```text
Summarize the project's requirements for my manager.
```

Expected:

```text
Resource: project://requirements
Prompt: summarize_project
Audience: manager
```

### Case 2: Architecture + Technical Explanation

**Question:**

```text
Explain the technical architecture of our project to a developer.
```

Expected:

```text
Resource: project://architecture
Prompt: explain_technical
Audience: developer
```

### Case 3: Architecture + Summary

**Question:**

```text
Give my manager a high-level summary of our technical architecture.
```

Expected:

```text
Resource: project://architecture
Prompt: summarize_project
Audience: manager
```

### Case 4: Requirements + Technical Explanation

**Question:**

```text
Explain the project's functional requirements and constraints in detail to a developer.
```

Expected:

```text
Resource: project://requirements
Prompt: explain_technical
Audience: developer
```

### Bonus: Multiple Resources

**Question:**

```text
Compare the project's functional requirements
with its technical architecture.
```

The agent may retrieve:

```text
project://requirements
project://architecture
```

This demonstrates retrieval from multiple MCP Resources within the same agent workflow.

**Note:** These are expected tool selections. Because Groq makes the tool-call decisions, actual selection can vary. Check the terminal's Agent Activity output.

## 11. Dynamic Resource Updates

MCP Resources are backed by local Markdown files.

For example, update:

```text
data/architecture.md
```

Add a new architectural detail:

```text
The backend uses Redis to cache frequently
requested document responses.
```

Then ask:

```text
Explain the current backend architecture.
```

The agent can retrieve the updated content from the MCP Resource without requiring changes to `client.py` or `agent.py`.

This demonstrates how resource content can be maintained independently of the agent implementation.

The Redis statement is an example for testing dynamic resource updates, not a claim about infrastructure deployed by this POC.

## 12. Tool-Calling Behavior

The agent uses Groq's native tool-calling mechanism.

Initially, we configured:

```python
tool_choice="auto"
```

This allows Groq to decide whether to call a tool or generate an answer directly.

### Issue Encountered

During testing, we received:

```text
Assistant Error: The agent did not retrieve
both an MCP resource and an MCP prompt.
```

The agent had successfully retrieved the requirements resource but skipped the MCP Prompt.

Example:

```text
[1] Reading: Project Requirements
    Tool: read_mcp_resource
    Status: Completed
```

The agent then attempted to finish without calling `get_mcp_prompt`.

Our application requires both types of MCP retrieval before accepting the final answer.

### Why This Happens

With `tool_choice="auto"`, Groq can decide that it has enough information and stop requesting tools.

Instructions in the system prompt do not guarantee that every required tool will be called.

### Recommended Fix

The application should enforce missing tool calls through agent orchestration.

Expected logic:

```text
Start
  |
  v
Retrieve Resource?
  |
  +-- Missing --> Require resource tool
  |
  v
Retrieve Prompt?
  |
  +-- Missing --> Require prompt tool
  |
  v
Generate Final Answer
```

A possible approach is dynamically selecting the tool-choice setting:

```python
if not retrieved_resources and not retrieved_prompts:
    tool_choice = "required"

elif not retrieved_resources:
    tool_choice = {
        "type": "function",
        "function": {"name": "read_mcp_resource"},
    }

elif not retrieved_prompts:
    tool_choice = {
        "type": "function",
        "function": {"name": "get_mcp_prompt"},
    }

else:
    tool_choice = "auto"
```

Support for specific tool-choice options depends on the selected Groq model.

An alternative is to retain automatic selection and ask the model to call the missing tool.

**Implementation status:** This is a recommended improvement. The four test cases should be retested after implementing it.

## 13. Current POC Scope

### Implemented

- MCP Server using Python
- MCP Resources
- MCP Prompts
- MCP Client using stdio
- Groq AI integration
- Native function/tool calling
- Dynamic resource and prompt discovery
- Agent execution loop
- Human-readable terminal activity
- Source and prompt reporting
- Multiple-resource retrieval support

### Not Included

- Web frontend
- Database
- Authentication
- PDF upload
- Vector database or RAG pipeline
- Deployment infrastructure
- Production-grade monitoring

The documents served by this POC describe a separate sample Document Assistant project. Their contents should not be confused with features implemented in this MCP demonstration.

## 14. Key Learnings

This POC demonstrates:

1. **MCP Resources** expose reusable information.
2. **MCP Prompts** expose reusable instructions.
3. **MCP Clients** discover and retrieve server capabilities.
4. **Groq agents** dynamically select tools using LLM reasoning.
5. **Python adapters** bridge Groq function calls with MCP operations.
6. **Agent orchestration** ensures mandatory steps are completed.
7. **Resource content** can change independently of agent code.

## 15. Conclusion

This project demonstrates how MCP Resources and Prompts can be integrated into a Groq-powered AI assistant.

Instead of manually selecting a document and prompt, the user asks a natural-language question.

The Groq agent determines which MCP capabilities are relevant, Python executes the requested operations, and the retrieved information is used to generate a grounded response.

The result is a lightweight proof of concept for understanding MCP integration and AI agent tool calling.
