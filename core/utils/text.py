import re
from typing import Optional


def extract_verification_code(text: str) -> Optional[str]:
    """提取验证码"""
    patterns = [
        r"验证码\D*([0-9]{4,8})"
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            code = m.group(1)
            if 4 <= len(code) <= 8:
                return code
    return None