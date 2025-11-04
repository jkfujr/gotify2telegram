"""
测试脚本：读取配置并向 Telegram 发送一条测试消息
"""

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging

from core.logging import setup_logging
from core.config import Config
from core.telegram.sender import TelegramSender
from core.telegram.markup import build_copy_code_markup
from core.utils.text import extract_verification_code


def main():
    default_config_path = PROJECT_ROOT / "config.yaml"
    test_title = "【测试标题】验证码复制按钮"
    test_message = f"{test_title}\n账号中心，验证码：048460"

    setup_logging()
    logger = logging.getLogger("test_send")

    try:
        logger.info("加载配置中...")
        cfg_path = Path(default_config_path)
        if not cfg_path.exists():
            example = PROJECT_ROOT / "config.example.yaml"
            if example.exists():
                logger.warning("未找到配置文件 %s，改用示例配置 %s（可能需要填写真实值）", cfg_path, example)
                cfg_path = example
            else:
                raise FileNotFoundError(f"配置文件不存在: {cfg_path}")

        config = Config(config_path=str(cfg_path))
        logger.info("配置加载成功")

        logger.info("初始化 Telegram 连接并测试...")
        sender = TelegramSender(config)

        msg = test_message
        logger.info(f"准备发送: {msg}")

        reply_markup = None
        code = extract_verification_code(msg)
        if code:
            logger.info(f"识别到验证码: {code}，将附加复制按钮")
            reply_markup = build_copy_code_markup(code)
        else:
            logger.info("未识别到验证码，发送普通消息")

        ok = sender.send_text_message(msg, reply_markup=reply_markup)

        if ok:
            logger.info("✅ 测试消息已发送成功")
            sys.exit(0)
        else:
            logger.error("❌ 测试消息发送失败")
            sys.exit(2)

    except Exception as e:
        logger.error(f"运行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()