"""
Template for extracting enzymes from eggNOG annotations.
This script processes emapper annotation output and extracts enzyme data.
"""
import pandas as pd
import sys
sys.path.insert(0, r'{EGGNOG_DB_PATH}')

INPUT_FILE = r"{ANNOTATIONS_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

# Read header line manually
with open(INPUT_FILE, "r") as f:
    for line in f:
        if line.startswith("#query"):
            header = line.strip().lstrip("#").split("\t")
            break

# Read annotation file
df = pd.read_csv(INPUT_FILE, sep="\t", comment="#", names=header, low_memory=False)

# Keep only rows with valid EC numbers
df = df[df["EC"].notna() & (df["EC"] != "-")]

# Select required columns
enzymes_df = df[["query", "Preferred_name", "EC", "KEGG_ko", "KEGG_Pathway"]].copy()

# Rename columns
enzymes_df.columns = ["protein_id", "enzyme_name", "ec_number", "kegg_ko", "kegg_pathway"]

# Clean & normalize data
enzymes_df["ec_number"] = enzymes_df["ec_number"].str.split(",")
enzymes_df = enzymes_df.explode("ec_number")
enzymes_df["ec_number"] = enzymes_df["ec_number"].str.strip()
enzymes_df["kegg_ko"] = enzymes_df["kegg_ko"].astype(str).str.replace("ko:", "", regex=False)
enzymes_df["enzyme_name"] = enzymes_df["enzyme_name"].fillna("Unknown_enzyme")

# Drop duplicates
enzymes_df.drop_duplicates(subset=["protein_id", "ec_number"], inplace=True)

# Save output
enzymes_df.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Enzyme table created: {len(enzymes_df)} enzymes")

