from playwright.sync_api import sync_playwright
import os

COOKIE_PATH = "fb_session.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    # 檢查是否已有 cookie
    if os.path.exists(COOKIE_PATH):
        context = browser.new_context(storage_state=COOKIE_PATH)
        print("✅ 已載入登入 cookie，直接登入 Facebook")
    else:
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com")
        input("🔐 請手動登入 Facebook 並完成驗證後，按 Enter 繼續...")
        context.storage_state(path=COOKIE_PATH)
        print("✅ 登入 cookie 已儲存，下次會自動登入")

    # 開啟新頁面進入個人主頁
    page = context.new_page()
    page.goto("https://www.facebook.com/me")
    page.wait_for_timeout(5000)
    print("✅ 已登入 Facebook 並進入個人頁面")
    page.screenshot(path="debug_after_profile.png")

    # 嘗試尋找貼文啟動按鈕（繁體、英文、其他）
    selectors = [
        "div[aria-label='建立貼文']",
        "div[aria-label='Create post']",
        "div[role='button']:has(span:has-text('在想些什麼'))",
        "div[role='button']:has(span:has-text(\"What's on your mind\"))"
    ]

    post_trigger = None
    for sel in selectors:
        locator = page.locator(sel).first
        try:
            if locator.is_visible(timeout=3000):
                post_trigger = locator
                break
        except:
            continue

    if post_trigger:
        post_trigger.click()
        page.wait_for_timeout(2000)
        print("📝 成功開啟貼文對話框")
    else:
        page.screenshot(path="debug_post_button_failed.png")
        raise Exception("❌ 無法找到貼文按鈕，請確認 Facebook 語言設定與版面")

    # 等待貼文框出現
    post_box = page.locator("div[role='dialog'] div[contenteditable='true']").first
    post_box.wait_for(state="visible", timeout=5000)
    print("發文框已載入")

    # 模擬真人輸入貼文
    post_text = "這是一則由 Playwright 自動發佈的 Facebook 貼文！"
    page.keyboard.type(post_text, delay=100)
    print("已模擬真人輸入")

    # 觸發 Facebook 對輸入框的感知
    page.evaluate("""
        let postBox = document.querySelector('div[contenteditable="true"]');
        postBox.focus();
        postBox.dispatchEvent(new Event('focus', { bubbles: true }));
        postBox.dispatchEvent(new Event('input', { bubbles: true }));
        postBox.dispatchEvent(new Event('change', { bubbles: true }));
    """)
    print("Facebook 偵測到輸入")

    # 等待發佈按鈕可點擊
    print("⌛ 等待 Facebook 啟用發佈按鈕...")
    page.wait_for_selector("div[aria-label='發佈']:not([aria-disabled='true'])", timeout=10000)
    print("✅ 發佈按鈕已啟用，準備發文")

    # 點擊發佈
    publish_button = page.locator("div[aria-label='發佈']")
    publish_button.click()
    print("🚀 貼文發佈中...")

    page.wait_for_timeout(5000)
    print("🎉 貼文已成功發佈！")

    # 保留瀏覽器，方便 debug
    input("🔎 瀏覽器保持開啟，按 Enter 關閉...")
    browser.close()
