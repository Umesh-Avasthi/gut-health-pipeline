"""
Template for merging eggNOG results only (when KofamScan is not available).
This script creates the standardized annotation schema (FROZEN) with eggNOG data only.
"""
import pandas as pd
import re

EGGNOG_FILE = r"{EGGNOG_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

# Load eggnog data
df = pd.read_csv(EGGNOG_FILE)

# ============================================================================
# STANDARDIZED ANNOTATION SCHEMA (FROZEN) - eggNOG only
# ============================================================================

# 1. Extract contig_id from protein_id
# Common patterns: contig_123_orf_456, contig123_orf456, contig_123, etc.
def extract_contig_id(protein_id):
    if pd.isna(protein_id):
        return None
    protein_id_str = str(protein_id)
    # Try to extract contig ID (everything before last underscore or _orf)
    # Pattern 1: contig_123_orf_456 -> contig_123
    match = re.search(r'(contig[^_]*_[^_]+)', protein_id_str)
    if match:
        return match.group(1)
    # Pattern 2: contig123 -> contig123
    match = re.search(r'(contig[0-9]+)', protein_id_str, re.IGNORECASE)
    if match:
        return match.group(1)
    # Pattern 3: Extract everything before _orf or _ORF
    match = re.search(r'^([^_]+(?:_[^_]+)*?)(?:_orf|_ORF)', protein_id_str, re.IGNORECASE)
    if match:
        return match.group(1)
    # Default: use protein_id as contig_id (if no pattern matches)
    return protein_id_str.split('_')[0] if '_' in protein_id_str else protein_id_str

df["contig_id"] = df["protein_id"].apply(extract_contig_id)

# 2. Rename columns to match schema
df = df.rename(columns={
    "ec_number": "EC_number",
    "kegg_ko": "KEGG_KO",
    "enzyme_name": "enzyme_name",
    "kegg_pathway": "pathway"
})

# 3. Set confidence_score (MEDIUM since only one source)
df["confidence_score"] = "MEDIUM"

# 4. Set annotation_source
df["annotation_source"] = "eggnog"

# 5. Select and reorder columns to match frozen schema
final_columns = [
    "protein_id",
    "contig_id",
    "EC_number",
    "KEGG_KO",
    "enzyme_name",
    "pathway",
    "confidence_score",
    "annotation_source"
]

# Keep only columns that exist
final_columns = [col for col in final_columns if col in df.columns]
df = df[final_columns]

# Sort by protein_id
df = df.sort_values("protein_id")

# Save as final output
df.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Standardized annotation table created (eggnog only): {len(df)} entries")
print(f"   - All entries: MEDIUM confidence (single source)")

