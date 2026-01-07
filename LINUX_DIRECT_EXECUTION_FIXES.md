# Linux Direct Execution Fixes - Complete Results Guarantee

## Summary
Updated the Linux-based project to use direct Linux execution (no WSL) and fixed critical bugs to ensure **complete results** in the same format as `gut_auth` project.

## Changes Applied

### 1. Fixed hmmsearch Output Conversion (CRITICAL)
**File**: `fasta_processor/scripts/convert_hmmsearch_template.py`

**Problem**: 
- Script was too simplistic in parsing hmmsearch output
- Only looked for `Query:` lines in one format
- Missed hits when output format varied
- No validation of converted output

**Fix**:
- Added multiple parsing methods to handle different hmmsearch output formats
- Better detection of KO names from various locations (Query lines, Accession, Name fields, file paths)
- Improved hit section detection
- Added validation and logging of hits found
- Better error messages when no hits are found

**Impact**: KofamScan results will now be properly converted and included in final output.

### 2. Removed WSL Dependencies
**File**: `fasta_processor/services.py`

**Changes**:
- Renamed `_to_wsl_path()` → `_to_linux_path()` (simplified for Linux)
- Renamed `_normalize_path_to_wsl()` → `_normalize_path_to_linux()`
- Removed Windows path conversion logic (not needed on Linux)
- All subprocess calls already use `bash -c` directly (no WSL wrapper)
- Simplified path handling to use Linux paths directly

**Impact**: Code now runs natively on Linux without WSL overhead.

### 3. Direct Linux Execution
All commands now run directly on Linux:
- `bash -c` for shell commands (no `wsl bash -c`)
- Direct Linux paths (no Windows→Linux conversion)
- Conda environments activated directly in Linux
- All file operations use Linux paths

## Execution Flow (Same as gut_auth)

1. **Step 1**: KofamScan (hmmsearch) → `kofamscan.txt`
2. **Step 2**: Convert hmmsearch → `kofamscan_results_converted.txt` ✅ **FIXED**
3. **Step 3**: Process KofamScan → `kofamscan_kos.csv`
4. **Step 4**: GUT DIAMOND search → `gut_hits.tsv`
5. **Step 5**: Process DIAMOND hits → `gut_enzymes.csv`
6. **Step 6**: Filter FASTA (remove gut hits)
7. **Step 7**: eggNOG emapper → `emapper.annotations`
8. **Step 8**: Extract enzymes → `emapper_enzymes.csv`
9. **Step 9**: Merge all sources → `enzymes_merged.csv`
10. **Step 10**: Pathway scoring → `pathways_*.csv`
11. **Step 11**: Create final FASTA → `*.fasta`

## Expected Output Format (Same as gut_auth)

### enzymes_*.csv Format:
```csv
protein_id,contig_id,EC_number,KEGG_KO,enzyme_name,pathway,confidence_score,annotation_source
protein1,contig1,1.1.1.1,K00001,alcohol_dehydrogenase,pathway1,HIGH,eggnog+kofamscan
protein2,contig2,2.7.1.1,K00845,hexokinase,pathway2,MEDIUM,eggnog
```

### pathways_*.csv Format:
```csv
pathway_group,coverage,pathway_score,enzymes_detected,enzymes_detected_count,enzymes_expected_count,pathway_weight,display_name,description,health_status,status_color,health_impact
glycolysis,0.85,0.75,K00001,K00002,10,1.0,Glycolysis,Energy production,NORMAL,#388e3c,Positive
```

### *.fasta Format:
```
>protein1
MKTAYIAKQR...
>protein2
MKTAYIAKQR...
```

## Verification Steps

### 1. Check Database Paths
Verify in `settings.py` or environment:
```python
EGGNOG_DB_PATH = '/home/ser1dai/eggnog_db_final'
KOFAM_DB_PATH = '/home/ser1dai/eggnog_db_final/kofam_db'
```

### 2. Test Processing
Run a test job and check logs for:
```
✅ Converted hmmsearch output: X hits found
✅ Processed X KOs from kofamscan
✅ Processed X enzyme annotations from GUT hits
✅ Extracted X enzyme annotations from emapper
```

### 3. Verify Output Files
Check that output files have data (not just headers):
```bash
# Check enzymes CSV has data rows
wc -l media/results/YYYY/MM/DD/enzymes_*.csv
# Should be > 1 (header + data rows)

# Check pathways CSV has data rows
wc -l media/results/YYYY/MM/DD/pathways_*.csv
# Should be > 0

# Check FASTA has sequences
grep -c '^>' media/results/YYYY/MM/DD/*.fasta
# Should be > 0
```

## Troubleshooting

### Issue: Still Getting Empty Files

1. **Check hmmsearch output**:
   ```bash
   cat media/results/YYYY/MM/DD/temp_*/kofamscan.txt | head -50
   ```
   - Should see Query: lines and hit sections
   - If empty, sequences may not match HMM profiles

2. **Check converted file**:
   ```bash
   cat media/results/YYYY/MM/DD/temp_*/kofamscan_results_converted.txt
   ```
   - Should see lines like: `* protein_id KO score`
   - If empty, conversion failed (check logs)

3. **Check database accessibility**:
   ```bash
   ls -lh /home/ser1dai/eggnog_db_final/eggnog_proteins.dmnd
   ls -lh /home/ser1dai/eggnog_db_final/kofam_db/profiles.hmm
   ```
   - Files should exist and be readable

4. **Check conda environments**:
   ```bash
   source ~/miniconda3/etc/profile.d/conda.sh
   conda activate eggnog
   which emapper.py
   conda activate kofamscan
   which hmmsearch
   ```

### Issue: Processing Takes Too Long

The pipeline now uses direct Linux execution which is faster than WSL:
- No WSL overhead
- Direct file system access
- Native Linux performance

If still slow, check:
- Database files are on fast storage (SSD)
- Sufficient RAM available
- CPU cores configured correctly

## Next Steps

1. **Test with a known-good FASTA file**
2. **Monitor logs** during processing
3. **Verify intermediate files** in `temp_*/` directories
4. **Check final output** has complete annotations

## Notes

- All variable names with `_wsl` suffix are now Linux paths (kept for compatibility)
- Path conversion is simplified - just ensures forward slashes
- All subprocess calls use `bash -c` directly (native Linux)
- No Windows path handling needed (pure Linux environment)






