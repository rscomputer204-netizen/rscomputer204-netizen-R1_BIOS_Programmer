import ast, sys

try:
    with open('python_version/ui/main_gui.py', 'r', encoding='utf-8', errors='replace') as f:
        src = f.read()
    compile(src, 'main_gui.py', 'exec')
    print('COMPILE OK')
except SyntaxError as e:
    print(f'SyntaxError line={e.lineno} offset={e.offset}: {e.msg}')
    if e.text:
        print(f'  text: {repr(e.text[:120])}')
    # Also show line in file
    lines = src.splitlines()
    if e.lineno and e.lineno <= len(lines):
        print(f'  line content: {repr(lines[e.lineno-1][:120])}')
