import json
import glob
import os

brain_dir = r"C:\Users\R1 LAB\.gemini\antigravity-ide\brain"
for conv in glob.glob(os.path.join(brain_dir, "*", ".system_generated", "logs", "transcript.jsonl")):
    try:
        with open(conv, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                d = json.loads(line)
                txt = str(d.get('content', '')) + str(d.get('tool_calls', ''))
                if "AC3" in txt and ("LOW" in txt or "set_led" in txt or "0x41" in txt):
                    conv_id = conv.split(os.sep)[-4]
                    print(f"[{conv_id} Step {d.get('step_index')}] {txt[:200]}")
    except Exception as e:
        pass
