# File: main.py
import subprocess
import sys

def print_menu():
    """Prints the main menu for the user."""
    print("\n" + "="*22 + " Main Control Panel " + "="*22)
    print("1. 🚀 Launch Browser (Do this first)")
    print("2. 🔬 Analyze a Web Page (Requires browser to be running)")
    print("3. 📝 Fill an Input Field (Requires page to be analyzed)")
    print("4. 🖱️ Click a Button (Requires page to be analyzed)")
    print("5. 🚪 Exit")
    print("="*64)

def main():
    """The main function to run the automation system."""
    while True:
        print_menu()
        choice = input("Please select an option number: ")

        python_executable = sys.executable

        if choice == '1':
            print("\n--- [1] Launching Browser ---")
            subprocess.Popen([python_executable, "launch_browser.py"])
            print("✅ Sent command to launch browser. It may take a moment to appear.")
            print("❗️ Remember to log in within the new browser window.")

        elif choice == '2':
            print("\n--- [2] Analyzing Web Page ---")
            url = input("Please enter the full URL of the page to analyze: ")
            if url:
                subprocess.run([python_executable, "analyze_page.py", url])
            else:
                print("❌ No URL entered. Operation cancelled.")

        elif choice == '3':
            print("\n--- [3] Filling Input Field ---")
            text_to_fill = input("Please enter the text you want to type into the field: ")
            if text_to_fill:
                subprocess.run([python_executable, "fill_input.py", text_to_fill])
            else:
                print("❌ No text entered. Operation cancelled.")

        elif choice == '4':
            print("\n--- [4] Clicking a Button ---")
            button_text = input("Enter a part of the text on the button to search for: ")
            if button_text:
                subprocess.run([python_executable, "click_button.py", button_text])
            else:
                print("❌ No search text entered. Operation cancelled.")

        elif choice == '5':
            print("\n👋 Goodbye!")
            break

        else:
            print("❌ Invalid choice. Please enter a number from 1 to 5.")

if __name__ == "__main__":
    main()