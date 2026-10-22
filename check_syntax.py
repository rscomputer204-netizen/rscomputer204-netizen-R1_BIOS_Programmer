import ast, sys

try:
    with open('python_version/ui/main_gui.py', 'r', encoding='utf-8') as f:
        src = f.read()
    ast.parse(src)
    print('OK')
except SyntaxError as e:
    print(f'SyntaxError at line {e.lineno}: {e.msg}')
    print(f'Text: {e.text}')
