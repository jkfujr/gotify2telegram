import logging
import time
import json
from typing import Dict, Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import Config


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
            backoff_factor=1,           # 重试间隔: 1s, 2s, 4s
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

    def send_text_message(self, message: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """发送文本消息"""
        data = {
            'chat_id': self.config.telegram_chat_id,
            'text': message
        }
        if reply_markup is not None:
            data['reply_markup'] = json.dumps(reply_markup)
        return self._make_request("sendMessage", data)

    def send_document(self, title: str, content: str, reply_markup: Optional[Dict[str, Any]] = None) -> bool:
        """发送文档"""
        files = {
            'document': ('message.txt', content.encode('utf-8'))
        }
        data = {
            'chat_id': self.config.telegram_chat_id,
            'caption': f"{title} [消息过长，以文件形式发送]"
        }
        if reply_markup is not None:
            data['reply_markup'] = json.dumps(reply_markup)
        return self._make_request("sendDocument", data, files)