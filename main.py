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
        telegram_sender = TelegramSender(config)
        if telegram_sender.is_connected():
            logger.info("Telegram 连接测试通过")
        else:
            logger.warning("Telegram 暂不可用：消息将进入内存队列，等待连通后自动补发")

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
