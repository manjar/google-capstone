# ADK (Agent Development Kit) Reference for TimerMind

This document contains relevant ADK documentation extracted for the TimerMind project.

---

## Installation

```bash
pip install google-adk
pip install google-cloud-aiplatform  # For Vertex AI services
```

**Requirements:**
- Python 3.9 or higher
- Google Cloud project (for Vertex AI features)

---

## Core Concepts

### Agent
An AI agent powered by an LLM that can use tools and delegate to sub-agents.

### Session
Represents a **single, ongoing interaction** between a user and your agent system. Maintains the chronological sequence of messages and actions during one conversation thread.

**Session contains:**
- `id` - Unique session identifier
- `app_name` - Application name
- `user_id` - User identifier
- `events` - Chronological list of conversation events
- `state` - Temporary data for this conversation
- `last_update_time` - Timestamp of last activity

### Memory
A **searchable knowledge store** that spans multiple past sessions or external data sources. Used for long-term learning and personalization.

**Key difference:**
- Session = short-term, single conversation
- Memory = long-term, across all conversations

---

## SessionService Implementations

### InMemorySessionService
- In-memory storage (volatile)
- Data lost on restart
- Good for prototyping

### DatabaseSessionService
- SQLite-backed storage
- Persistent across restarts
- Local storage

### VertexAiSessionService (Recommended for TimerMind)
- Cloud-managed storage
- Persistent and scalable
- Requires Google Cloud project

```python
from google.adk.sessions import VertexAiSessionService

session_service = VertexAiSessionService(
    project_id="your-gcp-project-id",
    location="us-central1"
)

# Create session
session = session_service.create_session(
    app_name="timermind",
    user_id="user123"
)

# Get session
session = session_service.get_session(session_id=session.id)

# Add event to session
session_service.append_event(session_id=session.id, event=agent_event)

# List all sessions for user
sessions = session_service.list_sessions(user_id="user123")

# Delete session
session_service.delete_session(session_id=session.id)
```

---

## MemoryService Implementations

### InMemoryMemoryService
- Volatile memory storage
- Basic keyword matching
- Suitable for prototyping

### VertexAiMemoryBankService (Recommended for TimerMind)
- Persistent cloud storage
- **Semantic search** (not just keywords)
- LLM-powered memory extraction
- Automatically extracts relevant info from sessions

```python
from google.adk.memory import VertexAiMemoryBankService

memory_service = VertexAiMemoryBankService(
    project_id="your-gcp-project-id",
    location="us-central1"
)

# Store session into long-term memory
# Automatically extracts relevant information
memory_service.add_session_to_memory(session)

# Search long-term memory
results = memory_service.search_memory(
    query="user priority preferences",
    user_id="user123"
)
```

### VertexAiRagMemoryService
- Retrieval-augmented generation approach
- More advanced retrieval patterns

---

## Agent Definition

```python
from google.adk.agents import Agent

agent = Agent(
    name="agent_name",
    model="gemini-2.0-flash",
    description="What this agent does",
    instruction="""
    Detailed instructions for the agent behavior.
    - How to handle different situations
    - What tools to use when
    - How to format responses
    """,
    tools=[tool1, tool2, tool3],  # Custom tools available to agent
    sub_agents=[agent1, agent2]    # Optional sub-agents for delegation
)
```

**Key Properties:**
- `name` - Unique identifier for the agent
- `model` - LLM model to use (e.g., "gemini-2.0-flash")
- `description` - Short description of agent's purpose
- `instruction` - Detailed behavior instructions (system prompt)
- `tools` - List of tools the agent can call
- `sub_agents` - List of sub-agents for delegation

---

## Custom Tool Definition

Tools allow agents to perform actions and retrieve information.

```python
from google.adk.tools import FunctionTool

@FunctionTool
def create_timer(
    label: str,
    deadline_iso: str = None,
    category: str = "other"
) -> dict:
    """
    Create a new timer in the database.

    Args:
        label: Human-readable task name
        deadline_iso: Optional ISO 8601 deadline string
        category: Task category (work, personal, health, etc.)

    Returns:
        dict containing timer_id, success status, and computed scores
    """
    # Implementation here
    return {
        "timer_id": 123,
        "success": True,
        "urgency_score": 0.8,
        "importance_score": 0.6
    }
```

**Tool Requirements:**
- Decorated with `@FunctionTool`
- Clear docstring (agent uses this to understand the tool)
- Type hints for parameters
- Returns structured data (dict, list, etc.)

---

## Runner and Application

The Runner executes agents and manages services.

```python
from google.adk.runner import Runner

runner = Runner(
    agent=root_agent,
    session_service=session_service,
    memory_service=memory_service
)

# Execute agent with user input
response = runner.run(
    user_input="I need to submit my report by Friday",
    session_id=session.id
)
```

**Access Services:**
- `runner.session_service` - Session management
- `runner.memory_service` - Long-term memory

---

## Multi-Agent Architecture

### Sequential Agents
Agents execute in sequence, passing results forward.

```python
from google.adk.agents import SequentialAgent

pipeline = SequentialAgent(
    name="processing_pipeline",
    agents=[extraction_agent, scoring_agent, response_agent]
)
```

### Sub-Agent Delegation
Root agent delegates to specialized sub-agents.

```python
root_agent = Agent(
    name="orchestrator",
    model="gemini-2.0-flash",
    instruction="Delegate to appropriate sub-agent based on user intent",
    sub_agents=[extraction_agent, preference_agent]
)
```

### Parallel Agents
Execute multiple agents concurrently (if supported).

---

## Vertex AI Agent Engine

### Overview
Google Cloud service for deploying and managing AI agents in production.

### Key Features
- **Runtime**: Managed infrastructure, auto-scaling
- **Sessions**: Cloud-managed conversation state (preview)
- **Memory Bank**: Long-term knowledge storage with semantic search (preview)
- **Security**: VPC-SC compliance, IAM integration

### Free Tier
- Free tier available for Agent Engine Runtime
- Express mode for development without full GCP project setup

### Setup Requirements
1. Google Cloud project
2. Vertex AI API enabled
3. Install Vertex AI SDK: `pip install google-cloud-aiplatform`
4. Authenticate: `gcloud auth application-default login`
5. Set environment variables:
   ```
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_CLOUD_LOCATION=us-central1
   ```

---

## Best Practices

### Agent Instructions
- Be specific about when to use each tool
- Define clear delegation criteria for sub-agents
- Include examples in instructions
- Specify response format expectations

### Tool Design
- Single responsibility per tool
- Clear, descriptive names
- Comprehensive docstrings (agents read these)
- Return structured data with status indicators

### Memory Management
- Call `add_session_to_memory()` after meaningful conversations
- Use specific queries for `search_memory()`
- Don't over-query memory (has latency cost)

### Session Handling
- Create new session for each distinct conversation
- Use `append_event()` to track agent actions
- Clean up old sessions periodically

---

## Official Resources

- **ADK Documentation**: https://google.github.io/adk-docs/
- **ADK Python Repo**: https://github.com/google/adk-python
- **ADK Samples**: https://github.com/google/adk-samples
- **Vertex AI Agent Engine**: https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview
- **Google AI Studio**: https://aistudio.google.com/

---

## TimerMind-Specific Usage

### Agent Architecture
```
Root Agent (Orchestrator)
├── Extraction Agent (parses tasks → timers)
└── Preference Agent (learns user preferences)
```

### Service Configuration
```python
# Session management (cloud-persistent)
session_service = VertexAiSessionService(
    project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION")
)

# Long-term memory (semantic search)
memory_service = VertexAiMemoryBankService(
    project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION")
)
```

### Memory Usage Pattern
1. User chats with TimerMind
2. Agent extracts timers, updates preferences
3. After conversation, store session: `memory_service.add_session_to_memory(session)`
4. Next conversation, query memory: `memory_service.search_memory("user preferences")`
5. Agent uses memory results to personalize responses

---

## Troubleshooting

### Common Issues

**Authentication Error**
```
gcloud auth application-default login
```

**Project Not Set**
```
export GOOGLE_CLOUD_PROJECT=your-project-id
```

**API Not Enabled**
Enable Vertex AI API in Google Cloud Console

**Import Errors**
Ensure both packages installed:
```
pip install google-adk google-cloud-aiplatform
```

---

## Version Information

- ADK is actively developed by Google
- Check latest version: https://pypi.org/project/google-adk/
- Session and Memory Bank features are in **preview**
- API may change - refer to official docs for updates
