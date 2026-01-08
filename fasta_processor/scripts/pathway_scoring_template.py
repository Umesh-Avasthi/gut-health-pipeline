"""
Template for pathway scoring script.
This script calculates TPM-weighted real metabolic activity scores.
"""
import pandas as pd
import os

# These variables will be replaced at runtime
ENZYMES_CSV = r"{ENZYMES_CSV}"
PATHWAY_DEFS = r"{PATHWAY_DEFS}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

# Load enzyme data
enzymes = pd.read_csv(ENZYMES_CSV)
print(f"Loaded {len(enzymes)} enzyme annotations")

# Load pathway definitions
pathways = pd.read_csv(PATHWAY_DEFS, quotechar='"', skipinitialspace=True)
print(f"Loaded {len(pathways)} pathway definitions")

has_metadata = 'display_name' in pathways.columns

# ─────────────────────────────────────────────────────────────
# Pre-build KO → max TPM_norm map (FAST, O(N))
# ─────────────────────────────────────────────────────────────
ko_global_tpm = {}

for _, row in enzymes.iterrows():
    kegg_ko_str = str(row.get("KEGG_KO", ""))
    if pd.isna(kegg_ko_str) or kegg_ko_str in ("", "-"):
        continue

    kos = [k.strip() for k in kegg_ko_str.split(",") if k.strip()]
    tpm = float(row.get("TPM_norm", 0))

    for ko in kos:
        if ko not in ko_global_tpm or tpm > ko_global_tpm[ko]:
            ko_global_tpm[ko] = tpm

results = []

# ─────────────────────────────────────────────────────────────
# Process each pathway
# ─────────────────────────────────────────────────────────────
for _, p in pathways.iterrows():
    pathway_group = p.pathway_group
    expected = set(str(p.expected_kos).split("|"))
    total_expected_kos = len(expected)
    weight = float(p.weight)

    if total_expected_kos == 0:
        continue

    # Metadata defaults
    display_name = pathway_group.replace('_', ' ').title()
    description = ''
    health_impact = ''
    low_threshold, normal_threshold, high_threshold = 0.0, 0.3, 0.7

    if has_metadata:
        display_name = str(p.get('display_name', display_name))
        description = str(p.get('description', ''))
        health_impact = str(p.get('health_impact', ''))
        low_threshold = float(p.get('low_threshold', 0.0))
        normal_threshold = float(p.get('normal_threshold', 0.3))
        high_threshold = float(p.get('high_threshold', 0.7))

    # ─────────────────────────────────────────────────────────
    # TPM weighted metabolic flux scoring
    # ─────────────────────────────────────────────────────────
    unique_detected_kos = expected.intersection(ko_global_tpm.keys())
    if not unique_detected_kos:
        continue

    coverage_factor = min(len(unique_detected_kos) / total_expected_kos, 1.0)
    tpm_sum = sum(ko_global_tpm[ko] for ko in unique_detected_kos)
    pathway_score = (tpm_sum / total_expected_kos) * weight

    # Health status
    if pathway_score < low_threshold:
        health_status, status_color = "CRITICAL", "#d32f2f"
    elif pathway_score < normal_threshold:
        health_status, status_color = "LOW", "#f57c00"
    elif pathway_score < high_threshold:
        health_status, status_color = "NORMAL", "#388e3c"
    else:
        health_status, status_color = "OPTIMAL", "#1976d2"

    sorted_kos = sorted(unique_detected_kos)
    enzymes_detected_str = ",".join(sorted_kos[:10])
    if len(sorted_kos) > 10:
        enzymes_detected_str += f" (+{len(sorted_kos) - 10} more)"

    result = {
        "pathway_group": pathway_group,
        "coverage": round(coverage_factor, 4),
        "pathway_score": round(pathway_score, 4),
        "enzymes_detected": enzymes_detected_str,
        "enzymes_detected_count": len(unique_detected_kos),
        "enzymes_expected_count": total_expected_kos,
        "pathway_weight": weight,
        "display_name": display_name,
        "description": description,
        "health_status": health_status,
        "status_color": status_color,
        "health_impact": health_impact
    }

    results.append(result)

# Save results
df_results = pd.DataFrame(results)
df_results = df_results.sort_values("pathway_score", ascending=False) if len(df_results) else df_results
df_results.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Pathway-level metabolic activity scores calculated: {len(df_results)} pathways")
