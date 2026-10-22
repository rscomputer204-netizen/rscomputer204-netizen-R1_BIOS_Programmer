# More precise binary search
with open('python_version/ui/main_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

import ast

lo, hi = 1140, 1160
for mid in range(lo, hi):
    try:
        ast.parse(''.join(lines[:mid]))
        last_ok = mid
    except SyntaxError:
        print(f'Fails when adding line {mid+1}')
        print(repr(lines[mid]))
        break
