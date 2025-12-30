"""
Template for merging eggNOG and KofamScan results.
This script creates the standardized annotation schema (FROZEN).
"""
import pandas as pd
import re

EGGNOG_FILE = r"{EGGNOG_FILE}"
KOFAM_FILE = r"{KOFAM_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

# Load data
eggnog_df = pd.read_csv(EGGNOG_FILE)
kofam_df = pd.read_csv(KOFAM_FILE)

# Merge on protein_id
merged = eggnog_df.merge(
    kofam_df,
    on="protein_id",
    how="outer"
)

# ============================================================================
# STANDARDIZED ANNOTATION SCHEMA (FROZEN)
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

merged["contig_id"] = merged["protein_id"].apply(extract_contig_id)

# 2. Final KO logic (prefer eggNOG, fallback to KofamScan)
merged["KEGG_KO"] = merged["kegg_ko"]
merged["KEGG_KO"] = merged["KEGG_KO"].fillna(merged["kegg_ko_kofam"])

# 3. Rename columns to match schema
merged = merged.rename(columns={
    "ec_number": "EC_number",
    "enzyme_name": "enzyme_name",
    "kegg_pathway": "pathway"
})

# 4. Calculate confidence_score based on agreement
# HIGH: eggNOG + KofamScan agree on KO
# MEDIUM: Only one source matches
# LOW: Neither or conflicting
def calculate_confidence(row):
    has_eggnog = pd.notna(row.get("kegg_ko")) and row.get("kegg_ko") != "-"
    has_kofam = pd.notna(row.get("kegg_ko_kofam")) and row.get("kegg_ko_kofam") != "-"
    
    if has_eggnog and has_kofam:
        # Check if they agree
        if str(row.get("kegg_ko", "")).strip() == str(row.get("kegg_ko_kofam", "")).strip():
            return "HIGH"  # Both agree
        else:
            return "MEDIUM"  # Both present but disagree
    elif has_eggnog or has_kofam:
        return "MEDIUM"  # Only one source
    else:
        return "LOW"  # Neither

merged["confidence_score"] = merged.apply(calculate_confidence, axis=1)

# 5. Set annotation_source
merged["annotation_source"] = "eggnog"
merged.loc[
    merged["kegg_ko"].isna() & merged["kegg_ko_kofam"].notna(),
    "annotation_source"
] = "kofamscan"
merged.loc[
    merged["kegg_ko"].notna() & merged["kegg_ko_kofam"].notna(),
    "annotation_source"
] = "eggnog+kofamscan"

# 6. Combine HMM score with confidence (if available)
# HMM score from KofamScan (higher is better, typically 0-1000+)
if "hmm_score" in merged.columns:
    # Normalize HMM score to 0-1 range for combination
    max_hmm = merged["hmm_score"].max()
    if max_hmm and max_hmm > 0:
        merged["hmm_score_normalized"] = merged["hmm_score"] / max_hmm
    else:
        merged["hmm_score_normalized"] = 0.5  # Default if no scores
else:
    merged["hmm_score"] = None
    merged["hmm_score_normalized"] = 0.5

# 7. Select and reorder columns to match frozen schema
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

# Add hmm_score if available
if "hmm_score" in merged.columns:
    final_columns.append("hmm_score")

# Keep only columns that exist
final_columns = [col for col in final_columns if col in merged.columns]

# Select final columns
merged = merged[final_columns]

# 8. Sort by confidence_score (HIGH first, then MEDIUM, then LOW)
confidence_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
merged["_conf_order"] = merged["confidence_score"].map(confidence_order)
merged = merged.sort_values(["_conf_order", "protein_id"])
merged = merged.drop(columns=["_conf_order"])

# Save final output
merged.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Final standardized annotation table created: {len(merged)} entries")
print(f"   - HIGH confidence (both agree): {len(merged[merged['confidence_score'] == 'HIGH'])}")
print(f"   - MEDIUM confidence (one source): {len(merged[merged['confidence_score'] == 'MEDIUM'])}")
print(f"   - LOW confidence: {len(merged[merged['confidence_score'] == 'LOW'])}")
print(f"   - eggnog only: {len(merged[merged['annotation_source'] == 'eggnog'])}")
print(f"   - kofamscan only: {len(merged[merged['annotation_source'] == 'kofamscan'])}")
print(f"   - both: {len(merged[merged['annotation_source'] == 'eggnog+kofamscan'])}")

