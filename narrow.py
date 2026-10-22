import tokenize, io

with open('python_version/ui/main_gui.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Test each line range to find exactly where triple-string starts being unclosed
# Start from line 3127 backwards
for start in range(3126, 3100, -1):
    snippet = ''.join(lines[:start])
    try:
        list(tokenize.generate_tokens(io.StringIO(snippet).readline))
        print(f'OK up to line {start}')
        break
    except tokenize.TokenError:
        pass
