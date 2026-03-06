# UAP - Unified AI Protocol

A standardized protocol for applications to connect to AI models and agents.

## Core Idea

**Everything is a system interaction.**

Whether it's chatting, playing a game, controlling a desktop, or managing IoT devices — the pattern is the same:

```
Init Session (Declare System) → Send Inputs → AI Returns Actions → Execute → Repeat
                                                     ↑
                                       AI can also act proactively
```

UAP declares the system at session init, then exchanges `input` and `action` messages. Different scenarios are just different system declarations:

| Scenario | System | Inputs | Actions |
|----------|--------|--------|---------|
| Chat | Conversation | User message | Reply text |
| Gomoku | 15x15 board | Board state | Place stone, resign |
| Desktop | macOS screen | Screenshot, UI tree | Mouse, keyboard |
| Smart Home | Apartment | Sensor data | Lights, AC, curtains |
| Agent | Code/filesystem | File content, exec result | Read/write files |

## Protocol Flow

```
Consumer (App)                    Provider (AI)
     │                                │
     │──── session.init ─────────────>│  Declare the system
     │<─── { system_accepted } ───────│
     │                                │
     │──── input ────────────────────>│  Send inputs
     │<─── action { actions } ────────│  AI returns actions
     │                                │
     │──── input ────────────────────>│  Send updated inputs
     │<─── action { actions } ────────│
     │                                │
     │                                │── action (proactive)
     │<───────────────────────────────│  AI can act on its own
     │                                │
     │──── system.update ────────────>│  Update rules mid-session
     │<─── ok ────────────────────────│
     │                                │
     │──── session.close ────────────>│  End interaction
     │<─── { summary } ──────────────│
```

## How It Relates to MCP and A2A

```
              Application
                  │
                  │  UAP (this protocol)
                  │  App → AI
                  ▼
            AI Model / Agent
                  │
                  │  MCP (Model Context Protocol)
                  │  AI → Tools/Data
                  ▼
          Tools / Data Sources
```

- **UAP** — how apps call AI (downward)
- **MCP** — how AI calls tools (AI-side extensions)
- **A2A** — how agents talk to each other (lateral)

The three are complementary.

## Examples

### Chat (`examples/chat/`)

A conversational AI client demonstrating UAP for the simplest scenario.

```bash
cd examples/chat

uv run server.py                        # Interactive chat with Mock AI
uv run server.py --config openai.yaml   # Chat with OpenAI
uv run server.py "What is UAP?"         # Single message mode
```

**UAP flow:** `session.init` (declare conversation system) → `input` (user message) → `action` (reply) → repeat.

### Gomoku (`examples/gomoku/`)

A five-in-a-row game with GUI, showing UAP for a more complex system.

```bash
cd examples/gomoku

uv run server.py                        # Terminal: Human vs Mock AI
uv run server.py --config openai.yaml   # Terminal: Human vs OpenAI
uv run gui.py                           # GUI with menu to pick players
```

The GUI auto-discovers provider configs (`*.yaml`) in the directory. Each side (Black/White) can be Human or any AI provider.

**UAP flow:** `session.init` (board rules, actions) → `input` (board state) → `action` (place stone) → repeat.

### Provider Configuration

Both examples support pluggable providers via config files:

```yaml
# openai.yaml
provider: openai
api_key: sk-...
base_url: https://api.openai.com/v1
model: gpt-4o
temperature: 0.7
```

```yaml
# deepseek.yaml
provider: openai
api_key: sk-...
base_url: https://api.deepseek.com/v1
model: deepseek-chat
```

```yaml
# mock.yaml (or omit config entirely)
provider: mock
```

Environment variables `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` also work.

## Specification

See [SPEC.md](./SPEC.md) for the complete protocol specification (v0.3).

Key methods:

| Method | Purpose |
|--------|---------|
| `session.init` | Declare the system (description + inputs + actions + rules) and init session |
| `input` | Send input data to AI (structured + binary) |
| `action` | AI returns actions or proactively initiates actions |
| `system.update` | Update system rules/inputs/actions mid-session |
| `session.close` | End the interaction |

### System Declaration (Three-Layer Design)

| Layer | Field | Purpose |
|-------|-------|---------|
| Natural language | `description` | AI understands semantics and rules |
| Concrete example | `example` | AI understands data format |
| Formal definition | `inputs`/`actions` + schema | Program validation |

## License

MIT
