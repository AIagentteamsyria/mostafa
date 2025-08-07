# -*- coding: utf-8 -*-
# الملف: launch_browser.py

import subprocess
import os
import sys

# تحديد مسار مخصص لحفظ بيانات جلسة كروم (تسجيل الدخول، الكوكيز)
# سيتم إنشاء هذا المجلد بجانب ملف الكود
USER_DATA_DIR = os.path.join(os.getcwd(), "chrome_session_data")

def find_chrome_executable():
    """يحاول العثور على مسار متصفح جوجل كروم تلقائيًا."""
    if sys.platform == "win32":
        for path in [
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe")
        ]:
            if os.path.exists(path):
                return path
    elif sys.platform == "darwin": # macOS
        path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.exists(path):
            return path
    # يمكنك إضافة مسارات لينكس هنا إذا احتجت
    return None

def main():
    """يشغل متصفح كروم مع ملف شخصي مخصص ومنفذ تصحيح مفتوح."""
    chrome_path = find_chrome_executable()
    if not chrome_path:
        print("❌ لم يتم العثور على متصفح جوجل كروم. الرجاء التأكد من أنه مثبت.")
        return

    # إنشاء مجلد بيانات الجلسة إذا لم يكن موجودًا
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)

    command = [
        chrome_path,
        "--remote-debugging-port=9222", # المنفذ الذي سيتصل به الكود الثاني
        f"--user-data-dir={USER_DATA_DIR}" # المجلد الذي سيحفظ تسجيل الدخول
    ]

    print("🚀 جاري إطلاق متصفح كروم مخصص لجلسة التحليل...")
    print(f"📂 سيتم حفظ بيانات الجلسة (تسجيل الدخول) في: {USER_DATA_DIR}")
    
    # تشغيل كروم كعملية منفصلة
    subprocess.Popen(command)

    print("\n" + "="*60)
    print("--- ✅ الخطوة التالية: تسجيل الدخول (تقوم بها مرة واحدة فقط) ---")
    print("1. ستفتح نافذة جديدة لمتصفح كروم الآن.")
    print("2. استخدم هذه النافذة لتسجيل الدخول إلى حسابك في Google")
    print("   (mhialdenmostafa@gmail.com) وأي مواقع أخرى تحتاجها.")
    print("3. بمجرد تسجيل الدخول، **اترك نافذة المتصفح هذه مفتوحة في الخلفية**.")
    print("\n--- 🔬 أنت الآن جاهز للتحليل ---")
    print("🔹 افتح نافذة أوامر (Terminal) **جديدة**.")
    print("🔹 انتقل إلى مجلد المشروع.")
    print("🔹 قم بتشغيل الأمر التالي لتحليل أي صفحة:")
    print("   python analyze_page.py <الرابط الكامل للصفحة هنا>")
    print("\n(يمكنك إغلاق نافذة الأوامر هذه الآن، لكن اترك نافذة المتصفح مفتوحة)")

if __name__ == "__main__":
    main()