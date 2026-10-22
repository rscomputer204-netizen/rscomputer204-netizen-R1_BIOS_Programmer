with open('python_version/ui/main_gui.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Check all lines in my new code section (2460-2610)
for i in range(2459, 2605):
    line = lines[i]
    if '\"\"\"' in line:
        print(f'L{i+1}: {repr(line[:120])}')
