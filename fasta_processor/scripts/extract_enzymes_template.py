import pandas as pd

INPUT_FILE = r"{ANNOTATIONS_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

with open(INPUT_FILE) as f:
    for line in f:
        if line.startswith("#query"):
            header = line.lstrip("#").strip().split("\t")
            break

df = pd.read_csv(INPUT_FILE, sep="\t", comment="#", names=header)

# KEEP rows that have KEGG KOs (not EC!)
df = df[df["KEGG_ko"].notna() & (df["KEGG_ko"] != "-")]

df = df[["query","Preferred_name","KEGG_ko","KEGG_Pathway"]]
df.columns = ["protein_id","enzyme_name","kegg_ko","kegg_pathway"]
df["ec_number"] = "-"

df.to_csv(OUTPUT_FILE, index=False)
print("eggNOG enzymes:", len(df))
