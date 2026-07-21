# 心宠 Docker 安装与使用指南

本文适用于 Windows 10/11。请使用 UTF-8 编码打开本文档。完成后，ClawBody 会以无界面内部服务运行在 `http://127.0.0.1:7860`，Windows Host Bridge 会在 `http://127.0.0.1:7861` 管理 USB 发现和 Reachy daemon，统一从 Sentinel 的 `http://localhost:3000/pet-ai-management` 管理和发起对话。语音链路为：百度 ASR -> 通义千问 LLM -> 百度 TTS。

## 一、安装前准备

请提前准备：

1. 已安装并启动 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。
2. 已安装 Git，可在 PowerShell 执行 `git --version` 检查。
3. 已安装 Python 3.11，机器人已接通电源并通过 USB 连接。
4. 项目专用 `.env` 文件。该文件包含 API 密钥，应通过私密方式单独获取，不要上传到 Git。

打开 Docker Desktop，等待左下角显示 Docker Engine 正常运行，再继续后面的操作。

## 二、获取或更新项目

### 情况 A：电脑上还没有项目

打开 PowerShell，进入准备存放项目的目录，然后执行：

```powershell
git clone https://github.com/XingjianTian/clawbody-minimax.git
cd clawbody-minimax
```

执行 `Get-Location`，确认当前目录末尾是 `clawbody-minimax`。

### 情况 B：已经 Clone，但之前构建失败

进入已有项目目录并更新代码：

```powershell
cd <你的项目路径>\clawbody-minimax
git pull origin main
```

执行 `git log -1 --oneline`，应看到 `Stabilize Docker builds on domestic networks` 或更新的提交。

## 三、放置并检查 `.env`

把收到的 `.env` 放在项目根目录，与 `Dockerfile`、`docker-compose.yml` 同级：

```text
clawbody-minimax/
├── .env
├── Dockerfile
├── docker-compose.yml
└── robot_identity/
```

在 PowerShell 检查文件是否存在：

```powershell
Test-Path .env
```

返回 `True` 才能继续。不要把 `.env` 改名为 `.env.txt`。如果没有现成文件，可执行 `Copy-Item .env.example .env` 后自行填写。

`.env` 至少需要包含：

```dotenv
MINIMAX_API_KEY=你的阿里云百炼API_KEY
MINIMAX_MODEL=qwen-plus
MINIMAX_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MINIMAX_MAX_TOKENS=80
HTTP_TRUST_ENV=false

BAIDU_APP_ID=你的百度应用ID
BAIDU_API_KEY=你的百度API_KEY
BAIDU_SECRET_KEY=你的百度SECRET_KEY
BAIDU_TTS_PER=111
BAIDU_TTS_SPD=5
BAIDU_TTS_PIT=5
BAIDU_TTS_VOL=12
BAIDU_ASR_LANGUAGE=zh-CN

SERVICE_HOST=127.0.0.1
SERVICE_PORT=7860
SERVICE_API_KEY=另一个独立的长随机值

HOST_BRIDGE_HOST=127.0.0.1
HOST_BRIDGE_PORT=7861
HOST_BRIDGE_API_KEY=与Sentinel服务端完全相同的长随机值
HOST_BRIDGE_DAEMON_URL=http://127.0.0.1:8000
HOST_BRIDGE_CLAWBODY_HEALTH_URL=http://127.0.0.1:7860/health
```

可以执行以下命令生成随机值，每次执行一次，分别填写 Host Bridge 与 ClawBody service 的密钥：

```powershell
py -3.11 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Sentinel 服务端需要配置 `HOST_BRIDGE_URL=http://127.0.0.1:7861`，并使用与本项目 `.env` 完全相同的 `HOST_BRIDGE_API_KEY`。Host Bridge 在密钥为空或仍为示例占位值时会拒绝启动。不得把 Host Bridge 密钥放进 `NEXT_PUBLIC_*` 变量或浏览器代码。不要把任何真实 API 密钥粘贴到本文档、Issue、聊天群或 Git 提交中。

## 四、安装 Windows Host Bridge

第一次安装时，在项目根目录执行：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "reachy-mini==1.8.0"
python -m pip install -e ".[dev,mediapipe_vision]"
clawbody-host install
clawbody-host status
clawbody-host restart
```

`install` 创建或更新当前用户登录时运行的固定任务 `PsyTwin ClawBody Host Bridge`；`status` 查看该任务；`restart` 结束并重新启动这一个任务。以后更新 `.env` 或 Host Bridge 代码后，执行 `clawbody-host restart` 使其生效。若确实不再需要自动启动，可执行：

```powershell
.\.venv\Scripts\Activate.ps1
clawbody-host uninstall --yes
```

`uninstall --yes` 只删除上述固定任务，不卸载 Python 包，也不删除 `.env`。日常使用不要执行卸载。

Host Bridge 只监听 `127.0.0.1:7861`，所有 `/v1/*` 请求必须携带 `X-Host-Bridge-Key`。启动设备时，它在宿主机启动并管理 `127.0.0.1:8000` 的 Reachy daemon；Docker 容器通过 `host.docker.internal:8000` 访问同一个 daemon。`7861` 不对局域网或 Docker 发布。

**启动设备前必须彻底关闭 Reachy Mini Control**，否则它可能占用 USB 串口或 `8000` 端口。设备启动不需要 VPN，也不会访问 Hugging Face、GitHub、OpenAI 或任何应用目录；首次安装依赖以及后续阿里云/百度语音对话仍需要正常网络。

可用以下只读请求确认服务和 USB 发现，不会启动 daemon 或让机器人动作：

```powershell
Invoke-RestMethod http://127.0.0.1:7861/health
$hostBridgeKey = Read-Host "HOST_BRIDGE_API_KEY"
Invoke-RestMethod http://127.0.0.1:7861/v1/device/discover -Headers @{"X-Host-Bridge-Key"=$hostBridgeKey}
```

ClawBody 自身不再提供 Gradio 网页；浏览器只访问 Sentinel，Sentinel 服务端分别调用本机 `7861` 的 Host Bridge 和 `7860` 的 ClawBody service。

## 五、首次构建并启动

确认 PowerShell 当前位于项目根目录，然后执行：

```powershell
docker compose up -d --build
```

首次构建需要下载 Debian、GStreamer、Python 和机器人依赖，通常需要数分钟。命令结束时应出现类似内容：

```text
Image clawbody-minimax-clawbody Built
Container clawbody-reachy Started
```

如果命令仍在输出下载或编译信息，请等待它结束，不要关闭 PowerShell 或 Docker Desktop。

## 六、检查容器状态

执行：

```powershell
docker compose ps
```

正常情况下应看到：

```text
clawbody-reachy   Up ... (healthy)   127.0.0.1:7860->7860/tcp
```

刚启动时可能暂时显示 `health: starting`，等待 30 至 60 秒后再次执行 `docker compose ps`。可以检查内部服务健康状态：

```text
http://127.0.0.1:7860/health
```

然后执行日常流程：**启动 Docker -> 打开 Sentinel -> 选择“心宠调试” -> 点击“启动设备”**。面对机器人麦克风说话后，页面应依次显示识别文字、模型回答，并通过 Reachy 播放语音和动作。Reachy Mini Control 必须保持关闭。

## 七、以后如何启动和停止

镜像成功构建后，不需要每次重新构建。可以在 Docker Desktop 的 Containers 页面找到 `clawbody-reachy`，点击启动或停止按钮。

也可以使用 PowerShell：

```powershell
# 启动
docker compose up -d

# 停止但保留容器
docker compose stop

# 查看实时日志，按 Ctrl+C 退出日志
docker compose logs -f clawbody
```

只有拉取了新代码或 Dockerfile 发生变化时，才需要再次执行 `docker compose up -d --build`。

## 八、构建失败：`apt-get exit code 100`

这个错误发生在镜像构建阶段。镜像没有构建成功，所以 Docker Desktop 中不会出现可运行的 `clawbody-reachy` 容器。

本项目默认使用阿里云 Debian 镜像，并为 apt 设置了 5 次重试。先确认已经拉取最新修复：

```powershell
git pull origin main
git log -1 --oneline
```

然后清除本次失败的构建缓存并重新构建：

```powershell
docker builder prune -f
docker compose --progress=plain build --no-cache
docker compose up -d
```

`docker builder prune -f` 只清理未使用的构建缓存，不会删除源代码、`.env` 或正在运行的容器。

如果仍然失败，保存完整日志：

```powershell
docker compose --progress=plain build --no-cache 2>&1 | Tee-Object docker-build.log
```

把项目目录中的 `docker-build.log` 发给维护者。重点查看失败位置前面的第一条 `E:` 或 `Err:`：

- `Temporary failure resolving`：Docker 的 DNS 无法解析域名。
- `Connection timed out`、`Unable to connect` 或 `EOF`：网络、VPN、代理或镜像站连接失败。
- `Unable to locate package`：软件源索引没有完整下载，通常仍需先解决网络问题。
- 地址显示 `28.x.x.x`：通常是代理软件的 Fake-IP，Docker 没有正确使用该代理。

遇到代理或 Fake-IP 时：

1. 暂时退出 Clash、VPN 或其他代理软件。
2. 完全退出并重新启动 Docker Desktop。
3. 打开 Docker Desktop 的 **Settings > Resources > Proxies**，确认没有无效代理。
4. 打开 **Settings > Docker Engine**，检查 `registry-mirrors`；删除已失效的第三方镜像地址。
5. 点击 **Apply & restart**，然后重新执行构建命令。

海外网络需要切回 Debian 官方源时执行：

```powershell
docker compose build --no-cache --build-arg DEBIAN_MIRROR=https://deb.debian.org
docker compose up -d
```

## 九、运行问题排查

### 容器不断重启

```powershell
docker compose logs --tail 100 clawbody
```

根据日志最后一段错误排查，不要反复点击启动。

### `Robot connection failed`

先确认 Reachy Mini Control 已关闭、USB 线已连接，再检查 Host Bridge：

```powershell
.\.venv\Scripts\Activate.ps1
clawbody-host status
Test-NetConnection 127.0.0.1 -Port 7861
Invoke-RestMethod http://127.0.0.1:7861/health
```

如果计划任务存在但 `7861` 不通，检查 `.env` 是否仍是占位密钥，然后执行 `clawbody-host restart`。Host Bridge 就绪后，在 Sentinel 的“心宠调试”重新点击“启动设备”，再执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/daemon/status
docker compose restart clawbody
```

如果宿主机 `8000` 正常但容器仍然连接失败，验证 Docker Desktop 到宿主机 daemon 的路径：

```powershell
docker compose exec clawbody python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:8000/api/daemon/status', timeout=5).read().decode())"
```

该命令失败时，确认 Docker Desktop 已启动，并检查 Docker Desktop 的代理、防火墙或 `host.docker.internal` 配置；不要把 `HOST_BRIDGE_HOST` 改成 `0.0.0.0`。

### Host Bridge 返回 `401`

Sentinel 服务端与本项目 `.env` 的 `HOST_BRIDGE_API_KEY` 不一致。两边改成同一个长随机值后执行 `clawbody-host restart`，同时重启 Sentinel 服务。不要把密钥贴进浏览器控制台或 URL。

### Host Bridge 找不到 USB，或显示多个串口

关闭 Reachy Mini Control，重新插拔 USB，并在“心宠调试”刷新设备。没有设备时检查 Windows 设备管理器；存在多个匹配设备时，必须在 Sentinel 中明确选择正确的 `COM` 端口，Host Bridge 不会猜测。

### `7861` 或 `8000` 端口已被占用

```powershell
Get-NetTCPConnection -LocalPort 7861,8000 -ErrorAction SilentlyContinue
```

`7861` 应由一个 Host Bridge 计划任务占用；`8000` 应由 Host Bridge 启动的一个 Reachy daemon 占用。关闭 Reachy Mini Control 和手动启动的重复进程，然后用 `clawbody-host restart` 重启固定任务。不要同时运行计划任务与前台 `clawbody-host-bridge`。

### Sentinel 显示“心宠设备服务暂不可用”

确认 `docker compose ps` 显示 `healthy`，并检查本机回环地址的 7860 端口：

```powershell
Test-NetConnection localhost -Port 7860
```

`TcpTestSucceeded` 应为 `True`。

### 能动作但没有声音

保持 Reachy Mini Control 关闭。在 Sentinel 的“心宠调试”确认扬声器状态可用、输出音量不为 0，并执行“测试声音”。也可以只读检查 Host Bridge 启动的 daemon：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/media/status
Invoke-RestMethod http://127.0.0.1:8000/api/volume/current
docker compose logs --tail 100 clawbody
```

如果 daemon 扬声器状态不可用，先在“心宠调试”停止并重新启动设备；如果 daemon 状态与音量正常，则检查容器日志中的 Baidu TTS、音频通道或播放错误。不要打开 Reachy Mini Control 与 Host Bridge 争用设备。

### ASR、TTS 或 LLM 报错

检查 `.env` 中对应密钥是否完整、是否带多余引号或空格，并确认阿里云与百度云服务权限、余额和模型名称正确。修改 `.env` 后执行：

```powershell
docker compose up -d --force-recreate
```

## 十、修改身份和说话方式

编辑 `robot_identity/AGENTS.md` 可以修改心宠的名字、身份、记忆和说话方式。该目录会以只读方式挂载到容器中，保存后下一次回答会读取最新内容，通常无需重新构建镜像。
