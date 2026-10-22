with open('python_version/ui/main_gui.py', 'rb') as f:
    lines = f.read().split(b'\n')

line = lines[3126]  # 0-indexed, so line 3127
print(f'L3127 bytes: {line}')
print(f'L3127 repr: {repr(line)}')
