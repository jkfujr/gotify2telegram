import logging
import re
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
        self._warn_if_example_values()

    def _load_config(self) -> Dict[str, Any]:
        config_path = Path(self.config_path)
        example_path = Path(__file__).resolve().parents[1] / "config.example.yaml"

        if config_path.exists() and config_path.is_dir():
            raise IsADirectoryError(f"配置路径是目录，无法读取: {self.config_path}")

        if not config_path.exists():
            if example_path.exists():
                self.logger.warning("未找到配置文件 %s，已复制示例配置 %s", config_path, example_path)
                config_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        if config_path.stat().st_size == 0:
            if example_path.exists():
                self.logger.warning("检测到空配置文件 %s，已填充示例配置 %s", config_path, example_path)
                config_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                raise FileNotFoundError("配置文件为空，且未找到示例配置")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data is None:
                    return {}
                if not isinstance(data, dict):
                    raise ValueError("配置文件格式错误: 顶层必须是映射结构")
                return data
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

    def _warn_if_example_values(self) -> None:
        placeholders = {
            'telegram.bot_token': 'bot_token',
            'telegram.chat_id': 'chat_id',
            'gotify.server_url': 'server_url',
            'gotify.client_token': 'client_token',
        }
        example_like = [
            key for key, placeholder in placeholders.items()
            if self._get_nested_value(key) == placeholder
        ]
        if example_like:
            self.logger.warning(
                "检测到示例配置值未修改: %s，请更新为真实值",
                ", ".join(example_like)
            )

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

    # ========= Gotify 过滤配置 =========
    def _to_int_list(self, value: Any) -> list[int]:
        result: list[int] = []
        if isinstance(value, list):
            for v in value:
                try:
                    result.append(int(v))
                except Exception:
                    self.logger.warning(f"Gotify 过滤ID不是有效数字，已忽略: {v}")
        return result

    @property
    def gotify_whitelist(self) -> list[int]:
        # 支持两种配置路径: gotify.filter.whitelist 或 gotify.whitelist
        raw = self._get_nested_value('gotify.filter.whitelist')
        if raw is None:
            raw = self._get_nested_value('gotify.whitelist')
        return self._to_int_list(raw)

    @property
    def gotify_blacklist(self) -> list[int]:
        # 支持两种配置路径: gotify.filter.blacklist 或 gotify.blacklist
        raw = self._get_nested_value('gotify.filter.blacklist')
        if raw is None:
            raw = self._get_nested_value('gotify.blacklist')
        return self._to_int_list(raw)

    def is_app_allowed(self, app_id: int) -> bool:
        """根据白名单/黑名单判断是否允许转发
        规则: 
        - 若白名单非空，仅允许在白名单中的 app_id
        - 否则，若黑名单非空，拒绝黑名单中的 app_id
        - 若都为空，允许全部
        """
        whitelist = self.gotify_whitelist
        blacklist = self.gotify_blacklist

        if whitelist:
            return app_id in whitelist
        if blacklist:
            return app_id not in blacklist
        return True

    @property
    def max_message_length(self) -> int:
        return self._get_nested_value('message.max_length') or 4000

    @property
    def title_format(self) -> str:
        return self._get_nested_value('message.title_format') or "[Gotify→{app_name}] - {title}"

    # ========= 消息文本过滤配置 =========
    def _compile_regex_list(self, raw_list: Any) -> list[re.Pattern]:
        patterns = []
        if isinstance(raw_list, list):
            for pattern_str in raw_list:
                try:
                    patterns.append(re.compile(str(pattern_str), re.IGNORECASE))
                except re.error as e:
                    self.logger.warning(f"无效的正则表达式 '{pattern_str}': {e}")
        return patterns

    @property
    def message_whitelist_patterns(self) -> list[re.Pattern]:
        raw = self._get_nested_value('message.filter.whitelist')
        return self._compile_regex_list(raw)

    @property
    def message_blacklist_patterns(self) -> list[re.Pattern]:
        raw = self._get_nested_value('message.filter.blacklist')
        return self._compile_regex_list(raw)

    def is_message_allowed(self, text: str) -> bool:
        """根据消息文本白名单/黑名单判断是否允许转发
        规则:
        1. 若匹配白名单任一规则，则允许（优先级最高）
        2. 若匹配黑名单任一规则，则拒绝
        3. 否则允许
        """
        if not text:
            return True

        # 1. 检查白名单 (WhiteList)
        for pattern in self.message_whitelist_patterns:
            if pattern.search(text):
                return True

        # 2. 检查黑名单 (BlackList)
        for pattern in self.message_blacklist_patterns:
            if pattern.search(text):
                return False

        # 3. 默认允许
        return True

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
