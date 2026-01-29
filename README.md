# Gotify2Telegram

Gotify 消息转发到 Telegram。

## 功能

- 🔄 实时转发 Gotify → Telegram
- 📁 长消息自动转文件
- 🌐 支持 HTTP/SOCKS5 代理
- 🔄 自动重试机制
- 🏷️ 应用名称缓存

## 快速开始

### 1. 准备配置

无论采用何种运行方式，都需要先准备配置文件 `config.yaml`。

```bash
# 复制示例配置
cp config.example.yaml config.yaml
```

编辑 `config.yaml` 填入真实信息：
```yaml
telegram:
  bot_token: "YOUR_BOT_TOKEN"     # @BotFather 获取
  chat_id: "YOUR_CHAT_ID"        # 聊天ID
  proxy:
    url: ""                      # 可选: http://127.0.0.1:10801

gotify:
  server_url: "http://localhost:8080"
  client_token: "YOUR_CLIENT_TOKEN"

message:
  max_length: 4000
  title_format: "[{app_name}] {title}"
```

### 2. 选择运行方式

#### 方式一：Docker 运行（推荐）

使用 GitHub Container Registry 镜像：

```bash
docker run --rm \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  ghcr.io/jkfujr/gotify2telegram:latest
```

> **提示**：如果挂载的 `config.yaml` 不存在或为空，容器会自动生成一份示例配置。

#### 方式二：源码运行

**安装依赖**
```bash
pip install -r requirements.txt
# 如果需要 SOCKS5 代理支持
pip install requests[socks]
```

**启动程序**
```bash
python main.py
```

## 获取配置说明

**Telegram Bot Token:**
1. 找 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`
3. 获取 token

**Chat ID:**
1. 给机器人发消息
2. 访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. 找到 `chat.id`

**Gotify Token:**
1. 登录 Gotify 管理界面
2. Clients → 创建客户端
3. 复制 token
