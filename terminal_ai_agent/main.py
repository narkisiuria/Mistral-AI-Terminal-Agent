def main():
    import subprocess
    import time
    import os
    import re
    import sys
    import json
    from datetime import datetime
    from groq import Groq
    from dotenv import load_dotenv
    from colorama import init, Fore, Style
    from terminal_ai_agent.memory.save_and_load_memory import save_memory, load_memory

    init(autoreset=True)

    # ==========================================
    # VOICE IMPORTS
    # ==========================================
    try:
        import speech_recognition as sr
        import pyttsx3
        import sounddevice as sd
        import numpy as np
        VOICE_AVAILABLE = True
    except ImportError:
        VOICE_AVAILABLE = False
        sr = None
        pyttsx3 = None
        sd = None
        np = None

    # ==========================================
    # WEB TOOL IMPORTS
    # ==========================================
    try:
        import requests
        from bs4 import BeautifulSoup
        WEB_TOOLS_AVAILABLE = True
    except ImportError:
        requests = None
        BeautifulSoup = None
        WEB_TOOLS_AVAILABLE = False

    DDGS_CLASS = None
    try:
        from ddgs import DDGS as _DDGS
        DDGS_CLASS = _DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS as _DDGS2
            DDGS_CLASS = _DDGS2
        except ImportError:
            DDGS_CLASS = None

    # ==========================================
    # CONFIG
    # ==========================================
    MEMORY_DIR = "memory"
    AI_MEMORY_FILE = os.path.join(MEMORY_DIR, "ai_memory.txt")
    SESSION_HISTORY_FILE = os.path.join(MEMORY_DIR, "session_history.json")
    MAX_FEEDBACK_CHARS = 2500
    MAX_DISPLAY_CHARS = 5000
    KEY_COOLDOWN_SECONDS = 60
    MAX_AGENT_ITERATIONS = 8
    MAX_WEB_RESULTS = 5
    MAX_FETCH_CHARS = 3500
    MAX_TOOLS_PER_ITERATION = 5

    VOICE_SAMPLE_RATE = 16000
    VOICE_SILENCE_THRESHOLD = 500
    VOICE_SILENCE_DURATION = 1.4
    VOICE_MAX_DURATION = 20
    VOICE_START_TIMEOUT = 8

    # Commands / tools the AI sometimes emits as placeholders instead of leaving blank
    PLACEHOLDER_TOKENS = {"EMPTY", "NONE", "NULL", "N/A", "NA", "--", "-", "...", "N/A."}

    DANGEROUS_PATTERNS = [
        r"\bformat\b", r"\brm -rf\b", r"\bdel /f\b", r"\bdel /s\b", r"\bshutdown\b",
        r"\bstop-computer\b", r"\bdiskpart\b", r"\bcipher /w\b",
        r"\bRemove-Item -Recurse -Force C:\b", r"\breg delete\b",
        r"\bStop-Process -Force\b", r"\btaskkill /f /im\b"
    ]

    state = {
        "show_thoughts": True,
        "voice_mode": False,
        "recognizer": None,
        "tts": None,
    }

    def is_dangerous(cmd):
        return any(re.search(p, cmd.lower()) for p in DANGEROUS_PATTERNS)

    def truncate(text, max_chars):
        if len(text) <= max_chars:
            return text, False
        return text[:max_chars] + f"\n... [truncated, {len(text) - max_chars} more chars]", True

    def strip_chain_prefix(cmd):
        s = cmd.strip()
        if s.upper().startswith("CHAINING:"):
            s = s[len("CHAINING:"):].strip()
        return s

    def is_placeholder(text):
        """Returns True if the AI output a placeholder like EMPTY/NONE instead of leaving blank."""
        return text.strip().upper() in PLACEHOLDER_TOKENS

    def banner():
        print(Fore.CYAN + Style.BRIGHT + r"""
     ██  █████  ██████  ██    ██ ██ ███████
     ██ ██   ██ ██   ██ ██    ██ ██ ██
     ██ ███████ ██████  ██    ██ ██ ███████
██   ██ ██   ██ ██   ██  ██  ██  ██      ██
 █████  ██   ██ ██   ██   ████   ██ ███████
""" + Style.RESET_ALL)
        print(Fore.CYAN + "     Terminal AI Agent — Actor Mode" + Style.RESET_ALL)
        print(Fore.WHITE + "     Type " + Fore.YELLOW + "/help" + Fore.WHITE + " for commands, or just ask." + Style.RESET_ALL)
        if VOICE_AVAILABLE:
            print(Fore.WHITE + "     Type " + Fore.YELLOW + "/voice" + Fore.WHITE + " to enable voice mode. 🎤" + Style.RESET_ALL)
        if WEB_TOOLS_AVAILABLE and DDGS_CLASS:
            print(Fore.WHITE + "     Web research: " + Fore.GREEN + "enabled" + Style.RESET_ALL)
        else:
            print(Fore.WHITE + "     Web research: " + Fore.RED + "unavailable (pip install ddgs requests beautifulsoup4)" + Style.RESET_ALL)
        print()

    # ==========================================
    # WEB TOOLS
    # ==========================================
    def tool_web_search(query, max_results=MAX_WEB_RESULTS):
        if not DDGS_CLASS:
            return "[ERROR] Web search not available (missing ddgs library)."
        try:
            results = []
            with DDGS_CLASS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", "") or r.get("url", ""),
                        "snippet": r.get("body", "") or r.get("snippet", "")
                    })
            if not results:
                return f"[No results for: {query}]"

            output = f"Search results for: {query}\n\n"
            for i, r in enumerate(results, 1):
                output += f"[{i}] {r['title']}\n"
                output += f"    URL: {r['url']}\n"
                output += f"    {r['snippet']}\n\n"
            return output.strip()
        except Exception as e:
            return f"[ERROR] Search failed: {e}"

    def tool_web_fetch(url, max_chars=MAX_FETCH_CHARS):
        if not requests or not BeautifulSoup:
            return "[ERROR] Web fetch not available (missing requests/bs4)."
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

            if resp.status_code in (401, 403, 429):
                return (
                    f"[ERROR] {resp.status_code} from {url}. "
                    f"This site blocks automated scrapers (paywall/bot protection). "
                    f"Try a different source — prefer open sites like Wikipedia, blogs, "
                    f"dev.to, medium.com, news.ycombinator.com, arstechnica.com, theverge.com, "
                    f"or use the search snippet instead."
                )
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type:
                return f"[Fetched {url}, but content-type is {content_type}; not reading.]"

            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else url

            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r"[ \t]{2,}", " ", text)

            if len(text) > max_chars:
                text = text[:max_chars] + f"\n... [truncated at {max_chars} chars]"

            return f"# Page: {title}\n# URL: {url}\n\n{text}"
        except Exception as e:
            return f"[ERROR] Fetch failed for {url}: {e}"

    def parse_tool_call(line):
        line = line.strip()
        if not line or is_placeholder(line):
            return None
        if line.upper().startswith("WEB_SEARCH:"):
            return ("WEB_SEARCH", line.split(":", 1)[1].strip())
        if line.upper().startswith("WEB_FETCH:"):
            return ("WEB_FETCH", line.split(":", 1)[1].strip())
        return None

    def execute_tool(tool_name, arg):
        print(Fore.BLUE + f"  🔧 {tool_name}: {arg}" + Style.RESET_ALL)
        t0 = time.time()
        if tool_name == "WEB_SEARCH":
            result = tool_web_search(arg)
        elif tool_name == "WEB_FETCH":
            result = tool_web_fetch(arg)
        else:
            result = f"[ERROR] Unknown tool: {tool_name}"
        dt = time.time() - t0

        preview, _ = truncate(result, 600)
        if result.startswith("[ERROR]") or result.startswith("[No results"):
            print(Fore.RED + f"     {preview}" + Style.RESET_ALL)
        else:
            print(Fore.WHITE + f"     {preview}" + Style.RESET_ALL)
        print(Fore.WHITE + f"     ⏱  {dt:.2f}s" + Style.RESET_ALL)

        return result

    # ==========================================
    # VOICE ENGINE
    # ==========================================
    def init_voice():
        if not VOICE_AVAILABLE:
            return
        try:
            recognizer = sr.Recognizer()
            tts = pyttsx3.init()
            voices = tts.getProperty('voices')
            chosen = None
            for preference in ['david', 'mark', 'guy', 'male']:
                for v in voices:
                    if preference in v.name.lower():
                        chosen = v
                        break
                if chosen:
                    break
            if not chosen and voices:
                chosen = voices[0]
            if chosen:
                tts.setProperty('voice', chosen.id)
                print(Fore.GREEN + f"🔊 TTS voice: {chosen.name}" + Style.RESET_ALL)
            tts.setProperty('rate', 175)
            tts.setProperty('volume', 1.0)
            state["recognizer"] = recognizer
            state["tts"] = tts
        except Exception as e:
            print(Fore.RED + f"⚠️  Voice init failed: {e}" + Style.RESET_ALL)

    def strip_for_speech(text):
        if not text:
            return ""
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'[*_#>~|]', ' ', text)
        text = re.sub(
            r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF'
            r'✓✗✔❌⚠️🔊🎤🧠💬📝📖📜🔑🧹👋⏱️]',
            ' ', text
        )
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def speak(text, force=False):
        if not state["tts"]:
            return
        if not force and not state["voice_mode"]:
            return
        clean = strip_for_speech(text)
        if not clean:
            return
        try:
            state["tts"].say(clean)
            state["tts"].runAndWait()
        except Exception as e:
            print(Fore.RED + f"🔊 TTS error: {e}" + Style.RESET_ALL)

    def record_until_silence():
        chunk_dur = 0.1
        chunk_samples = int(VOICE_SAMPLE_RATE * chunk_dur)
        max_chunks = int(VOICE_MAX_DURATION / chunk_dur)
        silent_needed = int(VOICE_SILENCE_DURATION / chunk_dur)
        start_timeout_chunks = int(VOICE_START_TIMEOUT / chunk_dur)

        recorded = []
        silent_count = 0
        started = False

        try:
            stream = sd.InputStream(
                samplerate=VOICE_SAMPLE_RATE, channels=1,
                dtype='int16', blocksize=chunk_samples
            )
            stream.start()
        except Exception as e:
            print(Fore.RED + f"🎤 Mic open failed: {e}" + Style.RESET_ALL)
            return None

        try:
            for i in range(max_chunks):
                chunk, _ = stream.read(chunk_samples)
                recorded.append(chunk.copy())
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

                if rms > VOICE_SILENCE_THRESHOLD:
                    if not started:
                        print(Fore.GREEN + "🎤 (speaking...)" + Style.RESET_ALL)
                    started = True
                    silent_count = 0
                else:
                    if started:
                        silent_count += 1
                        if silent_count >= silent_needed:
                            break
                    else:
                        if i >= start_timeout_chunks:
                            print(Fore.YELLOW + "🎤 No speech detected (timeout)." + Style.RESET_ALL)
                            return None
        except KeyboardInterrupt:
            return None
        finally:
            try:
                stream.stop(); stream.close()
            except Exception:
                pass

        if not started:
            return None
        return np.concatenate(recorded, axis=0)

    def listen():
        if not state["recognizer"]:
            print(Fore.RED + "🎤 Voice not initialized. Run /voice to enable." + Style.RESET_ALL)
            return None
        print(Fore.CYAN + "🎤 Listening... (speak now)" + Style.RESET_ALL)
        audio_np = record_until_silence()
        if audio_np is None:
            return None
        try:
            pcm_bytes = audio_np.tobytes()
            audio_data = sr.AudioData(pcm_bytes, VOICE_SAMPLE_RATE, 2)
            print(Fore.CYAN + "🎤 Transcribing..." + Style.RESET_ALL)
            return state["recognizer"].recognize_google(audio_data)
        except sr.UnknownValueError:
            print(Fore.RED + "🎤 Couldn't understand. Try again." + Style.RESET_ALL)
            return None
        except sr.RequestError as e:
            print(Fore.RED + f"🎤 Recognition service error: {e}" + Style.RESET_ALL)
            return None
        except Exception as e:
            print(Fore.RED + f"🎤 Transcribe error: {e}" + Style.RESET_ALL)
            return None

    # ==========================================
    # MEMORY
    # ==========================================
    def load_ai_memory():
        os.makedirs(MEMORY_DIR, exist_ok=True)
        if not os.path.exists(AI_MEMORY_FILE):
            return "No memory yet. This is your first interaction."
        with open(AI_MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()

    def save_ai_memory(new_facts):
        if new_facts and new_facts.strip().upper() != "NONE":
            with open(AI_MEMORY_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n- {new_facts.strip()}")
            print(Fore.GREEN + "📝 Memory updated." + Style.RESET_ALL)

    def clear_ai_memory():
        if os.path.exists(AI_MEMORY_FILE):
            with open(AI_MEMORY_FILE, "w", encoding="utf-8") as f:
                f.write("")
        print(Fore.GREEN + "🧹 Memory cleared." + Style.RESET_ALL)

    def load_session_history():
        os.makedirs(MEMORY_DIR, exist_ok=True)
        if not os.path.exists(SESSION_HISTORY_FILE):
            return []
        try:
            with open(SESSION_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_session_history(history):
        os.makedirs(MEMORY_DIR, exist_ok=True)
        with open(SESSION_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-50:], f, indent=2, ensure_ascii=False)

    # ==========================================
    # MULTI-KEY CLIENT
    # ==========================================
    load_dotenv()
    key_names = ["GROQ_API_KEY", "GROQ_API_KEY2", "GROQ_API_KEY3", "GROQ_API_KEY4", "GROQ_API_KEY5"]
    clients = []
    for name in key_names:
        val = os.getenv(name)
        if val:
            clients.append({"name": name, "client": Groq(api_key=val), "cooldown_until": 0})

    if not clients:
        print(Fore.RED + "❌ No GROQ_API_KEY found in .env" + Style.RESET_ALL)
        sys.exit(1)

    print(Fore.GREEN + f"✔ Loaded {len(clients)} Groq key(s): {', '.join(c['name'] for c in clients)}" + Style.RESET_ALL)

    def is_rate_limit(err):
        s = str(err).lower()
        return ("413" in s or "429" in s or "rate_limit" in s
                or "tokens per minute" in s or "request too large" in s)

    def call_ai(system_prompt, user_content):
        now = time.time()
        available = [c for c in clients if c["cooldown_until"] <= now]
        if not available:
            soonest = min(c["cooldown_until"] for c in clients) - now
            print(Fore.RED + f"❌ All keys on cooldown. Retry in {int(soonest)}s." + Style.RESET_ALL)
            raise RuntimeError("All keys on cooldown")

        last_err = None
        for entry in available:
            try:
                t0 = time.time()
                print(Fore.CYAN + f"🧠 AI thinking (key: {entry['name']})..." + Style.RESET_ALL)
                resp = entry["client"].chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                )
                dt = time.time() - t0
                print(Fore.CYAN + f"✔ AI responded in {dt:.1f}s" + Style.RESET_ALL)
                return resp.choices[0].message.content
            except Exception as e:
                last_err = e
                if is_rate_limit(e):
                    entry["cooldown_until"] = time.time() + KEY_COOLDOWN_SECONDS
                    print(Fore.YELLOW + f"⚠️  {entry['name']} rate-limited → benched {KEY_COOLDOWN_SECONDS}s." + Style.RESET_ALL)
                    continue
                print(Fore.RED + f"AI error on {entry['name']}: {e}" + Style.RESET_ALL)
                raise
        raise last_err if last_err else RuntimeError("No working keys")

    # ==========================================
    # POWERSHELL
    # ==========================================
    proc = subprocess.Popen(
        ["powershell.exe", "-NoLogo", "-NoExit"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1
    )

    def read_until_prompt(proc, timeout=90):
        output = ""
        start = time.time()
        while True:
            if time.time() - start > timeout:
                break
            char = proc.stdout.read(1)
            if not char:
                break
            output += char
            stripped = output.rstrip()
            if stripped.endswith(">") and "PS " in stripped.splitlines()[-1]:
                break
        return output

    def parse_result(raw):
        lines = raw.split("\n")
        echoed = lines[0].strip() if lines else ""
        prompt = lines[-1].strip() if lines else ""
        output_lines = lines[1:-1]
        while output_lines and not output_lines[0].strip():
            output_lines.pop(0)
        while output_lines and not output_lines[-1].strip():
            output_lines.pop()
        return echoed, "\n".join(output_lines), prompt

    def command_actually_failed(result):
        lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
        marker = lines[-2] if len(lines) >= 2 else ""
        return marker == "__CMD_FAILED__"

    # ==========================================
    # STARTUP
    # ==========================================
    print(Fore.CYAN + "Booting PowerShell session..." + Style.RESET_ALL)
    time.sleep(1.5)
    read_until_prompt(proc)

    proc.stdin.write(
        "chcp 65001 > $null; "
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "[Console]::InputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$PSDefaultParameterValues['Out-String:Width'] = 300; "
        "$PSDefaultParameterValues['Format-Table:AutoSize'] = $true\n"
    )
    proc.stdin.flush()
    time.sleep(0.7)
    read_until_prompt(proc)

    proc.stdin.write("echo __FLUSH__\n")
    proc.stdin.flush()
    time.sleep(0.6)
    read_until_prompt(proc)

    os.system("cls")
    banner()

    proc.stdin.write("echo ready\n")
    proc.stdin.flush()
    time.sleep(0.5)
    result = read_until_prompt(proc)
    _, _, prompt = parse_result(result)

    if VOICE_AVAILABLE:
        init_voice()

    # ==========================================
    # SYSTEM PROMPT
    # ==========================================
    system_prompt = (
        '''You are JARVIS, an advanced AI controlling a Windows machine via a real PowerShell session,
            with the ability to research the web.
            You are NOT a translator. You are an ACTOR. You DO things, you don't just explain them.
            You can open applications, create files, run programs, research the web, and interact with the OS.
            Do not ask for permission. Just output the commands/tools to be executed.

            Current memory about the user and their system:
            ---
            {memory_context}
            ---

            You operate in an AGENT LOOP:
            - You output commands (PowerShell) and/or tools (web research).
            - You will then be shown their REAL results.
            - Based on those results, you can run MORE commands/tools, or give your FINAL ANSWER.
            - Only output a final [REPLY] when you have NO commands and NO tools left to run.

            You must respond in the following exact format:
            [THOUGHT]
            Your step-by-step reasoning here.
            [/THOUGHT]
            [REPLY]
            Your conversational reply. If you're just executing, output NONE.
            [/REPLY]
            [COMMANDS]
            PowerShell command 1
            PowerShell command 2
            [/COMMANDS]
            [TOOLS]
            WEB_SEARCH: search query here
            WEB_FETCH: https://example.com/article
            [/TOOLS]
            [MEMORY_UPDATE]
            - Any new fact learned about the user, their preferences, or their project
            [/MEMORY_UPDATE]

            If you learn nothing new, output:
            [MEMORY_UPDATE]
            NONE
            [/MEMORY_UPDATE]

            CRITICAL: If a block has no content, leave it COMPLETELY EMPTY.
            Do NOT put the word "EMPTY", "NONE", "N/A", or anything else inside an unused block.
            An empty [COMMANDS] block looks like this: [COMMANDS][/COMMANDS] on a single line.

            Only give a final [REPLY] when both [COMMANDS] and [TOOLS] are empty.

            STOPPING RULES (VERY IMPORTANT):
            - You get a LIMITED number of iterations. Do not waste them.
            - If you already have enough info from a search snippet OR a fetched page, STOP and give [REPLY].
            - NEVER run the same WEB_SEARCH query twice. If a search didn't work, change strategy or just answer.
            - If a WEB_FETCH returns 401/403/429, do NOT try another URL from the same domain.
              Try a different site from the search results (Wikipedia, blogs, dev.to, medium.com,
              arstechnica.com, theverge.com, news.ycombinator.com) — or just answer from the snippets.
            - You will be reminded to wrap up in your final iterations. When you see that reminder,
              output [REPLY] with your best answer and leave both blocks empty.

            WHEN TO USE WHICH:
            - [COMMANDS] for local actions: opening apps, creating/editing files, running programs, git, etc.
            - [TOOLS] for anything on the internet:
                * WEB_SEARCH: find current info, articles, docs, news, tutorials.
                * WEB_FETCH: read the full text of a specific URL.
              Use tools whenever the user asks about "current", "latest", "recent", "today's", or anything
              you don't already know from training.
              If search snippets already contain the answer, you do NOT need to fetch — just answer.

            WEB RESEARCH PATTERN:
            1. [TOOLS] WEB_SEARCH: <query>
            2. Review results. If snippets answer the question, go to step 4.
            3. [TOOLS] WEB_FETCH: <the most promising OPEN url>  (avoid reuters/wsj/bloomberg/paywalled)
            4. Summarize for the user in [REPLY].
            - If the user says "latest" or "current", and your only info is from session history older than today, do a FRESH search instead of relying on old results.

            VOICE MODE NOTE: When voice mode is on, your [REPLY] will be SPOKEN aloud.
            Keep it conversational, natural, and concise. Avoid code, URLs, and special symbols in [REPLY].

            CRITICAL RULES FOR [COMMANDS]:
            - RAW PowerShell commands. No markdown, no backticks.
            - One command per line. Do NOT add "CHAINING:" label anywhere.
            - NEVER use here-strings (@""@). All commands MUST be single-line.
            - Do not use ';' inside quotes or arguments.
            - To open an app: `Start-Process notepad -ArgumentList "file.txt"`.
            - Never invent flags or cmdlets that don't exist in PowerShell.
            - Assume current working directory is correct — don't cd unless asked.

            OUTPUT SIZE RULES:
            - NEVER run `Get-ChildItem -Recurse` without filters.
            - ALWAYS exclude heavy dirs: `-Exclude .git,node_modules,__pycache__,venv,.venv,build,dist,*.pyc`
            - ALWAYS cap output: pipe through `Select-Object -First 50` for lists.
            - Read files with `-TotalCount 100` cap.

            Host slash commands (do NOT run as PowerShell): /help, /memory, /forget, /history, /keys, /voice, /voices, /clear, /toggle-think, /quit.'''
    )

    failure_system_prompt = (
        '''You are a PowerShell error-diagnosis assistant.
            You will be given a command that failed and its raw error output.
            Your job: diagnose the error, and if there's a clear, safe, one-command fix, propose it.

            Rules:
            - If there's a clear fix, output EXACTLY: FIXABLE: <the fixed command>
            - Otherwise, output a short plain-text explanation (2-3 sentences, no commands).
            - Never output more than one command after "FIXABLE:".
            - Never use ";" inside the fixed command's own content.
            - Never use "&&" (not valid in PowerShell) — use ";" or "if ($?) { ... }".
            - Never use here-strings. All commands MUST be single-line.
            - If the fix is "the file doesn't exist", output an explanation, not a fix.
            - If the command was a placeholder like EMPTY/NONE/N/A, tell the caller to skip it (no fix).'''
    )

    # ==========================================
    # EXECUTE ONE COMMAND
    # ==========================================
    def execute_command(cmd, current_prompt):
        cmd = strip_chain_prefix(cmd)
        if not cmd or is_placeholder(cmd):
            return True, "", current_prompt

        if is_dangerous(cmd):
            print(Fore.RED + f"\n⚠️  DANGER: destructive command: {cmd}" + Style.RESET_ALL)
            speak("Warning. A dangerous command was blocked.", force=True)
            confirm = input(Fore.RED + "Override and run? (y/n) > " + Style.RESET_ALL).lower()
            if confirm != 'y':
                print(Fore.RED + "❌ Aborted." + Style.RESET_ALL)
                return False, "[user aborted dangerous command]", current_prompt

        t0 = time.time()
        print(Fore.YELLOW + f"  > {cmd}" + Style.RESET_ALL)
        real_cmd = cmd + "; if ($?) {'success'} else {'__CMD_FAILED__'}\n"
        proc.stdin.write(real_cmd)
        proc.stdin.flush()
        time.sleep(0.4)
        result = read_until_prompt(proc)

        attempts = 0
        resolved = not command_actually_failed(result)
        gave_up = False

        while command_actually_failed(result) and attempts < 3:
            attempts += 1
            print(Fore.RED + f"  ⚠️  Failed (retry {attempts}/3)" + Style.RESET_ALL)
            try:
                failure_response = call_ai(failure_system_prompt, f"failed command: {cmd}\nreason: {result[:1500]}")
            except Exception:
                gave_up = True
                break

            if "FIXABLE: " in failure_response:
                fix_cmd = strip_chain_prefix(failure_response.split("FIXABLE: ", 1)[1].strip())
                if is_placeholder(fix_cmd):
                    gave_up = True
                    break
                if is_dangerous(fix_cmd):
                    print(Fore.RED + f"\n⚠️  DANGER in fix: {fix_cmd}" + Style.RESET_ALL)
                    cf = input(Fore.RED + "Override? (y/n) > " + Style.RESET_ALL).lower()
                    if cf != 'y':
                        break
                cmd = fix_cmd
                print(Fore.YELLOW + f"  > {cmd}" + Style.RESET_ALL)
                real_cmd = cmd + "; if ($?) {'success'} else {'__CMD_FAILED__'}\n"
                proc.stdin.write(real_cmd)
                proc.stdin.flush()
                time.sleep(0.4)
                result = read_until_prompt(proc)
                resolved = not command_actually_failed(result)
            else:
                print(Fore.RED + "  ℹ " + failure_response + Style.RESET_ALL)
                gave_up = True
                break

        dt = time.time() - t0
        _, output, new_prompt = parse_result(result)
        clean_output = "\n".join(l for l in output.strip().split("\n") if l.strip() not in ("success", "__CMD_FAILED__"))

        display_text, _ = truncate(clean_output, MAX_DISPLAY_CHARS)
        if resolved:
            if display_text:
                print(Fore.GREEN + display_text + Style.RESET_ALL)
            print(Fore.WHITE + f"  ⏱  {dt:.2f}s" + Style.RESET_ALL)
        elif not gave_up:
            print(Fore.RED + "Command failed after retries:" + Style.RESET_ALL)
            print(Fore.RED + display_text + Style.RESET_ALL)

        feedback_text, _ = truncate(clean_output, MAX_FEEDBACK_CHARS)
        return resolved, feedback_text, new_prompt

    # ==========================================
    # AGENT TURN
    # ==========================================
    def run_agent_turn(client_request, memory_context, current_prompt, session_history):
        recent = session_history[-3:]
        history_text = "\n".join(
            f"Request: {h['request']}\nStep: {h.get('command') or h.get('tool')}\nOutput: {h['output'][:400]}"
            for h in recent
        )

        user_content = (
            f"{memory_context}\n\n"
            f"Recent session history:\n{history_text}\n\n"
            f"Current request: {client_request}"
        )

        turn_start = time.time()
        steps_run = 0
        iterations_used = 0

        for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
            iterations_used = iteration
            try:
                ai_response = call_ai(system_prompt.format(memory_context=memory_context), user_content)
            except Exception as e:
                print(Fore.RED + f"❌ AI call failed, aborting turn: {e}" + Style.RESET_ALL)
                break

            thought_match = re.search(r"\[THOUGHT\](.*?)\[/THOUGHT\]", ai_response, re.DOTALL)
            thought = thought_match.group(1).strip() if thought_match else ""

            reply_match = re.search(r"\[REPLY\](.*?)\[/REPLY\]", ai_response, re.DOTALL)
            reply = reply_match.group(1).strip() if reply_match else "NONE"

            commands = []
            cmd_match = re.search(r"\[COMMANDS\](.*?)\[/COMMANDS\]", ai_response, re.DOTALL)
            if cmd_match:
                commands = [strip_chain_prefix(l) for l in cmd_match.group(1).strip().split("\n") if l.strip()]
                commands = [c for c in commands if c and not is_placeholder(c)]

            tools = []
            tools_match = re.search(r"\[TOOLS\](.*?)\[/TOOLS\]", ai_response, re.DOTALL)
            if tools_match:
                for line in tools_match.group(1).strip().split("\n"):
                    parsed = parse_tool_call(line)
                    if parsed:
                        tools.append(parsed)
                tools = tools[:MAX_TOOLS_PER_ITERATION]

            memory_update = "NONE"
            mem_match = re.search(r"\[MEMORY_UPDATE\](.*?)\[/MEMORY_UPDATE\]", ai_response, re.DOTALL)
            if mem_match:
                memory_update = mem_match.group(1).strip()

            if thought and state["show_thoughts"]:
                print(Fore.MAGENTA + f"\n🤖 (thinking): {thought}" + Style.RESET_ALL)

            if reply and reply.upper() != "NONE":
                print(Fore.CYAN + f"\n💬 JARVIS: {reply}" + Style.RESET_ALL)
                speak(reply)

            if memory_update and memory_update.upper() != "NONE":
                save_ai_memory(memory_update)

            if not commands and not tools:
                total_dt = time.time() - turn_start
                print(Fore.WHITE + f"\n── Turn done · {iterations_used} iter · {steps_run} step · {total_dt:.1f}s ──" + Style.RESET_ALL)
                return current_prompt, session_history

            # Execute commands
            step_outputs = []
            if commands:
                print(Fore.YELLOW + f"\n⚡ Commands (iteration {iteration}/{MAX_AGENT_ITERATIONS}):" + Style.RESET_ALL)
                for cmd in commands:
                    resolved, feedback, current_prompt = execute_command(cmd, current_prompt)
                    steps_run += 1
                    step_outputs.append({
                        "type": "COMMAND",
                        "name": cmd,
                        "output": feedback,
                        "success": resolved
                    })
                    session_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "request": client_request,
                        "command": cmd,
                        "output": feedback
                    })

            # Execute tools
            if tools:
                print(Fore.BLUE + f"\n🌐 Web tools (iteration {iteration}/{MAX_AGENT_ITERATIONS}):" + Style.RESET_ALL)
                for tool_name, arg in tools:
                    result = execute_tool(tool_name, arg)
                    steps_run += 1
                    capped, _ = truncate(result, MAX_FEEDBACK_CHARS)
                    step_outputs.append({
                        "type": "TOOL",
                        "name": f"{tool_name}: {arg}",
                        "output": capped,
                        "success": not result.startswith("[ERROR]")
                    })
                    session_history.append({
                        "timestamp": datetime.now().isoformat(),
                        "request": client_request,
                        "tool": f"{tool_name}: {arg}",
                        "output": capped
                    })

            # Feed everything back
            output_text = "\n\n".join(
                f"[{s['type']}] {s['name']}\nSuccess: {s['success']}\nOutput:\n{s['output']}"
                for s in step_outputs
            )

            # Wrap-up nudge when we're near the end
            remaining = MAX_AGENT_ITERATIONS - iteration
            if remaining <= 1:
                wrap_note = (
                    f"\n\n⚠️  WRAP-UP: You are on iteration {iteration} of {MAX_AGENT_ITERATIONS}. "
                    f"You have {remaining} iteration(s) left. STOP gathering more info NOW. "
                    f"Give your best FINAL ANSWER in [REPLY] and leave [COMMANDS] and [TOOLS] EMPTY."
                )
            elif remaining <= 3:
                wrap_note = (
                    f"\n\n(Note: You have {remaining} iterations left. If you have enough to answer, "
                    f"give the FINAL ANSWER in [REPLY] and leave both blocks EMPTY.)"
                )
            else:
                wrap_note = ""

            user_content = (
                f"{memory_context}\n\n"
                f"Original request: {client_request}\n\n"
                f"You just ran these steps:\n---\n{output_text}\n---\n\n"
                f"Now either:\n"
                f"1. Output MORE commands in [COMMANDS] or tools in [TOOLS], OR\n"
                f"2. If you have enough info, output the FINAL ANSWER in [REPLY] and leave both "
                f"[COMMANDS] and [TOOLS] empty.{wrap_note}"
            )

        # If loop ends without a final answer, force one
        print(Fore.YELLOW + f"⚠️  Iteration budget exhausted. Asking AI for a final summary..." + Style.RESET_ALL)
        try:
            force_prompt = (
                f"{memory_context}\n\n"
                f"Original request: {client_request}\n\n"
                f"You ran out of iterations. Based on everything you gathered, "
                f"give your FINAL ANSWER now in [REPLY]. Leave [COMMANDS] and [TOOLS] empty."
            )
            final_response = call_ai(system_prompt.format(memory_context=memory_context), force_prompt)
            reply_match = re.search(r"\[REPLY\](.*?)\[/REPLY\]", final_response, re.DOTALL)
            if reply_match:
                reply = reply_match.group(1).strip()
                if reply and reply.upper() != "NONE":
                    print(Fore.CYAN + f"\n💬 JARVIS: {reply}" + Style.RESET_ALL)
                    speak(reply)
        except Exception as e:
            print(Fore.RED + f"Couldn't get final answer: {e}" + Style.RESET_ALL)

        return current_prompt, session_history

    # ==========================================
    # SLASH COMMANDS
    # ==========================================
    def print_help():
        print(Fore.CYAN + "\n📖 Available commands:" + Style.RESET_ALL)
        print(Fore.YELLOW + "  /help" + Fore.WHITE + "           Show this help")
        print(Fore.YELLOW + "  /memory" + Fore.WHITE + "         Show the AI's current memory about you")
        print(Fore.YELLOW + "  /forget" + Fore.WHITE + "         Wipe the AI's memory")
        print(Fore.YELLOW + "  /history" + Fore.WHITE + "        Show last 10 commands from session")
        print(Fore.YELLOW + "  /keys" + Fore.WHITE + "           Show API key cooldown status")
        print(Fore.YELLOW + "  /voice" + Fore.WHITE + "          Toggle voice mode")
        print(Fore.YELLOW + "  /voices" + Fore.WHITE + "         List TTS voices")
        print(Fore.YELLOW + "  /clear" + Fore.WHITE + "          Clear the screen")
        print(Fore.YELLOW + "  /toggle-think" + Fore.WHITE + "   Show/hide AI's [THOUGHT] block")
        print(Fore.YELLOW + "  /quit" + Fore.WHITE + "           Exit\n")
        print(Fore.CYAN + "💡 Try asking:" + Style.RESET_ALL)
        print(Fore.WHITE + "  • \"search the web for the latest Python 3.14 features\"" + Style.RESET_ALL)
        print(Fore.WHITE + "  • \"what's the current price of bitcoin?\"" + Style.RESET_ALL)
        print(Fore.WHITE + "  • \"research the best way to structure a python package and save notes to notes.txt\"" + Style.RESET_ALL + "\n")

    def handle_slash(cmd, session_history):
        cmd = cmd.lower().strip()

        if cmd == "/help":
            print_help(); return True
        if cmd == "/memory":
            mem = load_ai_memory()
            print(Fore.CYAN + "\n🧠 Current AI memory:" + Style.RESET_ALL)
            print(Fore.WHITE + (mem if mem else "(empty)") + Style.RESET_ALL + "\n")
            return True
        if cmd == "/forget":
            confirm = input(Fore.RED + "Wipe all AI memory? (y/n) > " + Style.RESET_ALL).lower()
            if confirm == 'y':
                clear_ai_memory()
            else:
                print(Fore.YELLOW + "Cancelled." + Style.RESET_ALL)
            return True
        if cmd == "/history":
            recent = session_history[-10:]
            print(Fore.CYAN + f"\n📜 Last {len(recent)} steps:" + Style.RESET_ALL)
            for h in recent:
                label = h.get('command') or h.get('tool') or "?"
                print(Fore.YELLOW + "  • " + Fore.WHITE + f"{label[:100]}" + Style.RESET_ALL)
            print()
            return True
        if cmd == "/keys":
            now = time.time()
            print(Fore.CYAN + "\n🔑 API key status:" + Style.RESET_ALL)
            for c in clients:
                remaining = c["cooldown_until"] - now
                if remaining > 0:
                    print(Fore.RED + f"  ✗ {c['name']} — benched for {int(remaining)}s" + Style.RESET_ALL)
                else:
                    print(Fore.GREEN + f"  ✓ {c['name']} — ready" + Style.RESET_ALL)
            print()
            return True
        if cmd == "/voice":
            if not VOICE_AVAILABLE:
                print(Fore.RED + "❌ Voice libs not installed." + Style.RESET_ALL)
                return True
            if not state["tts"]:
                init_voice()
                if not state["tts"]:
                    return True
            state["voice_mode"] = not state["voice_mode"]
            status = "ON" if state["voice_mode"] else "OFF"
            color = Fore.GREEN if state["voice_mode"] else Fore.YELLOW
            print(color + f"🎤 Voice mode: {status}" + Style.RESET_ALL)
            if state["voice_mode"]:
                speak("Voice mode activated.", force=True)
            else:
                speak("Voice mode deactivated.", force=True)
            return True
        if cmd == "/voices":
            if not state["tts"]:
                print(Fore.RED + "❌ TTS not initialized." + Style.RESET_ALL); return True
            voices = state["tts"].getProperty('voices')
            print(Fore.CYAN + "\n🔊 Available voices:" + Style.RESET_ALL)
            for i, v in enumerate(voices):
                print(Fore.YELLOW + f"  [{i}] " + Fore.WHITE + f"{v.name}" + Style.RESET_ALL)
            print()
            return True
        if cmd == "/clear":
            os.system("cls"); banner(); return True
        if cmd == "/toggle-think":
            state["show_thoughts"] = not state["show_thoughts"]
            print(Fore.GREEN + f"🧠 Thought display: {'ON' if state['show_thoughts'] else 'OFF'}" + Style.RESET_ALL)
            return True
        if cmd == "/quit":
            return False
        print(Fore.RED + f"Unknown command: {cmd}. Try /help" + Style.RESET_ALL)
        return True

    # ==========================================
    # MAIN LOOP
    # ==========================================
    past_requests = []
    old_memory = load_ai_memory()
    session_history = load_session_history()

    try:
        while True:
            if state["voice_mode"]:
                print(Fore.CYAN + "\n🎤 Press Enter to speak (or type a command):" + Style.RESET_ALL)
                try:
                    raw = input(Fore.YELLOW + "> " + Style.RESET_ALL)
                except EOFError:
                    break
                if raw.strip() == "":
                    spoken = listen()
                    if spoken:
                        print(Fore.CYAN + f"🎤 You said: " + Style.RESET_ALL + spoken)
                        client_request = spoken
                    else:
                        continue
                else:
                    client_request = raw
            else:
                try:
                    client_request = input(Fore.YELLOW + f"\nAI-CLI ({prompt})> " + Style.RESET_ALL)
                except EOFError:
                    break

            if not client_request.strip():
                continue

            if client_request.startswith("/"):
                if client_request.lower().strip() in ("/quit", "/exit"):
                    save_memory(past_requests)
                    save_session_history(session_history)
                    print(Fore.YELLOW + "\n👋 Saved. Goodbye." + Style.RESET_ALL)
                    if state["voice_mode"]:
                        speak("Goodbye.", force=True)
                    sys.exit(0)
                handle_slash(client_request, session_history)
                continue

            past_requests.append(client_request)
            recent_past = past_requests[-4:]
            session_summary = "LAST USER REQUESTS:\n" + "\n".join(f"{i}: {r}" for i, r in enumerate(recent_past, 1))
            memory_context = f"{old_memory}\n\n{session_summary}"

            prompt, session_history = run_agent_turn(client_request, memory_context, prompt, session_history)
            save_session_history(session_history)

    except KeyboardInterrupt:
        save_memory(past_requests)
        save_session_history(session_history)
        print(Fore.YELLOW + "\n\n👋 Interrupted. Saved. Goodbye." + Style.RESET_ALL)
        sys.exit(0)

main()