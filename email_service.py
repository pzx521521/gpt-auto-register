"""
邮箱服务模块
基于 cloudflare_temp_email 项目实现临时邮箱功能
项目地址: https://github.com/dreamhunter2333/cloudflare_temp_email
"""
import json
import random
import re
import string
import time
import email
from email import policy

from config import (
    EMAIL_WORKER_URL,
    EMAIL_DOMAIN,
    EMAIL_PREFIX_LENGTH,
    EMAIL_WAIT_TIMEOUT,
    EMAIL_POLL_INTERVAL,
    HTTP_TIMEOUT
)
from utils import http_session, get_user_agent, extract_verification_code

def create_my_email(index: int):
    fallback_email = f"chatgpt{index}@{EMAIL_DOMAIN}"
    return fallback_email, None
def create_temp_email():
    """
    创建临时邮箱
    调用 cloudflare_temp_email 的 /api/new_address 接口
    
    注意: 服务器会自动给邮箱名称添加 'tmp' 前缀，
    因此应该使用服务器返回的 address 字段作为实际邮箱地址
    
    返回:
        tuple: (邮箱地址, JWT令牌)，失败返回 (None, None)
    """
    print("📧 正在创建临时邮箱...")
    
    # 生成随机邮箱前缀（服务器会自动添加 tmp 前缀）
    prefix = ''.join(random.choices(
        string.ascii_lowercase + string.digits, 
        k=EMAIL_PREFIX_LENGTH
    ))
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": get_user_agent()
    }
    
    try:
        # 调用创建邮箱接口
        response = http_session.post(
            f"{EMAIL_WORKER_URL}/api/new_address",
            headers=headers,
            json={"name": prefix},
            timeout=HTTP_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            jwt_token = result.get('jwt')
            # 使用服务器返回的实际邮箱地址（包含 tmp 前缀）
            actual_email = result.get('address')
            
            if jwt_token and actual_email:
                print(f"✅ 邮箱创建成功: {actual_email}")
                return actual_email, jwt_token
            elif jwt_token:
                # 兼容：如果服务器没有返回 address，则自己拼接
                fallback_email = f"tmp{prefix}@{EMAIL_DOMAIN}"
                print(f"✅ 邮箱创建成功: {fallback_email}")
                return fallback_email, jwt_token
            else:
                print(f"⚠️ 响应中未包含 JWT: {result}")
        else:
            print(f"❌ API 错误: HTTP {response.status_code}")
            print(f"   响应内容: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ 创建邮箱失败: {e}")
    
    return None, None


def fetch_emails(jwt_token: str):
    """
    获取邮件列表
    
    参数:
        jwt_token: 创建邮箱时获得的 JWT 令牌
    
    返回:
        list: 邮件列表，失败返回 None
    """
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "User-Agent": get_user_agent()
    }
    
    try:
        # API 需要 limit 和 offset 参数
        response = http_session.get(
            f"{EMAIL_WORKER_URL}/all",
            headers=headers,
            timeout=HTTP_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # 处理不同的返回格式
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return result.get('result')
        else:
            print(f"  获取邮件错误: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"  获取邮件错误: {e}")
    
    return None


def get_email_detail(jwt_token: str, email_id: str):
    """
    获取邮件详情
    
    参数:
        jwt_token: JWT 令牌
        email_id: 邮件 ID
    
    返回:
        dict: 邮件详情，失败返回 None
    """
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "User-Agent": get_user_agent()
    }
    
    try:
        response = http_session.get(
            f"{EMAIL_WORKER_URL}/api/mails/{email_id}",
            headers=headers,
            timeout=HTTP_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()
            
    except Exception as e:
        print(f"  获取邮件详情错误: {e}")
    
    return None


def parse_raw_email(raw_content: str):
    """
    解析原始邮件内容
    
    参数:
        raw_content: 原始邮件字符串
    
    返回:
        dict: 包含 subject, body, sender 的字典
    """
    result = {'subject': '', 'body': '', 'sender': ''}
    
    if not raw_content:
        return result
    
    try:
        msg = email.message_from_string(raw_content, policy=policy.default)
        
        result['subject'] = msg.get('Subject', '')
        result['sender'] = msg.get('From', '')
        
        # 获取正文
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type in ['text/plain', 'text/html']:
                    payload = part.get_payload(decode=True)
                    if payload:
                        result['body'] = payload.decode('utf-8', errors='ignore')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                result['body'] = payload.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  解析邮件错误: {e}")
    
    return result


def wait_for_verification_email(jwt_token: str, timeout: int = None):
    """
    等待并提取 OpenAI 验证码
    会持续轮询邮箱直到收到验证邮件或超时
    
    参数:
        jwt_token: JWT 令牌
        timeout: 超时时间（秒），默认使用配置文件中的值
    
    返回:
        str: 验证码，未找到返回 None
    """
    if timeout is None:
        timeout = EMAIL_WAIT_TIMEOUT
    
    print(f"⏳ 正在等待验证邮件（最长 {timeout} 秒）...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        emails = fetch_emails(jwt_token)
        
        if emails and len(emails) > 0:
            for email_item in emails:
                # 尝试解析 raw 字段（如果存在）
                raw_content = email_item.get('raw', '')
                if raw_content:
                    parsed = parse_raw_email(raw_content)
                    subject = parsed['subject']
                    sender = parsed['sender'].lower()
                    body = parsed['body']
                else:
                    # 回退到旧的字段
                    sender = str(email_item.get('from') or email_item.get('source', '')).lower()
                    subject = email_item.get('subject', '') or ''
                    body = ''
                
                # 判断是否为 OpenAI 验证邮件
                if 'openai' in sender or 'chatgpt' in subject.lower():
                    print(f"\n📧 收到 OpenAI 验证邮件!")
                    print(f"   主题: {subject}")
                    
                    # 先尝试从主题提取验证码
                    code = extract_verification_code(subject)
                    if code:
                        return code
                    
                    # 如果主题中没有，从正文提取
                    if body:
                        code = extract_verification_code(body)
                        if code:
                            return code
                    
                    # 如果还没有，尝试获取邮件详情
                    email_id = email_item.get('id')
                    if email_id:
                        detail = get_email_detail(jwt_token, email_id)
                        if detail:
                            # 解析详情中的 raw
                            detail_raw = detail.get('raw', '')
                            if detail_raw:
                                parsed_detail = parse_raw_email(detail_raw)
                                code = extract_verification_code(parsed_detail['subject'])
                                if code:
                                    return code
                                code = extract_verification_code(parsed_detail['body'])
                                if code:
                                    return code
                            
                            # 尝试其他字段
                            content = (
                                detail.get('html') or 
                                detail.get('html_content') or 
                                detail.get('text') or 
                                detail.get('content', '')
                            )
                            if content:
                                code = extract_verification_code(content)
                                if code:
                                    return code
        
        # 显示等待进度
        elapsed = int(time.time() - start_time)
        print(f"  等待中... ({elapsed}秒)", end='\r')
        time.sleep(EMAIL_POLL_INTERVAL)
    
    print("\n⏰ 等待验证邮件超时")
    return None


def my_wait_for_verification_email(email_addr: str, timeout: int = None):
    """
    等待并提取 OpenAI 验证码
    会持续轮询邮箱直到收到验证邮件或超时

    参数:
        jwt_token: JWT 令牌
        timeout: 超时时间（秒），默认使用配置文件中的值

    返回:
        str: 验证码，未找到返回 None
    """
    if timeout is None:
        timeout = EMAIL_WAIT_TIMEOUT

    print(f"⏳ 正在等待验证邮件（最长 {timeout} 秒）...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        emails = fetch_emails(email_addr)

        if emails and len(emails) > 0:
            #[{'key': 'app_logs', 'value': None}, {'key': 'pzx521521@qq.com|admin@para.de5.net', 'value': '{"subject":"转发：你的 ChatGPT 代码为 245344","content":"原始邮件\\r\\n         \\r\\n       \\r\\n发件人：OpenAI <otp@tm1.openai.com&gt;\\r\...n\\r\\n\\r\\n谨致问候\\r\\nChatGPT 团队 \\r\\n\\r\\n\\r\\n \\r\\n\\r\\n\\r\\nChatGPT                              \\r\\n\\r\\n帮助中心"}'}]
            for email_item in emails:
                key = email_item.get("key", "")
                value = email_item.get("value")
                if  email_addr in key:
                    try:
                        parsed = json.loads(value)
                    except json.JSONDecodeError:
                        continue

                    subject = parsed.get("subject", "")
                    sender = parsed.get("sender", "").lower()
                    body = parsed.get("content", "")

                    # 从 subject 中读取验证码（连续数字）
                    match = re.search(r"\d{4,8}", subject)
                    if match:
                        code = match.group()
                        return code
        # 显示等待进度
        elapsed = int(time.time() - start_time)
        print(f"  等待中... ({elapsed}秒)", end='\r')
        time.sleep(EMAIL_POLL_INTERVAL)

    print("\n⏰ 等待验证邮件超时")
    return None
