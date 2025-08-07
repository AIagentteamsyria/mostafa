# File: analyze_page.py
import pandas as pd
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from bs4 import BeautifulSoup, element as bs4_element
import json
import time
import sys
import os
import re

def generate_control_selector(element: bs4_element.Tag) -> str:
    """Creates a simple CSS selector for an element, prioritizing ID then class."""
    if element.has_attr('id'): return f"#{element['id']}"
    if element.has_attr('class'):
        classes = [c for c in element['class'] if c]
        if classes: return f"{element.name}.{'.'.join(classes)}"
    return element.name

def write_content_json_file(filename: str, media: list, interactives: list, texts: list):
    """Writes the categorized content into a formatted JSON file."""
    page_content_structure = {
        "media_content": {"count": len(media), "items": media},
        "interactive_elements": {"count": len(interactives), "items": interactives},
        "main_texts": {"count": len(texts), "items": texts}
    }
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(page_content_structure, f, ensure_ascii=False, indent=4)

def get_next_analysis_filenames():
    """Finds the next available number for analysis filenames."""
    i = 1
    while True:
        csv_filename = f"live_profile_analysis_{i}.csv"
        json_filename = f"live_profile_content_{i}.json"
        if not os.path.exists(csv_filename) and not os.path.exists(json_filename):
            return csv_filename, json_filename
        i += 1

def analyze_live_chrome_page(target_url: str):
    """Connects to a running Chrome instance, navigates to a URL, and analyzes the page."""
    
    csv_filename, json_filename = get_next_analysis_filenames()
    
    print(f"🚀 Attempting to connect to Chrome browser on port 9222...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.new_page()
            page.goto(target_url, wait_until='networkidle', timeout=90000)
            print("✅ Page loaded successfully.")

            print("\n" + "="*50)
            print("--- 🔴 Manual Action Required (Optional) ---")
            print("1. The page is now in front of you in the browser.")
            print("2. You can perform any final preparations (e.g., scroll down, close a pop-up).")
            input("\n⬅️  When you are ready, press Enter here to start the analysis...")

            print(f"\n✅ Acknowledged! Starting analysis of page: {page.title()}")
            time.sleep(2)

            page_content = page.content()
            soup = BeautifulSoup(page_content, 'lxml')
            all_tags = soup.find_all(True)
            print(f"🔬 Found {len(all_tags)} elements, now processing and classifying...")

            all_elements_data, media_elements, interactive_elements, text_elements = [], [], [], []
            MEDIA_TAGS = {'img', 'video', 'audio', 'source', 'picture'}
            INTERACTIVE_TAGS = {'a', 'button', 'input', 'select', 'textarea'}
            TEXT_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'span'}

            for i, element in enumerate(all_tags, 1):
                attrs = element.attrs
                selector = generate_control_selector(element)
                text = element.get_text(separator=' ', strip=True)
                all_elements_data.append({'element_id': i, 'tag_name': element.name, 'control_selector': selector, 'text_content': text or None, 'id_attr': attrs.get('id'), 'class_attr': ' '.join(attrs.get('class', [])), 'href_attr': attrs.get('href'), 'src_attr': attrs.get('src'), 'all_attributes_json': json.dumps(attrs, ensure_ascii=False)})
                tag_name = element.name.lower()
                if tag_name in MEDIA_TAGS and element.has_attr('src'): media_elements.append({'tag': tag_name, 'src': element['src']})
                elif tag_name in INTERACTIVE_TAGS or element.has_attr('onclick'): interactive_elements.append({'tag': tag_name, 'text': text, 'selector': selector})
                elif tag_name in TEXT_TAGS and text and len(text) > 15:
                    if not element.find_parent(lambda p_tag: p_tag.name in INTERACTIVE_TAGS): text_elements.append(text)
            
            df = pd.DataFrame(all_elements_data)
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"\n🎉 Success! Detailed spreadsheet saved to: {csv_filename}")

            write_content_json_file(json_filename, media_elements, interactive_elements, list(set(text_elements)))
            print(f"💾 Success! Content summary saved to JSON file: {json_filename}")

        except PlaywrightError as e:
            print(f"\n❌ A Playwright error occurred: {e}")
            print("  - Ensure you have launched the browser using 'launch_browser.py' and it is still running.")
        except Exception as e:
            print(f"\n❌ An unexpected fatal error occurred: {e}")
        finally:
            if 'browser' in locals() and browser.is_connected(): browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Error: No page URL was provided.")
        sys.exit(1)
    target_url = sys.argv[1]
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        print("❌ Error: Invalid URL. It must start with http:// or https://")
    else:
        analyze_live_chrome_page(target_url=target_url)