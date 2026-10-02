# Jarvis AI Terminal Agent

An AI agent that runs inside a real, persistent PowerShell session on Windows. Give it a request in plain English (typed or spoken) and it plans commands, executes them, reads the output, recovers from errors, researches the web, and replies — sometimes out loud.

Every command actually runs on your machine.

---

## Features

- Natural language → real PowerShell commands, executed directly
- Multi-step agent loop (up to 8 iterations per request)
- Persistent PowerShell session — `cd`, env vars, and state carry over
- Web research via DuckDuckGo search and full-page fetching
- Voice mode: speech-to-text input and text-to-speech replies
- Persistent memory across sessions (`memory/ai_memory.txt`)
- Cross-session command history (`memory/session_history.json`)
- Multi-key rotation with automatic cooldown on rate limits
- Error recovery with AI-diagnosed fixes (max 3 retries per command)
- Blocklist for destructive commands (format, shutdown, rm -rf, etc.) that always require confirmation

---

## Requirements

- Windows
- Python 3.10+
- A free [Groq API key](https://console.groq.com)

---

## Install

```bash
git clone https://github.com/narkisiuria/Jarvis-AI-Terminal-Agent.git
cd Jarvis-AI-Terminal-Agent
pip install -e .
```

Optional voice dependencies:

```powershell
pip install SpeechRecognition pyttsx3 sounddevice numpy
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
# GROQ_API_KEY2=optional_second_key
# GROQ_API_KEY3=...
```

Up to 5 keys can be added for automatic rotation when hitting rate limits.

Launch:

```powershell
jarvis
```

---

## Usage

```
> open chrome and go to github
> analyze my project and tell me what it's about
> what's the latest news about OpenAI?
> search the web for the best way to structure a python package
> /voice
> /memory
```

---

## Commands

| Command | Description |
|---|---|
| `/help` | Show all commands |
| `/memory` | Show the AI's current memory |
| `/forget` | Wipe memory |
| `/history` | Last 10 steps this session |
| `/keys` | API key cooldown status |
| `/voice` | Toggle voice mode |
| `/voices` | List Windows TTS voices |
| `/clear` | Clear screen |
| `/toggle-think` | Show/hide the reasoning block |
| `/quit` | Exit and save |

---

## How it works

The model responds in a structured format that the host parses:

```
[THOUGHT] reasoning [/THOUGHT]
[REPLY] conversational reply [/REPLY]
[COMMANDS] raw PowerShell, one per line [/COMMANDS]
[TOOLS] WEB_SEARCH: query / WEB_FETCH: url [/TOOLS]
[MEMORY_UPDATE] new facts to save [/MEMORY_UPDATE]
```

Commands and tools execute, their real output is fed back to the model, and the loop continues until both `[COMMANDS]` and `[TOOLS]` are empty. The final `[REPLY]` is the answer.

---

## Limitations

- Windows only (Linux/WSL support is planned)
- Paywalled sites block the fetcher — falls back to Wikipedia, dev.to, and other open sources
- Voice STT requires internet (Google's free recognizer); TTS is offline
- Keep your work under Git — the AI has broad permissions on non-blocked commands

---

## Safety

Destructive patterns (`format`, `rm -rf`, `del /f`, `shutdown`, `diskpart`, `Stop-Process -Force`, `taskkill /f /im`, and others) are hardcoded-blocked and always require explicit confirmation.

Everything else runs without asking. Run in a VM or Windows Sandbox the first few times if you want a safety net.

---

## Roadmap

- Wake word activation
- Streaming voice replies
- Linux/WSL backend
- GUI automation
- Vector memory for smarter recall

---
