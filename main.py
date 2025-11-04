import sys
import asyncio
import logging

from core.logging import setup_logging
from core.config import Config
from core.telegram.sender import TelegramSender
from core.bridge.gotify_to_telegram import GotifyToTelegramBridge
from core.gotify.listener import GotifyListener


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

        bridge = GotifyToTelegramBridge(config, telegram_sender)
        listener = GotifyListener(config, bridge)
        await listener.start_listening()

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
