import logging
from typing import Dict

try:
    from gotify import AsyncGotify
except ImportError as e:
    raise ImportError("缺少必要的依赖包: gotify（python 客户端），请运行: pip install -r requirements.txt") from e

from core.config import Config
from core.bridge.gotify_to_telegram import GotifyToTelegramBridge


class GotifyListener:
    def __init__(self, config: Config, bridge: GotifyToTelegramBridge):
        self.config = config
        self.bridge = bridge
        self.logger = logging.getLogger(__name__)
        self._app_cache: Dict[int, str] = {}

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
                    # 过滤: 白名单/黑名单
                    app_id = message.get('appid')
                    if isinstance(app_id, int):
                        if self.config.gotify_whitelist:
                            if app_id not in self.config.gotify_whitelist:
                                self.logger.info(f"白名单模式: 跳过 appid={app_id} 的消息")
                                continue
                        elif self.config.gotify_blacklist:
                            if app_id in self.config.gotify_blacklist:
                                self.logger.info(f"黑名单过滤: 跳过 appid={app_id} 的消息")
                                continue

                    # 使用已解析的 app_id 获取应用名
                    app_name = await self._get_application_name(async_gotify, app_id)

                    self.logger.info(f"收到来自 {app_name} 的消息: {message.get('title')}")

                    success = self.bridge.send_message(
                        app_name=app_name,
                        title=message.get('title') or "",
                        body=message.get('message') or ""
                    )

                    if not success:
                        self.logger.warning("消息发送失败，但继续监听...")

                except Exception as e:
                    self.logger.error(f"处理消息时出错: {e}")

        except Exception as e:
            self.logger.error(f"连接 Gotify 服务器失败: {e}")
            raise