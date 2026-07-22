# 新 Windows 电脑配置心宠调试与 Reachy Mini 实时联调

本文档用于在另一台 Windows 10/11 电脑上，从零配置 PsyTwin Sentinel、ClawBody、Windows Host Bridge 和 Reachy Mini Lite。

完成后可以：

- 不打开 Reachy Mini Control，直接在 Sentinel 的“心宠调试”中启动 Reachy Mini Lite。
- 调试机器人动作、头部姿态、天线、麦克风和扬声器。
- 从“心宠调试”返回“实时联调”，使用测试学生进行语音对话。
- 点击关机时，机器人先完整进入休眠姿态，再关闭 Reachy daemon。

> 本文所有命令默认在 Windows PowerShell 中执行。除非公司环境另有要求，不需要使用管理员 PowerShell。

---

## 1. 运行结构

系统包含以下四部分：

```text
浏览器
  │
  ▼
PsyTwin Sentinel（localhost:3000）
  ├── ClawBody Docker 服务（127.0.0.1:7860）
  └── Windows Host Bridge（127.0.0.1:7861）
          └── Reachy daemon（127.0.0.1:8000）
                  └── USB/COM ── Reachy Mini Lite
```

| 端口 | 用途 | 运行位置 |
|---|---|---|
| `3000` | Sentinel 网页和服务端 API | Windows/Node.js |
| `7860` | ClawBody 对话服务 | Docker |
| `7861` | USB 设备控制桥 | Windows/Python |
| `8000` | Reachy Mini daemon | Windows/Python，由 Host Bridge 管理 |

`7861` 和 `8000` 不要暴露到局域网或公网。

---

## 2. 准备清单

### 2.1 硬件

- Reachy Mini Lite。
- Reachy 电源。
- 支持数据传输的 USB 线。
- Windows 10/11 电脑。

### 2.2 软件

安装以下软件：

- Git。
- Python 3.11。
- Node.js 20 或 Sentinel 当前规定的 Node.js 版本。
- npm。
- Docker Desktop。
- Sentinel 所需的 PostgreSQL 数据库。

检查环境：

```powershell
git --version
py -3.11 --version
node --version
npm --version
docker --version
docker compose version
```

如果 `py -3.11` 无法执行，请重新安装 Python 3.11，并勾选 Python Launcher。

### 2.3 云服务凭据

完整实时对话需要：

- 阿里云百炼 DashScope API Key。
- 百度智能云语音应用的 App ID。
- 百度语音 API Key。
- 百度语音 Secret Key。

只启动机器人和调试动作时，不需要 VPN，也不需要云服务凭据。实时对话需要电脑能够访问阿里云和百度服务。

---

## 3. 拉取两个仓库的 `main`

建议把两个仓库放在同一个父目录中，例如：

```text
C:\PsyTwin\
├── clawbody-minimax\
└── PsyTwin-Sentinel\
```

### 3.1 首次克隆

```powershell
New-Item -ItemType Directory -Path C:\PsyTwin -Force
Set-Location C:\PsyTwin

git clone git@github.com:XingjianTian/clawbody-minimax.git
git clone git@github.com:XingjianTian/PsyTwin-Sentinel.git
```

确认两个仓库都使用 `main`：

```powershell
cd C:\PsyTwin\clawbody-minimax
git switch main
git pull origin main

cd C:\PsyTwin\PsyTwin-Sentinel
git switch main
git pull origin main
```

### 3.2 确认包含最新 Reachy 修复

ClawBody 执行：

```powershell
cd C:\PsyTwin\clawbody-minimax
git log -1 --oneline
```

提交必须是 `f965069` 或比它更新。`f965069` 包含：

- daemon 启动等待从 15 秒增加到 45 秒。
- 关机等待休眠动作真正完成后再关闭 daemon。

Sentinel 执行：

```powershell
cd C:\PsyTwin\PsyTwin-Sentinel
git log -1 --oneline
```

提交必须是 `a692d64` 或比它更新。

---

## 4. 创建 ClawBody Python 环境

进入 ClawBody：

```powershell
cd C:\PsyTwin\clawbody-minimax
```

创建 Python 3.11 虚拟环境：

```powershell
py -3.11 -m venv .venv
```

激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止脚本运行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

关闭并重新打开普通 PowerShell，再激活虚拟环境。

安装依赖：

```powershell
python -m pip install --upgrade pip
pip install reachy-mini==1.8.0
pip install -e ".[dev,mediapipe_vision]"
```

验证：

```powershell
python -c "import reachy_mini; print(reachy_mini.__version__)"
clawbody-host --help
```

Reachy SDK 版本应为：

```text
1.8.0
```

---

## 5. 生成两组内部密钥

ClawBody 和 Sentinel 之间使用两组不同的密钥。

在已激活的 ClawBody 虚拟环境中连续执行两次：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

保存两次不同的输出：

```text
第一组：ClawBody 服务密钥
第二组：Host Bridge 密钥
```

对应关系：

| ClawBody | Sentinel | 要求 |
|---|---|---|
| `SERVICE_API_KEY` | `CLAWBODY_SERVICE_KEY` | 两边完全相同 |
| `HOST_BRIDGE_API_KEY` | `HOST_BRIDGE_API_KEY` | 两边完全相同 |

两组密钥彼此不要相同，不要使用文档里的示例值。

---

## 6. 配置 ClawBody `.env`

创建配置文件：

```powershell
cd C:\PsyTwin\clawbody-minimax
Copy-Item .env.example .env
```

编辑 `.env`，至少确认以下内容：

```dotenv
# 阿里云百炼。MINIMAX_* 是项目保留的兼容变量名。
MINIMAX_API_KEY=填写DashScope_API_Key
MINIMAX_MODEL=qwen-plus
MINIMAX_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MINIMAX_MAX_TOKENS=80

# 百度 ASR/TTS
BAIDU_APP_ID=填写百度应用ID
BAIDU_API_KEY=填写百度API_Key
BAIDU_SECRET_KEY=填写百度Secret_Key
BAIDU_TTS_PER=111
BAIDU_TTS_SPD=5
BAIDU_TTS_PIT=5
BAIDU_TTS_VOL=12
BAIDU_ASR_LANGUAGE=zh-CN

# Docker ClawBody 服务
SERVICE_HOST=127.0.0.1
SERVICE_PORT=7860
SERVICE_API_KEY=填写第一组随机密钥

# Windows Host Bridge
HOST_BRIDGE_HOST=127.0.0.1
HOST_BRIDGE_PORT=7861
HOST_BRIDGE_API_KEY=填写第二组随机密钥
HOST_BRIDGE_DAEMON_URL=http://127.0.0.1:8000
HOST_BRIDGE_CLAWBODY_HEALTH_URL=http://127.0.0.1:7860/health
```

注意：

- `.env` 中保留 `SERVICE_HOST=127.0.0.1`。Docker Compose 会在容器内部自动覆盖为 `0.0.0.0`。
- `HOST_BRIDGE_HOST` 必须是 `127.0.0.1`。
- 不要提交 `.env`。
- 不要把真实密钥发到聊天、Issue、PR 或截图中。

---

## 7. 安装 Windows Host Bridge

Host Bridge 必须运行在 Windows 宿主机，因为 Docker 容器不能直接管理 Windows USB/COM 设备。

保持虚拟环境已激活：

```powershell
cd C:\PsyTwin\clawbody-minimax
.\.venv\Scripts\Activate.ps1

clawbody-host install
clawbody-host restart
clawbody-host status
```

安装后会出现计划任务：

```text
PsyTwin ClawBody Host Bridge
```

正常状态应该包含：

```text
Status: Running
```

检查 Host Bridge：

```powershell
Invoke-RestMethod http://127.0.0.1:7861/health
```

预期：

```text
status
------
ok
```

### 7.1 如果这是全新电脑

安装和启动后会直接加载最新修复，不需要额外处理。

### 7.2 如果电脑以前运行过旧版 Host Bridge

仅执行 `git pull` 不会更新已经在内存中的 Python 进程。

执行：

```powershell
cd C:\PsyTwin\clawbody-minimax
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,mediapipe_vision]"
clawbody-host install
clawbody-host restart
```

如果页面仍显示旧版的 `within 15 seconds`，重启一次 Windows。登录后计划任务会自动加载新代码。

---

## 8. 启动 ClawBody Docker 服务

启动 Docker Desktop，等待 Docker Engine 完全就绪。

首次启动：

```powershell
cd C:\PsyTwin\clawbody-minimax
docker compose up -d --build
```

检查：

```powershell
docker compose ps
```

刚启动时可能暂时显示 `starting`，等待 30～60 秒后再次检查。

检查服务接口：

```powershell
Invoke-RestMethod http://127.0.0.1:7860/health
```

查看日志：

```powershell
docker compose logs --tail 100 clawbody
```

日常启动不需要每次重新构建：

```powershell
docker compose up -d
```

只有依赖或 Dockerfile 更新时才需要：

```powershell
docker compose up -d --build
```

---

## 9. 配置 Sentinel

安装依赖：

```powershell
cd C:\PsyTwin\PsyTwin-Sentinel
npm install
```

如果还没有 `.env`：

```powershell
Copy-Item .env.example .env
```

保留 Sentinel 原有数据库、认证和业务配置，并加入：

```dotenv
CLAWBODY_SERVICE_URL="http://127.0.0.1:7860"
CLAWBODY_SERVICE_KEY="填写ClawBody的SERVICE_API_KEY"

HOST_BRIDGE_URL="http://127.0.0.1:7861"
HOST_BRIDGE_API_KEY="填写ClawBody的HOST_BRIDGE_API_KEY"

PET_AI_DEMO_STUDENT_ID="stu-test"
```

绝对不要使用：

```dotenv
NEXT_PUBLIC_CLAWBODY_SERVICE_KEY=...
NEXT_PUBLIC_HOST_BRIDGE_API_KEY=...
```

密钥只能由 Sentinel 服务端使用，不能进入浏览器代码。

---

## 10. 准备 Sentinel 数据库

确认 Sentinel `.env` 中的 `DATABASE_URL` 正确。

生成 Prisma Client：

```powershell
npx prisma generate
```

已有数据库或共享环境使用：

```powershell
npx prisma migrate deploy
```

全新的本地开发数据库可以按照项目原有流程使用：

```powershell
npx prisma migrate dev
npx prisma db seed
```

不要在已有业务数据的数据库上执行：

```text
prisma migrate reset
```

---

## 11. 启动 Sentinel

```powershell
cd C:\PsyTwin\PsyTwin-Sentinel
npm run dev
```

打开：

```text
http://localhost:3000
```

使用已有后台账号登录。

---

## 12. 首次连接 Reachy Mini Lite

### 12.1 关闭 Reachy Mini Control

必须完全退出 Reachy Mini Control，包括系统托盘中的后台实例。

不要同时运行：

- Reachy Mini Control。
- 手动启动的 Reachy daemon。
- 第二个前台 `clawbody-host-bridge`。

### 12.2 连接硬件

1. 接通 Reachy Mini Lite 电源。
2. 使用数据 USB 线连接电脑。
3. 打开 Windows 设备管理器。
4. 在“端口（COM 和 LPT）”中确认出现类似 `USB-Enhanced-SERIAL CH343 (COM5)`。

COM 号码可能不是 COM5，以对方电脑实际显示为准。

### 12.3 启动设备

1. 打开 Sentinel。
2. 左侧展开“心图·AI配置”。
3. 点击“心宠AI管理中心”。
4. 点击右上角“心宠调试”。
5. 在“可用连接”中选择 Reachy USB/COM。
6. 点击“启动设备”。
7. 等待状态依次变化：

```text
START → CONNECT → HEALTHCHECK → APPS → Ready
```

当前版本允许 daemon 最多使用 45 秒开始监听。正常实体机器通常需要约 20～30 秒。

启动时机器人可能执行唤醒动作，确保周围没有障碍物。

---

## 13. 使用心宠调试

Ready 后可以使用：

- 唤醒。
- 休眠。
- 头部归中。
- 天线测试。
- 头部俯仰、侧倾、转向。
- 身体转向。
- 左右天线控制。
- 扬声器音量和测试声音。
- 麦克风输入音量。
- 实时日志。
- 顶部关机按钮。

### 13.1 休眠与关机的区别

“休眠”：

- 机器人进入休眠姿态。
- daemon 继续运行。
- 可以继续点击唤醒或使用控制器。

“关机”：

- 先执行完整休眠动作。
- 等待动作 UUID 从运行列表中消失。
- 然后关闭 daemon。
- 页面最终显示离线。

关机通常需要约 5～8 秒。按钮处于处理中时不要连续点击。

---

## 14. 使用实时联调

设备显示 Ready 后：

1. 点击“返回实时联调”。
2. 页面会自动切换回“心宠管理”。
3. 页面自动打开“实时联调”页签。
4. 在学生列表中选择“测试学生”。
5. 点击“开始对话”。

当前首版只允许 `PET_AI_DEMO_STUDENT_ID` 对应的测试学生启动实体 Reachy 对话。其他学生按钮不可用属于正常行为。

完整链路：

```text
学生语音
→ 百度 ASR
→ 心宠 AI
→ 必要时进入咨询师 AI
→ 心宠人格化转述
→ 百度 TTS
→ Reachy 播放语音和动作
```

结束时：

1. 在实时联调点击“停止”。
2. 返回心宠调试。
3. 点击顶部“关机”。
4. 等待机器人完成休眠并显示离线。

---

## 15. 每天使用的最短流程

首次配置完成后，每天只需要：

```text
1. 接通 Reachy 电源和 USB
2. 完全退出 Reachy Mini Control
3. 启动 Docker Desktop
4. 在 ClawBody 目录执行 docker compose up -d
5. 确认 Host Bridge 正常
6. 在 Sentinel 目录执行 npm run dev
7. 心宠调试 → 选择 USB → 启动设备
8. Ready → 返回实时联调
9. 选择测试学生 → 开始对话
10. 结束对话 → 返回心宠调试 → 关机
```

检查 Host Bridge：

```powershell
C:\PsyTwin\clawbody-minimax\.venv\Scripts\clawbody-host.exe status
```

---

## 16. 更新代码后的生效方式

### 16.1 更新 ClawBody

```powershell
cd C:\PsyTwin\clawbody-minimax
git switch main
git pull origin main

.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,mediapipe_vision]"
clawbody-host install
clawbody-host restart
```

`git pull` 只更新磁盘文件，不会替换已经运行在内存中的 Host Bridge。必须重启 Host Bridge；若旧进程仍占用 7861，重启 Windows 后再继续。

如果 Docker 相关依赖也发生变化：

```powershell
docker compose up -d --build
```

### 16.2 更新 Sentinel

```powershell
cd C:\PsyTwin\PsyTwin-Sentinel
git switch main
git pull origin main
npm install
npx prisma generate
npx prisma migrate deploy
npm run dev
```

---

## 17. 快速状态检查

```powershell
# Host Bridge
Invoke-RestMethod http://127.0.0.1:7861/health

# ClawBody
Invoke-RestMethod http://127.0.0.1:7860/health

# Docker
cd C:\PsyTwin\clawbody-minimax
docker compose ps

# Sentinel
Invoke-WebRequest http://localhost:3000 -UseBasicParsing

# 端口
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in 3000,7860,7861,8000 } |
    Select-Object LocalAddress,LocalPort,OwningProcess
```

未启动设备时，8000 不监听属于正常情况。设备 Ready 后，8000 应该监听。

---

## 18. 常见故障

### 18.1 “心宠设备控制桥未运行”

```powershell
cd C:\PsyTwin\clawbody-minimax
.\.venv\Scripts\clawbody-host.exe status
.\.venv\Scripts\clawbody-host.exe restart
Invoke-RestMethod http://127.0.0.1:7861/health
```

检查 `.env` 中的 Host Bridge 密钥是否仍是占位值。

### 18.2 页面仍提示 `within 15 seconds`

这表示运行的还是旧版 Host Bridge。

```powershell
cd C:\PsyTwin\clawbody-minimax
git log -1 --oneline
```

确认包含 `f965069` 或更新提交，然后：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,mediapipe_vision]"
clawbody-host install
clawbody-host restart
```

仍显示 15 秒时，重启 Windows。

### 18.3 点击关机没有进入休眠

旧版代码会在休眠动作完成前关闭 daemon。确认已拉取 `f965069` 或更新版本，并重新启动 Host Bridge。

修复生效后，关机应持续约 5～8 秒，然后页面显示离线。

### 18.4 找不到 USB/COM

检查：

- Reachy 是否通电。
- USB 线是否支持数据。
- Windows 设备管理器是否显示 CH343 COM 端口。
- Reachy Mini Control 是否完全退出。
- 是否有其他串口程序占用设备。
- 更换 USB 口或数据线。

### 18.5 Host Bridge 返回 401

确认：

```text
ClawBody HOST_BRIDGE_API_KEY
==
Sentinel HOST_BRIDGE_API_KEY
```

修改后重启 Host Bridge 和 Sentinel。

### 18.6 Sentinel 显示设备命令来源无效

使用正确地址访问：

```text
http://localhost:3000
```

修改 Sentinel `.env` 后必须重新启动 `npm run dev`。

### 18.7 心宠调试正常，但无法开始对话

检查：

- Docker Desktop 是否运行。
- `docker compose ps` 是否健康。
- 7860 `/health` 是否可访问。
- `CLAWBODY_SERVICE_KEY` 是否等于 `SERVICE_API_KEY`。
- 是否选择测试学生。
- 设备是否为 Ready。

### 18.8 ASR 没有文字

检查百度语音凭据、麦克风设备、输入音量和 Docker 日志：

```powershell
docker compose logs --tail 100 clawbody
```

### 18.9 没有 TTS 声音

检查百度 TTS 权限、扬声器音量，并在心宠调试中点击“测试声音”。

### 18.10 模型调用失败

检查：

- `MINIMAX_API_KEY` 是否为有效 DashScope Key。
- `MINIMAX_MODEL=qwen-plus` 是否可用。
- `MINIMAX_BASE_URL` 是否正确。
- 当前网络是否能够访问阿里云百炼。

---

## 19. 安全要求

- 不提交两个仓库的 `.env`。
- 不在浏览器变量中使用内部密钥。
- 不创建 `NEXT_PUBLIC_HOST_BRIDGE_API_KEY`。
- 不创建 `NEXT_PUBLIC_CLAWBODY_SERVICE_KEY`。
- 不把 7860、7861、8000 暴露到公网。
- 不允许通过 Sentinel 设备接口执行任意 Shell 命令。
- 操作机器人前清理周围障碍物。
- 不确定进程来源时，不要随意强制结束进程。

---

## 20. 最终验收清单

- [ ] ClawBody `main` 包含 `f965069` 或更新提交。
- [ ] Sentinel `main` 包含 `a692d64` 或更新提交。
- [ ] Python 3.11 虚拟环境可用。
- [ ] Reachy SDK 为 1.8.0。
- [ ] 两组随机密钥已生成并正确对应。
- [ ] 两个 `.env` 均未提交。
- [ ] Host Bridge 计划任务为 Running。
- [ ] `http://127.0.0.1:7861/health` 正常。
- [ ] Docker ClawBody 为 healthy。
- [ ] `http://127.0.0.1:7860/health` 正常。
- [ ] Sentinel 可以登录。
- [ ] 心宠调试可以发现 Reachy COM 端口。
- [ ] 启动设备在 45 秒内进入 Ready。
- [ ] 唤醒、休眠、归中和天线测试正常。
- [ ] 扬声器和麦克风正常。
- [ ] 返回实时联调后自动打开实时联调页签。
- [ ] 测试学生可以开始和停止对话。
- [ ] ASR、模型、TTS 链路正常。
- [ ] 点击关机后先完成休眠，再显示离线。

---

## 21. 获取帮助时提供的信息

不要提供任何密钥。可以提供：

```powershell
git -C C:\PsyTwin\clawbody-minimax log -1 --oneline
py -3.11 --version
node --version
docker compose version

C:\PsyTwin\clawbody-minimax\.venv\Scripts\clawbody-host.exe status
Invoke-RestMethod http://127.0.0.1:7861/health

cd C:\PsyTwin\clawbody-minimax
docker compose ps
docker compose logs --tail 100 clawbody
```

同时说明：

- Windows 版本。
- Reachy 型号。
- 实际 COM 端口。
- 页面完整错误信息。
- 错误发生在发现、启动、动作、关机、ASR、模型还是 TTS 阶段。

发送日志前删除 API Key、服务密钥、Cookie、JWT 和学生隐私信息。
