# -*- coding: utf-8 -*-

import pandas as pd
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from bs4 import BeautifulSoup, element as bs4_element
import json
import time

def generate_control_selector(element: bs4_element.Tag) -> str:
    """
    ينشئ مُحدِّد CSS بسيطًا للتحكم في العنصر، مع إعطاء الأولوية للـ ID ثم الكلاس.
    """
    if element.has_attr('id'):
        return f"#{element['id']}"
    if element.has_attr('class'):
        # تنقية الكلاسات من أي قيم فارغة قد تسبب أخطاء
        classes = [c for c in element['class'] if c]
        if classes:
            return f"{element.name}.{'.'.join(classes)}"
    return element.name

def write_content_json_file(filename: str, media: list, interactives: list, texts: list):
    """
    يكتب المحتويات المصنفة (ميديا، تفاعلية، نصوص) في ملف JSON منسق.
    """
    # تجميع كل البيانات في قاموس واحد رئيسي
    page_content_structure = {
        "media_content": {
            "count": len(media),
            "items": media
        },
        "interactive_elements": {
            "count": len(interactives),
            "items": interactives
        },
        "main_texts": {
            "count": len(texts),
            "items": texts
        }
    }

    # كتابة القاموس إلى ملف JSON مع تنسيق جميل ودعم للغة العربية
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(page_content_structure, f, ensure_ascii=False, indent=4)

def analyze_live_chrome_page(target_url: str, csv_filename: str = "live_profile_analysis.csv", 
                             json_filename: str = "live_profile_content.json"):
    """
    يتصل بمتصفح كروم يعمل، ينتقل إلى الرابط المحدد، ثم يقوم بتحليل الصفحة.
    """
    print("🚀 محاولة الاتصال بمتصفح كروم الذي يعمل على المنفذ 9222...")
    with sync_playwright() as p:
        try:
            # الاتصال بمتصفح كروم الموجود مسبقًا
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            # استخدام السياق الافتراضي للمتصفح (الذي يحتوي على جلساتك وتسجيل دخولك)
            context = browser.contexts[0]
            
            print(f"جاري فتح تبويب جديد والانتقال إلى: {target_url} ...")
            page = context.new_page()
            # الانتقال للرابط مع انتظار اكتمال تحميل الشبكة ومهلة زمنية طويلة
            page.goto(target_url, wait_until='networkidle', timeout=90000)
            print("✅ تم تحميل الصفحة بنجاح.")

            # --- نقطة التفاعل اليدوي للمستخدم ---
            print("\n" + "="*50)
            print("--- 🔴 إجراء مطلوب منك (اختياري) ---")
            print("1. الصفحة الآن أمامك في المتصفح.")
            print("2. يمكنك القيام بأي تجهيزات نهائية (مثل التمرير للأسفل، إغلاق نافذة منبثقة).")
            input("\n⬅️  عندما تكون الصفحة جاهزة تمامًا، اضغط على مفتاح Enter هنا لبدء التحليل...")
            
            print(f"\n✅ تم استلام الأمر! بدء تحليل الصفحة: {page.title()}")
            time.sleep(2) # إعطاء فرصة بسيطة للصفحة لتستقر بعد أي تفاعل أخير

            # استخلاص محتوى الصفحة بعد التجهيز اليدوي
            page_content = page.content()
            soup = BeautifulSoup(page_content, 'lxml')
            all_tags = soup.find_all(True) # الحصول على كل العناصر في الصفحة

            print(f"🔬 تم العثور على {len(all_tags)} عنصر، جاري المعالجة والتصنيف...")
            
            # تهيئة القوائم لتخزين البيانات
            all_elements_data_for_csv = []
            media_elements = []
            interactive_elements = []
            text_elements = []
            
            # تعريف أنواع التاغات لتسهيل التصنيف
            MEDIA_TAGS = {'img', 'video', 'audio', 'source', 'picture'}
            INTERACTIVE_TAGS = {'a', 'button', 'input', 'select', 'textarea'}
            TEXT_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'span'}
            
            # المرور على كل عنصر وتصنيفه
            for i, element in enumerate(all_tags, 1):
                attributes = element.attrs
                control_selector = generate_control_selector(element)
                text_content = element.get_text(separator=' ', strip=True)
                
                # تجميع البيانات لملف CSV
                all_elements_data_for_csv.append({
                    'element_id': i,
                    'tag_name': element.name,
                    'control_selector': control_selector,
                    'text_content': text_content or None,
                    'id_attr': attributes.get('id'),
                    'class_attr': ' '.join(attributes.get('class', [])),
                    'href_attr': attributes.get('href'),
                    'src_attr': attributes.get('src'),
                    'all_attributes_json': json.dumps(attributes, ensure_ascii=False)
                })
                
                # تصنيف العناصر لملف JSON
                tag_name = element.name.lower()
                if tag_name in MEDIA_TAGS and element.has_attr('src'):
                    media_elements.append({'tag': tag_name, 'src': element['src']})
                elif tag_name in INTERACTIVE_TAGS or element.has_attr('onclick'):
                    interactive_elements.append({'tag': tag_name, 'text': text_content, 'selector': control_selector})
                elif tag_name in TEXT_TAGS and text_content and len(text_content) > 15:
                    # التأكد من أن النص ليس جزءًا من عنصر تفاعلي (مثل نص داخل زر)
                    if not element.find_parent(lambda p: p.name in INTERACTIVE_TAGS):
                        text_elements.append(text_content)

            # --- حفظ المخرجات ---
            # 1. إنشاء وحفظ ملف CSV
            df = pd.DataFrame(all_elements_data_for_csv)
            df.rename(columns={'control_selector': 'تاغ التحكم بالعنصر'}, inplace=True)
            df = df[['element_id', 'tag_name', 'تاغ التحكم بالعنصر', 'text_content', 'id_attr', 'class_attr', 'href_attr', 'src_attr', 'all_attributes_json']]
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"\n🎉 نجاح! تم حفظ جدول البيانات المفصل في: {csv_filename}")
            
            # 2. إنشاء وحفظ ملف JSON
            write_content_json_file(json_filename, media_elements, interactive_elements, list(set(text_elements))) # استخدام set لإزالة النصوص المكررة
            print(f"💾 نجاح! تم حفظ ملخص المحتويات في ملف JSON: {json_filename}")

        except PlaywrightError as e:
            print(f"\n❌ حدث خطأ من Playwright: {e}")
            print("  - تأكد من أنك قمت بتشغيل كروم بالطريقة الصحيحة من سطر الأوامر (مع --remote-debugging-port=9222).")
            print("  - تأكد من أن الرابط الذي أدخلته صحيح ويمكن الوصول إليه.")
        except Exception as e:
            print(f"\n❌ حدث خطأ فادح وغير متوقع: {e}")
        finally:
            print("\n👍 تم قطع الاتصال بالمتصفح. يمكنك الآن إغلاق كروم يدويًا.")
            if 'browser' in locals() and browser.is_connected():
                browser.close()

# --- نقطة انطلاق البرنامج ---
if __name__ == "__main__":
    print("--- ⚠️ تذكير ---")
    print("قبل المتابعة، تأكد من أنك قمت بتشغيل Google Chrome من سطر الأوامر")
    print("مع تفعيل منفذ التصحيح (e.g., --remote-debugging-port=9222).\n")
    
    target_url = ""
    while not target_url:
        target_url = input("الرجاء إدخال رابط الصفحة الكامل الذي تريد تحليله: ")
        if not (target_url.startswith("http://") or target_url.startswith("https://")):
            print("الرابط غير صالح. يجب أن يبدأ بـ http:// أو https://. الرجاء المحاولة مرة أخرى.")
            target_url = ""

    # استدعاء الدالة الرئيسية مع الرابط الذي أدخله المستخدم
    analyze_live_chrome_page(target_url=target_url)