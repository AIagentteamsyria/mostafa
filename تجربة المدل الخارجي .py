import os
import json
import time
import queue
import threading
import re
import requests
from collections import deque
from urllib.parse import urlparse
from flask import Flask
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# ==============================================================================
# 1. Settings & Configuration
# ==============================================================================
# -- OpenRouter API Configuration --
OPENROUTER_API_KEY = "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"
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL   = "openai/gpt-4o" 

# -- General Application Settings --
YOUR_SITE_URL      = "http://localhost:3000"
YOUR_APP_NAME      = "Reactive AI Agent"

# -- Browser Automation Settings --
CHROME_PROFILE_NAME = "Profile 1"
CHROME_USER_DATA_PATH = rf"C:\Users\Mostafa\AppData\Local\Google\Chrome\User Data\{CHROME_PROFILE_NAME}"
HEADLESS = False
SNAPSHOT_FOLDER = "الملفات"

# -- Agent Control Settings --
VALID_ACTIONS = ["goto", "find_and_type", "find_and_click", "finish"]
MAX_STEPS = 50

# -- Global Variables --
command_queue = queue.Queue()
result_queue = queue.Queue()
app = Flask(__name__)
CURRENT_BROWSER_URL = ""

# ==============================================================================
# 2. Model Communication Manager (FINALIZED with max_tokens)
# ==============================================================================
class ModelManager:
    """Encapsulates all communication logic with the LLM API, with robust error handling."""
    def __init__(self, api_key, api_url, model_identifier, site_url, app_name):
        if not api_key or "sk-or-v1-" not in api_key:
            raise ValueError("API key for OpenRouter is not set or invalid.")
        self.api_url = api_url
        self.model = model_identifier
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": site_url, 
            "X-Title": app_name,
        })

    def call_model(self, prompt, max_retries=4):
        """
        Calls the OpenAI-compatible API with a given prompt.
        Implements exponential backoff and now explicitly sets a reasonable max_tokens limit.
        """
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 1024,
            "stream": False
        }
        wait_time = 5

        for attempt in range(max_retries):
            try:
                response = self.session.post(self.api_url, json=payload, timeout=150)
                response.raise_for_status()
                data = response.json()

                if "choices" in data and data["choices"]:
                    content = data["choices"][0].get("message", {}).get("content")
                    return content.strip() if content else ""
                else:
                    print(f"❌ Model response malformed: {data}")
                    return ""
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code in [429, 402]:
                    print(f"⚠️ API Limit Reached ({e.response.status_code}). Waiting {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    wait_time *= 2
                else:
                    print(f"\n❌ HTTP Error communicating with model: {e.response.status_code} {e.response.text}")
                    return None
            
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                print(f"\n❌ Model communication error: {e}")
                return None
        
        print(f"❌ Failed to get a response from the model after {max_retries} attempts.")
        return None

# ==============================================================================
# 3. Browser Manager (No Changes)
# ==============================================================================
class BrowserManager(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.playwright = None; self.browser = None; self.page = None; self.initialized = False
    def run(self): self.playwright = sync_playwright().start(); self._command_loop()
    def _update_current_url(self):
        global CURRENT_BROWSER_URL
        if self.page:
            try: CURRENT_BROWSER_URL = self.page.url
            except Exception: CURRENT_BROWSER_URL = ""
    def _launch_browser_if_needed(self):
        if not self.browser:
            self.browser = self.playwright.chromium.launch_persistent_context(user_data_dir=CHROME_USER_DATA_PATH, headless=HEADLESS, args=["--start-maximized"])
            self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()
            self.page.on("load", self._update_current_url); self.initialized = True; print("✅ Browser is now running."); self._update_current_url()
    def _execute_command(self, action, params):
        try:
            if action != "shutdown": self._launch_browser_if_needed()
            if action == "goto":
                self.page.goto(params["url"], timeout=60000, wait_until="domcontentloaded"); self._update_current_url(); return {"status": "success"}
            elif action == "get_full_page_html": return {"status": "success", "data": self.page.content()}
            elif action == "click_element": self.page.locator(params["selector"]).first.click(timeout=15000); return {"status": "success"}
            elif action == "type_in_element":
                selector = params["selector"]; text_to_type = params["text"]
                self.page.locator(selector).first.click(timeout=15000)
                self.page.locator(selector).first.fill(text_to_type, timeout=15000); return {"status": "success"}
            return {"status": "error", "error": f"Unknown action: {action}"}
        except Exception as e:
            error_message = str(e).split('\n')[0]; return {"status": "error", "error": f"Action '{action}' failed: {error_message}", "action": action}
    def _command_loop(self):
        while True:
            cmd = command_queue.get(); action, params = cmd.get("action"), cmd.get("params", {});
            if action == "shutdown": break
            result = self._execute_command(action, params); result_queue.put(result)
        self.stop()
    def stop(self):
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()
        print("🛑 Browser manager stopped.")

def send_command(action, params={}): command_queue.put({"action": action, "params": params}); return result_queue.get()

# ==============================================================================
# 4. Page Context Extraction (No Changes)
# ==============================================================================
def extract_page_context(html_content):
    if not html_content: return {}
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.title.string if soup.title else "No title found"
        links = [a.get_text(strip=True) for a in soup.find_all('a', href=True) if a.get_text(strip=True)][:20]
        buttons = [btn.get_text(strip=True) for btn in soup.find_all('button') if btn.get_text(strip=True)][:20]
        return {"page_title": title, "links_sample": links, "buttons_sample": buttons}
    except Exception as e:
        print(f"Could not extract page context: {e}")
        return {}

# ==============================================================================
# 5. Intelligent Interaction Logic (No Changes)
# ==============================================================================
def generate_playwright_selector(description, model_manager):
    prompt = f"""You are an expert Playwright automation engineer. Convert the user's natural language description of a web element into the most precise and robust Playwright CSS or XPath selector.
USER DESCRIPTION: "{description}"
Respond with ONLY the selector string. Do not include any explanation, markdown, or conversation. For example: `[aria-label="Search"]`
SELECTOR STRING:"""
    response = model_manager.call_model(prompt)
    if not response:
        print("❌ Model returned no response for selector generation.")
        return None
    selector = response.strip().replace("`", "").replace("'", "\"")
    
    if selector:
        print(f"🤖 Model generated selector: `{selector}`")
        return selector
    print(f"❌ Could not extract a valid selector from model response: {response}")
    return None

def find_and_interact(interaction_type, description, model_manager, text_to_type=None):
    selector = generate_playwright_selector(description, model_manager)
    if not selector: return False
    
    action_map = {
        "CLICK": ("click_element", {"selector": selector}),
        "TYPE": ("type_in_element", {"selector": selector, "text": text_to_type})
    }
    
    action, params = action_map.get(interaction_type)
    if not action: return False

    result = send_command(action, params)

    if result.get("status") == "success":
        print(f"✅ Interaction '{interaction_type}' on '{description}' was successful.")
        return True
    else:
        print(f"❌ Playwright execution failed: {result.get('error')}")
        return False

# ==============================================================================
# 6. Step Generation and Execution (No Changes)
# ==============================================================================
def generate_next_step(user_prompt, model_manager, page_context=None, history=None):
    context_str = "The browser is on a blank page."
    if page_context and any(page_context.values()): context_str = f"Current page context:\n{json.dumps(page_context, indent=2, ensure_ascii=False)}"
    
    history_str = "No actions performed yet."
    if history: history_str = "Recent actions:\n" + "\n".join([f"- {item}" for item in history])
    
    prompt = f"""You are a precise web automation agent. Decide the single next action to achieve the user's objective based on the context.
OBJECTIVE: "{user_prompt}"
IMPORTANT RULES:
1. If the browser is already on the correct website, you MUST choose 'find_and_type' or 'find_and_click'.
2. DO NOT issue a 'goto' command to the same site again to avoid loops.
{history_str}
{context_str}
ALLOWED ACTIONS & FORMATS (STRICT):
- Go to a webpage: {{"action": "goto", "url": "https://www.example.com"}}
- Type in a field: {{"action": "find_and_type", "description": "a clear description of the input", "text": "text to type"}}
- Click an element: {{"action": "find_and_click", "description": "a clear description of the button/link"}}
- Finish the task: {{"action": "finish", "reason": "why the task is complete"}}
Your response MUST be ONLY a single, valid JSON object and nothing else.
JSON RESPONSE:"""
    
    response = model_manager.call_model(prompt)
    if not response:
        print("Model returned empty response after all retries.")
        return None
    try:
        match = re.search(r'```json\s*(\{.*?\})\s*```|(\{.*?\})', response, re.DOTALL)
        if not match:
            raise json.JSONDecodeError("No JSON object found in model's response.", response, 0)
        
        json_str = match.group(1) or match.group(2)
        step = json.loads(json_str)

        if step.get("action") not in VALID_ACTIONS:
            print(f"❌ Model generated an invalid action: {step.get('action')}")
            return None
        return step
    except json.JSONDecodeError:
        print(f"❌ Failed to decode JSON from model response: '{response}'")
        return None
    
def execute_step(step, model_manager):
    action = step.get('action')
    print(f"\n--- Executing: {action} ---"); print(json.dumps(step, indent=2, ensure_ascii=False))
    
    if action == "goto":
        destination_url = step.get('url')
        if not destination_url:
            print("❌ 'goto' failed: Missing URL."); return False
        
        try:
            current_domain = urlparse(CURRENT_BROWSER_URL).netloc
            destination_domain = urlparse(destination_url).netloc
            if current_domain and destination_domain and current_domain in destination_domain:
                print(f"⚠️  Loop detected. Refusing to 'goto' same site: {destination_url}"); return False
        except Exception: pass
        result = send_command("goto", {"url": destination_url})
        return result.get("status") == "success"

    elif action == "find_and_type":
        return find_and_interact("TYPE", step.get('description'), model_manager, text_to_type=step.get('text'))

    elif action == "find_and_click":
        return find_and_interact("CLICK", step.get('description'), model_manager)

    elif action == "finish":
        print(f"🏁 Finish reason: {step.get('reason')}"); return "finish"
    
    print(f"❌ Step '{action}' failed due to missing or invalid parameters."); return False

def get_page_state_for_model():
    print("🕵️  Getting current page state...")
    result = send_command("get_full_page_html")
    html = result.get("data", "")
    if not html: return None
    context = extract_page_context(html)
    os.makedirs(SNAPSHOT_FOLDER, exist_ok=True); timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(SNAPSHOT_FOLDER, f"context_{timestamp}.json")
    try:
        with open(filename, "w", encoding="utf-8") as f: json.dump(context, f, ensure_ascii=False, indent=2)
        print(f"📄 Context saved to '{filename}'")
    except Exception as e: print(f"❌ Could not save context file: {e}")
    return context

# ==============================================================================
# 7. Timer Thread (No Changes)
# ==============================================================================
class TimerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.start_time = time.time()
        self.running = True
    def run(self):
        while self.running:
            elapsed = int(time.time() - self.start_time)
            hours, rem = divmod(elapsed, 3600)
            mins, secs = divmod(rem, 60)
            print(f"\r⏱  Elapsed time: {hours:02d}:{mins:02d}:{secs:02d}", end="")
            time.sleep(1)
    def stop(self):
        self.running = False

# ==============================================================================
# 8. Main Application Loop
# ==============================================================================
if __name__ == '__main__':
    try:
        model = ModelManager(
            api_key=OPENROUTER_API_KEY, api_url=OPENROUTER_URL,
            model_identifier=OPENROUTER_MODEL, site_url=YOUR_SITE_URL,
            app_name=YOUR_APP_NAME
        )
    except ValueError as e:
        print(f"🚨 Configuration Error: {e}"); exit(1)

    browser_manager = BrowserManager(); browser_manager.start()
    # *** FIX APPLIED HERE: Corrected the class name from Thread to TimerThread. ***
    timer = TimerThread(); timer.start()
    
    while True:
        try:
            user_prompt = input("\n\n============================================\n🤖 Enter your task (or 'exit' to quit):\n\t> ")
            if user_prompt.lower() in ["exit", "quit"]: break
            
            start_time = time.time(); page_context = None; action_history = deque(maxlen=6); step_counter = 0
            
            while step_counter < MAX_STEPS:
                step_counter += 1
                print(f"\n-=-=-=-= Step {step_counter}/{MAX_STEPS} =-=-=-=-")
                
                next_step = generate_next_step(user_prompt, model, page_context, list(action_history))
                if not next_step:
                    print("❌ Model failed to provide a valid action. Aborting task."); break
                
                result = execute_step(next_step, model)
                
                if result == "finish":
                    print(f"\n🎉 Task completed successfully in {time.time() - start_time:.2f} seconds.")
                    break
                
                step_description = next_step.get('description', next_step.get('url', 'N/A'))
                if result:
                    print("--- ✅ Step completed successfully ---")
                    action_history.append(f"Action '{next_step.get('action')}' on '{step_description}' succeeded.")
                else:
                    print("--- ❌ Step failed. Agent will re-evaluate and try a different approach. ---")
                    action_history.append(f"Action '{next_step.get('action')}' on '{step_description}' failed. Must try something else.")
                
                print("⏳ Waiting for page to stabilize after action...")
                time.sleep(4)
                page_context = get_page_state_for_model()

            if step_counter >= MAX_STEPS: print(f"\n⚠️  Reached safety limit of {MAX_STEPS} steps. Aborting task.")

        except (KeyboardInterrupt, EOFError):
            print("\nUser requested exit."); break
        except Exception as e:
            import traceback
            print(f"\n🚨 An unexpected error occurred in the main loop: {e}")
            traceback.print_exc()

    print("\nShutting down..."); send_command("shutdown"); timer.stop()
    browser_manager.join(timeout=5); timer.join(timeout=5)
    print("\n✅ Program finished.")