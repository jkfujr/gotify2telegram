import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
except ImportError as e:
    raise ImportError("缺少必要的依赖包: PyYAML，请运行: pip install -r requirements.txt") from e


class Config:
    """配置管理"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
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
                import socks  # type: ignore
            except ImportError:
                raise ImportError("使用 SOCKS5 代理需要安装 requests[socks] 依赖: pip install requests[socks]")

        return {
            'http': proxy_url,
            'https': proxy_url
        }