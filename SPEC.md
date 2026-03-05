# UAP - Unified AI Protocol Specification

> Version: 0.2.0 (Draft)
> Status: Working Draft

## 1. 概述

### 1.1 动机

当前应用接入 AI 的方式高度碎片化：

- 每个 AI 提供商都有不同的 API 格式
- CLI 工具、SDK、REST API 之间缺乏统一抽象
- 应用在切换 AI 后端时需要大量改造
- Agent 的能力描述、任务管理、流式输出等没有统一标准

UAP（Unified AI Protocol）旨在定义一套 **应用 -> AI/Agent** 的标准化接入协议，覆盖从传输层到应用层的完整链路，支持 API、CLI、编程语言 SDK 等多种接入方式。

### 1.2 核心思想

**一切交互都是环境交互。**

无论是聊天对话、操作电脑、下棋、还是控制智能家居，本质上都是同一个模式：

```
声明环境 → 发送输入 → AI 返回动作 → 执行动作 → 发送新输入 → ...
```

UAP 将这个模式抽象为统一的 `env.*` 方法族，不同场景只是环境声明不同：

| 场景 | 环境 | inputs | actions |
|------|------|--------|---------|
| 聊天对话 | 对话窗口 | 用户消息 | 回复文本、调用工具 |
| 桌面操作 | macOS 桌面 | 截图、UI树 | 鼠标、键盘、shell |
| 五子棋 | 15x15 棋盘 | 棋盘状态 | 落子、认输 |
| 智能家居 | 公寓设备 | 传感器数据 | 灯光、空调、窗帘 |
| Agent 任务 | 代码/文件系统 | 文件内容、执行结果 | 读写文件、执行代码 |

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **万物皆环境** | 所有交互统一为 env.declare → env.observe → env.act 循环 |
| **传输无关** | 协议定义消息格式和语义，不绑定特定传输方式（HTTP/WebSocket/stdio/gRPC） |
| **渐进复杂** | 最简场景（聊天）使用预定义模板，复杂场景自定义环境声明 |
| **后端无关** | 同一客户端代码可对接 OpenAI、Anthropic、本地模型等不同后端 |
| **可扩展** | 核心协议精简，通过 Capability 机制声明和协商扩展能力 |
| **多接口统一** | API / CLI / SDK 共享同一套消息模型和语义 |

### 1.4 与现有协议的关系

```
                    ┌─────────────────────────────┐
                    │         Application          │
                    └──────────┬──────────────────-┘
                               │ UAP (本协议)
                               │ 应用 -> AI/Agent
                    ┌──────────▼──────────────────-┐
                    │      AI Model / Agent         │
                    └──────────┬──────────────────-┘
                               │ MCP
                               │ AI -> 外部工具/数据
                    ┌──────────▼──────────────────-┐
                    │   Tools / Data Sources        │
                    └──────────────────────────────-┘
```

- **UAP** 解决 "应用如何调用 AI" 的问题（下行接口）
- **MCP** 解决 "AI 如何调用工具" 的问题（AI 侧扩展）
- **A2A** 解决 "Agent 之间如何协作" 的问题（横向通信）

三者互补，UAP 可以与 MCP/A2A 协同工作。

---

## 2. 核心概念

### 2.1 角色

| 角色 | 说明 |
|------|------|
| **Consumer** | 发起请求的应用程序（Web 应用、CLI 工具、移动端等），持有并管理环境 |
| **Provider** | 提供 AI 能力的服务端（模型 API、Agent 运行时等），在环境中行动 |
| **Gateway** | 可选的中间层，负责路由、认证、限流、协议转换等 |

### 2.2 核心抽象

```
┌────────────────────────────────────────────────────┐
│                     Session                         │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │              Environment                      │  │
│  │                                               │  │
│  │  description  "这是一个对话环境..."            │  │
│  │  example      {inputs: ..., actions: ...}     │  │
│  │  inputs       [message, image, ...]           │  │
│  │  actions      [reply, tool_call, ...]         │  │
│  │  constraints  {max_turns: 100, ...}           │  │
│  │                                               │  │
│  │  ┌────────┐  ┌────────┐  ┌────────┐         │  │
│  │  │  Turn  │  │  Turn  │  │  Turn  │  ...     │  │
│  │  │ ob→act │  │ ob→act │  │ ob→act │         │  │
│  │  └────────┘  └────────┘  └────────┘         │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  Capabilities: streaming, vision, audio, ...        │
└────────────────────────────────────────────────────-┘
```

| 抽象 | 说明 |
|------|------|
| **Session** | 一次连接会话，包含认证信息和能力协商结果 |
| **Environment** | 一个交互环境的完整声明（描述、输入、动作、约束） |
| **Turn** | 一次 observe → act 交互 |
| **Capability** | Provider 声明支持的能力（流式、工具调用、多模态等） |

---

## 3. 消息格式

UAP 使用 JSON 作为消息序列化格式。所有消息共享统一的信封结构。

### 3.1 请求信封 (Request Envelope)

```json
{
  "uap": "0.2",
  "id": "req_abc123",
  "method": "env.observe",
  "params": { ... },
  "meta": {
    "timeout_ms": 30000,
    "trace_id": "trace_xyz"
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `uap` | string | yes | 协议版本 |
| `id` | string | yes | 请求唯一标识 |
| `method` | string | yes | 方法名 |
| `params` | object | yes | 方法参数 |
| `meta` | object | no | 请求级元数据（超时、追踪等） |

### 3.2 响应信封 (Response Envelope)

```json
{
  "uap": "0.2",
  "id": "req_abc123",
  "status": "ok",
  "result": { ... },
  "usage": {
    "input_tokens": 150,
    "output_tokens": 320
  },
  "meta": {}
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `uap` | string | yes | 协议版本 |
| `id` | string | yes | 对应的请求 ID |
| `status` | string | yes | `"ok"` / `"error"` / `"streaming"` |
| `result` | object | conditional | 成功时的结果 |
| `error` | object | conditional | 失败时的错误信息 |
| `usage` | object | no | Token 用量等计量信息 |
| `meta` | object | no | 响应级元数据 |

### 3.3 流式事件 (Stream Event)

当 Provider 支持 `streaming` 能力时，`env.act` 的响应可以是一系列流式事件：

```json
{"uap":"0.2","id":"req_abc123","event":"stream.start","data":{}}
{"uap":"0.2","id":"req_abc123","event":"stream.delta","data":{"action_id":"reply","text":"Hello"}}
{"uap":"0.2","id":"req_abc123","event":"stream.delta","data":{"action_id":"reply","text":" world"}}
{"uap":"0.2","id":"req_abc123","event":"stream.end","data":{"status":"continue"},"usage":{"input_tokens":10,"output_tokens":5}}
```

事件类型：

| 事件 | 说明 |
|------|------|
| `stream.start` | 流开始 |
| `stream.delta` | 增量内容（文本、动作参数等） |
| `stream.end` | 流结束，包含最终统计和 status |
| `stream.error` | 流中错误 |
| `stream.ping` | 心跳保活 |

### 3.4 错误格式

```json
{
  "code": "rate_limited",
  "message": "Too many requests, retry after 5s",
  "details": {
    "retry_after_ms": 5000
  }
}
```

标准错误码：

| 错误码 | 说明 |
|--------|------|
| `invalid_request` | 请求格式错误 |
| `authentication_error` | 认证失败 |
| `permission_denied` | 无权限 |
| `not_found` | 方法或资源不存在 |
| `rate_limited` | 限流 |
| `context_length_exceeded` | 上下文长度超限 |
| `content_filtered` | 内容被安全策略过滤 |
| `provider_error` | 后端服务错误 |
| `timeout` | 请求超时 |
| `cancelled` | 请求被取消 |
| `invalid_action` | AI 返回了无效动作（不在声明的 actions 中） |
| `env_not_found` | 指定的 env_id 不存在 |

---

## 4. 核心方法

### 4.1 会话管理

#### `session.init` - 初始化会话

建立会话并进行能力协商。

**请求：**
```json
{
  "method": "session.init",
  "params": {
    "client": {
      "name": "my-app",
      "version": "1.0.0"
    },
    "capabilities_requested": ["streaming", "vision", "env"],
    "connection_mode": "stateful",
    "auth": {
      "type": "bearer",
      "token": "sk-..."
    }
  }
}
```

**响应：**
```json
{
  "result": {
    "session_id": "sess_abc123",
    "provider": {
      "name": "openai",
      "version": "1.0.0"
    },
    "capabilities": {
      "streaming": true,
      "vision": true,
      "env": true,
      "max_context_tokens": 128000,
      "models": ["gpt-4o", "gpt-4o-mini"]
    },
    "connection_mode": "stateful"
  }
}
```

#### `session.close` - 关闭会话

### 4.2 环境交互 (Environment Interaction)

UAP 的核心。所有 AI 交互都通过环境模型进行。

核心思路：**Consumer 向 Provider 声明环境——有什么、能感知什么、能做什么——然后进入"输入-行动"循环。**

```
Consumer (环境持有者)                Provider (AI)
    │                                    │
    │── env.declare (声明环境) ──────────>│
    │<── 确认理解 + 请求初始输入 ─────────│
    │                                    │
    │── env.observe (发送输入) ──────────>│
    │<── env.act (返回动作) ─────────────│
    │                                    │
    │   (Consumer 执行动作，更新环境)      │
    │                                    │
    │── env.observe (新输入) ────────────>│
    │<── env.act ────────────────────────│
    │         ...循环...                  │
    │                                    │
    │── env.close (结束) ───────────────>│
```

#### `env.declare` - 声明环境

告诉 AI 当前环境的完整描述。由三层信息组成：

| 层 | 字段 | 给谁用 |
|----|------|--------|
| 自然语言 | `description` | AI 理解环境语义、规则、目标（**必需**） |
| 具体示例 | `example` | AI 理解数据格式和交互方式（**强烈建议**） |
| 形式化定义 | `inputs` / `actions` + `params_schema` | 程序校验 AI 输出（**可选**） |

**请求（五子棋）：**
```json
{
  "method": "env.declare",
  "params": {
    "env_id": "gomoku_01",
    "name": "五子棋对局",
    "description": "15x15 标准五子棋。你执黑先行。棋盘用二维数组表示，0=空位 1=黑子 2=白子。坐标从左上角(0,0)开始，x为列y为行。先在横/竖/斜方向形成连续5子者获胜。只能在空位落子，黑白交替进行。",

    "example": {
      "inputs": {
        "board_state": {
          "board": [
            [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,2,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,1,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
          ],
          "current_turn": "black",
          "move_history": [
            {"x": 6, "y": 3, "color": "black"},
            {"x": 7, "y": 2, "color": "white"}
          ],
          "game_status": "playing"
        }
      },
      "actions": [
        {"id": "place_stone", "params": {"x": 7, "y": 3}}
      ]
    },

    "inputs": [
      {"id": "board_state", "type": "structured", "description": "当前棋盘完整状态"},
      {"id": "board_image", "type": "visual", "description": "棋盘渲染图片", "optional": true}
    ],

    "actions": [
      {
        "id": "place_stone",
        "description": "在空位落子",
        "params_schema": {
          "type": "object",
          "properties": {
            "x": {"type": "integer", "minimum": 0, "maximum": 14},
            "y": {"type": "integer", "minimum": 0, "maximum": 14}
          },
          "required": ["x", "y"]
        }
      },
      {
        "id": "resign",
        "description": "认输"
      }
    ],

    "constraints": {
      "turn_timeout_ms": 30000,
      "max_turns": 225
    }
  }
}
```

**响应：**
```json
{
  "result": {
    "env_id": "gomoku_01",
    "understood": true,
    "summary": "我理解这是一局15x15五子棋，我执黑先行。可用操作：落子(place_stone)和认输(resign)。",
    "ready": true,
    "initial_input_request": ["board_state"]
  }
}
```

**请求（聊天对话 — 使用预定义模板）：**
```json
{
  "method": "env.declare",
  "params": {
    "template": "chat",
    "env_id": "chat_01",
    "config": {
      "model": "gpt-4o",
      "system_prompt": "You are a helpful assistant.",
      "options": {
        "temperature": 0.7,
        "max_tokens": 4096,
        "stream": true
      },
      "tools": [
        {
          "name": "web_search",
          "description": "Search the web",
          "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
          }
        }
      ]
    }
  }
}
```

使用 `template` 时，环境的 description、inputs、actions 都由模板预定义，Consumer 只需提供配置。等价于手动声明：

```json
{
  "method": "env.declare",
  "params": {
    "env_id": "chat_01",
    "name": "对话",
    "description": "多轮对话环境。用户发送消息（文本/图片/音频/文件），你回复文本或调用工具。System prompt: You are a helpful assistant.",

    "example": {
      "inputs": {
        "message": {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
      },
      "actions": [
        {"id": "reply", "params": {"content": [{"type": "text", "text": "Hi! How can I help you?"}]}}
      ]
    },

    "inputs": [
      {"id": "message", "type": "structured", "description": "用户消息，含 role 和 content"},
      {"id": "tool_result", "type": "structured", "description": "工具调用结果", "optional": true}
    ],

    "actions": [
      {"id": "reply", "description": "回复用户消息"},
      {"id": "tool_call", "description": "调用工具"}
    ],

    "config": {
      "model": "gpt-4o",
      "options": {"temperature": 0.7, "max_tokens": 4096, "stream": true},
      "tools": [...]
    }
  }
}
```

**更多环境声明示例：**

桌面电脑操作环境：
```json
{
  "method": "env.declare",
  "params": {
    "env_id": "desktop_01",
    "name": "macOS 桌面",
    "description": "macOS 15.2 桌面环境，2560x1600 Retina 显示屏（缩放因子2x，逻辑分辨率1280x800）。你可以通过截图看到屏幕内容，通过 UI 元素树获取结构化信息。可用操作包括鼠标移动/点击/拖拽/滚动，键盘输入/按键/组合键，以及执行 shell 命令。所有坐标使用逻辑像素。",

    "example": {
      "inputs": {
        "screenshot": {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}},
        "ui_tree": {
          "elements": [
            {"id": "e1", "role": "button", "name": "Submit", "bounds": [100, 200, 80, 30]},
            {"id": "e2", "role": "textfield", "name": "Search", "bounds": [50, 100, 300, 30], "value": ""}
          ]
        }
      },
      "actions": [
        {"id": "mouse_click", "params": {"x": 200, "y": 115, "button": "left"}},
        {"id": "keyboard_type", "params": {"text": "hello world"}}
      ]
    },

    "inputs": [
      {"id": "screenshot", "type": "visual", "description": "屏幕截图"},
      {"id": "ui_tree", "type": "accessibility", "description": "UI 无障碍元素树", "optional": true},
      {"id": "audio", "type": "audio", "description": "麦克风录音", "optional": true}
    ],

    "actions": [
      {"id": "mouse_move", "description": "移动鼠标"},
      {"id": "mouse_click", "description": "鼠标点击"},
      {"id": "mouse_drag", "description": "鼠标拖拽"},
      {"id": "mouse_scroll", "description": "鼠标滚动"},
      {"id": "keyboard_type", "description": "输入文本"},
      {"id": "keyboard_press", "description": "按下单个键"},
      {"id": "keyboard_hotkey", "description": "组合键"},
      {"id": "shell_command", "description": "执行 shell 命令", "requires_approval": true}
    ],

    "constraints": {
      "approval_required": ["shell_command"],
      "sensitive_regions": [{"description": "密码输入框", "auto_mask": true}],
      "max_actions_per_turn": 10
    }
  }
}
```

智能家居环境：
```json
{
  "method": "env.declare",
  "params": {
    "env_id": "home_01",
    "name": "智能家居",
    "description": "三室一厅公寓，房间有：客厅、主卧、次卧、书房。配备智能灯光（亮度0-100，色温2700K-6500K）、空调（制冷/制热/自动/关闭，温度16-30度）、电动窗帘（开合度0-100）、智能音箱。夜间模式(22:00-07:00)音量不超过30。",

    "example": {
      "inputs": {
        "device_states": {
          "客厅": {"light": {"on": true, "brightness": 80, "color_temp": 4000}, "ac": {"mode": "cool", "temperature": 26}, "curtain": {"position": 100}},
          "主卧": {"light": {"on": false}, "ac": {"mode": "off"}, "curtain": {"position": 0}}
        },
        "sensors": {
          "客厅": {"temperature": 28.5, "humidity": 65, "light_level": 300},
          "主卧": {"temperature": 27.0, "humidity": 60, "light_level": 0}
        }
      },
      "actions": [
        {"id": "ac_set", "params": {"room": "客厅", "mode": "cool", "temperature": 25}},
        {"id": "curtain_set", "params": {"room": "客厅", "position": 50}}
      ]
    },

    "inputs": [
      {"id": "device_states", "type": "structured", "description": "所有设备当前状态"},
      {"id": "sensors", "type": "structured", "description": "温湿度、光照等传感器数据"},
      {"id": "camera", "type": "visual", "description": "摄像头画面", "optional": true}
    ],

    "actions": [
      {"id": "light_set", "description": "控制灯光，参数: room, brightness(0-100), color_temp(2700-6500)"},
      {"id": "ac_set", "description": "控制空调，参数: room, mode(cool/heat/auto/off), temperature(16-30)"},
      {"id": "curtain_set", "description": "控制窗帘，参数: room, position(0=全关 100=全开)"},
      {"id": "speaker_play", "description": "播放音频，参数: room, content(音乐名或TTS文本), volume(0-100)"}
    ],

    "constraints": {
      "rules": ["夜间模式(22:00-07:00)音量不超过30"]
    }
  }
}
```

#### `env.observe` - 发送环境输入

Consumer 将当前环境的输入数据发送给 Provider。

**请求（五子棋）：**
```json
{
  "method": "env.observe",
  "params": {
    "env_id": "gomoku_01",
    "inputs": {
      "board_state": {
        "board": [[0,0,0,"..."], ["..."]],
        "current_turn": "black",
        "move_history": [],
        "game_status": "playing"
      }
    },
    "message": "游戏开始，请落子。"
  }
}
```

**请求（聊天）：**
```json
{
  "method": "env.observe",
  "params": {
    "env_id": "chat_01",
    "inputs": {
      "message": {
        "role": "user",
        "content": [
          {"type": "text", "text": "Describe this image"},
          {"type": "image", "source": {"type": "url", "url": "https://example.com/img.png"}}
        ]
      }
    }
  }
}
```

**请求（聊天 — 工具调用结果）：**
```json
{
  "method": "env.observe",
  "params": {
    "env_id": "chat_01",
    "inputs": {
      "tool_result": {
        "tool_call_id": "tc_001",
        "content": "北京今天晴，最高温度 25°C"
      }
    }
  }
}
```

**请求（桌面操作）：**
```json
{
  "method": "env.observe",
  "params": {
    "env_id": "desktop_01",
    "inputs": {
      "screenshot": {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "..."}},
      "ui_tree": {
        "elements": [
          {"id": "e1", "role": "button", "name": "Submit", "bounds": [100, 200, 80, 30]},
          {"id": "e2", "role": "textfield", "name": "Search", "bounds": [50, 100, 300, 30]}
        ]
      }
    },
    "action_results": [
      {"id": "keyboard_type", "success": true}
    ]
  }
}
```

#### `env.act` - AI 返回动作

Provider 分析输入后返回要执行的动作。

**响应（五子棋）：**
```json
{
  "result": {
    "env_id": "gomoku_01",
    "thinking": "棋盘为空，我先占据天元位置（中心点）。",
    "actions": [
      {"id": "place_stone", "params": {"x": 7, "y": 7}}
    ],
    "status": "continue",
    "next_input_request": ["board_state"]
  }
}
```

**响应（聊天 — 纯文本回复）：**
```json
{
  "result": {
    "env_id": "chat_01",
    "actions": [
      {"id": "reply", "params": {"content": [{"type": "text", "text": "The image shows a sunset over the ocean."}]}}
    ],
    "status": "continue",
    "next_input_request": ["message"]
  }
}
```

**响应（聊天 — 工具调用）：**
```json
{
  "result": {
    "env_id": "chat_01",
    "actions": [
      {"id": "tool_call", "params": {"tool_call_id": "tc_001", "name": "web_search", "arguments": {"query": "北京今天天气"}}}
    ],
    "status": "continue",
    "next_input_request": ["tool_result"]
  }
}
```

**响应（桌面 — 多步动作）：**
```json
{
  "result": {
    "env_id": "desktop_01",
    "thinking": "我需要点击搜索框，然后输入搜索内容",
    "actions": [
      {"id": "mouse_move", "params": {"x": 200, "y": 115}},
      {"id": "mouse_click", "params": {"button": "left", "click_type": "single"}},
      {"id": "keyboard_type", "params": {"text": "天气预报"}},
      {"id": "keyboard_press", "params": {"key": "Enter"}}
    ],
    "status": "continue",
    "wait_before_observe_ms": 2000,
    "next_input_request": ["screenshot"]
  }
}
```

`status` 取值：

| 值 | 说明 |
|----|------|
| `continue` | 等待下一次输入，继续交互 |
| `done` | AI 认为任务已完成 |
| `failed` | AI 认为任务无法完成 |
| `need_approval` | 需要用户审批后续动作 |
| `need_input` | 需要用户补充信息 |

#### `env.update` - 动态更新环境声明

环境可能发生变化（新设备上线、游戏规则变化、新增工具等），Consumer 可以增量更新。

```json
{
  "method": "env.update",
  "params": {
    "env_id": "home_01",
    "add_actions": [
      {"id": "robot_vacuum", "description": "启动扫地机器人，参数: room"}
    ],
    "remove_actions": [],
    "update_constraints": {
      "rules": ["夜间模式(22:00-07:00)音量不超过30", "扫地机器人仅在无人时启动"]
    }
  }
}
```

聊天环境中动态增加工具：
```json
{
  "method": "env.update",
  "params": {
    "env_id": "chat_01",
    "add_tools": [
      {"name": "calculator", "description": "计算数学表达式", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}
    ]
  }
}
```

#### `env.close` - 结束环境交互

```json
{
  "method": "env.close",
  "params": {
    "env_id": "gomoku_01",
    "reason": "game_over",
    "summary_request": true
  }
}
```

**响应：**
```json
{
  "result": {
    "env_id": "gomoku_01",
    "summary": "本局五子棋共进行32手，我执黑获胜，在第7行形成横向五连珠。",
    "stats": {
      "total_turns": 32,
      "total_actions": 16,
      "duration_ms": 120000
    }
  }
}
```

### 4.3 Provider 推送 (Provider-Initiated Messages)

在长连接模式（WebSocket / stdio）下，Provider 可以主动向 Consumer 发送消息：

```json
{
  "uap": "0.2",
  "id": "push_001",
  "event": "provider.request_input",
  "data": {
    "env_id": "desktop_01",
    "message": "操作已执行，请发送新的截图",
    "input_request": ["screenshot"]
  }
}
```

```json
{
  "uap": "0.2",
  "id": "push_002",
  "event": "provider.notification",
  "data": {
    "env_id": "home_01",
    "message": "检测到客厅温度升高到30度，建议开启空调"
  }
}
```

Provider 推送事件类型：

| 事件 | 说明 |
|------|------|
| `provider.request_input` | 主动请求新的输入数据 |
| `provider.notification` | 通知/建议（不需要 Consumer 立即响应） |
| `provider.approval_request` | 请求用户审批某个操作 |

### 4.4 模型与能力发现

#### `provider.info` - 查询 Provider 信息

```json
{
  "method": "provider.info",
  "params": {}
}
```

**响应：**
```json
{
  "result": {
    "name": "my-ai-gateway",
    "version": "2.0.0",
    "templates": ["chat", "agent", "computer_use"],
    "models": [
      {
        "id": "gpt-4o",
        "provider": "openai",
        "capabilities": ["streaming", "vision", "env"],
        "context_window": 128000,
        "max_output_tokens": 16384,
        "pricing": {
          "input_per_1m_tokens": 2.5,
          "output_per_1m_tokens": 10.0,
          "currency": "USD"
        }
      },
      {
        "id": "claude-opus-4-6",
        "provider": "anthropic",
        "capabilities": ["streaming", "vision", "env"],
        "context_window": 200000,
        "max_output_tokens": 32000
      }
    ]
  }
}
```

---

## 5. 预定义环境模板 (Environment Templates)

高频场景提供预定义模板，Consumer 用 `template` 字段即可快速创建环境，无需手动声明完整的 inputs/actions。

### 5.1 `chat` - 对话

```json
{"method": "env.declare", "params": {"template": "chat", "env_id": "chat_01", "config": {"model": "gpt-4o", "system_prompt": "You are helpful.", "options": {"temperature": 0.7, "stream": true}, "tools": [...]}}}
```

预定义的 inputs: `message`, `tool_result`
预定义的 actions: `reply`, `tool_call`

### 5.2 `agent` - Agent 任务

```json
{"method": "env.declare", "params": {"template": "agent", "env_id": "agent_01", "config": {"model": "claude-opus-4-6", "instruction": "Analyze the sales data and generate a report", "context": [{"type": "file", "name": "sales.csv", "content": "..."}], "options": {"max_steps": 20, "approval_mode": "auto"}}}}
```

预定义的 inputs: `task_update`, `approval_response`, `file_content`
预定义的 actions: `thinking`, `tool_call`, `file_write`, `file_read`, `complete`

### 5.3 `computer_use` - 计算机操作

```json
{"method": "env.declare", "params": {"template": "computer_use", "env_id": "desktop_01", "config": {"os": "macOS 15.2", "resolution": [2560, 1600], "scale_factor": 2}}}
```

预定义的 inputs: `screenshot`, `ui_tree`, `audio`
预定义的 actions: `mouse_move`, `mouse_click`, `mouse_drag`, `mouse_scroll`, `keyboard_type`, `keyboard_press`, `keyboard_hotkey`, `shell_command`

### 5.4 自定义模板

Provider 可以注册自定义模板（以 `x-` 前缀命名）：

```json
{"method": "env.declare", "params": {"template": "x-trading", "env_id": "trade_01", "config": {"account": "demo", "instruments": ["BTCUSDT", "ETHUSDT"]}}}
```

---

## 6. 连接模式 (Connection Modes)

UAP 支持两种连接模式，在 `session.init` 时协商确定。

### 6.1 无状态模式 (Stateless)

每次 `env.observe` 请求携带完整上下文，Provider 不保存任何状态。

```
Consumer                                Provider
   │                                        │
   │── env.observe ────────────────────────>│
   │   (携带 env 声明 + 全部历史输入)         │
   │<── env.act ────────────────────────────│
   │                                        │
   │── env.observe ────────────────────────>│
   │   (携带 env 声明 + 全部历史输入 + 新输入) │
   │<── env.act ────────────────────────────│
```

特点：
- 每次请求独立，Provider 无状态
- Consumer 管理全部上下文
- 适合 HTTP/REST 短连接
- 简单可靠，易于负载均衡
- 数据量随对话增长

无状态模式下，`env.declare` 和 `env.observe` 可以合并为单次请求：

```json
{
  "method": "env.observe",
  "params": {
    "env": {
      "template": "chat",
      "config": {"model": "gpt-4o", "system_prompt": "You are helpful."}
    },
    "history": [
      {"inputs": {"message": {"role": "user", "content": [{"type": "text", "text": "Hi"}]}},
       "actions": [{"id": "reply", "params": {"content": [{"type": "text", "text": "Hello!"}]}}]},
    ],
    "inputs": {
      "message": {"role": "user", "content": [{"type": "text", "text": "What is 1+1?"}]}
    }
  }
}
```

### 6.2 有状态模式 (Stateful)

Provider 通过 `env_id` / `session_id` 维护上下文，Consumer 只发增量数据。

```
Consumer                                Provider
   │                                        │
   │── env.declare ────────────────────────>│  (Provider 存储环境声明)
   │<── ok ─────────────────────────────────│
   │                                        │
   │── env.observe (仅增量输入) ────────────>│  (Provider 追加到上下文)
   │<── env.act ────────────────────────────│
   │                                        │
   │── env.observe (仅增量输入) ────────────>│
   │<── env.act ────────────────────────────│
```

特点：
- Provider 维护会话状态
- Consumer 只发增量数据，省流量
- 适合 WebSocket / stdio 长连接
- Provider 可以主动推送消息
- 需要处理连接断开和状态恢复

### 6.3 模式协商

在 `session.init` 中协商：

```json
{
  "method": "session.init",
  "params": {
    "connection_mode": "stateful",
    ...
  }
}
```

Provider 在响应中确认实际采用的模式。如果 Provider 不支持 stateful，可以降级为 stateless。

---

## 7. 传输绑定 (Transport Bindings)

UAP 消息可以通过多种传输方式传递。

### 7.1 HTTP/REST

最通用的传输方式。通常配合无状态模式使用。

```
POST /uap/v1/{method}
Content-Type: application/json
Authorization: Bearer sk-...
X-UAP-Request-Id: req_abc123

{params body}
```

- 非流式：返回 `application/json`
- 流式：返回 `text/event-stream`（SSE），每行一个 JSON 事件

**URL 映射规则：** `method` 中的 `.` 映射为 `/`

```
env.declare     -> POST /uap/v1/env/declare
env.observe     -> POST /uap/v1/env/observe
env.close       -> POST /uap/v1/env/close
session.init    -> POST /uap/v1/session/init
provider.info   -> GET  /uap/v1/provider/info
```

### 7.2 WebSocket

适合有状态模式和双向实时通信。

```
ws://host/uap/v1/ws

# 连接后通过 JSON 消息双向通信
# 每条消息即一个完整的 UAP 信封
# Provider 可以主动推送消息
```

### 7.3 stdio（CLI / 子进程）

适合 CLI 工具和本地 Agent。天然长连接。

```
# Consumer 写入 stdin（每行一个 JSON）
{"uap":"0.2","id":"1","method":"env.declare","params":{...}}

# Provider 写入 stdout（每行一个 JSON）
{"uap":"0.2","id":"1","status":"ok","result":{...}}

# Provider 可以主动推送
{"uap":"0.2","id":"push_1","event":"provider.request_input","data":{...}}
```

### 7.4 gRPC（可选）

为高性能场景保留。使用 Protocol Buffers 定义消息，语义与 JSON 格式一一对应。

---

## 8. 多接口统一模型

UAP 的核心价值之一是 API / CLI / SDK 共享同一套消息模型。

### 8.1 架构

```
┌───────────────────────────────────────────────────────────┐
│                    UAP Message Model                       │
│          (统一的 env.* 消息格式和语义)                       │
└───────┬──────────────┬──────────────────┬────────────────-┘
        │              │                  │
   ┌────▼────┐   ┌─────▼─────┐   ┌───────▼───────┐
   │REST API │   │   CLI     │   │  SDK (Python) │
   │POST /uap│   │$ uap chat │   │env.observe()  │
   │/v1/env/ │   │  "hello"  │   │               │
   │observe  │   │           │   │               │
   └─────────┘   └───────────┘   └───────────────┘
        │              │                  │
        └──────────────┴──────────────────┘
                       │
            ┌──────────▼──────────┐
            │   UAP Provider      │
            └─────────────────────┘
```

### 8.2 CLI 接口规范

CLI 工具 `uap` 提供常用模板的快捷命令：

```bash
# 聊天（chat 模板的快捷方式）
uap chat "What is the capital of France?"
uap chat --model gpt-4o --temperature 0.7 "Explain quantum computing"
uap chat --stream "Write a poem"

# 多轮对话（有状态模式）
uap chat --env chat_01 "Follow up question"

# Agent 任务（agent 模板的快捷方式）
uap agent "Analyze sales data" --file sales.csv
uap agent --model claude-opus-4-6 "Refactor this code" --file main.py

# 通用环境交互
uap env declare --file my-env.json
uap env observe --env gomoku_01 --input board_state.json
uap env close gomoku_01

# 查询 Provider 信息
uap provider info

# 管理会话
uap session init --provider openai
uap session close sess_abc123

# 配置
uap config set provider.url https://api.openai.com
uap config set auth.token sk-...
```

**CLI 输出格式：**

```bash
# 默认: 纯文本（流式输出到 stdout）
uap chat "hello"
# -> Hello! How can I help you?

# JSON 输出
uap chat --output json "hello"
# -> {"actions":[{"id":"reply","params":{"content":[{"type":"text","text":"Hello!"}]}}],"status":"continue"}

# 静默模式（只输出内容，无装饰）
uap chat --quiet "hello"
```

### 8.3 SDK 接口规范 (Python)

```python
import uap

# 初始化客户端
client = uap.Client(
    provider="https://api.openai.com",
    auth=uap.BearerAuth("sk-..."),
)

# === 聊天（使用 chat 模板快捷方式）===

# 同步对话
env = client.env.declare(template="chat", config={
    "model": "gpt-4o",
    "system_prompt": "You are helpful.",
    "options": {"temperature": 0.7},
})
response = env.observe(message=uap.UserMessage("Hello"))
print(response.reply_text)  # 快捷访问回复文本

# 流式对话
async for event in env.observe_stream(message=uap.UserMessage("Write a story")):
    if event.type == "delta":
        print(event.text, end="", flush=True)

# 带工具调用
env = client.env.declare(template="chat", config={
    "model": "gpt-4o",
    "tools": [uap.Tool(name="web_search", description="Search the web",
                       parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})]
})

response = env.observe(message=uap.UserMessage("Search for latest AI news"))
if response.has_tool_calls:
    for tc in response.tool_calls:
        result = execute_tool(tc.name, tc.arguments)
        response = env.observe(tool_result=uap.ToolResult(tc.id, result))
    print(response.reply_text)

# === 通用环境交互 ===

# 五子棋
env = client.env.declare(
    name="五子棋",
    description="15x15 标准五子棋...",
    example={...},
    inputs=[...],
    actions=[...],
)
response = env.observe(board_state={"board": [...], "current_turn": "black", ...})
print(response.actions)  # [{"id": "place_stone", "params": {"x": 7, "y": 7}}]

# === 无状态模式（一次性调用）===

response = client.env.observe_stateless(
    env={"template": "chat", "config": {"model": "gpt-4o"}},
    history=[...],
    inputs={"message": uap.UserMessage("Hello")},
)

# === Provider 发现 ===
info = client.provider.info()
for model in info.models:
    print(f"{model.id}: {model.capabilities}")
```

---

## 9. 能力协商 (Capability Negotiation)

能力协商是 UAP 的核心机制，确保 Consumer 和 Provider 之间对支持的功能达成一致。

### 9.1 标准能力

| 能力 ID | 说明 |
|---------|------|
| `streaming` | 流式输出 |
| `vision` | 图片输入 |
| `audio` | 音频输入/输出 |
| `file` | 文件上传/下载 |
| `env` | 环境交互 |
| `stateful` | 有状态连接模式 |
| `provider_push` | Provider 主动推送消息 |
| `structured_output` | JSON Schema 约束输出 |
| `embeddings` | 向量嵌入 |
| `batch` | 批量请求 |

### 9.2 协商流程

```
Consumer                          Provider
   │                                 │
   │─── session.init ───────────────>│
   │    capabilities_requested:      │
   │    [streaming, env, stateful]   │
   │                                 │
   │<── session.init response ───────│
   │    capabilities:                │
   │    {streaming:true,             │
   │     env:true,                   │
   │     stateful:true}              │
   │                                 │
   │  (Consumer knows what           │
   │   is supported, adapts UX)      │
```

---

## 10. 认证与安全

### 10.1 认证方式

| 方式 | `auth.type` | 适用场景 |
|------|-------------|----------|
| Bearer Token | `bearer` | API Key 直接访问 |
| OAuth 2.0 | `oauth2` | 第三方应用授权 |
| API Key Header | `api_key` | 自定义 Header 传递 |
| mTLS | `mtls` | 机器间安全通信 |

### 10.2 安全要求

- 所有 HTTP 传输 **必须** 使用 TLS 1.2+
- Token 不得出现在 URL 中
- Provider 应支持请求签名验证（可选）
- 敏感参数（如 `auth.token`）在日志中必须脱敏

---

## 11. Provider 适配层

UAP Gateway 或 SDK 内部负责将 UAP 消息转换为具体 Provider 的格式。

### 11.1 适配器接口

```python
class ProviderAdapter(Protocol):
    """每个 AI 后端实现此接口"""

    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> set[str]: ...

    async def env_act(
        self, env_declaration: EnvDeclaration, inputs: dict, history: list
    ) -> EnvActResult: ...

    async def env_act_stream(
        self, env_declaration: EnvDeclaration, inputs: dict, history: list
    ) -> AsyncIterator[StreamEvent]: ...
```

### 11.2 内置适配器

| 适配器 | 后端 |
|--------|------|
| `openai` | OpenAI API / Azure OpenAI |
| `anthropic` | Anthropic Claude API |
| `google` | Google Gemini API |
| `ollama` | Ollama 本地模型 |
| `custom` | 任意兼容 OpenAI 格式的端点 |

---

## 12. 扩展机制

### 12.1 自定义能力

Provider 可以声明自定义能力，以 `x-` 前缀命名：

```json
{
  "capabilities": {
    "streaming": true,
    "x-code-execution": true,
    "x-web-browsing": {
      "enabled": true,
      "max_pages": 10
    }
  }
}
```

### 12.2 自定义方法

Provider 可以注册自定义方法，以 `x-` 前缀命名：

```json
{
  "method": "x-rag.query",
  "params": {
    "collection": "docs",
    "query": "How to configure...",
    "top_k": 5
  }
}
```

### 12.3 Middleware / Hooks

SDK 和 Gateway 支持 middleware 机制：

```python
@client.middleware
async def log_requests(request, next):
    print(f"-> {request.method}")
    response = await next(request)
    print(f"<- {response.status} ({response.usage.total_tokens} tokens)")
    return response

@client.middleware
async def add_default_system_prompt(request, next):
    if request.method == "env.observe" and request.params.get("template") == "chat":
        # 注入默认 system prompt
        pass
    return await next(request)
```

---

## 13. 配置规范

### 13.1 配置文件

`~/.uap/config.yaml`:

```yaml
version: "0.2"

# 默认 Provider
default_provider: my-gateway

# Provider 配置
providers:
  openai:
    url: https://api.openai.com
    auth:
      type: bearer
      token_env: OPENAI_API_KEY
    default_model: gpt-4o

  anthropic:
    url: https://api.anthropic.com
    auth:
      type: api_key
      header: x-api-key
      token_env: ANTHROPIC_API_KEY
    default_model: claude-opus-4-6

  my-gateway:
    url: https://ai-gateway.mycompany.com
    auth:
      type: oauth2
      client_id: myapp
      token_url: https://auth.mycompany.com/token

  local:
    url: http://localhost:11434
    adapter: ollama
    default_model: llama3

# 全局默认选项
defaults:
  temperature: 0.7
  max_tokens: 4096
  stream: true
  connection_mode: stateful
```

### 13.2 环境变量

| 变量 | 说明 |
|------|------|
| `UAP_PROVIDER` | 覆盖默认 Provider |
| `UAP_MODEL` | 覆盖默认模型 |
| `UAP_CONFIG_PATH` | 自定义配置文件路径 |
| `UAP_LOG_LEVEL` | 日志级别 |
| `UAP_CONNECTION_MODE` | 覆盖默认连接模式 |

---

## 14. 协议版本与兼容性

### 14.1 版本格式

`MAJOR.MINOR`（如 `0.2`、`1.0`）

- **MAJOR** 变更：不兼容的协议变更
- **MINOR** 变更：向后兼容的新增功能

### 14.2 版本协商

Consumer 在 `session.init` 中声明支持的版本范围，Provider 选择最高兼容版本：

```json
{
  "method": "session.init",
  "params": {
    "uap_versions": ["0.2", "1.0"],
    ...
  }
}
```

---

## 附录 A: 完整方法参考

```
session.init          # 初始化会话，协商能力和连接模式
session.close         # 关闭会话
env.declare           # 声明环境（描述、输入、动作、约束，或使用模板）
env.observe           # 发送环境输入数据
env.act               # AI 返回要执行的动作（响应）
env.update            # 动态更新环境声明
env.close             # 结束环境交互
provider.info         # 查询 Provider 信息和可用模型
```

## 附录 B: 预定义模板参考

| 模板 | inputs | actions |
|------|--------|---------|
| `chat` | `message`, `tool_result` | `reply`, `tool_call` |
| `agent` | `task_update`, `approval_response`, `file_content` | `thinking`, `tool_call`, `file_write`, `file_read`, `complete` |
| `computer_use` | `screenshot`, `ui_tree`, `audio` | `mouse_*`, `keyboard_*`, `shell_command` |

## 附录 C: 与 OpenAI API 的映射关系

| UAP | OpenAI |
|-----|--------|
| `env.declare(template="chat")` | N/A（隐含） |
| `env.observe(message=...)` | `POST /v1/chat/completions` |
| `inputs.message.role` | `messages[].role` |
| `inputs.message.content` | `messages[].content` |
| `config.options.temperature` | `temperature` |
| `config.options.max_tokens` | `max_tokens` |
| `config.tools` | `tools` (function calling) |
| `stream: true` | `stream: true` (SSE) |

## 附录 D: 与 Anthropic API 的映射关系

| UAP | Anthropic |
|-----|-----------|
| `env.declare(template="chat")` | N/A（隐含） |
| `env.observe(message=...)` | `POST /v1/messages` |
| `inputs.message.content` | `content` (array of blocks) |
| `config.options.max_tokens` | `max_tokens` |
| `config.tools` | `tools` |
| `config.system_prompt` | `system` 参数 |

---

*End of Specification*
