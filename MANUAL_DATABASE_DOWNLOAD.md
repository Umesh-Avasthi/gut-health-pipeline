# 🔴 CRITICAL: Manual Database Download Required

## Problem
The automatic database download is failing with **404 errors** because the eggNOG server URLs have changed or the files are temporarily unavailable.

## ✅ SOLUTION: Download Database Manually

### Step 1: Check Current Status
```bash
cd /home/ser1dai/eggnog_db_final
ls -lh eggnog_proteins.dmnd*
```

### Step 2: Download DIAMOND Database Manually

**Option A: Direct Download (Recommended)**
```bash
cd /home/ser1dai/eggnog_db_final

# Try downloading from the official site
# Visit: http://eggnog5.embl.de/#/app/downloads
# Look for "DIAMOND database" download link
# Or try this direct command:

wget -O eggnog_proteins.dmnd.gz \
    "http://eggnogdb.embl.de/download/emapperdb-5.0.2/eggnog_proteins.dmnd.gz" \
    --continue --progress=bar

# If that fails, try alternative URLs:
# wget "http://eggnog5.embl.de/download/eggnog_5.0/per_tax_level/eggnog_proteins.dmnd.gz"
# or check the official downloads page for current URLs

# Decompress
gunzip -f eggnog_proteins.dmnd.gz

# Verify
source ~/miniconda3/etc/profile.d/conda.sh
conda activate eggnog
echo ">test" > /tmp/test_seq.faa
echo "MKTAYIAKQR" >> /tmp/test_seq.faa
diamond blastp -d eggnog_proteins.dmnd -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6
```

**Option B: Use Backup (If Available)**
```bash
cd /home/ser1dai/eggnog_db_final

# Check if any backup works
for backup in eggnog_proteins.dmnd.backup eggnog_proteins.dmnd.broken eggnog_proteins.dmnd.corrupted.*; do
    if [ -f "$backup" ]; then
        echo "Testing $backup..."
        diamond blastp -d "$backup" -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6 2>&1 | head -1
        if [ $? -eq 0 ] && ! diamond blastp -d "$backup" -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6 2>&1 | grep -q "Unexpected end"; then
            echo "✅ $backup works! Copying to main file..."
            cp "$backup" eggnog_proteins.dmnd
            break
        fi
    fi
done
```

**Option C: Update eggNOG-mapper (May Fix Download URLs)**
```bash
conda activate eggnog
conda update -c bioconda eggnog-mapper
download_eggnog_data.py --data_dir /home/ser1dai/eggnog_db_final -y -f
```

### Step 3: Verify Database Works
```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate eggnog

# Test the database
echo ">test" > /tmp/test_seq.faa
echo "MKTAYIAKQR" >> /tmp/test_seq.faa

diamond blastp -d /home/ser1dai/eggnog_db_final/eggnog_proteins.dmnd \
    -q /tmp/test_seq.faa \
    --threads 1 \
    --max-target-seqs 1 \
    --outfmt 6

# Should return results, NOT "Unexpected end of input"
```

### Step 4: Restart Django Server
After the database is downloaded and verified:
1. Restart your Django server
2. Try processing a FASTA file again

## 🔍 Why This Happens

1. **Server Issues**: The eggNOG download server may be temporarily down or URLs changed
2. **Version Mismatch**: The download script expects version 5.0.2 but server may have updated
3. **Network Issues**: Connection timeouts or DNS problems

## 📝 Alternative: Skip eggNOG, Use Only KofamScan

If you can't download the database, you can modify the pipeline to:
- Use only KofamScan (which is working)
- Skip eggNOG annotation
- Still get functional annotations from KofamScan

Let me know if you want this option implemented.



