# ClawBody 项目全面分析文档

> **项目来源**: https://github.com/wuzhenhuo/clawbody-minimax  
> **分析日期**: 2026年4月27日  
> **分析范围**: 完整代码库结构、架构设计、实现细节、依赖关系

---

## 1. 项目概述

### 1.1 项目定位

**ClawBody** 是一个将 AI 智能助手赋予物理机器人身体的开源项目。它将：
- **OpenClaw AI**（Clawson 智能助手）的智力能力
- **Reachy Mini** 机器人的物理表现力
- **MiniMax M2.7** 大语言模型 + **ElevenLabs TTS** 的语音对话能力

三者融合，创造一个能够看、听、说、动的具身智能（Embodied AI）系统。

### 1.2 核心特性

| 特性 | 描述 |
|------|------|
| 🎤 实时语音对话 | 基于 MiniMax STT + ElevenLabs TTS 的端到端语音交互 |
| 🧠 AI 智能 | 通过 OpenClaw Gateway 获取完整工具链（网页浏览、日历、智能家居等）|
| 👁️ 人脸追踪 | 支持 MediaPipe 和 YOLO 两种方案，实现自然的目光接触 |
| 💃 丰富动作 | 100Hz 运动控制循环，支持情绪表达、舞蹈、头部运动 |
| 🖥️ 模拟器支持 | 无需实体机器人，通过 MuJoCo 物理仿真运行 |
| 🎭 个性定制 | 支持自定义角色配置文件 |

### 1.3 技术栈概览

```
Python 3.11+
├── LLM: MiniMax M2.7 (OpenAI-compatible API)
├── STT: Google Speech Recognition (免费)
├── TTS: ElevenLabs API
├── 机器人: Reachy Mini (Pollen Robotics)
├── 模拟器: MuJoCo
├── 视觉: MediaPipe / YOLO / SmolVLM2
├── Web UI: Gradio
└── 协议: WebSocket (OpenClaw Gateway)
```

---

## 2. 项目结构

```
clawbody-minimax/
├── src/reachy_mini_openclaw/          # 核心源代码
│   ├── __init__.py
│   ├── main.py                         # 主入口与 ClawBodyCore 类
│   ├── config.py                       # 配置管理（环境变量 + dataclass）
│   ├── openai_realtime.py              # 语音处理管道（VAD → STT → LLM → TTS）
│   ├── openclaw_bridge.py              # OpenClaw Gateway WebSocket 客户端
│   ├── moves.py                        # 100Hz 运动控制系统
│   ├── camera_worker.py                # 摄像头工作线程 + 人脸追踪
│   ├── gradio_app.py                   # Gradio Web UI
│   ├── prompts.py                      # 系统提示词管理
│   ├── audio/
│   │   ├── __init__.py
│   │   └── head_wobbler.py             # 音频驱动的头部摆动
│   ├── tools/
│   │   ├── __init__.py
│   │   └── core_tools.py               # 工具定义（look/camera/dance/emotion 等）
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── head_tracker.py             # 人脸追踪抽象接口
│   │   ├── mediapipe_tracker.py        # MediaPipe 实现
│   │   ├── yolo_head_tracker.py        # YOLO 实现
│   │   └── processors.py               # 本地视觉处理（SmolVLM2）
│   └── prompts/                        # 角色配置文件目录
│       └── default.txt
├── openclaw-skill/
│   └── SKILL.md                        # OpenClaw 技能定义
├── pyproject.toml                      # Python 项目配置
├── .env.example                        # 环境变量模板
├── index.html                          # 静态页面（Hugging Face Spaces）
├── style.css                           # 样式文件
├── README.md                           # 项目文档
├── CONTRIBUTING.md                     # 贡献指南
├── LICENSE                             # Apache 2.0 许可证
├── vnc-xstartup-root                   # VNC 启动脚本
└── .github/                            # GitHub 配置
```

---

## 3. 架构设计

### 3.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户语音 / 麦克风                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Reachy Mini 机器人（或 MuJoCo 模拟器）                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   麦克风      │  │    摄像头     │  │      运动系统            │  │
│  │   (输入)      │  │   (视觉)      │  │ (头部、触角、身体)        │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘  │
└─────────┼────────────────┼──────────────────────┼─────────────────┘
          │                │                      │
          ▼                ▼                      │
┌─────────────────────────────────────────────────┼─────────────────┐
│                      ClawBody                    │                 │
│  ┌─────────────────────────────────────────────┼────────────┐   │
│  │         语音处理管道 (VoiceHandler)          │            │   │
│  │  • VAD 语音活动检测                          │            │   │
│  │  • Google STT 语音识别                       │            │   │
│  │  • MiniMax M2.7 LLM (支持工具调用)           │            │   │
│  │  • ElevenLabs TTS 语音合成                  ─┘            │   │
│  │  • 音频驱动的头部摆动 (HeadWobbler)                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              OpenClaw Gateway Bridge                     │   │
│  │  • AI 响应来自 Clawson (OpenClaw)                       │   │
│  │  • 完整 OpenClaw 工具访问                                │   │
│  │  • 对话记忆与上下文同步                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway                                  │
│  • 网页浏览  • 日历  • 智能家居  • 记忆  • 工具                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件交互

```
main.py (ClawBodyCore)
    ├── OpenAIRealtimeHandler (VoiceHandler)
    │       ├── VAD 检测用户语音
    │       ├── Google STT 转文字
    │       ├── MiniMax M2.7 LLM 生成回复（支持工具调用）
    │       ├── ElevenLabs TTS 合成语音
    │       └── 对话同步回 OpenClaw
    │
    ├── MovementManager (100Hz 运动控制)
    │       ├── 主运动队列（舞蹈、情绪、头部动作）
    │       ├── 叠加偏移量（语音摆动 + 人脸追踪 + 思考动画）
    │       └── 空闲呼吸动画
    │
    ├── CameraWorker (25Hz 摄像头)
    │       ├── 帧捕获与缓冲
    │       ├── 人脸检测与追踪
    │       └── 房间扫描（未检测到人脸时）
    │
    ├── OpenClawBridge (WebSocket)
    │       ├── 连接 OpenClaw Gateway
    │       ├── 发送/接收聊天消息
    │       └── 同步对话记忆
    │
    └── HeadWobbler (音频驱动)
            └── 根据 TTS 音频振幅生成头部偏移
```

---

## 4. 核心模块详解

### 4.1 main.py - 应用主控

**职责**: 协调所有子系统，管理生命周期

**关键类**:

#### `ClawBodyCore`
- **初始化流程**:
  1. 验证配置（MINIMAX_API_KEY、ELEVENLABS_API_KEY）
  2. 连接 Reachy Mini 机器人（支持实体和模拟器）
  3. 初始化运动系统（MovementManager + HeadWobbler）
  4. 初始化 OpenClaw Bridge
  5. 初始化摄像头工作线程（含人脸追踪）
  6. 初始化本地视觉处理器（可选）
  7. 创建工具依赖注入容器
  8. 初始化语音处理 Handler

- **运行时循环**:
  ```
  1. 测试 OpenClaw 连接
  2. 启用电机并归位到中性姿态
  3. 启动运动系统
  4. 启动摄像头
  5. 启动本地视觉（如启用）
  6. 启动音频录制/播放
  7. 启动三个异步任务:
     - handler.start_up()    # 语音处理主循环
     - record_loop()         # 麦克风输入 → Handler
     - play_loop()           # Handler → 扬声器输出
  ```

- **音频处理细节**:
  - 采样率: 16kHz（输入）/ 24kHz（输出）
  - 块大小: 1600 样本（100ms）
  - 自动检测设备: 优先 Reachy Mini Audio，回退到系统默认输入
  - 音量衰减: 50% 防止失真

#### `ClawBodyApp`
- Reachy Mini App 框架入口点
- 允许从机器人仪表盘直接运行

### 4.2 openai_realtime.py - 语音处理管道

**职责**: 完整的语音对话流水线

#### `VoiceHandler` 类（继承 `AsyncStreamHandler`）

**处理流程**:

```
用户语音
    ↓
VAD (能量阈值检测)
    • ENERGY_THRESHOLD = 50 (RMS)
    • SILENCE_FRAMES_THRESHOLD = 25 (~250ms 静音触发处理)
    • MIN_SPEECH_FRAMES = 3 (最小有效语音帧)
    • MAX_SPEECH_SECONDS = 30 (最大语音时长)
    ↓
Google Speech Recognition (STT)
    • 免费，无需 API Key
    • 语言: en-US
    ↓
MiniMax M2.7 LLM (Chat Completions)
    • 系统提示词: OpenClaw Agent 上下文 + 机器人身体指令
    • 工具调用: look/camera/dance/emotion + ask_openclaw
    • 最多 5 轮工具调用
    • 对话历史保留 20 轮
    • 温度: 0.8，最大 token: 500
    ↓
ElevenLabs TTS
    • 模型: eleven_multilingual_v2
    • 输出格式: PCM 24kHz 单声道
    • 语音设置: stability=0.5, similarity_boost=0.75
    ↓
对话同步回 OpenClaw
    • 保持跨渠道记忆一致性
```

**VAD 实现**:
```python
energy = sqrt(mean(audio^2))
if energy > ENERGY_THRESHOLD:
    # 检测到语音
    开始/继续录音
elif 正在录音 and 静音帧数 >= SILENCE_FRAMES_THRESHOLD:
    # 语音结束，触发处理
    发送音频到 STT → LLM → TTS
```

**工具调用处理**:
```python
# LLM 返回 tool_calls
for tool_call in message.tool_calls:
    if tool_name == "ask_openclaw":
        # 查询 OpenClaw 获取外部信息
        result = await _handle_openclaw_query(args)
    else:
        # 执行机器人动作工具
        result = await dispatch_tool_call(tool_name, args, deps)
    
    # 将工具结果返回给 LLM 继续对话
    messages.append({"role": "tool", ...})
```

### 4.3 openclaw_bridge.py - OpenClaw 网关桥接

**职责**: 通过 WebSocket 协议与 OpenClaw Gateway 通信

#### `OpenClawBridge` 类

**协议流程**:
```
1. 连接 WebSocket (带 origin 头)
2. 接收 connect.challenge
3. 发送 connect 请求 (含 token、协议版本、角色、scope)
4. 接收 hello 响应确认连接
5. 启动后台监听器循环 (_listen_loop)
```

**聊天 API**:
```python
# 发送消息
chat.send(idempotencyKey, sessionKey, message)

# 接收事件流
runId → event_queue
    ├── agent/stream=assistant → 累积文本
    ├── agent/stream=lifecycle/end → 结束
    └── chat/state=final → 最终消息
```

**关键设计**:
- **会话共享**: `session_key = "main"` 与 WhatsApp 等其他渠道共享上下文
- **会话键格式**: `agent:<agent_id>:<session_key>`
- **幂等性**: 每个请求带唯一 `idempotencyKey`
- **流式响应**: 通过 `event_queue` 收集流式事件
- **记忆同步**: `sync_conversation()` 将机器人对话同步回 OpenClaw

### 4.4 moves.py - 运动控制系统

**职责**: 100Hz 实时运动控制

#### 核心架构

```
主运动 (Primary Moves) - 顺序执行
├── HeadLookMove (看方向)
├── BreathingMove (呼吸动画)
└── 舞蹈/情绪动画 (外部库)

叠加偏移 (Secondary Offsets) - 实时叠加
├── Speech Offsets (语音摆动)
├── Face Tracking Offsets (人脸追踪)
└── Thinking Offsets (思考动画)

最终姿态 = Primary + Secondary (通过 compose_world_offset 组合)
```

#### `MovementManager` 类

**控制循环** (100Hz):
```python
def _run_loop(self):
    while not stopped:
        # 1. 处理命令队列
        self._poll_signals()
        
        # 2. 管理运动队列
        self._manage_move_queue()
        
        # 3. 管理呼吸动画（空闲时）
        self._manage_breathing()
        
        # 4. 更新人脸追踪偏移
        self._update_face_tracking()
        
        # 5. 更新思考动画
        self._update_thinking_offsets()
        
        # 6. 组合最终姿态
        head, antennas, body_yaw = self._compose_pose()
        
        # 7. 混合触角（监听时冻结）
        antennas = self._blend_antennas(antennas)
        
        # 8. 发送到机器人
        self._issue_command(head, antennas, body_yaw)
        
        # 9. 维持 100Hz 定时
        sleep(target_period - elapsed)
```

**动作类**:

| 动作类 | 功能 | 参数 |
|--------|------|------|
| `BreathingMove` | 空闲呼吸动画 | z 轴 5mm 正弦运动，触角 15° 摇摆 |
| `HeadLookMove` | 头部看向方向 | left/right/up/down/front，1 秒持续时间 |

**思考动画**:
- 启动: 0.5s 平滑淡入
- 头部: ±12° 偏航漂移 (0.15Hz) + 6° 俯仰 (0.2Hz) + 3mm 垂直摆动
- 触角: ±20° 不对称扫描 (0.4Hz，相位差 70°)
- 结束: 0.5s 平滑淡出

### 4.5 camera_worker.py - 摄像头与人脸追踪

**职责**: 25Hz 摄像头采集 + 人脸追踪状态机

#### 人脸追踪状态机

```
┌──────────┐     未检测到人脸      ┌──────────┐
│ SCANNING │ ──────────────────→ │ TRACKING │
│ 房间扫描  │  ←────────────────  │ 人脸追踪  │
└──────────┘    检测到人脸         └──────────┘
     ↑                                  │
     │                                  │ 人脸丢失
     │                                  ▼
     │                           ┌──────────┐
     │                           │ WAITING  │
     │                           │ 等待 2s  │
     │                           └────┬─────┘
     │                                │ 超时
     │                                ▼
     │                           ┌──────────┐
     └────────────────────────── │ RETURNING│
         插值完成，开始扫描        │ 插值回中性 │
                                 └──────────┘
```

**追踪参数**:
- **比例增益**: 0.85（闭环反馈，避免过冲）
- **平滑因子**: α=0.25（指数移动平均，0.5s 内 95% 收敛）
- **扫描模式**: ±35° 偏航正弦扫描，8 秒周期，轻微向上倾斜

**房间扫描**: 未检测到人脸时，机器人缓慢左右扫视房间

### 4.6 audio/head_wobbler.py - 音频驱动头部摆动

**职责**: 根据 TTS 音频振幅生成自然的头部运动

**设计**:
- **更新频率**: 30Hz
- **音频分析**: RMS 振幅计算
- **运动生成**:
  - z 轴: 振幅 × 8mm × sin(8t) — 垂直摆动
  - 横滚: 振幅 × 0.15rad × sin(3t) — 侧倾
  - 俯仰: 振幅 × 0.08rad × sin(5t+0.5) — 点头
  - 偏航: 振幅 × 0.05rad × sin(2t) — 轻微转头

**平滑处理**:
- 音频缓冲: 10 帧循环队列
- 平滑因子: 0.3
- 衰减: 静默 0.3s 后开始指数衰减（衰减率 3.0/s）

### 4.7 tools/core_tools.py - 工具系统

**职责**: 定义 LLM 可调用的机器人工具

#### 工具列表

| 工具 | 功能 | 参数 |
|------|------|------|
| `look` | 头部看向方向 | direction: left/right/up/down/front |
| `camera` | 捕获并分析图像 | 无（自动获取最新帧） |
| `face_tracking` | 启停人脸追踪 | enabled: bool |
| `dance` | 执行舞蹈 | dance_name: happy/excited/wave/nod/shake/bounce |
| `emotion` | 表达情绪 | emotion_name: happy/sad/surprised/curious/thinking/confused/excited |
| `stop_moves` | 停止所有运动 | 无 |
| `idle` | 保持静止 | 无 |
| `ask_openclaw` | 查询 OpenClaw | query: string, include_image: bool |

#### 视觉分析优先级

```
1. 本地 SmolVLM2（设备端，无网络延迟）
2. MiniMax Vision API（云端视觉）
3. OpenClaw Gateway（文本回退）
```

### 4.8 vision/ - 视觉系统

**职责**: 人脸检测与本地视觉处理

#### 人脸追踪实现

| 方案 | 文件 | 特点 | 依赖 |
|------|------|------|------|
| YOLO | `yolo_head_tracker.py` | 更准确，资源消耗大 | ultralytics, supervision |
| MediaPipe | `mediapipe_tracker.py` | 更轻量，速度快 | mediapipe>=0.10.14 |

**接口**: `HeadTracker.get_head_position(frame)` → `(eye_center, bbox)` 或 `(None, None)`

#### 本地视觉处理 (SmolVLM2)

```python
VisionConfig(
    model_path="HuggingFaceTB/SmolVLM2-256M-Video-Instruct",
    device_preference="auto",  # cuda/mps/cpu
)
```

---

## 5. 配置系统

### 5.1 环境变量

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `MINIMAX_API_KEY` | ✓ | - | MiniMax API 密钥 |
| `MINIMAX_MODEL` | ✗ | MiniMax-M2.7 | LLM 模型 |
| `MINIMAX_BASE_URL` | ✗ | https://api.minimaxi.chat/v1/ | API 基础 URL |
| `ELEVENLABS_API_KEY` | ✓ | - | ElevenLabs API 密钥 |
| `ELEVENLABS_VOICE_ID` | ✗ | 21m00Tcm4TlvDq8ikWAM | TTS 语音 ID |
| `OPENCLAW_GATEWAY_URL` | ✗ | ws://localhost:18789 | OpenClaw 网关地址 |
| `OPENCLAW_TOKEN` | ✗ | None | 认证令牌 |
| `ROBOT_HOST` | ✗ | reachy-mini.local | 机器人主机 |
| `ROBOT_PORT` | ✗ | 8000 | 机器人端口 |
| `ENABLE_FACE_TRACKING` | ✗ | true | 启用人脸追踪 |
| `HEAD_TRACKER_TYPE` | ✗ | yolo | 追踪器类型 |
| `ENABLE_LOCAL_VISION` | ✗ | false | 启用本地视觉 |

### 5.2 命令行参数

| 参数 | 说明 |
|------|------|
| `--debug` | 调试日志 |
| `--gradio` | 启动 Web UI |
| `--robot-name NAME` | 指定机器人名称 |
| `--robot-host HOST` | 机器人主机 |
| `--robot-port PORT` | 机器人端口 |
| `--gateway-url URL` | OpenClaw 网关 URL |
| `--no-camera` | 禁用摄像头 |
| `--no-openclaw` | 禁用 OpenClaw |
| `--no-face-tracking` | 禁用面部追踪 |
| `--local-vision` | 启用本地视觉处理 |
| `--profile NAME` | 使用自定义角色 |

---

## 6. 依赖分析

### 6.1 核心依赖

```toml
[project.dependencies]
openai>=1.50.0          # MiniMax LLM (OpenAI-compatible)
httpx>=0.25.0           # ElevenLabs TTS HTTP 调用
fastrtc>=0.0.17         # 音频流处理框架
numpy                   # 数值计算
scipy                   # 信号处理（重采样）
websockets>=12.0        # OpenClaw WebSocket 客户端
gradio>=4.0.0           # Web UI
python-dotenv           # 环境变量加载
```

### 6.2 可选依赖

```toml
[project.optional-dependencies]
yolo_vision = ["opencv-python", "ultralytics", "supervision"]
mediapipe_vision = ["mediapipe>=0.10.14"]
wireless = ["pygobject"]
dev = ["pytest", "pytest-asyncio", "ruff", "mypy"]
```

### 6.3 外部依赖（需单独安装）

```bash
# Reachy Mini SDK（机器人控制）
pip install git+https://github.com/pollen-robotics/reachy_mini.git

# 或模拟器支持
pip install "reachy-mini[mujoco]"

# 本地视觉（可选）
pip install torch transformers
```

---

## 7. 关键设计决策

### 7.1 为什么选择 MiniMax + ElevenLabs 而非 OpenAI Realtime？

原项目使用 OpenAI Realtime API，此 fork 改为：
- **MiniMax M2.7**: 成本更低，支持 OpenAI-compatible API
- **Google STT**: 免费，无需 API Key
- **ElevenLabs TTS**: 更自然的语音质量

**优势**:
- 降低运行成本
- 语音质量更好（ElevenLabs）
- STT 免费（Google Speech Recognition）

**劣势**:
- 延迟可能稍高（三个独立 API 调用）
- Google STT 需要联网

### 7.2 为什么保留 OpenClaw 集成？

即使使用 MiniMax 处理对话，仍保留 OpenClaw Bridge：
1. **记忆连续性**: 跨渠道（WhatsApp、Web、机器人）共享对话上下文
2. **工具扩展**: 访问 OpenClaw 的丰富工具集（日历、智能家居等）
3. **个性一致性**: 保持 Clawson 的统一人格

### 7.3 运动控制的分层设计

```
Primary Moves (主运动)
├── 占用运动队列
├── 顺序执行
└── 示例: 舞蹈、情绪表达、看向某处

Secondary Offsets (叠加偏移)
├── 实时计算
├── 叠加到主运动上
└── 示例: 语音摆动、人脸追踪、思考动画
```

这种设计允许：
- 舞蹈时仍能追踪人脸
- 说话时保持头部摆动
- 思考时展示自然动画

### 7.4 人脸追踪的闭环控制

```
摄像头帧 → 人脸检测 → 像素坐标 → look_at_image() → 
目标姿态 → 比例缩放(0.85) → EMA平滑(α=0.25) → 
运动系统 → 机器人执行 → 新帧 → ...
```

**比例增益 0.85**: 避免单帧过冲导致的抖动
**EMA α=0.25**: 在 25Hz 下，0.5s 内 95% 收敛，平衡响应速度与平滑度

---

## 8. 代码质量评估

### 8.1 优点

| 方面 | 评价 |
|------|------|
| **架构清晰** | 组件职责明确，依赖注入设计合理 |
| **类型提示** | 大量使用类型注解，提高可维护性 |
| **异步设计** | 正确使用 asyncio，避免阻塞 |
| **线程安全** | 多线程组件使用锁保护共享状态 |
| **错误处理** | 广泛的异常捕获，优雅降级 |
| **配置管理** | 环境变量 + dataclass，验证完整 |
| **日志系统** | 结构化日志，支持调试模式 |
| **文档** | 详细的 docstring 和注释 |

### 8.2 潜在改进点

| 问题 | 建议 |
|------|------|
| **全局状态** | `config = Config()` 全局实例可改为依赖注入 |
| **魔法数字** | 部分阈值参数可提取为配置项 |
| **测试覆盖** | 缺少单元测试和集成测试 |
| **STT 依赖性** | Google STT 需联网，可考虑本地 Whisper |
| **并发安全** | `asyncio.create_task()` 结果未保存，可能泄漏 |
| **资源清理** | 部分异常路径下资源释放不够彻底 |
| **类型检查** | 部分 `Any` 类型可进一步细化 |

### 8.3 代码规范

- **格式化**: Ruff (line-length=120)
- **类型检查**: mypy (python_version=3.11)
- **导入排序**: Ruff 自动处理
- **文档**: Google Style Docstrings

---

## 9. 运行模式

### 9.1 控制台模式（实体机器人）

```bash
clawbody
```

直接通过系统麦克风和扬声器进行语音对话。

### 9.2 模拟器模式

```bash
# 终端 1: 启动模拟器
reachy-mini-daemon --sim

# 终端 2: 启动 ClawBody（带 Web UI）
clawbody --gradio
```

### 9.3 Gradio Web UI 模式

```bash
clawbody --gradio
```

- 通过浏览器麦克风输入
- 实时显示对话记录
- 支持角色配置
- 显示系统状态

### 9.4 Reachy Mini App 模式

作为 Reachy Mini 应用框架的一部分运行，从机器人仪表盘启动。

---

## 10. 扩展性分析

### 10.1 添加新工具

在 `tools/core_tools.py` 中：
1. 定义工具规格（添加到 `TOOL_SPECS`）
2. 实现处理函数（`_handle_xxx`）
3. 注册到 `handlers` 字典

### 10.2 添加新动作

在 `moves.py` 中：
1. 继承 `Move` 类
2. 实现 `evaluate(t)` 方法
3. 通过 `movement_manager.queue_move()` 入队

### 10.3 添加新视觉处理器

在 `vision/` 中：
1. 实现 `HeadTracker` 接口
2. 实现 `get_head_position(frame)` 方法
3. 在 `config.py` 中添加配置项
4. 在 `main.py` 中初始化

### 10.4 更换 LLM/TTS

- **LLM**: 修改 `openai_realtime.py` 中的 `_get_llm_response()`
- **TTS**: 修改 `_synthesize_and_queue()`
- **STT**: 修改 `_transcribe()`

---

## 11. 安全与隐私

### 11.1 API 密钥管理

- 使用 `.env` 文件存储敏感信息
- `.gitignore` 排除 `.env`
- 支持环境变量覆盖

### 11.2 数据传输

- MiniMax API: HTTPS 加密
- ElevenLabs API: HTTPS 加密
- OpenClaw Gateway: WebSocket (ws:// 或 wss://)
- 机器人通信: 本地网络（8000 端口）

### 11.3 隐私考虑

- 摄像头数据仅本地处理（除非启用云视觉）
- 语音数据发送到 Google/MiniMax/ElevenLabs
- 对话内容同步到 OpenClaw Gateway

---

## 12. 性能特征

### 12.1 延迟分析

| 环节 | 预估延迟 | 说明 |
|------|----------|------|
| VAD 检测 | ~250ms | 静音阈值触发 |
| Google STT | 500-1500ms | 取决于网络 |
| MiniMax LLM | 500-2000ms | 取决于模型负载 |
| ElevenLabs TTS | 200-800ms | 取决于文本长度 |
| **总延迟** | **1.5-4.5s** | 端到端响应时间 |

### 12.2 资源消耗

| 组件 | CPU | 内存 | GPU |
|------|-----|------|-----|
| 主程序 | 低 | ~100MB | 无 |
| YOLO 人脸追踪 | 中等 | ~200MB | 可选 |
| MediaPipe | 低 | ~100MB | 无 |
| SmolVLM2 | 高 | ~500MB | 推荐 |
| MuJoCo 模拟器 | 中等 | ~300MB | 无 |

### 12.3 实时性保证

- **运动控制**: 100Hz 硬实时（独立线程）
- **人脸追踪**: 25Hz（独立线程）
- **音频处理**: 实时流（异步）
- **VAD**: 100ms 块处理

---

## 13. 与上游项目对比

### 13.1 原始项目 (tomrikert/clawbody)

| 特性 | 原始项目 | 此 Fork |
|------|----------|---------|
| LLM | OpenAI GPT-4 | MiniMax M2.7 |
| STT | OpenAI Whisper | Google Speech Recognition |
| TTS | OpenAI Realtime | ElevenLabs |
| 语音框架 | OpenAI Realtime API | fastrtc + 自定义管道 |
| 成本 | 较高（OpenAI） | 较低（MiniMax + 免费 STT） |
| 语音质量 | 好 | 更好（ElevenLabs） |

### 13.2 架构差异

```
原始: OpenAI Realtime API (一体化语音处理)
      └── 同时处理 STT + LLM + TTS

此 Fork: 分离式处理
      ├── Google STT
      ├── MiniMax LLM
      └── ElevenLabs TTS
```

**优势**:
- 每个组件可独立替换
- 更好的语音质量（ElevenLabs）
- STT 免费

**劣势**:
- 延迟稍高（三次 API 调用）
- 复杂度增加

---

## 14. 部署建议

### 14.1 开发环境

```bash
# 克隆项目
git clone https://github.com/wuzhenhuo/clawbody-minimax.git
cd clawbody-minimax

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[mediapipe_vision]"
pip install "reachy-mini[mujoco]"

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API 密钥
```

### 14.2 生产环境

- 使用物理机器人时，直接在机器人上运行
- 使用 Docker 容器化部署
- 配置日志轮转
- 监控 API 配额和延迟

### 14.3 常见问题

| 问题 | 解决方案 |
|------|----------|
| 机器人连接超时 | 检查 `reachy-mini-daemon` 是否运行 |
| OpenClaw 连接失败 | 检查网关 URL 和 token |
| STT 无法识别 | 检查麦克风权限和设备 |
| TTS 无声音 | 检查 ElevenLabs API 密钥和余额 |
| 人脸追踪卡顿 | 切换到 MediaPipe 或减少分辨率 |

---

## 15. 总结

### 15.1 项目价值

ClawBody 是一个设计精良的具身智能项目，成功将：
1. **大语言模型**（MiniMax M2.7）的推理能力
2. **语音技术**（STT + TTS）的自然交互
3. **机器人硬件**（Reachy Mini）的物理表现力
4. **AI 助手框架**（OpenClaw）的工具生态

融合为一个完整的语音交互机器人系统。

### 15.2 技术亮点

- ✅ **100Hz 运动控制**: 流畅的实时运动
- ✅ **分层动画系统**: 主运动 + 叠加偏移的优雅设计
- ✅ **多模态感知**: 语音 + 视觉 + 运动
- ✅ **开放架构**: 组件可替换，易于扩展
- ✅ **成本优化**: 相比原始项目显著降低运行成本

### 15.3 适用场景

- 教育机器人编程
- 语音交互研究
- 具身智能实验
- 智能家居助手
- 社交机器人原型

### 15.4 推荐指数

| 维度 | 评分 | 说明 |
|------|------|------|
| 代码质量 | ⭐⭐⭐⭐ | 结构清晰，类型完整 |
| 文档完整度 | ⭐⭐⭐⭐⭐ | README 详尽，注释丰富 |
| 架构设计 | ⭐⭐⭐⭐⭐ | 组件解耦，扩展性强 |
| 功能完整性 | ⭐⭐⭐⭐ | 覆盖主要场景 |
| 易用性 | ⭐⭐⭐⭐ | 安装配置较简单 |
| 社区活跃度 | ⭐⭐⭐ | 较新项目，社区待建 |

---

## 附录

### A. 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `main.py` | 711 | 主控逻辑 |
| `openai_realtime.py` | 578 | 语音处理管道 |
| `moves.py` | 648 | 运动控制系统 |
| `openclaw_bridge.py` | 610 | OpenClaw 网关客户端 |
| `camera_worker.py` | 382 | 摄像头与人脸追踪 |
| `core_tools.py` | 459 | 工具定义与实现 |
| `head_wobbler.py` | 223 | 音频驱动头部摆动 |
| `gradio_app.py` | 208 | Web UI |
| `config.py` | 92 | 配置管理 |
| `prompts.py` | 98 | 提示词管理 |

**总计**: ~4009 行 Python 代码

### B. 外部 API 依赖

| 服务 | 用途 | 计费模式 |
|------|------|----------|
| MiniMax API | LLM + Vision | 按 token |
| ElevenLabs API | TTS | 按字符 |
| Google Speech API | STT | 免费（有限额）|

### C. 许可证

- **项目**: Apache 2.0
- **Reachy Mini SDK**: 需查看 Pollen Robotics 许可证
- **OpenClaw**: 需查看 OpenClaw 许可证

---

*本文档基于对 clawbody-minimax 代码库的静态分析生成，所有结论基于代码本身，未经运行时验证。*
