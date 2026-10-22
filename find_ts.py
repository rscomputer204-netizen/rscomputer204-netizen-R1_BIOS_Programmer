import tokenize, io

with open('python_version/ui/main_gui.py', 'r', encoding='utf-8', errors='replace') as f:
    src = f.read()

# Track all triple-quoted string tokens
reader = io.StringIO(src).readline
toks = []
try:
    for tok in tokenize.generate_tokens(reader):
        if tok.type == tokenize.STRING:
            if tok.string.startswith('\"\"\"') or tok.string.startswith("'''"):
                toks.append((tok.start[0], tok.end[0], tok.string[:50]))
except tokenize.TokenError as e:
    print(f'Error at: {e}')
    print(f'Last complete triple-string tokens:')
    for t in toks[-5:]:
        print(f'  lines {t[0]}-{t[1]}: {repr(t[2])}')
