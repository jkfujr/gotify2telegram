import logging
import time
import json
import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Deque, Literal
from collections import deque

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import Config


TelegramMethod = Literal["sendMessage", "sendDocument"]


class _RequestOutcome(str, Enum):
    OK = "ok"
    API_ERROR = "api_error"
    NETWORK_ERROR = "network_error"


@dataclass(frozen=True)
class _PendingTelegramRequest:
    created_at: datetime
    method: TelegramMethod
    data: Dict[str, Any]
    files: Optional[Dict]
    received_at: datetime


class TelegramSender:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session = self._create_session()
        self._pending: Deque[_PendingTelegramRequest] = deque()
        self._pending_lock = threading.Lock()
        self._connected = False
        self._probe_interval_seconds = 300
        self._test_connection()
        self._start_probe_thread()

    def _start_probe_thread(self) -> None:
        thread = threading.Thread(target=self._probe_loop, daemon=True, name="tgapi-probe")
        thread.start()

    def _probe_loop(self) -> None:
        while True:
            time.sleep(self._probe_interval_seconds)

            with self._pending_lock:
                has_pending = len(self._pending) > 0
                connected = self._connected

            if not has_pending and connected:
                continue

            if not self._test_connection():
                continue

            self._flush_pending()

    def _test_connection(self) -> bool:
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
                self._connected = True
                return True
            else:
                raise Exception(f"Telegram API 返回错误: {result}")

        except requests.exceptions.SSLError as e:
            self.logger.error(f"SSL 连接失败: {e}")
            self.logger.error("建议: 1) 检查网络连接 2) 配置代理服务器")
            self._connected = False
            return False

        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"网络连接失败: {e}")
            if self.config.proxy_url:
                self.logger.error(f"当前使用代理: {self.config.proxy_url}")
                self.logger.error("请检查代理服务器是否正常工作")
            else:
                self.logger.error("建议配置代理服务器")
            self._connected = False
            return False

        except requests.exceptions.Timeout as e:
            self.logger.error(f"连接超时: {e}")
            self._connected = False
            return False

        except Exception as e:
            self.logger.error(f"Telegram API 连接测试失败: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected

    def _create_session(self) -> requests.Session:
        session = requests.Session()

        retry_strategy = Retry(
            total=0,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _make_request(self, method: TelegramMethod, data: Dict[str, Any], files: Optional[Dict] = None) -> bool:
        return self._make_request_outcome(method, data, files) == _RequestOutcome.OK

    def _make_request_outcome(
        self, method: TelegramMethod, data: Dict[str, Any], files: Optional[Dict] = None
    ) -> _RequestOutcome:
        url = f'https://api.telegram.org/bot{self.config.telegram_bot_token}/{method}'

        proxies = self.config.get_proxy_dict()
        if proxies:
            self.logger.debug(f"使用代理: {self.config.proxy_url}")

        max_attempts = 3

        for attempt in range(max_attempts):
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
                    self._connected = True
                    return _RequestOutcome.OK
                else:
                    self.logger.error(f"Telegram API 错误: {result}")
                    self._connected = True
                    return _RequestOutcome.API_ERROR

            except requests.exceptions.SSLError as e:
                self._connected = False
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"SSL 连接失败 (尝试 {attempt + 1}/{max_attempts})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"SSL 连接最终失败: {e}")
                    self.logger.error("建议: 1) 检查网络连接 2) 配置代理服务器")
                    return _RequestOutcome.NETWORK_ERROR

            except requests.exceptions.ConnectionError as e:
                self._connected = False
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"网络连接失败 (尝试 {attempt + 1}/{max_attempts})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"网络连接最终失败: {e}")
                    return _RequestOutcome.NETWORK_ERROR

            except requests.exceptions.Timeout as e:
                self._connected = False
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"请求超时 (尝试 {attempt + 1}/{max_attempts})，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"请求最终超时: {e}")
                    return _RequestOutcome.NETWORK_ERROR

            except requests.RequestException as e:
                self._connected = False
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"网络请求失败 (尝试 {attempt + 1}/{max_attempts}): {e}")
                    self.logger.warning(f"{wait_time}秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"网络请求最终失败: {e}")
                    return _RequestOutcome.NETWORK_ERROR

            except Exception as e:
                self.logger.error(f"发送消息时出现未知错误: {e}")
                self._connected = False
                return _RequestOutcome.NETWORK_ERROR

        return _RequestOutcome.NETWORK_ERROR

    def _enqueue_failed_request(
        self,
        method: TelegramMethod,
        data: Dict[str, Any],
        files: Optional[Dict],
        received_at: datetime,
    ) -> None:
        pending = _PendingTelegramRequest(
            created_at=datetime.now(),
            method=method,
            data=data,
            files=files,
            received_at=received_at,
        )
        with self._pending_lock:
            self._pending.append(pending)
            self.logger.warning(f"Telegram 发送失败，已放入内存队列等待补发 (队列长度: {len(self._pending)})")

    def _flush_pending(self) -> None:
        to_send: list[_PendingTelegramRequest] = []
        with self._pending_lock:
            while self._pending:
                to_send.append(self._pending.popleft())

        if not to_send:
            return

        to_send.sort(key=lambda x: x.received_at)
        self.logger.info(f"Telegram 连接恢复，开始补发 {len(to_send)} 条历史消息...")

        for i, pending in enumerate(to_send):
            method, adjusted_data, adjusted_files = self._augment_with_received_time(pending)
            outcome = self._make_request_outcome(method, adjusted_data, adjusted_files)
            if outcome == _RequestOutcome.OK:
                continue
            if outcome == _RequestOutcome.NETWORK_ERROR:
                with self._pending_lock:
                    for rest in reversed(to_send[i:]):
                        self._pending.appendleft(rest)
                self.logger.warning("补发过程中再次失败，等待下次 5 分钟探测后继续")
                return
            if outcome == _RequestOutcome.API_ERROR:
                self.logger.error("补发消息被 Telegram API 拒绝，已丢弃该条消息以避免阻塞队列")
                continue

        self.logger.info("历史消息补发完成")

    def _augment_with_received_time(
        self, pending: _PendingTelegramRequest
    ) -> tuple[TelegramMethod, Dict[str, Any], Optional[Dict]]:
        received_at_str = pending.received_at.strftime("%Y-%m-%d %H:%M:%S")

        if pending.method == "sendMessage":
            data = dict(pending.data)
            original_text = str(data.get("text") or "")
            data["text"] = f"{original_text}\n\n接收时间: {received_at_str}"
            if len(data["text"]) >= self.config.max_message_length:
                title = str(original_text).split("\n", 1)[0].strip() or "消息"
                content = data["text"]
                files = {'document': ('message.txt', content.encode('utf-8'))}
                new_data = {'chat_id': self.config.telegram_chat_id, 'caption': f"{title} [消息过长，以文件形式发送]"}
                if "reply_markup" in data:
                    new_data["reply_markup"] = data["reply_markup"]
                return "sendDocument", new_data, files
            return "sendMessage", data, None

        if pending.method == "sendDocument":
            data = dict(pending.data)
            files = pending.files or {}
            doc = files.get("document")
            if doc and isinstance(doc, tuple) and len(doc) >= 2:
                filename = doc[0]
                content_bytes = doc[1]
                try:
                    content_str = content_bytes.decode("utf-8")
                except Exception:
                    content_str = str(content_bytes)
                new_content = f"{content_str}\n\n接收时间: {received_at_str}"
                new_files = dict(files)
                new_files["document"] = (filename, new_content.encode("utf-8"))
                return "sendDocument", data, new_files
            return "sendDocument", data, files

        return pending.method, pending.data, pending.files

    def send_text_message(
        self,
        message: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        received_at: Optional[datetime] = None,
    ) -> bool:
        """发送文本消息"""
        data = {
            'chat_id': self.config.telegram_chat_id,
            'text': message
        }
        if reply_markup is not None:
            data['reply_markup'] = json.dumps(reply_markup)
        ok = self._make_request("sendMessage", data)
        if not ok and not self._connected:
            self._enqueue_failed_request("sendMessage", data, None, received_at or datetime.now())
        return ok

    def send_document(
        self,
        title: str,
        content: str,
        reply_markup: Optional[Dict[str, Any]] = None,
        received_at: Optional[datetime] = None,
    ) -> bool:
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
        ok = self._make_request("sendDocument", data, files)
        if not ok and not self._connected:
            self._enqueue_failed_request("sendDocument", data, files, received_at or datetime.now())
        return ok
