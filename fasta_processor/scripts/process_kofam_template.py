"""
Template for processing KofamScan results.
This script extracts KEGG KOs and HMM scores from KofamScan output.
"""
import pandas as pd

INPUT_FILE = r"{INPUT_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

rows = []

with open(INPUT_FILE, "r") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        confident = line.startswith("*")
        if confident:
            line = line.lstrip("* ").strip()

        parts = line.split()
        if len(parts) < 2:
            continue
        protein_id = parts[0]
        kegg_ko = parts[1]
        # Extract HMM score if available (usually 3rd or 4th column)
        hmm_score = None
        if len(parts) >= 3:
            try:
                hmm_score = float(parts[2])  # Score is usually in 3rd column
            except (ValueError, IndexError):
                pass

        rows.append({
            "protein_id": protein_id,
            "kegg_ko_kofam": kegg_ko,
            "hmm_score": hmm_score,
            "confidence": "high" if confident else "low"
        })

# Check if we have any rows
if not rows:
    # Create empty DataFrame with correct columns
    df = pd.DataFrame(columns=["protein_id", "kegg_ko_kofam", "hmm_score", "confidence"])
    print(f"⚠️  No KofamScan hits found in input file")
else:
    df = pd.DataFrame(rows)
    
    # Check if confidence column exists before filtering
    if "confidence" in df.columns:
        # Keep only HIGH confidence hits
        df = df[df["confidence"] == "high"]
    else:
        # If confidence column is missing, keep all hits (assume all are high confidence)
        print(f"⚠️  Warning: 'confidence' column not found, keeping all hits")
        df = df[["protein_id", "kegg_ko_kofam", "hmm_score"]].copy()

# Select only required columns for output
output_columns = ["protein_id", "kegg_ko_kofam"]
if "hmm_score" in df.columns:
    output_columns.append("hmm_score")

df = df[output_columns] if len(df) > 0 else pd.DataFrame(columns=output_columns)

df.to_csv(OUTPUT_FILE, index=False)

print(f"✅ KofamScan KO table created: {len(df)} entries")

