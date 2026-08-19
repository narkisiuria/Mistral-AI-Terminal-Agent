import subprocess
import time
import os
from mistralai.client import Mistral
from dotenv import load_dotenv
import shlex
import sys

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
        Your only job: convert the user's plain-English request into ONE single valid PowerShell command that does what they asked.

        Rules:
        - Output ONLY the raw command. No explanation, no markdown, no backticks, no extra text.
        - If the request needs multiple steps, output only the FIRST command needed — do not chain with ; or &&.
        - Never invent flags or cmdlets that don't exist in PowerShell.
        - If the request is ambiguous or unsafe to guess (e.g. could delete/overwrite something unintended), output exactly: CLARIFY: <short question>
        - Assume current working directory is already correct — don't cd unless explicitly asked.
        - Prefer built-in PowerShell cmdlets over external tools unless the user names one.
        - If the user's request is a question you can answer directly (e.g. using the memory context provided, general knowledge,
        or explaining something) rather than something that needs a real system action,
        output an `echo "<your answer>"` command instead of searching for an unrelated real cmdlet.'''
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
MEMORY_FILE = "last_requests.txt"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return f.read()
    return ""

def save_memory(requests_list):
    with open(MEMORY_FILE, "w") as f:
        f.write("LAST USER REQUESTS:\n")
        for i, r in enumerate(requests_list[-4:], 1):
            f.write(f"{i}: {r}\n")

past_requests = []
memory_context = load_memory()
session_history = []

client_request = ""
try:
    while True:        
        client_request = input(f"AI-CLI ({prompt})> ")
        if client_request == "quit":
            save_memory(past_requests)
            sys.exit(0)

        past_requests.append(client_request)
        user_content = f"{memory_context}\n\nCurrent request: {client_request}"
        
        recent = session_history[-3:]
        history_text = "\n".join(f"Request: {h['request']}\nCommand: {h['command']}\nOutput: {h['output']}" for h in recent)
        user_content = f"{memory_context}\n\nRecent session history:\n{history_text}\n\nCurrent request: {client_request}"
        
        shell = call_mistral(system_prompt, user_content)
        if shell.split(":")[0] == "CLARIFY":
            answer = input(f"{shell} ")
            user_content = f"{user_content}\nClarification: {answer}"
            shell = call_mistral(user_content=user_content, system_prompt=system_prompt)

        confirmation = input(f"procced running: '{shell}' (n/y)> ")
        shell += "\n"

        if confirmation == "y" or confirmation == "":
            proc.stdin.write(shell)
            proc.stdin.flush()
            time.sleep(0.5)
            result = read_until_prompt(proc)

            cmd, output, prompt = parse_result(result)

            print(output.strip())
            session_history.append({"request": client_request, "command": shell.strip(), "output": output.strip()})

        else:
            continue

except KeyboardInterrupt:
    save_memory(past_requests)
    print("\nsaved memory, exiting.")
    sys.exit(0)

