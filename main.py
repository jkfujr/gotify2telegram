import sys, asyncio, logging, requests, time
from pathlib import Path
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import yaml
    from gotify import AsyncGotify
except ImportError as e:
    print(f"缺少必要的依赖包: {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)


class Config:
    """配置管理"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        if not Path(self.config_path).exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}")
    
    def _validate_config(self):
        required_keys = [
            'telegram.bot_token',
            'telegram.chat_id', 
            'gotify.server_url',
            'gotify.client_token'
        ]
        
        for key in required_keys:
            if not self._get_nested_value(key):
                raise ValueError(f"配置项缺失或为空: {key}")
    
    def _get_nested_value(self, key: str) -> Any:
        keys = key.split('.')
        value = self.config
        for k in keys:
            value = value.get(k, {})
        return value if value != {} else None
    
    @property
    def telegram_bot_token(self) -> str:
        return self._get_nested_value('telegram.bot_token')
    
    @property
    def telegram_chat_id(self) -> str:
        return self._get_nested_value('telegram.chat_id')
    
    @property
    def gotify_server_url(self) -> str:
        return self._get_nested_value('gotify.server_url')
    
    @property
    def gotify_client_token(self) -> str:
        return self._get_nested_value('gotify.client_token')
    
    @property
    def max_message_length(self) -> int:
        return self._get_nested_value('message.max_length') or 4000
    
    @property
    def title_format(self) -> str:
        return self._get_nested_value('message.title_format') or "[Gotify→{app_name}] - {title}"
    
    @property
    def proxy_url(self) -> Optional[str]:
        proxy_url = self._get_nested_value('telegram.proxy.url')
        if proxy_url and proxy_url.strip():
            return proxy_url.strip()
        return None
    
    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        proxy_url = self.proxy_url
        if not proxy_url:
            return None
        
        if not (proxy_url.startswith(('http://', 'https://', 'socks5://'))):
            raise ValueError(f"不支持的代理格式: {proxy_url}。支持的格式: http://, https://, socks5://")
        
        if proxy_url.startswith('socks5://'):
            try:
                import socks
            except ImportError:
                raise ImportError("使用 SOCKS5 代理需要安装 requests[socks] 依赖: pip install requests[socks]")
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }


class TelegramSender:    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = self._create_session()
        self._test_connection()
    
    def _test_connection(self) -> None:
         """测试 Telegram API 连接"""
         self.logger.info("正在测试 Telegram API 连接...")
         
         try:
             url = f'https://api.telegram.org/bot{self.config.telegram_bot_token}/getMe'
             proxies = self.config.get_proxy_dict()
             
             response = self.session.get(url, timeout=10, proxies=proxies)
             result = response.json()
             
             if result.get('ok'):
                 bot_info = result['result']
                 bot_name = bot_info.get('first_name', 'Unknown')
                 bot_username = bot_info.get('username', 'Unknown')
                 self.logger.info(f"✅ Telegram API 连接成功！")
                 self.logger.info(f"   机器人名称: {bot_name}")
                 self.logger.info(f"   用户名: @{bot_username}")
                 self.logger.info(f"   目标聊天: {self.config.telegram_chat_id}")
                 self.logger.info("服务就绪，等待 Gotify 消息...")
             else:
                 raise Exception(f"Telegram API 返回错误: {result}")
                 
         except requests.exceptions.SSLError as e:
             self.logger.error(f"SSL 连接失败: {e}")
             self.logger.error("建议: 1) 检查网络连接 2) 配置代理服务器")
             raise Exception("Telegram API SSL 连接失败")
             
         except requests.exceptions.ConnectionError as e:
             self.logger.error(f"网络连接失败: {e}")
             if self.config.proxy_url:
                 self.logger.error(f"当前使用代理: {self.config.proxy_url}")
                 self.logger.error("请检查代理服务器是否正常工作")
             else:
                 self.logger.error("建议配置代理服务器")
             raise Exception("Telegram API 网络连接失败")
             
         except requests.exceptions.Timeout as e:
             self.logger.error(f"连接超时: {e}")
             raise Exception("Telegram API 连接超时")
             
         except Exception as e:
             self.logger.error(f"Telegram API 连接测试失败: {e}")
             raise Exception(f"Telegram API 连接失败: {e}")
    
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,                    # 总共重试3次
            backoff_factor=1,           # 重试间隔：1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],  # 状态码重试
            allowed_methods=["POST"],   # 只对 POST 请求重试
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _make_request(self, method: str, data: Dict[str, Any], files: Optional[Dict] = None) -> bool:
        url = f'https://api.telegram.org/bot{self.config.telegram_bot_token}/{method}'
        
        proxies = self.config.get_proxy_dict()
        if proxies:
            self.logger.debug(f"使用代理: {self.config.proxy_url}")
        
        max_manual_retries = 2
        
        for attempt in range(max_manual_retries + 1):
            try:
                response = self.session.post(
                    url, 
                    data=data, 
                    files=files, 
                    timeout=30,
                    proxies=proxies
                )
                
                result = response.json()
                
                if result.get('ok'):
                    if attempt > 0:
                        self.logger.info(f"消息发送成功 (重试 {attempt} 次后): {method}")
                    else:
                        self.logger.info(f"消息发送成功: {method}")
                    return True
                else:
                    self.logger.error(f"Telegram API 错误: {result}")
                    return False
                    
            except requests.exceptions.SSLError as e:
                if attempt < max_manual_retries:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"SSL 连接失败 (尝试 {attempt + 1}/{max_manual_retries + 1})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"SSL 连接最终失败: {e}")
                    self.logger.error("建议: 1) 检查网络连接 2) 配置代理服务器")
                    return False
                    
            except requests.exceptions.ConnectionError as e:
                if attempt < max_manual_retries:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"网络连接失败 (尝试 {attempt + 1}/{max_manual_retries + 1})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"网络连接最终失败: {e}")
                    return False
                    
            except requests.exceptions.Timeout as e:
                if attempt < max_manual_retries:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"请求超时 (尝试 {attempt + 1}/{max_manual_retries + 1})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"请求最终超时: {e}")
                    return False
                    
            except requests.RequestException as e:
                if attempt < max_manual_retries:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"网络请求失败 (尝试 {attempt + 1}/{max_manual_retries + 1}): {e}")
                    self.logger.warning(f"{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"网络请求最终失败: {e}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"发送消息时出现未知错误: {e}")
                return False
        
        return False
    
    def send_text_message(self, message: str) -> bool:
        """发送文本消息"""
        data = {
            'chat_id': self.config.telegram_chat_id,
            'text': message
        }
        return self._make_request("sendMessage", data)
    
    def send_document(self, title: str, content: str) -> bool:
        """发送文档"""
        files = {
            'document': ('message.txt', content.encode('utf-8'))
        }
        data = {
            'chat_id': self.config.telegram_chat_id,
            'caption': f"{title} [消息过长，以文件形式发送]"
        }
        return self._make_request("sendDocument", data, files)
    
    def send_message(self, app_name: str, title: str, body: str) -> bool:
        """根据长度选择发送方式"""
        formatted_title = self.config.title_format.format(
            app_name=app_name, 
            title=title
        )
        full_message = f"{formatted_title}\n\n{body}"
        
        if len(full_message) >= self.config.max_message_length:
            self.logger.info(f"消息过长 ({len(full_message)} 字符)，以文件形式发送")
            return self.send_document(formatted_title, full_message)
        else:
            return self.send_text_message(full_message)


class GotifyListener:
    def __init__(self, config: Config, telegram_sender: TelegramSender):
        self.config = config
        self.telegram_sender = telegram_sender
        self.logger = logging.getLogger(__name__)
        self._app_cache = {}
    
    async def _get_application_name(self, async_gotify: AsyncGotify, app_id: int) -> str:
        if app_id in self._app_cache:
            return self._app_cache[app_id]
        
        try:
            applications = await async_gotify.get_applications()
            app_name = next(
                (app['name'] for app in applications if app['id'] == app_id), 
                f"未知应用({app_id})"
            )
            self._app_cache[app_id] = app_name
            return app_name
        except Exception as e:
            self.logger.error(f"获取应用信息失败: {e}")
            return f"应用{app_id}"
    
    async def start_listening(self):
        self.logger.info("开始连接 Gotify 服务器...")
        
        try:
            async_gotify = AsyncGotify(
                base_url=self.config.gotify_server_url,
                client_token=self.config.gotify_client_token,
            )
            
            self.logger.info("成功连接到 Gotify 服务器，开始监听消息...")
            
            async for message in async_gotify.stream():
                try:
                    app_name = await self._get_application_name(async_gotify, message['appid'])
                    
                    self.logger.info(f"收到来自 {app_name} 的消息: {message['title']}")
                    
                    success = self.telegram_sender.send_message(
                        app_name=app_name,
                        title=message['title'],
                        body=message['message']
                    )
                    
                    if not success:
                        self.logger.warning("消息发送失败，但继续监听...")
                        
                except Exception as e:
                    self.logger.error(f"处理消息时出错: {e}")
                    
        except Exception as e:
            self.logger.error(f"连接 Gotify 服务器失败: {e}")
            raise


def setup_logging():
    """日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('gotify2telegram.log', encoding='utf-8')
        ]
    )


async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("正在加载配置...")
        config = Config()
        logger.info("配置加载成功")
        logger.info("正在初始化 Telegram 连接...")
        try:
            telegram_sender = TelegramSender(config)
            logger.info("Telegram 连接测试通过")
        except Exception as e:
            logger.error(f"Telegram 连接失败: {e}")
            logger.error("程序无法启动，请检查配置和网络连接")
            sys.exit(1)
        
        gotify_listener = GotifyListener(config, telegram_sender)
        await gotify_listener.start_listening()
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在退出...")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"启动失败: {e}")
        sys.exit(1)
