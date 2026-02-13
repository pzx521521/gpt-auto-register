from time import sleep

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from browser import SafeChrome
import undetected_chromedriver as uc

import os, certifi

from finger_manager import FingerprintManager


def get_visitor_id(driver, timeout=10):
    wait = WebDriverWait(driver, timeout)
    pre = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "pre.giant"))
    )
    return pre.text.strip()

def main():
    os.environ['SSL_CERT_FILE'] = certifi.where()
    options = uc.ChromeOptions()
    driver = SafeChrome(options=options, use_subprocess=True, headless=False)

    # --- 使用场景演示 ---
    url ="https://fingerprintjs.github.io/fingerprintjs/"
    # ... 初始化代码 ...
    manager = FingerprintManager(driver)

    # 第一次注册
    manager.update_identity()
    driver.get(url)
    print(f"身份 1 ID: {get_visitor_id(driver)}")


    sleep(2)

    # 第二次注册
    manager.update_identity()
    driver.get(url)
    print(f"身份 2 ID: {get_visitor_id(driver)}")
    input("")

if __name__ == '__main__':
    main()