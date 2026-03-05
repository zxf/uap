# UAP - Unified AI Protocol

A standardized protocol for applications to connect to AI models and agents.

## Core Idea

**Everything is an environment interaction.**

Whether it's chatting, playing a game, controlling a desktop, or managing IoT devices — the pattern is the same:

```
Declare Environment → Send Inputs → AI Returns Actions → Execute → Repeat
```

UAP unifies this into `env.*` methods. Different scenarios are just different environment declarations:

| Scenario | Environment | Inputs | Actions |
|----------|------------|--------|---------|
| Chat | Conversation | User message | Reply text |
| Gomoku | 15x15 board | Board state | Place stone, resign |
| Desktop | macOS screen | Screenshot, UI tree | Mouse, keyboard |
| Smart Home | Apartment | Sensor data | Lights, AC, curtains |
| Agent | Code/filesystem | File content, exec result | Read/write files |

## Protocol Flow

```
Consumer (App)                    Provider (AI)
     │                                │
     │──── env.declare ──────────────>│  Describe the environment
     │<─── { understood, ready } ─────│
     │                                │
     │──── env.observe ──────────────>│  Send inputs
     │<─── env.act { actions } ───────│  AI returns actions
     │                                │
     │──── env.observe ──────────────>│  Send updated inputs
     │<─── env.act { actions } ───────│
     │         ...                    │
     │                                │
     │──── env.close ────────────────>│  End interaction
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

**UAP flow:** `env.declare` (conversation environment) → `env.observe` (user message) → `env.act` (reply) → repeat.

### Gomoku (`examples/gomoku/`)

A five-in-a-row game with GUI, showing UAP for a more complex environment.

```bash
cd examples/gomoku

uv run server.py                        # Terminal: Human vs Mock AI
uv run server.py --config openai.yaml   # Terminal: Human vs OpenAI
uv run gui.py                           # GUI with menu to pick players
```

The GUI auto-discovers provider configs (`*.yaml`) in the directory. Each side (Black/White) can be Human or any AI provider.

**UAP flow:** `env.declare` (board rules, actions) → `env.observe` (board state) → `env.act` (place stone) → repeat.

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

See [SPEC.md](./SPEC.md) for the complete protocol specification (v0.2).

Key methods:

| Method | Purpose |
|--------|---------|
| `env.declare` | Describe the environment (description + example + inputs/actions) |
| `env.observe` | Send input data to AI |
| `env.act` | AI returns actions |
| `env.close` | End the interaction |

### env.declare Three-Layer Design

| Layer | Field | Purpose |
|-------|-------|---------|
| Natural language | `description` | AI understands semantics and rules |
| Concrete example | `example` | AI understands data format |
| Formal definition | `inputs`/`actions` + schema | Program validation |

## License

MIT
