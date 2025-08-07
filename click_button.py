# File: click_button.py
import json
import sys
from playwright.sync_api import sync_playwright
import os
import re

def find_latest_analysis_file():
    """Finds the analysis JSON file with the highest number."""
    files = os.listdir('.')
    analysis_files = [f for f in files if f.startswith('live_profile_content_') and f.endswith('.json')]
    if not analysis_files:
        return None
    
    highest_num = 0
    latest_file = None
    for f in analysis_files:
        match = re.search(r'_(\d+)\.json$', f)
        if match:
            num = int(match.group(1))
            if num > highest_num:
                highest_num = num
                latest_file = f
    return latest_file

def main(button_text_query: str):
    """Finds an interactive element from the latest analysis and clicks it."""
    json_filename = find_latest_analysis_file()
    if not json_filename:
        print("❌ Error: No analysis file found. Please run the analysis (option 2) first.")
        return
        
    print(f"📄 Using the latest analysis file: {json_filename}")
    try:
        with open(json_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Could not find the file '{json_filename}'.")
        return

    target_selector = None
    for item in data.get("interactive_elements", {}).get("items", []):
        item_text = item.get("text", "")
        if button_text_query.lower() in item_text.lower():
            target_selector = item.get("selector")
            print(f"✅ Found button/link containing '{button_text_query}' with selector: {target_selector}")
            break

    if not target_selector:
        print(f"❌ No button or link was found containing the text: '{button_text_query}'")
        return

    print("🚀 Connecting to browser to click the element...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[-1]
            print(f"🖱️ Clicking element: '{target_selector}'")
            page.locator(target_selector).click()
            print("🎉 Success! The element has been clicked.")
            browser.close()
    except Exception as e:
        print(f"❌ An error occurred while trying to click the element: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Error: No button text was provided to search for.")
        print("💡 Usage: python click_button.py \"Text on the button\"")
    else:
        main(sys.argv[1])