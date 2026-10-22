import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\R1 LAB\.gemini\antigravity-ide\brain\94fce4b3-9e93-486c-a218-f689291d72bd\.system_generated\logs\transcript.jsonl"
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        d = json.loads(line)
        step = d.get('step_index')
        if step in [713, 719, 723, 727, 729, 731]:
            print(f"=== STEP {step} ===")
            print(json.dumps(d, indent=2))
