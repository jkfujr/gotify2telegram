import logging
from typing import Optional

from core.config import Config
from core.telegram.sender import TelegramSender
from core.telegram.markup import build_copy_code_markup
from core.utils.text import extract_verification_code


class GotifyToTelegramBridge:
    """格式化消息、提取验证码并选择发送方式"""

    def __init__(self, config: Config, telegram_sender: TelegramSender):
        self.config = config
        self.telegram_sender = telegram_sender
        self.logger = logging.getLogger(__name__)

    def compose_message(self, app_name: str, title: str, body: str) -> tuple[str, str]:
        """返回 (formatted_title, full_message)"""
        formatted_title = self.config.title_format.format(app_name=app_name, title=title)
        full_message = f"{formatted_title}\n\n{body}"
        return formatted_title, full_message

    def send_message(self, app_name: str, title: str, body: str) -> bool:
        formatted_title, full_message = self.compose_message(app_name, title, body)
        code: Optional[str] = extract_verification_code(full_message)
        reply_markup = build_copy_code_markup(code) if code else None

        if len(full_message) >= self.config.max_message_length:
            self.logger.info(f"消息过长 ({len(full_message)} 字符)，以文件形式发送")
            return self.telegram_sender.send_document(title=formatted_title, content=full_message, reply_markup=reply_markup)
        else:
            return self.telegram_sender.send_text_message(full_message, reply_markup=reply_markup)