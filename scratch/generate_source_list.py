import yaml

with open('data/urls.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

md_lines = [
    '# Verified Source List (Groww Mutual Fund Pages)',
    '',
    '**Scope**: Mirae Asset Mutual Funds  ',
    '**Total Sources**: 36 URLs',
    '',
    '| Category | Scheme Name | Groww URL |',
    '| :--- | :--- | :--- |'
]

for entry in config.get('urls', []):
    md_lines.append(f'| {entry["category"]} | {entry["scheme_name"]} | [Link]({entry["url"]}) |')

with open('Docs/Source_List.md', 'w', encoding='utf-8') as out:
    out.write('\n'.join(md_lines))
