"""
从 .docs/验证码.md 中逐行读取短信示例，测试验证码提取是否正确。

用法: 直接运行
  - python tools/test_extract_from_docs.py

输出: 每行对应的提取结果，以及成功/失败统计。
"""

import sys
from pathlib import Path

# 允许作为脚本直接运行: 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.utils.text import extract_verification_code


def main():
    docs_path = PROJECT_ROOT / ".docs" / "验证码.md"
    if not docs_path.exists():
        print(f"❌ 示例文件不存在: {docs_path}")
        sys.exit(1)

    lines = docs_path.read_text(encoding="utf-8").splitlines()
    total, ok_count, fail_count = 0, 0, 0

    print(f"读取示例文件: {docs_path}")
    print("开始测试提取结果:\n")

    for idx, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        total += 1
        code = extract_verification_code(text)
        if code:
            ok_count += 1
            print(f"[{idx:02d}] ✅ 提取成功: {code}\n    文本: {text}")
        else:
            fail_count += 1
            print(f"[{idx:02d}] ❌ 未提取到验证码\n    文本: {text}")

    print("\n测试完成")
    print(f"总计: {total} 行, 成功: {ok_count}, 失败: {fail_count}")
    if fail_count == 0:
        print("结果: ✅ 所有示例均成功提取验证码")
        sys.exit(0)
    else:
        print("结果: 部分示例未能提取，请根据输出审查并调整规则")
        sys.exit(2)


if __name__ == "__main__":
    main()