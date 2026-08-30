# Mistral Terminal AI Agent (v2.0)

An AI agent that lives inside a real, persistent PowerShell session on your machine. Type a request in plain English, it turns it into a real command, and after you confirm it actually runs. Not a simulation, every approved command really executes on your machine.

---

## 🚀 Key Features

### 🧠 Natural Language Command Engine
*   **Plain-English Input:** Describe what you want in normal words, the AI translates it into a real, valid PowerShell command.
*   **Command Chaining:** Multi-step requests (e.g. "commit and push") are broken into an ordered chain of real commands, shown to you in full before anything runs.
*   **Clarify-on-Ambiguity:** If a request is genuinely unclear, the agent asks one direct clarifying question instead of guessing, then commits to a final answer.

### 🖥️ Live, Stateful Shell
*   **Real Persistent Process:** A single PowerShell process is kept alive in the background for the entire session, not a fresh subprocess per command.
*   **True State Persistence:** cd, environment variables, and shell state carry over between commands exactly like a real terminal session, because it is one.
*   **Prompt-Based Output Parsing:** Output is read directly off the live shell's stdout stream and parsed into clean, structured results.

### 🩹 Error Recovery
*   **Real Failure Detection:** Every command's actual exit status is checked, not just its printed text, so failures are never missed or falsely flagged.
*   **AI-Diagnosed Fixes:** On failure, the agent diagnoses the real error and proposes a safe, valid PowerShell fix when one exists, capped at 3 retry attempts.
*   **Confirmation on Every Fix:** No proposed fix ever runs automatically, you approve each one before it touches your machine.

### 🛡️ Safety and Memory
*   **Confirmation Before Execution:** No command, single or chained, ever runs without explicit user confirmation.
*   **Session Memory:** The agent recalls recent requests, commands, and outputs from earlier in the current session.
*   **Cross-Session Memory:** A short history of past requests is saved to disk on exit and loaded back in on the next run.

### 🌍 Run From Anywhere
*   **Installable Package:** The agent is packaged as a real Python package with a console entry point, install it once and run it from any folder.

---

## 📂 Project Structure

```text
Terminal-AI-Agent/
├── terminal_ai_agent/
│   ├── __init__.py
│   ├── main.py                   # Core agent loop, shell control, and AI integration
│   └── memory/
│       ├── __init__.py
│       ├── last_requests.txt     # Saved cross-session request history
│       └── save_and_load_memory.py
├── tests/
│   ├── chaining_test_input.md
│   ├── chaining_test_output.md
│   ├── error_recovery_test_input.md
│   ├── error_recovery_test_output.md
│   ├── file_writing_and_creation_test_input.md
│   └── file_writing_and_creation_test_output.md
├── .env                          # Mistral API key (not committed)
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 🛠️ Requirements and System Setup

*   **Runtime Environment:** Python 3.10 or higher.
*   **Platform:** Windows (spawns powershell.exe and parses Windows-style prompts).
*   **Dependencies:** mistralai, python-dotenv.

```bash
git clone https://github.com/narkisiuria/Mistral-AI-Terminal-Agent.git
cd Mistral-AI-Terminal-Agent
pip install -e .
```

Installing with `-e` (editable mode) means any code changes take effect immediately, no reinstall needed. This also registers a console command so the agent can be launched from any folder, not just the project directory.

---

## 💻 How to Run

### 1. Set Your API Key
Create a `.env` file in the project root:
```
MISTRAL_API_KEY2=your_api_key_here
```

### 2. Launch the Agent
From any directory:
```bash
jarvis
```

### 3. Give it a request
```
AI-CLI (PS C:\Users\you\project>) > create a folder called test and a file called notes.txt inside it
Full chain planned:
  1. New-Item -ItemType Directory -Name test
  2. New-Item -Path test\notes.txt -ItemType File
proceed running this chain? (n/y)> y
```

Type `quit` to exit, session history is saved automatically.

---

## ⚠️ Warning

This tool executes real commands on your real machine after confirmation. Always read the full command (or command chain) before approving it, the AI can make mistakes.

---

## 🗺️ Roadmap

*   [x] Live persistent shell with prompt detection
*   [x] Plain-English to PowerShell command translation
*   [x] Clarify-on-ambiguity (capped at one question per request)
*   [x] Command chaining with full-chain preview and single confirmation
*   [x] Error recovery with AI-diagnosed, confirmed fixes
*   [x] Session and cross-session memory
*   [x] Installable as a global command via pip
*   [ ] App-launching support
*   [ ] Cross-platform (Linux/Kali) shell support
