# Mistral Terminal AI Agent (v2.0)

An AI agent that lives inside a real, persistent PowerShell session on your machine. Type a request in plain English, it turns it into a real command, and after you confirm it actually runs. Not a simulation, every approved command really executes on your machine.

---

## 🚀 Key Features

### 🧠 Natural Language Command Engine
*   **Plain-English Input:** Describe what you want in normal words, the AI translates it into a real, valid PowerShell command.
*   **Command Chaining:** Multi-step requests (e.g. "commit and push") are broken into an ordered chain of real commands, shown to you in full before anything runs.
*   **Clarify-on-Ambiguity:** If a request is unclear or risky to guess, the agent asks a direct clarifying question instead of guessing.

### 🖥️ Live, Stateful Shell
*   **Real Persistent Process:** A single PowerShell process is kept alive in the background for the entire session, not a fresh subprocess per command.
*   **True State Persistence:** cd, environment variables, and shell state carry over between commands exactly like a real terminal session, because it is one.
*   **Prompt-Based Output Parsing:** Output is read directly off the live shell's stdout stream and parsed into clean, structured results.

### 🛡️ Safety and Memory
*   **Confirmation Before Execution:** No command, single or chained, ever runs without explicit user confirmation.
*   **Session Memory:** The agent recalls recent requests, commands, and outputs from earlier in the current session.
*   **Cross-Session Memory:** A short history of past requests is saved to disk on exit and loaded back in on the next run.

---

## 📂 Project Structure

```text
Mistral-Terminal-AI-Agent/
├── memory/
│   ├── __pycache__/
│   ├── last_requests.txt        # Saved cross-session request history
│   └── save_and_load_memory.py  # Memory read/write logic
├── tests/
│   ├── chaining_test_input.md
│   ├── chaining_test_output.md
│   ├── file_writing_and_creation_test_input.md
│   └── file_writing_and_creation_test_output.md
├── .env                          # Mistral API key (not committed)
├── .gitignore
├── main.py                       # Core agent loop, shell control, and AI integration
└── README.md
```

---

## 🛠️ Requirements and System Setup

*   **Runtime Environment:** Python 3.10 or higher.
*   **Platform:** Windows (spawns powershell.exe and parses Windows-style prompts).
*   **Dependencies:** mistralai, python-dotenv.

```bash
pip install mistralai python-dotenv
```

---

## 💻 How to Run

### 1. Set Your API Key
Create a `.env` file in the project root:
```
MISTRAL_API_KEY2=your_api_key_here
```

### 2. Launch the Agent
```bash
python main.py
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
*   [x] Clarify-on-ambiguity
*   [x] Command chaining with full-chain preview and single confirmation
*   [x] Session and cross-session memory
*   [ ] Error recovery (agent reads command failures and proposes a fix)
*   [ ] App-launching support
*   [ ] Cross-platform (Linux/Kali) shell support
