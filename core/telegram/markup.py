from typing import Dict, Any


def build_copy_code_markup(code: str) -> Dict[str, Any]:
    """验证码按钮"""
    return {
        'inline_keyboard': [[{
            'text': code,
            'copy_text': {'text': code}
        }]]
    }