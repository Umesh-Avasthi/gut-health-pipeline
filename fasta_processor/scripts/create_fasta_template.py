import pandas as pd

MERGED_CSV = r"{MERGED_CSV}"
INPUT_FASTA = r"{INPUT_FASTA}"
OUTPUT_FASTA = r"{OUTPUT_FASTA}"

df = pd.read_csv(MERGED_CSV)

annotated = set(df["protein_id"].dropna().astype(str))

with open(INPUT_FASTA) as fin, open(OUTPUT_FASTA,"w") as fout:
    keep = False
    for line in fin:
        if line.startswith(">"):
            pid = line[1:].split()[0]
            keep = pid in annotated
        if keep:
            fout.write(line)

print("Final FASTA sequences:", len(annotated))
