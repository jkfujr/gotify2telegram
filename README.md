# Gotify2Telegram

Gotify 消息转发到 Telegram。

## 功能

- 🔄 实时转发 Gotify → Telegram
- 📁 长消息自动转文件
- 🌐 支持 HTTP/SOCKS5 代理
- 🔄 自动重试机制
- 🏷️ 应用名称缓存

## 快速开始

### 1. 安装
```bash
pip install -r requirements.txt
```

### 2. 配置
```bash
cp "config.example.yaml" config.yaml
```

编辑 `config.yaml`: 
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

### 3. 运行
```bash
python main.py
```

## 获取配置

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

SOCKS5 代理需要: `pip install requests[socks]`
