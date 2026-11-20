import os
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

VIDEO_DIR = Path("/tmp/agent_demo_raw")
if VIDEO_DIR.exists():
    shutil.rmtree(VIDEO_DIR)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

FINAL_OUTPUT = Path("/config/Desktop/BuildWithGemini/demo_video.mp4")

def type_like_human(page, selector, text, delay=0.03):
    element = page.locator(selector)
    element.click()
    element.fill("")
    for char in text:
        element.type(char, delay=int(delay * 1000))
        time.sleep(delay)

def wait_for_response(page, timeout_sec=90):
    start = time.time()
    time.sleep(3)
    while time.time() - start < timeout_sec:
        send_btn = page.locator("button.send-message-btn")
        if not send_btn.is_disabled():
            time.sleep(3)
            return True
        time.sleep(1)
    return False

def main():
    print("Launching browser and starting recording...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1280, "height": 720},
            viewport={"width": 1280, "height": 720},
        )
        page = context.new_page()

        print("Navigating to ADK Dev UI...")
        page.goto("http://localhost:8080")
        page.wait_for_timeout(3000)

        # 1. First interaction: Core domain expertise (Travel concierge recommendation)
        prompt_1 = "你好！我想規劃京都 2 天悠閒慢活的秘境漫步行程，請為我推薦幾處清幽有禪意的私房景點！"
        print(f"Typing Prompt 1: {prompt_1}")
        type_like_human(page, 'textarea[placeholder="Type a message..."]', prompt_1, delay=0.03)
        page.wait_for_timeout(1000)
        page.locator("button.send-message-btn").click()
        print("Sent Prompt 1. Waiting for agent response...")
        wait_for_response(page, timeout_sec=60)
        print("Prompt 1 completed.")
        page.wait_for_timeout(4000)

        # 2. Second interaction: Database lookup, tool call & image generation
        prompt_2 = "太棒了！請從資料庫查詢『嵐山竹林祕徑』的詳細資訊，並幫我生成一張清晨晨霧灑在竹林中的明信片風格照片！"
        print(f"Typing Prompt 2: {prompt_2}")
        type_like_human(page, 'textarea[placeholder="Type a message..."]', prompt_2, delay=0.03)
        page.wait_for_timeout(1000)
        page.locator("button.send-message-btn").click()
        print("Sent Prompt 2. Waiting for tool execution, image generation, and response...")
        wait_for_response(page, timeout_sec=90)
        print("Prompt 2 completed.")
        page.wait_for_timeout(4000)

        # Showcase Artifacts tab
        try:
            artifacts_btn = page.locator("button:has-text('Artifacts')")
            if artifacts_btn.is_visible():
                print("Clicking Artifacts tab...")
                artifacts_btn.click()
                page.wait_for_timeout(3000)
        except Exception as e:
            print("Notice on artifacts tab:", e)

        print("Closing context to finalize video recording...")
        page.wait_for_timeout(2000)
        context.close()
        browser.close()

    webm_files = list(VIDEO_DIR.glob("*.webm"))
    if not webm_files:
        raise RuntimeError("No recorded video found in temp dir!")

    raw_video = webm_files[0]
    print(f"Raw video recorded: {raw_video} ({raw_video.stat().st_size} bytes)")

    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_video),
        "-c:v", "libx264",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        str(FINAL_OUTPUT),
    ]
    print("Running ffmpeg conversion...")
    subprocess.run(cmd, check=True)
    print(f"Final demo video created at {FINAL_OUTPUT} ({FINAL_OUTPUT.stat().st_size} bytes)!")

if __name__ == "__main__":
    main()
