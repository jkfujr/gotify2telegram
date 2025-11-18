import re
from typing import Optional


def extract_verification_code(text: str) -> Optional[str]:
    """从文本中提取验证码/OTP
    覆盖常见中文与英文样式，优先匹配更明确的上下文以降低误判。

    示例（来自 .docs/验证码.md）: 
    - "验证码为:9138"、"验证码287686"、"验证码: 235658"、"手机号验证码: 114614"
    - "您的验证码为362133"、"验证码是325969"、"验证码是860977"
    - "PayPal: 232148 是您的验证码"
    - "9580（动态验证码）"
    - "验证密码】642167"
    - 英文: "code 123456"、"otp 654321"、"verification code: 112233"
    """

    candidate_patterns = [
        # 中文: 各种“验证码为/是/: /:”形式，允许前缀“短信/手机/动态”
        r"(?:短信|手机|动态)?验证码(?:为|是|: |:)?\D*([0-9]{4,8})",
        # 中文: 您的验证码为/是...
        r"您的?(?:手机)?验证码(?:为|是|: |:)?\D*([0-9]{4,8})",
        # 中文: 数字在前，随后出现“是您的验证码”（如 PayPal: 232148 是您的验证码）
        r"([0-9]{4,8})\D*(?:是|为)?\D*您的?验证码",
        # 中文: 数字在前，随后紧跟“动态验证码”（如 9580（动态验证码））
        r"([0-9]{4,8})\D*动态?验证码",
        # 中文: 数字在前，随后出现“(登录|短信|手机|动态|一次性|本次)?验证码”（如 775831（登录验证码））
        r"([0-9]{4,8})\D{0,20}(?:登录|短信|手机|动态|一次性|本次)?验证码",
        # 中文: 术语“验证密码”
        r"验证密码\D*([0-9]{4,8})",
        # 英文: code/otp/verification (包括 'verification code')
        r"(?i)\b(?:verification\s*code|code|otp|verification)\b\D*([0-9]{4,8})",
        # 英文: 数字在前 -> "9488 is your verification code ..."
        r"(?i)([0-9]{4,8})\D{0,40}(?:is\s*your\s*(?:verification\s*code|otp|code))",
    ]

    for pattern in candidate_patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        code = m.group(1)
        if code and 4 <= len(code) <= 8:
            return code

    return None