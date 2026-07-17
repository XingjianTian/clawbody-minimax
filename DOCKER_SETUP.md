# 心宠 Docker 配置指南

本指南适用于 Windows 10/11。完成后，心宠控制网页运行在 `http://localhost:7860`，语音链路为：百度 ASR -> 通义千问 LLM -> 百度 TTS。

## 1. 准备环境

安装并启动 Docker Desktop、Git 和心宠控制软件。接通机器人电源，在控制软件中连接 USB 设备，并确认本机守护服务显示在 `localhost:8000`。

```powershell
git clone <仓库地址>
cd clawbody-minimax
Copy-Item .env.example .env
```

## 2. 配置 API 密钥

用文本编辑器打开仓库根目录的 `.env`，替换下列占位值：

```dotenv
# 阿里云百炼 DashScope：对话模型
MINIMAX_API_KEY=填写阿里云百炼API_KEY
MINIMAX_MODEL=qwen-plus
MINIMAX_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MINIMAX_MAX_TOKENS=80
HTTP_TRUST_ENV=false

# 百度智能云：语音识别和语音合成
BAIDU_APP_ID=填写百度应用ID
BAIDU_API_KEY=填写百度API_KEY
BAIDU_SECRET_KEY=填写百度SECRET_KEY
BAIDU_TTS_PER=111
BAIDU_TTS_SPD=5
BAIDU_TTS_PIT=5
BAIDU_TTS_VOL=12
BAIDU_ASR_LANGUAGE=zh-CN
```

不要把真实密钥写进本文档或提交到 Git。`.env` 已被 `.gitignore` 忽略，Docker Compose 会在启动时自动读取它。

## 3. 启动服务

首次启动或代码更新后执行：

```powershell
docker compose up -d --build
```

Dockerfile 默认使用阿里云 Debian 镜像，以提高国内网络下首次构建的稳定性。海外网络需要改回官方源时，可执行：

```powershell
docker compose build --build-arg DEBIAN_MIRROR=https://deb.debian.org
docker compose up -d
```

构建完成后打开 `http://localhost:7860`，点击“开始对话”，面对机器人麦克风说话。机器人应显示识别文字、生成回答、播放语音并配合动作。

以后可在 Docker Desktop 的 Containers 页面启动或停止 `clawbody-reachy`，无需重新构建。也可以使用：

```powershell
docker compose up -d
docker compose stop
```

## 4. 验证与排错

```powershell
docker compose ps
docker compose logs -f clawbody
```

正常状态应为 `healthy`。常见问题：

- `Robot connection failed`：先启动心宠控制软件，确认守护服务监听 `localhost:8000`，再重启容器。
- 网页打不开：确认 Docker Desktop 正在运行，且 7860 端口未被其他程序占用。
- 能动作但无声音：在心宠控制软件中确认扬声器设备、音量和系统输出设备正确。
- ASR/TTS 或 LLM 报错：检查 `.env` 中对应密钥、服务权限、余额及模型名称。

如果构建停在 `apt-get` 并显示 `exit code: 100`，先导出未折叠的完整日志：

```powershell
docker compose build --no-cache --progress=plain 2>&1 | Tee-Object docker-build.log
```

查看 `docker-build.log` 中 `exit code: 100` 前面的第一条 `E:` 或 `Err:`：

- `Temporary failure resolving`、`Connection timed out` 或 `EOF`：属于网络、DNS 或镜像源问题。退出 VPN/代理后重启 Docker Desktop，并重试构建。
- 错误地址包含失效的第三方 Docker 镜像站：在 Docker Desktop 的 **Settings > Docker Engine** 中移除对应 `registry-mirrors`，点击 **Apply & restart**。
- `Unable to locate package`：通常是软件源索引未完整下载；先解决前面的网络错误，再重新构建。

修改身份和说话方式时，编辑 `robot_identity/AGENTS.md`；容器以只读方式挂载该目录，下一次回答会读取最新内容。
