# UAP - Unified AI Protocol

## Project Overview

UAP (Unified AI Protocol) is a full-stack standard protocol for applications to connect to AI models and agents. Core idea: **everything is an environment interaction** — chat, computer use, games, IoT, agents all share the same `env.declare → env.observe → env.act` loop.

## Key Files

- `SPEC.md` - Protocol specification document (v0.2, RFC-style)
- `README.md` - Project introduction

## Architecture

```
Application (Consumer)
    │
    │  UAP Protocol (env.*)
    │  (HTTP / WebSocket / stdio / gRPC)
    │
AI Model / Agent (Provider)
    │
    │  MCP (Model Context Protocol)
    │
Tools / Data Sources
```

## Core Design: Everything is Environment

All interactions follow one pattern:
1. `env.declare` — describe the environment (or use a template like "chat")
2. `env.observe` — send inputs (user message, screenshot, board state, sensor data...)
3. `env.act` — AI returns actions (reply, mouse click, place stone, turn on AC...)
4. Repeat 2-3 until done

Templates provide shortcuts for common scenarios:
- `chat` — conversational AI (inputs: message, tool_result; actions: reply, tool_call)
- `agent` — autonomous tasks (inputs: task_update, file_content; actions: thinking, tool_call, file_write)
- `computer_use` — desktop automation (inputs: screenshot, ui_tree; actions: mouse_*, keyboard_*)

## Core Methods

| Method | Purpose |
|--------|---------|
| `session.init` | Initialize session, negotiate capabilities and connection mode |
| `session.close` | Close session |
| `env.declare` | Declare environment (description + example + inputs/actions, or template) |
| `env.observe` | Send input data to AI |
| `env.act` | AI returns actions (response to env.observe) |
| `env.update` | Dynamically update environment declaration |
| `env.close` | End environment interaction |
| `provider.info` | Query provider info and available models |

## Connection Modes

- **Stateless**: Each request carries full context. For HTTP/REST.
- **Stateful**: Provider maintains session state, consumer sends incremental data. For WebSocket/stdio. Provider can push messages.

## env.declare Three-Layer Design

| Layer | Field | For whom |
|-------|-------|----------|
| Natural language | `description` | AI understands semantics, rules, goals (**required**) |
| Concrete example | `example` | AI understands data format (**recommended**) |
| Formal definition | `inputs`/`actions` + `params_schema` | Program validation (**optional**) |

## Tech Stack

- **Language**: Python
- **Serialization**: JSON
- **Transports**: HTTP/REST, WebSocket, stdio, gRPC (optional)
- **Config**: YAML (`~/.uap/config.yaml`)

## Naming Conventions

- Methods use dot notation: `env.declare`, `env.observe`
- HTTP URLs map dots to slashes: `env.observe` → `POST /uap/v1/env/observe`
- Custom extensions use `x-` prefix: `x-rag.query`, `x-trading`
- Python SDK: `client.env.declare()`, `env.observe()`
- CLI shortcuts: `uap chat "hello"`, `uap agent "analyze data"`
