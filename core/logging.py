import logging
import sys


def setup_logging():
    """初始化日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('gotify2telegram.log', encoding='utf-8')
        ]
    )