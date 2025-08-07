# File: launch_browser.py
import subprocess
import os
import sys

USER_DATA_DIR = os.path.join(os.getcwd(), "chrome_session_data")

def find_chrome_executable():
    """Attempts to find the Google Chrome executable automatically."""
    if sys.platform == "win32":
        for path in [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe")
        ]:
            if os.path.exists(path):
                return path
    elif sys.platform == "darwin":
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(path):
            return path
    return None

def main():
    """Launches Chrome with a custom user profile and an open debugging port."""
    chrome_path = find_chrome_executable()
    if not chrome_path:
        print("❌ Google Chrome executable not found. Please ensure it's installed.")
        return

    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    command = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={USER_DATA_DIR}"
    ]

    print("🚀 Launching a dedicated Chrome browser for the session...")
    subprocess.Popen(command)
    print("\n--- ✅ Browser is now ready. ---")
    print("--- Please log into your required accounts in the new browser window. ---")
    print("--- Then, use a new terminal to run 'main.py' to control the actions. ---")

if __name__ == "__main__":
    main()