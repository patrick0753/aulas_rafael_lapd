import json

with open(r'c:\Users\52068085801\Downloads\Rede_Saber60_API_SIDRA_MT.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

print("Celulas:", len(nb["cells"]))
for i, c in enumerate(nb["cells"]):
    tipo = c["cell_type"]
    preview = "".join(c["source"])[:80].replace("\n", " ")
    print(f"  [{i:2d}] {tipo:8s} | {preview}")
