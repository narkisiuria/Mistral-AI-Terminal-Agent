# Terminal-AI-Agent v1.0

An AI that controls your real PowerShell terminal. Type a request in plain English, it turns it into a real command, and after you confirm it actually runs: creating files, writing to files, running programs, whatever you asked. Not a simulation. It remembers past requests and asks before guessing on unclear ones.

## How it works

1. A real PowerShell process is spawned and kept alive in the background, not a one-off subprocess per command.
2. You type a request in plain English.
3. Mistral AI translates it into a single real PowerShell command.
4. If the request is ambiguous, the AI asks a clarifying question instead of guessing.
5. The command is shown to you and **only runs after you confirm** (y/n).
6. Output is read back from the live shell and printed.
7. Recent requests are remembered during the session, and a short history is saved across restarts.

Because the same shell process stays alive the whole time, state persists naturally between commands — `cd`, environment variables, everything behaves like a real terminal session, because it is one.

## Features

- Plain-English → real PowerShell command
- Confirmation required before every command runs
- Clarifying questions on ambiguous requests
- Session memory (recalls recent requests/commands/output)
- Persistent memory across restarts (last few requests saved to disk)
- Live, stateful shell — not isolated one-shot commands

## Setup

1. Install dependencies:
   ```
   pip install mistralai python-dotenv
   ```
2. Create a `.env` file in the project root:
   ```
   MISTRAL_API_KEY2=your_api_key_here
   ```
3. Run:
   ```
   python main.py
   ```

## Usage

```
AI-CLI (PS C:\Users\you\project>) > create a file called notes.txt
proceed running: 'New-Item -ItemType File -Name notes.txt' (n/y)> y
...
```

Type `quit` or press `Ctrl+C` to exit, your recent requests are saved for next time.

## Roadmap

- [ ] Multi-step command chaining
- [ ] Error recovery (AI retries on failed commands)
- [ ] App-launching support
- [ ] Cross-platform (Linux/Kali) shell support

## Status

v1 complete and working: live shell, prompt detection, AI command translation, confirmation, clarification, and memory are all functional.

## Warning

This tool executes real commands on your real machine after your confirmation. Always read the command before approving it since the AI can make mistakes.
