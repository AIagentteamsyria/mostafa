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

def main(text_to_fill: str):
    """Finds the first input field from the latest analysis and fills it with text."""
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
        if item.get("tag") in ["input", "textarea"]:
            target_selector = item.get("selector")
            print(f"✅ Found an input field with selector: {target_selector}")
            break

    if not target_selector:
        print("❌ No suitable input field (input/textarea) was found in the analysis file.")
        return

    print("🚀 Connecting to browser to fill the field...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            page = browser.contexts[0].pages[-1]
            print(f"📝 Filling field '{target_selector}' with text: '{text_to_fill}'")
            page.locator(target_selector).fill(text_to_fill)
            print("🎉 Success! The field has been filled.")
            browser.close()
    except Exception as e:
        print(f"❌ An error occurred while trying to fill the field: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Error: No text was provided to fill.")
        print("💡 Usage: python fill_input.py \"Text you want to type\"")
    else:
        main(sys.argv[1])