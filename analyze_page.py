# -*- coding: utf-8 -*-
# الملف: analyze_page.py

import pandas as pd
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from bs4 import BeautifulSoup, element as bs4_element
import json
import time
import sys # لاستقبال الرابط من سطر الأوامر

# (كل الدوال المساعدة ودالة التحليل الرئيسية تبقى كما هي بدون أي تغيير)

def generate_control_selector(element: bs4_element.Tag) -> str:
    if element.has_attr('id'): return f"#{element['id']}"
    if element.has_attr('class'):
        classes = [c for c in element['class'] if c]
        if classes: return f"{element.name}.{'.'.join(classes)}"
    return element.name

def write_content_json_file(filename: str, media: list, interactives: list, texts: list):
    page_content_structure = {
        "media_content": {"count": len(media), "items": media},
        "interactive_elements": {"count": len(interactives), "items": interactives},
        "main_texts": {"count": len(texts), "items": texts}
    }
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(page_content_structure, f, ensure_ascii=False, indent=4)

def analyze_live_chrome_page(target_url: str, csv_filename: str = "live_profile_analysis.csv", 
                             json_filename: str = "live_profile_content.json"):
    print("🚀 محاولة الاتصال بمتصفح كروم الذي يعمل على المنفذ 9222...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            print(f"جاري فتح تبويب جديد والانتقال إلى: {target_url} ...")
            page = context.new_page()
            page.goto(target_url, wait_until='networkidle', timeout=90000)
            print("✅ تم تحميل الصفحة بنجاح.")
            
            print("\n" + "="*50)
            print("--- 🔴 إجراء مطلوب منك (اختياري) ---")
            print("1. الصفحة الآن أمامك في المتصفح. قم بأي تجهيزات نهائية.")
            input("\n⬅️  عندما تكون جاهزًا، اضغط على مفتاح Enter هنا لبدء التحليل...")
            
            print(f"\n✅ تم استلام الأمر! بدء تحليل الصفحة: {page.title()}")
            time.sleep(2)
            
            page_content = page.content()
            soup = BeautifulSoup(page_content, 'lxml')
            all_tags = soup.find_all(True)
            print(f"🔬 تم العثور على {len(all_tags)} عنصر، جاري المعالجة...")
            
            all_elements_data_for_csv, media_elements, interactive_elements, text_elements = [], [], [], []
            MEDIA_TAGS, INTERACTIVE_TAGS, TEXT_TAGS = {'img', 'video', 'audio', 'source', 'picture'}, {'a', 'button', 'input', 'select', 'textarea'}, {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'span'}
            
            for i, element in enumerate(all_tags, 1):
                attributes, control_selector, text_content = element.attrs, generate_control_selector(element), element.get_text(separator=' ', strip=True)
                all_elements_data_for_csv.append({'element_id': i, 'tag_name': element.name, 'control_selector': control_selector, 'text_content': text_content or None, 'id_attr': attributes.get('id'), 'class_attr': ' '.join(attributes.get('class', [])), 'href_attr': attributes.get('href'), 'src_attr': attributes.get('src'), 'all_attributes_json': json.dumps(attributes, ensure_ascii=False)})
                tag_name = element.name.lower()
                if tag_name in MEDIA_TAGS and element.has_attr('src'): media_elements.append({'tag': tag_name, 'src': element['src']})
                elif tag_name in INTERACTIVE_TAGS or element.has_attr('onclick'): interactive_elements.append({'tag': tag_name, 'text': text_content, 'selector': control_selector})
                elif tag_name in TEXT_TAGS and text_content and len(text_content) > 15:
                    if not element.find_parent(lambda p: p.name in INTERACTIVE_TAGS): text_elements.append(text_content)
            
            df = pd.DataFrame(all_elements_data_for_csv)
            df.rename(columns={'control_selector': 'تاغ التحكم بالعنصر'}, inplace=True)
            df = df[['element_id', 'tag_name', 'تاغ التحكم بالعنصر', 'text_content', 'id_attr', 'class_attr', 'href_attr', 'src_attr', 'all_attributes_json']]
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"\n🎉 نجاح! تم حفظ جدول البيانات المفصل في: {csv_filename}")
            
            write_content_json_file(json_filename, media_elements, interactive_elements, list(set(text_elements)))
            print(f"💾 نجاح! تم حفظ ملخص المحتويات في ملف JSON: {json_filename}")

        except PlaywrightError as e:
            print(f"\n❌ حدث خطأ من Playwright: {e}")
            print("  - تأكد من أنك قمت بتشغيل المتصفح أولاً باستخدام `launch_browser.py` وأن نافذة المتصفح ما زالت مفتوحة.")
        except Exception as e:
            print(f"\n❌ حدث خطأ فادح وغير متوقع: {e}")
        finally:
            print("\n👍 تم قطع الاتصال بالمتصفح لهذه الجلسة.")
            if 'browser' in locals() and browser.is_connected():
                browser.close()

# --- نقطة انطلاق البرنامج (تم تعديلها) ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ خطأ: لم يتم توفير رابط الصفحة.")
        print("💡 طريقة الاستخدام الصحيحة:")
        print(f"   python {sys.argv[0]} <الرابط الكامل للصفحة>")
        print("\nمثال:")
        print(f"   python {sys.argv[0]} https://myaccount.google.com")
        sys.exit(1)

    target_url = sys.argv[1]
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        print("الرابط غير صالح. يجب أن يبدأ بـ http:// أو https://.")
    else:
        analyze_live_chrome_page(target_url=target_url)