# Binary search to find the bad line
with open('python_version/ui/main_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

import ast

lo, hi = 0, len(lines)
while lo < hi - 1:
    mid = (lo + hi) // 2
    try:
        ast.parse(''.join(lines[:mid]))
        lo = mid
    except SyntaxError:
        hi = mid

print(f'Problem starts around line: {hi}')
for i in range(max(0, hi-3), min(len(lines), hi+3)):
    print(f'L{i+1}: {repr(lines[i][:100])}')
