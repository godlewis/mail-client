import os
import requests
from dotenv import load_dotenv
import json

# 加载环境变量
load_dotenv()

LLM_API_BASE = os.getenv('LLM_API_BASE')
LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_MODEL = os.getenv('LLM_MODEL')


def analyze_email_content(content: str):
    """
    调用LLM接口，分析邮件内容，提取"实际应付""账单合计""账单周期"
    """
    prompt = f"""
请从以下邮件内容中，提取出：
1. 实际应付
2. 账单合计
3. 账单周期

要求：
- 只输出提取到的字段及其内容，格式如下：
实际应付: xxx\n账单合计: xxx\n账单周期: xxx
- 如果没有某项内容，请输出"无"

邮件内容：
{content}
"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    response = requests.post(
        f"{LLM_API_BASE}/chat/completions",
        headers=headers,
        data=json.dumps(data),
        timeout=60
    )
    response.raise_for_status()
    result = response.json()
    return result['choices'][0]['message']['content'].strip()


def test():
    # 测试用例1
    content1 = """
尊敬的客户：
您的账单周期为2024年5月1日至2024年5月31日。
本期账单合计：¥1234.56。
实际应付：¥1200.00。
感谢您的使用！
"""
    print("测试用例1：")
    print(analyze_email_content(content1))
    print("\n---------------------\n")

    # 测试用例2
    content2 = """
您好，
本月账单总额为888元，账单周期2024/04/01-2024/04/30。
请于5月10日前支付。
"""
    print("测试用例2：")
    print(analyze_email_content(content2))
    print("\n---------------------\n")

    # 测试用例3
    content3 = """
Hi,
This is a notification. No payment required.
"""
    print("测试用例3：")
    print(analyze_email_content(content3))
    print("\n---------------------\n")

if __name__ == "__main__":
    test() 