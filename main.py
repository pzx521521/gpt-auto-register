"""
ChatGPT 账号自动注册脚本
主程序入口

使用方法:
    1. 修改 config.py 中的配置
    2. 运行: python main.py

依赖安装:
    pip install undetected-chromedriver selenium requests

功能:
    - 自动创建临时邮箱（基于 cloudflare_temp_email）
    - 自动完成 ChatGPT 注册流程
    - 自动提取验证码
    - 批量注册支持
"""

import time
import random

from config import (
    TOTAL_ACCOUNTS,
    BATCH_INTERVAL_MIN,
    BATCH_INTERVAL_MAX, save_email_prefix_length, EMAIL_PREFIX_LENGTH
)
from finger_manager import FingerprintManager
from utils import generate_random_password, save_to_txt, update_account_status
from email_service import wait_for_verification_email, create_my_email, \
    my_wait_for_verification_email
from browser import (
    create_driver,
    fill_signup_form,
    enter_verification_code,
    fill_profile_info,
    subscribe_plus_trial,
    cancel_subscription
)


def register_one_account(index: int, driver=None, monitor_callback=None):
    """
    注册单个账号
    :param monitor_callback: 回调函数 func(driver, step_name)，用于截图和中断检查
    
    返回:
        tuple: (邮箱, 密码, 是否成功)
    """
    email = None
    password = None
    success = False
    
    # 辅助函数：执行回调
    def _report(step_name):
        if monitor_callback and driver:
            monitor_callback(driver, step_name)

    try:
        # 1. 创建临时邮箱
        print("📧 正在创建临时邮箱...")
        email, jwt_token = create_my_email(index)
        if not email:
            print("❌ 创建邮箱失败，终止注册")
            return None, None, False
        
        # 2. 生成随机密码
        # password = generate_random_password()
        password = "52113147758pzx"
        # 3. 初始化浏览器
        if driver == None:    # 清除当前域名下的所有 cookie
            driver = create_driver(headless=False)
        _report("init_browser")
        
        # 4. 打开注册页面
        url = "https://chat.openai.com/chat"
        print(f"🌐 正在打开 {url}...")
        driver.get(url)
        time.sleep(3)
        _report("open_page")
        
        # 5. 填写注册表单（邮箱和密码）
        if not fill_signup_form(driver, email, password):
            print("❌ 填写注册表单失败")
            return email, password, False
        _report("fill_form")
        
        # 6. 等待验证邮件
        time.sleep(2)
        verification_code = my_wait_for_verification_email(email)
        
        # 如果没有自动获取到验证码，提示手动输入
        if not verification_code:
            print("⚠️ 未自动获取验证码，尝试请求用户输入...")
            # 可以在这里扩展手动输入回调，暂略
            # verification_code = input("⌨️ 请手动输入验证码: ").strip()
        
        if not verification_code:
            print("❌ 未获取到验证码，终止注册")
            return email, password, False
        
        # 7. 输入验证码
        if not enter_verification_code(driver, verification_code):
            print("❌ 输入验证码失败")
            return email, password, False
        _report("enter_code")
        
        # 8. 填写个人资料
        if not fill_profile_info(driver):
            print("❌ 填写个人资料失败")
            return email, password, False
        _report("fill_profile")
        
        # 9. 保存账号信息 (注册成功)
        print("🎉 保存账号信息")
        save_to_txt(email, password, "已注册")
        print(f"🎉 更新配置文件:{index}")
        save_email_prefix_length(index)
        # 10. 完成注册
        print("\n" + "=" * 50)
        print("🎉 注册成功！")
        print(f"   邮箱: {email}")
        print(f"   密码: {password}")
        print("=" * 50)
        
        success = True
        print("⏳ 等待页面稳定...")
        time.sleep(random.uniform(2, 5))
        _report("registered")
        
    except InterruptedError:
        print("🛑 任务已被用户强制中断")
        if email: update_account_status(email, "用户中断")
        return email, password, False
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        # 即使出错也保存已有的账号信息（便于排查）
        if email and password:
            update_account_status(email, f"错误: {str(e)[:50]}")
    
    # finally:
        # if driver:
        #     print("🔒 正在关闭浏览器...")
        #     driver.quit()
    
    return email, password, success
    



def run_batch():
    """
    批量注册账号
    """
    print("\n" + "=" * 60)
    print(f"🚀 开始批量注册，目标数量: {TOTAL_ACCOUNTS}")
    print("=" * 60 + "\n")
    success_count = 0
    fail_count = 0
    registered_accounts = []
    driver = create_driver(headless=False)
    manager = FingerprintManager(driver)

    for i in range(TOTAL_ACCOUNTS):
        print("\n" + "#" * 60)
        print(f"📝 正在注册第 {i + 1}/{TOTAL_ACCOUNTS} 个账号")
        print("#" * 60 + "\n")
        print("🧹清理cookie,更换指纹 ...")
        manager.update_identity()
        email, password, success = register_one_account(i+EMAIL_PREFIX_LENGTH, driver)
        
        if success:
            success_count += 1
            registered_accounts.append((email, password))
        else:
            fail_count += 1
            break
        
        # 显示进度
        print("\n" + "-" * 40)
        print(f"📊 当前进度: {i + 1}/{TOTAL_ACCOUNTS}")
        print(f"   ✅ 成功: {success_count}")
        print(f"   ❌ 失败: {fail_count}")
        print("-" * 40)
        
        # 如果还有下一个，等待随机时间
        if i < TOTAL_ACCOUNTS - 1:
            wait_time = random.randint(BATCH_INTERVAL_MIN, BATCH_INTERVAL_MAX)
            print(f"\n⏳ 等待 {wait_time} 秒后继续下一个注册...")
            time.sleep(wait_time)
    
    # 最终统计
    print("\n" + "=" * 60)
    print("🏁 批量注册完成")
    print("=" * 60)
    print(f"   总计: {TOTAL_ACCOUNTS}")
    print(f"   ✅ 成功: {success_count}")
    print(f"   ❌ 失败: {fail_count}")
    
    if registered_accounts:
        print("\n📋 成功注册的账号:")
        for email, password in registered_accounts:
            print(f"   - {email}")
    
    print("=" * 60)


if __name__ == "__main__":
    import os, certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    run_batch()
