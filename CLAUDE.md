# UAP - Unified AI Protocol

## Project Overview

UAP (Unified AI Protocol) is a full-stack standard protocol for applications to connect to AI models and agents. Core idea: **everything is a system interaction** — chat, computer use, games, IoT, agents all share the same `session.init (declare system) → input → action` loop.

## Key Files

- `SPEC.md` - Protocol specification document (v0.3, RFC-style)
- `README.md` - Project introduction

## Architecture

```
Application (Consumer)
    │
    │  UAP Protocol (session/input/action)
    │  (HTTP / WebSocket / stdio / gRPC)
    │
AI Model / Agent (Provider)
    │
    │  MCP (Model Context Protocol)
    │
Tools / Data Sources
```

## Core Design: Everything is a System

All interactions follow one pattern:
1. `session.init` — establish session, declare the system (description + inputs + actions + rules)
2. `input` — send inputs (user message, screenshot, board state, sensor data...)
3. `action` — AI returns actions (reply, mouse click, place stone, turn on AC...)
4. AI can also proactively initiate actions (in stateful mode)
5. `system.update` — dynamically update system rules/inputs/actions mid-session
6. Repeat 2-3 until done

## Core Methods

| Method | Purpose |
|--------|---------|
| `session.init` | Initialize session, declare system (description, inputs, actions, rules), negotiate capabilities |
| `session.close` | Close session |
| `input` | Send input data to AI (supports structured + binary) |
| `action` | AI returns actions (response) or proactively initiates actions |
| `system.update` | Dynamically update system declaration mid-session |
| `provider.info` | Query provider info and available models |

## Connection Modes

- **Stateless**: Each request carries full context (system + history). For HTTP/REST. No AI-initiated actions.
- **Stateful**: Provider maintains session state, consumer sends incremental data. For WebSocket/stdio. AI can proactively push actions.

## System Declaration (Three-Layer Design)

Declared in `session.init`, the system tells AI about the interaction environment:

| Layer | Field | For whom |
|-------|-------|----------|
| Natural language | `description` | AI understands semantics, rules, goals (**required**) |
| Concrete example | `example` | AI understands data format (**recommended**) |
| Formal definition | `inputs`/`actions` + `params_schema` | Program validation (**optional**) |

Additional fields: `rules` (behavioral constraints), `constraints` (technical limits), `config` (model, options, tools).

## Key Features

- **Binary input support**: inputs can be `type: "binary"` with `media_type` and `data` (base64) or `ref` (URI)
- **AI-initiated actions**: In stateful mode, Provider can proactively send actions without waiting for input
- **System updates**: `system.update` allows adding/removing inputs, actions, rules mid-session

## Tech Stack

- **Language**: Python
- **Serialization**: JSON
- **Transports**: HTTP/REST, WebSocket, stdio, gRPC (optional)
- **Config**: YAML (`~/.uap/config.yaml`)

## Naming Conventions

- Methods use dot notation for namespaced methods: `session.init`, `system.update`
- Top-level methods: `input`, `action`
- HTTP URLs map dots to slashes: `system.update` → `POST /uap/v1/system/update`
- Custom extensions use `x-` prefix: `x-rag.query`
- Python SDK: `client.session.init()`, `session.input()`
- CLI: `uap session init`, `uap input`
