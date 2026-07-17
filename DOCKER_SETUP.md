# 心宠 Docker 安装与使用指南

本文适用于 Windows 10/11。请使用 UTF-8 编码打开本文档。完成后，对话网页地址为 `http://localhost:7860`，语音链路为：百度 ASR -> 通义千问 LLM -> 百度 TTS。

## 一、安装前准备

请提前准备：

1. 已安装并启动 [Docker Desktop](https://www.docker.com/products/docker-desktop/)。
2. 已安装 Git，可在 PowerShell 执行 `git --version` 检查。
3. 已安装心宠控制软件，机器人已接通电源并通过 USB 连接。
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
```

不要把真实 API 密钥粘贴到本文档、Issue、聊天群或 Git 提交中。

## 四、启动机器人控制服务

1. 接通机器人电源并按下开机键。
2. 打开心宠控制软件。
3. 选择 USB 设备并完成连接。
4. 确认机器人状态为 Ready，电机、麦克风和扬声器均可用。
5. 确认软件检测到本机守护服务 `localhost:8000`。

Docker 容器会通过 `host.docker.internal:8000` 访问这个宿主机服务。控制软件没有启动时，网页可能能打开，但机器人无法动作或播放声音。

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
clawbody-reachy   Up ... (healthy)   0.0.0.0:7860->7860/tcp
```

刚启动时可能暂时显示 `health: starting`，等待 30 至 60 秒后再次执行 `docker compose ps`。然后打开：

```text
http://localhost:7860
```

进入网页后点击“开始对话”，面对机器人麦克风说话。正常链路应依次显示识别文字、模型回答，并播放语音和动作。

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

先启动心宠控制软件，确认机器人 Ready 且 `localhost:8000` 可用，然后执行：

```powershell
docker compose restart clawbody
```

### 网页打不开

确认 `docker compose ps` 显示 `healthy`，并检查 7860 端口：

```powershell
Test-NetConnection localhost -Port 7860
```

`TcpTestSucceeded` 应为 `True`。

### 能动作但没有声音

在心宠控制软件中检查扬声器设备和音量；同时确认 Windows 默认输出设备正确，再查看 `docker compose logs -f clawbody` 中是否有 TTS 错误。

### ASR、TTS 或 LLM 报错

检查 `.env` 中对应密钥是否完整、是否带多余引号或空格，并确认阿里云与百度云服务权限、余额和模型名称正确。修改 `.env` 后执行：

```powershell
docker compose up -d --force-recreate
```

## 十、修改身份和说话方式

编辑 `robot_identity/AGENTS.md` 可以修改心宠的名字、身份、记忆和说话方式。该目录会以只读方式挂载到容器中，保存后下一次回答会读取最新内容，通常无需重新构建镜像。
