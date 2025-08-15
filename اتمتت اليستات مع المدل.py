import os
import json
import time
import queue
import threading
import re
import requests
from flask import Flask
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup, Comment

# ==============================================================================
# 1. Settings
# ==============================================================================
MODEL_NAME = "llama2:13b"
OLLAMA_API_URL = "http://127.0.0.1:11434/v1/completions"
PROFILE_NAME = "Profile 1"
HEADLESS = False
SNAPSHOT_FOLDER = "الملفات"

command_queue = queue.Queue()
result_queue = queue.Queue()
app = Flask(__name__)

# ... (Browser Manager - No changes) ...
class BrowserManager(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.playwright = None; self.browser = None; self.page = None; self.initialized = False
    def run(self):
        self.playwright = sync_playwright().start()
        self._command_loop()
    def _command_loop(self):
        while True:
            cmd = command_queue.get()
            action, params = cmd.get("action"), cmd.get("params", {})
            if action == "shutdown": break
            result = self._execute_command(action, params)
            result_queue.put(result)
        self.stop()
    def _launch_browser_if_needed(self):
        if not self.browser:
            profile_path = os.path.abspath(rf"C:\Users\Mostafa\AppData\Local\Google\Chrome\User Data\{PROFILE_NAME}")
            self.browser = self.playwright.chromium.launch_persistent_context(user_data_dir=profile_path, headless=HEADLESS, args=["--start-maximized"])
            self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()
            self.initialized = True
            print("✅ Browser is now running.")
    def _execute_command(self, action, params):
        try:
            if action != "shutdown": self._launch_browser_if_needed()
            actions = {"goto": lambda p: self.page.goto(p["url"], timeout=60000),"keyboard_type": lambda p: self.page.keyboard.type(p["text"], delay=50),"keyboard_press": lambda p: self.page.keyboard.press(p["key"], delay=0),"get_active_element_html": lambda p: self.page.evaluate("document.activeElement.outerHTML"),"click_active_element": lambda p: self.page.evaluate("document.activeElement.click()"),"get_full_page_html": lambda p: self.page.content(),}
            if action in actions: return {"status": "success", "action": action, "data": actions[action](params)}
            return {"status": "error", "error": f"Unknown action: {action}"}
        except Exception as e:
            return {"status": "error", "error": str(e), "action": action}
    def stop(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()
        print("🛑 Browser manager stopped.")

# ==============================================================================
# 3. Model Communication
# ==============================================================================
def send_command(action, params={}):
    command_queue.put({"action": action, "params": params})
    return result_queue.get()

def call_model_with_prompt(prompt):
    payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
    try:
        resp = requests.post(OLLAMA_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0].get("text", "").strip() if "choices" in data and data["choices"] else ""
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"\n❌ Error in model communication: {e}")
        return None

def generate_action_plan(user_prompt):
    prompt = f"""
Convert the user request into a JSON action plan.
USER REQUEST: "{user_prompt}"
ACTIONS:
- goto: {{ "action": "goto", "url": "..." }}
- find_and_type: {{ "action": "find_and_type", "description": "...", "text": "..." }}
- find_and_click: {{ "action": "find_and_click", "description": "..." }}
Your response MUST be ONLY the JSON list, with no other text.
JSON PLAN:"""
    response = call_model_with_prompt(prompt)
    if not response: return None
    try:
        start_index = response.find('[')
        if start_index == -1: raise json.JSONDecodeError("No JSON list '[' found.", response, 0)
        decoder = json.JSONDecoder()
        json_obj, _ = decoder.raw_decode(response[start_index:])
        return json_obj
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON parsing for ACTION PLAN failed: {e.msg}")
        return None

# ==============================================================================
# 4. UI Element Extraction and Classification
# ==============================================================================

# تم التعديل: الدالة الجديدة والذكية لاستخراج العناصر
def extract_interactive_elements(html_content):
    """
    Parses HTML and extracts interactive elements into structured lists.
    """
    if not html_content: return {}
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = {"links": [], "buttons": [], "inputs": []}

        # Extract links
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True) or a.get('aria-label', '')
            if text:
                elements["links"].append({"text": text, "href": a['href']})

        # Extract buttons
        for btn in soup.find_all(['button', 'input']):
            if btn.name == 'button' or btn.get('type') in ['submit', 'button', 'reset']:
                text = btn.get_text(strip=True) or btn.get('value') or btn.get('aria-label')
                if text:
                    elements["buttons"].append({"text": text})

        # Extract text inputs
        for inp in soup.find_all(['input', 'textarea']):
            inp_type = inp.get('type', 'textarea')
            if inp_type in ['text', 'search', 'email', 'password', 'url', 'tel', 'textarea']:
                label = inp.get('placeholder') or inp.get('aria-label') or inp.get('name')
                if label:
                    elements["inputs"].append({"label": label, "type": inp_type})

        return elements
    except Exception as e:
        print(f"Could not extract elements from HTML: {e}")
        return {}


def model_classify_element(structured_elements, target_description):
    # تم التعديل: Prompt جديد بالكامل يعمل على البيانات المنظمة
    prompt = f"""
You are an expert UI analyst. Below are lists of interactive elements found on a web page, in JSON format.
Your task is to find the single best element that matches the user's description and classify it.

USER DESCRIPTION: "{target_description}"

INTERACTIVE ELEMENTS:
{json.dumps(structured_elements, indent=2, ensure_ascii=False)}

Analyze the lists above and respond ONLY with a valid JSON object with your classification.
- "classification": Should be "TEXT_INPUT", "CLICKABLE_BUTTON", or "IGNORE".
  - A "link" or "button" from the lists is a "CLICKABLE_BUTTON".
  - An "input" from the lists is a "TEXT_INPUT".
- "reason": Briefly explain your choice.
- "confidence": A score from 0.0 to 1.0.

JSON RESPONSE:
"""
    response = call_model_with_prompt(prompt)
    if not response: return {"classification": "IGNORE", "reason": "Model call failed", "confidence": 0.0}

    try:
        start_index = response.find('{')
        if start_index == -1: raise json.JSONDecodeError("No JSON object '{' found.", response, 0)
        decoder = json.JSONDecoder()
        result, _ = decoder.raw_decode(response[start_index:])
        return {
            "classification": result.get("classification", "IGNORE"),
            "reason": result.get("reason", "No reason."),
            "confidence": float(result.get("confidence", 0.0))
        }
    except json.JSONDecodeError as e:
        print(f"\nDEBUG: JSON CLASSIFICATION failed: {e.msg}")
        return {"classification": "IGNORE", "reason": f"JSON error: {e.msg}", "confidence": 0.0}

# ==============================================================================
# 5. Find and Interact with Elements
# ==============================================================================
def find_element_and_interact(goal_type, description, text_to_type=None):
    print(f"🔍 Searching for '{description}' in the page...")
    res = send_command("get_full_page_html")
    html = res.get("data", "")
    if not html:
        print("Could not get page HTML."); return False

    # تم التعديل: استخدام الدالة الجديدة للحصول على القوائم المنظمة
    structured_elements = extract_interactive_elements(html)
    if not any(structured_elements.values()):
        print("No interactive elements found on the page."); return False

    print(f"Calling expert model to analyze extracted elements...")
    model_decision = model_classify_element(structured_elements, description)
    
    classification = model_decision.get("classification")
    reason = model_decision.get("reason")
    confidence = model_decision.get("confidence")

    print(f"[Decision] Classification: {classification}, Confidence: {confidence:.2f}")
    print(f"[Reason] {reason}")

    if classification == goal_type and confidence >= 0.7:
        print(f"✅ Target element identified!")
        if goal_type == "TEXT_INPUT" and text_to_type is not None:
            send_command("keyboard_type", {"text": text_to_type}); print(f">> Typed: '{text_to_type}'")
        elif goal_type == "CLICKABLE_BUTTON":
            send_command("click_active_element"); print(">> Clicked the element.")
        return True
    
    print("... Target not confirmed by model.")
    return False

# ... (Execute Plan is largely unchanged, but now more likely to succeed) ...
def execute_plan(plan):
    for i, step in enumerate(plan):
        if not isinstance(step, dict): continue
        action = step.get('action')
        if not action: continue
        print(f"\n--- Step {i+1}/{len(plan)}: {action} ---")
        success = False
        try:
            if action == "goto":
                url = step.get('url')
                if url: send_command("goto", {"url": url}); success = True
            elif action == "find_and_type":
                description = step.get('description')
                text = step.get('text')
                if description and text is not None: success = find_element_and_interact("TEXT_INPUT", description, text_to_type=text)
            elif action == "find_and_click":
                description = step.get('description')
                if description: success = find_element_and_interact("CLICKABLE_BUTTON", description)

            if not success: print(f"❌ Step '{action}' failed.")
            else: print(f"--- ✅ Step {i+1} completed ---")
        except Exception as e:
            print(f"🚨 Error in step {i+1}: {e}"); return False
        time.sleep(2)
    return True

# ==============================================================================
# 7. Page Saver Thread
# ==============================================================================
class PageSaver(threading.Thread):
    def __init__(self, interval=60):
        super().__init__(daemon=True); self.interval = interval; self.running = True
    def run(self):
        os.makedirs(SNAPSHOT_FOLDER, exist_ok=True)
        print(f"📄 Page snapshots (structured JSON) will be saved in '{SNAPSHOT_FOLDER}/' folder.")
        while self.running:
            time.sleep(self.interval)
            try:
                if browser_manager.initialized and self.running:
                    html_data = send_command("get_full_page_html").get("data", "")
                    # تم التعديل: حفظ القوائم المنظمة بدلاً من HTML
                    structured_data = extract_interactive_elements(html_data)
                    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
                    filename = os.path.join(SNAPSHOT_FOLDER, f"page_snapshot_{timestamp}.json")
                    with open(filename, "w", encoding="utf-8") as f:
                        json.dump(structured_data, f, ensure_ascii=False, indent=2)
            except Exception: pass
    def stop(self): self.running = False
# ... (Timer and Main Entry are unchanged) ...
class TimerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.start_time = time.time(); self.running = True
    def run(self):
        while self.running:
            elapsed = int(time.time() - self.start_time)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"\r⏱ Elapsed time: {hours:02d}:{minutes:02d}:{seconds:02d}", end="")
            time.sleep(1)
    def stop(self): self.running = False

if __name__ == '__main__':
    browser_manager = BrowserManager(); browser_manager.start()
    page_saver = PageSaver(interval=60); page_saver.start()
    timer = TimerThread(); timer.start()
    while True:
        try:
            user_prompt = input("\n\n============================================\n🤖 Enter your task (or 'exit' to quit):\n\t> ")
            if user_prompt.lower() in ["exit", "quit"]: break
            print("\n⏳ Generating action plan...")
            action_plan = generate_action_plan(user_prompt)
            if not action_plan or not isinstance(action_plan, list):
                print("❌ Could not generate a valid action plan."); continue
            print("✅ Action Plan:"); print(json.dumps(action_plan, indent=2, ensure_ascii=False))
            confirm = input("\n🔹 Press Enter to execute... ")
            if confirm.lower() == 'no': print("Cancelled."); continue
            start_time = time.time()
            success = execute_plan(action_plan)
            if success:
                print(f"\n🎉 Task completed in {time.time() - start_time:.2f} seconds.")
        except (KeyboardInterrupt, EOFError):
            print("\nUser requested exit."); break
        except Exception as e:
            print(f"\n🚨 Unexpected error: {e}")
    print("\nShutting down...")
    send_command("shutdown")
    timer.stop(); page_saver.stop()
    browser_manager.join(timeout=5); page_saver.join(timeout=5); timer.join(timeout=5)
    print("\n✅ Program finished.")