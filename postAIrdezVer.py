from playwright.sync_api import sync_playwright
import os
import random
from dotenv import load_dotenv

# 讀取 .env 檔案
load_dotenv()
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")

# 檢查環境變數是否正確載入
print(f"載入的帳號: {REDDIT_USERNAME}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # 可見瀏覽器
    page = browser.new_page()

    print("啟動瀏覽器，前往 Reddit...")
    page.goto("https://www.reddit.com/")
    page.wait_for_timeout(random.randint(2000, 4000))

    # 點擊登入按鈕
    login_button = page.locator("a[href*='/login']")
    login_button.wait_for(state="visible", timeout=10000)
    login_button.click()
    print("已點擊登入按鈕")
    page.wait_for_timeout(random.randint(2000, 4000))

    # 填入帳號與密碼
    page.fill("input[name='username']", REDDIT_USERNAME)
    page.wait_for_timeout(random.randint(1000, 3000))
    page.fill("input[name='password']", REDDIT_PASSWORD)
    page.press("input[name='password']", "Enter")
    print("提交登入資訊")
    page.wait_for_timeout(random.randint(3000, 5000))

    print("登入成功！")
    
    # 搜尋 Minecraft Movie
    search_box = page.locator("input[placeholder='Search Reddit']").first
    search_box.wait_for(state="visible", timeout=10000)
    search_box.fill("Minecraft Movie")
    page.press("input[placeholder='Search Reddit']", "Enter")
    print("已提交搜尋")
    page.wait_for_timeout(random.randint(2000, 4000))

    

    input("瀏覽器保持開啟，按 Enter 關閉...")
    browser.close()
    print("瀏覽器已關閉")
