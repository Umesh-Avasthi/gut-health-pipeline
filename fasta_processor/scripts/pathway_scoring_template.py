"""
Template for pathway scoring script.
This script calculates pathway-level scores from enzyme data.
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

# Load pathway definitions with proper CSV quoting
pathways = pd.read_csv(PATHWAY_DEFS, quotechar='"', skipinitialspace=True)
print(f"Loaded {len(pathways)} pathway definitions")

# Handle both old format (3 columns) and new format (8 columns)
has_metadata = 'display_name' in pathways.columns

results = []

# Process each pathway
for _, p in pathways.iterrows():
    pathway_group = p.pathway_group
    expected_kos_str = p.expected_kos
    weight = float(p.weight)
    
    # Get metadata if available - handle missing or invalid values safely
    display_name = pathway_group.replace('_', ' ').title()
    description = ''
    low_threshold = 0.0
    normal_threshold = 0.3
    high_threshold = 0.7
    health_impact = ''
    
    if has_metadata:
        try:
            display_name = str(p.get('display_name', display_name)) if pd.notna(p.get('display_name')) else display_name
            description = str(p.get('description', '')) if pd.notna(p.get('description')) else ''
            health_impact = str(p.get('health_impact', '')) if pd.notna(p.get('health_impact')) else ''
            
            # Safely convert thresholds to float
            low_val = p.get('low_threshold', 0.0)
            if pd.notna(low_val) and str(low_val).strip():
                try:
                    low_threshold = float(low_val)
                except (ValueError, TypeError):
                    low_threshold = 0.0
            
            normal_val = p.get('normal_threshold', 0.3)
            if pd.notna(normal_val) and str(normal_val).strip():
                try:
                    normal_threshold = float(normal_val)
                except (ValueError, TypeError):
                    normal_threshold = 0.3
            
            high_val = p.get('high_threshold', 0.7)
            if pd.notna(high_val) and str(high_val).strip():
                try:
                    high_threshold = float(high_val)
                except (ValueError, TypeError):
                    high_threshold = 0.7
        except Exception as e:
            print(f"Warning: Error parsing metadata for {pathway_group}: {e}")
            # Use defaults
    
    # Parse expected KOs (pipe-separated)
    expected = set(expected_kos_str.split("|"))
    total_expected_kos = len(expected)
    
    # Skip pathways with no expected KOs
    if total_expected_kos == 0:
        continue
    
    # CRITICAL FIX: Extract UNIQUE KEGG KOs from detected enzymes
    # Step 1: Collect all KOs from enzyme rows, handling comma-separated values
    ko_to_eas = {}  # Map each unique KO to its best EAS score
    
    for idx, row in enzymes.iterrows():
        kegg_ko_str = str(row.get("KEGG_KO", ""))
        if pd.isna(kegg_ko_str) or kegg_ko_str == "" or kegg_ko_str == "-":
            continue
        
        # Handle comma-separated KOs (e.g., "K00813,K00832")
        kos_in_row = [ko.strip() for ko in kegg_ko_str.split(",") if ko.strip()]
        
        # Calculate EAS for this row
        if "hmm_score" in row.index and pd.notna(row.get("hmm_score")):
            eas = float(row.get("hmm_score", 0)) / 200.0
            eas = min(eas, 1.0)  # Cap at 1.0
        else:
            # Fallback: use confidence_score
            confidence_map = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.3}
            conf = str(row.get("confidence_score", "MEDIUM")).upper()
            eas = confidence_map.get(conf, 0.5)
        
        # For each KO in this row that matches expected pathway KOs
        for ko in kos_in_row:
            if ko in expected:
                # Keep the maximum EAS score for each unique KO
                # (in case same KO appears in multiple rows with different scores)
                if ko not in ko_to_eas or eas > ko_to_eas[ko]:
                    ko_to_eas[ko] = eas
    
    # Step 2: Get unique detected KOs (only those in expected set)
    unique_detected_kos = set(ko_to_eas.keys())
    
    if not unique_detected_kos:
        continue  # Skip pathways with no detected enzymes
    
    # Step 3: Calculate coverage as unique_detected_KOs / total_expected_KOs
    coverage_factor = len(unique_detected_kos) / total_expected_kos
    # Ensure coverage never exceeds 1.0
    coverage_factor = min(coverage_factor, 1.0)
    
    # Step 4: Calculate pathway_score as mean(enzyme_EAS) * coverage * pathway_weight
    eas_values = [ko_to_eas[ko] for ko in unique_detected_kos]
    mean_eas = sum(eas_values) / len(eas_values) if eas_values else 0.0
    pathway_score = mean_eas * coverage_factor * weight
    
    # Determine health status based on score and thresholds
    if pathway_score < low_threshold:
        health_status = "CRITICAL"
        status_color = "#d32f2f"  # Red
    elif pathway_score < normal_threshold:
        health_status = "LOW"
        status_color = "#f57c00"  # Orange
    elif pathway_score < high_threshold:
        health_status = "NORMAL"
        status_color = "#388e3c"  # Green
    else:
        health_status = "OPTIMAL"
        status_color = "#1976d2"  # Blue
    
    # Step 5: enzymes_detected must list unique KEGG KOs, not protein names
    sorted_kos = sorted(unique_detected_kos)
    enzymes_detected_str = ",".join(sorted_kos[:10])  # Limit to first 10 for display
    if len(sorted_kos) > 10:
        enzymes_detected_str += f" (+{len(sorted_kos) - 10} more)"
    
    result_dict = {
        "pathway_group": pathway_group,
        "coverage": round(coverage_factor, 4),
        "pathway_score": round(pathway_score, 4),
        "enzymes_detected": enzymes_detected_str,
        "enzymes_detected_count": len(unique_detected_kos),  # Count unique KOs, not rows
        "enzymes_expected_count": total_expected_kos,
        "pathway_weight": weight
    }
    
    # Add metadata if available
    if has_metadata:
        result_dict.update({
            "display_name": display_name,
            "description": description,
            "health_status": health_status,
            "status_color": status_color,
            "health_impact": health_impact
        })
    
    results.append(result_dict)

# Create results DataFrame
if not results:
    # If no pathways had detected enzymes, create empty DataFrame with proper columns
    base_columns = ["pathway_group", "coverage", "pathway_score", "enzymes_detected", 
                    "enzymes_detected_count", "enzymes_expected_count", "pathway_weight"]
    if has_metadata:
        base_columns.extend(["display_name", "description", "health_status", "status_color", "health_impact"])
    df_results = pd.DataFrame(columns=base_columns)
    print("⚠️  No pathways had detected enzymes. Creating empty results file.")
else:
    df_results = pd.DataFrame(results)
    # Sort by pathway score (highest first) - only if column exists
    if "pathway_score" in df_results.columns and len(df_results) > 0:
        df_results = df_results.sort_values("pathway_score", ascending=False)

# Save pathway scores
df_results.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Pathway-level scores calculated: {len(df_results)} pathways")
if len(df_results) > 0 and "pathway_score" in df_results.columns:
    print(f"   Top pathways by score:")
    for idx, row in df_results.head(5).iterrows():
        print(f"   - {row['pathway_group']}: Score={row['pathway_score']:.4f}, Coverage={row['coverage']:.2%}")

