import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

path = r"C:\Users\R1 LAB\.gemini\antigravity-ide\brain\94fce4b3-9e93-486c-a218-f689291d72bd\.system_generated\logs\transcript.jsonl"
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        d = json.loads(line)
        content = str(d.get('content', ''))
        calls = str(d.get('tool_calls', ''))
        all_text = content + calls
        if any(w in all_text for w in ["set_led", "AC3", "AC3", "0x41"]):
            if d.get('type') in ['USER_INPUT', 'PLANNER_RESPONSE']:
                print(f"Step {d.get('step_index')} [{d.get('type')}]: {all_text[:300]}")
                print("=" * 60)
