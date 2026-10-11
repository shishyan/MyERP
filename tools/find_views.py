with open('static/index.html', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        if 'class="view-panel' in line:
            print(f'{idx}: {line.strip()}')
