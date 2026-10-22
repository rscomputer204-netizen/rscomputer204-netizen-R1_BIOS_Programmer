import tokenize, io

with open('python_version/ui/main_gui.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Narrow: 3037 is ok, find exact line that breaks it
for start in range(3038, 3044):
    snippet = ''.join(lines[:start])
    try:
        list(tokenize.generate_tokens(io.StringIO(snippet).readline))
        print(f'OK up to line {start}')
    except tokenize.TokenError as e:
        print(f'FAIL at line {start}: {e}')
        print(f'  bad line: {repr(lines[start-1][:120])}')
