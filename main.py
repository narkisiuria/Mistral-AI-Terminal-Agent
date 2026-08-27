import subprocess
import time
import os
from mistralai.client import Mistral
from dotenv import load_dotenv
import shlex
import sys
from memory.save_and_load_memory import save_memory
from memory.save_and_load_memory import load_memory

proc = subprocess.Popen(
    ["powershell.exe", "-NoLogo", "-NoExit"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

def read_until_prompt(proc):
    output = ""
    while True:
        char = proc.stdout.read(1)
        output += char
        if output.rstrip().endswith(">") and "PS " in output.splitlines()[-1]:
            break
        
    return output

def parse_result(raw):
    lines = raw.split("\n")
    
    echoed_command = lines[0].strip()
    prompt = lines[-1].strip()
    output_lines = lines[1:-1]
    
    while output_lines and output_lines[0].strip() == "":
        output_lines.pop(0)
    while output_lines and output_lines[-1].strip() == "":
        output_lines.pop()
    
    output = "\n".join(output_lines)
    
    return echoed_command, output, prompt


print("loading API key...")
load_dotenv()
api_key = os.getenv("MISTRAL_API_KEY2")

if not api_key:
    print("Error: MISTRAL_API_KEY2 not found in your environment variables (.env file).")
    sys.exit(1)
    
print("successfuly finished loading API key")
client = Mistral(api_key=api_key)

def command_actually_failed(result):
    lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
    marker_line = lines[-2] if len(lines) >= 2 else ""
    return marker_line == "__CMD_FAILED__"

def call_mistral(system_prompt, user_content):
    """Helper function to send data to Mistral AI."""
    try:
        print("AI proccessing request...")
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
        )
        print("AI finished proccessing request")
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"Error communicating with Mistral AI: {e}")
        sys.exit(1)


system_prompt = (
    '''You are a command-translation engine for a Windows PowerShell terminal.
        Your job: convert the user's plain-English request into either ONE valid PowerShell command, or a CHAINING of multiple commands.

        Rules:
        - Output ONLY the raw command (or CHAINING line). No explanation, no markdown, no backticks, no extra text.
        - Whenever a request can be broken into multiple separate commands, PREFER outputting CHAINING even if a single command could technically do it — chaining is preferred over single complex commands. Format: CHAINING: command1;command2;command3
        - Never use ";" inside an individual command's own content (e.g. inside a commit message) — since ";" is the separator between chained commands. Rephrase to avoid needing one.
        - Never invent flags or cmdlets that don't exist in PowerShell.
        - If the request is ambiguous or unsafe to guess (e.g. could delete/overwrite something unintended), output exactly: CLARIFY: <short question>
        - Assume current working directory is already correct — don't cd unless explicitly asked.
        - Prefer built-in PowerShell cmdlets over external tools unless the user names one.
        - If the user's request is a question you can answer directly (e.g. using the memory context provided, general knowledge,
        or explaining something) rather than something that needs a real system action,
        output an `echo "<your answer>"` command instead of searching for an unrelated real cmdlet.
        - You are given two kinds of context: "LAST USER REQUESTS" (old, saved from a previous run) and "Recent session history" (fresh, from THIS current session). When they conflict, always trust "Recent session history" over "LAST USER REQUESTS" — the session history is more current and accurate.'''
    )

failure_system_prompt = (
    '''You are a PowerShell error-diagnosis assistant.
        You will be given a command that failed and its raw error output.

        Your job: diagnose the error, and if there's a clear, safe, one-command fix, propose it.

        Rules:
        - If there's a clear fix, output EXACTLY: FIXABLE: <the fixed command>
        - If there's no safe automatic fix (e.g. needs user input, missing file, permissions issue), output a short plain-text explanation instead (2-3 sentences, no commands).
        - Never output more than one command after "FIXABLE:".
        - Never use ";" inside the fixed command's own content.
        - Any fix command must be valid PowerShell syntax. Never use "&&" (not valid in PowerShell) — use ";" to sequence commands instead, or "if ($?) { ... }" for conditional execution.'''
    )

time.sleep(0.5)
read_until_prompt(proc)  
shell = "echo hi\n"
os.system("cls")
proc.stdin.write(shell)
proc.stdin.flush()
time.sleep(0.5)
result = read_until_prompt(proc)
cmd, output, prompt = parse_result(result)
path = prompt.split()[1]
client_request = ""
MEMORY_FILE = "memory/last_requests.txt"

past_requests = []
memory_context = load_memory()
session_history = []
old_memory = load_memory()

client_request = ""
try:
    while True:        
        client_request = input(f"AI-CLI ({prompt})> ")
        if client_request == "quit":
            save_memory(past_requests)
            sys.exit(0)

        past_requests.append(client_request)
        recent_past = past_requests[-4:]
        session_summary = "LAST USER REQUESTS (this session):\n" + "\n".join(f"{i}: {r}" for i, r in enumerate(recent_past, 1))
        memory_context = f"{old_memory}\n\n{session_summary}"
        user_content = f"{memory_context}\n\nCurrent request: {client_request}"
        
        recent = session_history[-3:]
        history_text = "\n".join(f"Request: {h['request']}\nCommand: {h['command']}\nOutput: {h['output']}" for h in recent)
        user_content = f"{memory_context}\n\nRecent session history:\n{history_text}\n\nCurrent request: {client_request}"
        
        shell = call_mistral(system_prompt, user_content)
        if shell.split(":")[0] == "CLARIFY":
            answer = input(f"{shell} ")
            user_content = f"{user_content}\nClarification: {answer}"
            shell = call_mistral(user_content=user_content, system_prompt=system_prompt)
        
        if shell.split(":")[0] == "CHAINING":
            after_label = shell.split(":", 1)[1]
            output_list = after_label.split(";")
            output_list = [cmd.strip() for cmd in output_list]
            
            print("Full chain planned:")
            for i, cmd in enumerate(output_list, 1):
                print(f"  {i}. {cmd}")
            
            confirmation = input("proceed running this chain? (n/y)> ")
            
            if confirmation == "y" or confirmation == "":
                for cmd in output_list:
                    real_cmd = cmd + "; if ($?) {'success'} else {'__CMD_FAILED__'}\n"
                    proc.stdin.write(real_cmd)
                    proc.stdin.flush()
                    time.sleep(0.5)
                    result = read_until_prompt(proc)

                    attempts = 0
                    resolved = not command_actually_failed(result)
                    gave_up_with_explanation = False

                    while command_actually_failed(result) and attempts < 3:
                        attempts += 1
                        print(f"failure detected (fix attempt no. {attempts})")
                        failure_response = call_mistral(failure_system_prompt, f"failed command: {cmd}\nreason: {result}")

                        if "FIXABLE: " in failure_response:
                            fix_cmd = failure_response.split("FIXABLE: ", 1)[1].strip()
                            confirm_fix = input(f"proceed running fix: '{fix_cmd}' (n/y)> ")

                            if confirm_fix == "y" or confirm_fix == "":
                                cmd = fix_cmd
                                real_cmd = cmd + "; if ($?) {'success'} else {'__CMD_FAILED__'}\n"
                                proc.stdin.write(real_cmd)
                                proc.stdin.flush()
                                time.sleep(0.5)
                                result = read_until_prompt(proc)
                                resolved = not command_actually_failed(result)
                            else:
                                print("fix declined, stopping this step.")
                                break
                        else:
                            print(failure_response)
                            gave_up_with_explanation = True
                            break

                    cmd_out, output, prompt = parse_result(result)
                    clean_output = "\n".join(l for l in output.strip().split("\n") if l.strip() not in ("success", "__CMD_FAILED__"))

                    if resolved:
                        print(clean_output)
                    elif not gave_up_with_explanation:
                        print("Command failed after all retry attempts:")
                        print(clean_output)

                    session_history.append({"request": client_request, "command": cmd.strip(), "output": clean_output})

            else:
                confirmation = input(f"procced running: '{shell}' (n/y)> ")
                shell += "; if ($?) {'success'} else {'__CMD_FAILED__'}\n"

                if confirmation == "y" or confirmation == "":
                    proc.stdin.write(shell)
                    proc.stdin.flush()
                    time.sleep(0.5)
                    result = read_until_prompt(proc)

                    if command_actually_failed(result):
                        print("failure detected")
                        failure_response = call_mistral(failure_system_prompt, f"failed command: {shell}\nreason: {result}")
                        print(failure_response)
                    else:
                        cmd, output, prompt = parse_result(result)
                        print(output.strip())
                        session_history.append({"request": client_request, "command": shell.strip(), "output": output.strip()})


except KeyboardInterrupt:
    save_memory(past_requests)
    print("\nsaved memory, exiting.")
    sys.exit(0)

