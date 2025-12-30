"""
Template for processing DIAMOND hits from gut database.
This script converts DIAMOND BLAST output to enzyme annotation format.
"""
import pandas as pd

DIAMOND_HITS = r"{DIAMOND_HITS}"
KO2GENES_FILE = r"{KO2GENES_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

# Read diamond hits (tab-separated)
# Check if file is empty first
import os
if os.path.getsize(DIAMOND_HITS) == 0:
    # Create empty output with headers
    df = pd.DataFrame(columns=['protein_id', 'enzyme_name', 'ec_number', 'kegg_ko', 'kegg_pathway'])
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"⚠️  DIAMOND hits file is empty, creating empty output")
    exit(0)

hits_df = pd.read_csv(DIAMOND_HITS, sep='\t', header=None, 
                     names=['qseqid', 'sseqid', 'pident', 'length', 'mismatch', 
                            'gapopen', 'qstart', 'qend', 'sstart', 'send', 
                            'evalue', 'bitscore', 'qcovhsp', 'scovhsp'])

# Check if DataFrame is empty
if len(hits_df) == 0:
    # Create empty output with headers
    df = pd.DataFrame(columns=['protein_id', 'enzyme_name', 'ec_number', 'kegg_ko', 'kegg_pathway'])
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"⚠️  No DIAMOND hits found, creating empty output")
    exit(0)

# Try to load ko2genes mapping if available
ko_map = {}
if KO2GENES_FILE and KO2GENES_FILE != "None":
    try:
        with open(KO2GENES_FILE, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        ko = parts[0]
                        gene = parts[1]
                        if gene not in ko_map:
                            ko_map[gene] = []
                        ko_map[gene].append(ko)
    except FileNotFoundError:
        print(f"Warning: ko2genes.txt not found at {KO2GENES_FILE}, using fallback extraction")

# Map subject IDs to KOs
if ko_map:
    # Use ko2genes mapping
    hits_df['kegg_ko'] = hits_df['sseqid'].map(lambda x: ko_map.get(x, [None])[0] if x in ko_map else None)
else:
    # Fallback: Extract KO from subject ID (format: KO|protein_id or similar)
    hits_df['kegg_ko'] = hits_df['sseqid'].str.extract(r'(K\d{5})')[0]

# Create output
df = hits_df[hits_df['kegg_ko'].notna()].copy()
df['protein_id'] = df['qseqid']
df['enzyme_name'] = 'Unknown_enzyme'
df['ec_number'] = '-'
df['kegg_pathway'] = '-'

# Keep only required columns and remove duplicates
df = df[['protein_id', 'enzyme_name', 'ec_number', 'kegg_ko', 'kegg_pathway']].drop_duplicates()

# Save output
df.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Processed {len(df)} enzyme annotations from DIAMOND hits")

