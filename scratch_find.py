with open("python_version/ui/main_gui.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

in_triple = False
start_line = None
for i, line in enumerate(lines[:3174], 1):
    count = line.count('"""')
    if count % 2 == 1:
        in_triple = not in_triple
        if in_triple:
            start_line = i

print(f"Unclosed triple string started at line: {start_line}")
if start_line:
    print(lines[start_line-1][:120])
