import re

with open("ai_context.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Extract all supplier names from "(Approved Suppliers: [...])" patterns
suppliers = set()
for match in re.findall(r'Approved Suppliers: \[([^\]]+)\]', content):
    for s in match.split(", "):
        suppliers.add(s.strip())

for s in sorted(suppliers):
    print(f'    "{s}": "",')
print(f"\nTotal unique suppliers: {len(suppliers)}")
