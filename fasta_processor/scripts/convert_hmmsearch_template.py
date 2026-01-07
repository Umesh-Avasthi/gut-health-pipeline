import sys, re

INPUT_FILE = r"{INPUT_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

hits = 0
current_ko = None

with open(INPUT_FILE) as f, open(OUTPUT_FILE, "w") as out:
    for line in f:
        line = line.strip()
        if not line:
            continue

        # Detect KO being searched
        if "Query:" in line or "Accession:" in line:
            m = re.search(r'(K\d{5})', line)
            if m:
                current_ko = m.group(1)
            continue

        # Match real HMMER hit rows
        cols = line.split()
        if current_ko and len(cols) >= 9:
            try:
                float(cols[0])  # E-value
                seq = cols[8]
                score = abs(float(cols[1]))
                out.write(f"* {seq} {current_ko} {score}\n")
                hits += 1
            except:
                pass

print("Hits:", hits)
