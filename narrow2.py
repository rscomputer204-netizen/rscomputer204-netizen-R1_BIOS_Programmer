import tokenize, io

with open('python_version/ui/main_gui.py', 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

# Wider range
for start in range(3130, 2400, -1):
    snippet = ''.join(lines[:start])
    try:
        list(tokenize.generate_tokens(io.StringIO(snippet).readline))
        print(f'OK up to line {start}')
        print(f'Line {start}: {repr(lines[start-1][:80])}')
        break
    except tokenize.TokenError:
        pass
else:
    print('Error exists even with very short file')
