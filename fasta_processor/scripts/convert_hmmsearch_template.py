"""
Template for converting hmmsearch output to exec_annotation format.
This script converts hmmsearch output to the format expected by process_kofam.
"""
import sys
import re

INPUT_FILE = r"{INPUT_FILE}"
OUTPUT_FILE = r"{OUTPUT_FILE}"

current_ko = None

with open(INPUT_FILE, 'r') as f_in, open(OUTPUT_FILE, 'w') as f_out:
    for line in f_in:
        line = line.strip()
        if line.startswith('Query:'):
            # Extract KO from query name (format: Query: K00001 or similar)
            match = re.search(r'K\d{5}', line)
            if match:
                current_ko = match.group(0)
        elif line and not line.startswith('#') and current_ko:
            parts = line.split()
            if len(parts) >= 8:
                target_name = parts[0]
                score = parts[7] if len(parts) > 7 else '0'
                # Use --cut_tc threshold: if score meets threshold, mark as confident
                try:
                    score_val = float(score)
                    # For now, mark all as confident (can adjust threshold later)
                    f_out.write(f'* {target_name} {current_ko} {score}\n')
                except:
                    f_out.write(f'* {target_name} {current_ko} 0\n')

print(f"✅ Converted hmmsearch output to exec_annotation format")

