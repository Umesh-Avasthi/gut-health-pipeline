"""
Template for creating final FASTA file with annotated sequences only.
This script extracts sequences from the original FASTA that were successfully annotated.
"""
import pandas as pd
import sys

# These variables will be replaced at runtime
MERGED_CSV = r"{MERGED_CSV}"
INPUT_FASTA = r"{INPUT_FASTA}"
OUTPUT_FASTA = r"{OUTPUT_FASTA}"

# Read merged CSV to get annotated protein IDs
df = pd.read_csv(MERGED_CSV)

# Check if CSV has any data rows (not just headers)
if len(df) == 0:
    print(f"⚠️  No annotation data found in merged CSV. The CSV file only contains headers.")
    print(f"   This means KofamScan and/or eggNOG did not find any annotations.")
    print(f"   Creating empty FASTA file.")
    annotated_proteins = set()
else:
    # Filter out header row if it was included as data
    annotated_proteins = set(df['protein_id'].unique())
    # Remove 'protein_id' if it was included as a value (shouldn't happen, but just in case)
    annotated_proteins.discard('protein_id')
    print(f"Found {len(annotated_proteins)} annotated proteins from merged results")

# Read original FASTA and extract annotated sequences
sequences = {}
current_id = None
current_seq = []

with open(INPUT_FASTA, 'r') as f:
    for line in f:
        if line.startswith('>'):
            # Save previous sequence if it was annotated
            if current_id and current_id in annotated_proteins:
                sequences[current_id] = ''.join(current_seq)
            
            # Parse new header
            header = line[1:].strip()
            current_id = header.split()[0]  # Get first word (protein ID)
            current_seq = [line]  # Include header line
        else:
            if current_id:
                current_seq.append(line)
    
    # Don't forget the last sequence
    if current_id and current_id in annotated_proteins:
        sequences[current_id] = ''.join(current_seq)

# Write final FASTA file with annotated sequences only
with open(OUTPUT_FASTA, 'w') as f:
    for protein_id, sequence in sequences.items():
        f.write(sequence)

print(f"✅ Final merged FASTA file created: {len(sequences)} sequences")
print(f"   File saved to: {OUTPUT_FASTA}")

