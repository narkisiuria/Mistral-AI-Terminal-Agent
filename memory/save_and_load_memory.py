import os
MEMORY_FILE = "memory/last_requests.txt"

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