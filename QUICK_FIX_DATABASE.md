# 🚀 QUICK FIX: Database Download

## Current Problem
- Database file is **missing** (`eggnog_proteins.dmnd` not found)
- The compressed file (`eggnog_proteins.dmnd.gz`) is **corrupted/incomplete**
- Automatic download is failing with 404 errors

## ✅ IMMEDIATE SOLUTION

### Option 1: Download Using wget (Try This First)

```bash
cd /home/ser1dai/eggnog_db_final

# Remove corrupted file
rm -f eggnog_proteins.dmnd.gz

# Download directly (this may take 10-30 minutes depending on connection)
wget --continue --progress=bar \
    "http://eggnogdb.embl.de/download/emapperdb-5.0.2/eggnog_proteins.dmnd.gz" \
    -O eggnog_proteins.dmnd.gz

# If that URL fails, try these alternatives:
# wget "http://eggnog5.embl.de/download/eggnog_5.0/per_tax_level/eggnog_proteins.dmnd.gz"
# wget "https://eggnog5.embl.de/download/eggnog_5.0/per_tax_level/eggnog_proteins.dmnd.gz"

# Decompress (should be ~1.2GB when done)
gunzip -f eggnog_proteins.dmnd.gz

# Verify it works
source ~/miniconda3/etc/profile.d/conda.sh
conda activate eggnog
echo ">test" > /tmp/test_seq.faa
echo "MKTAYIAKQR" >> /tmp/test_seq.faa
diamond blastp -d eggnog_proteins.dmnd -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6

# Should show results, NOT "Unexpected end of input"
```

### Option 2: Use Browser Download

1. Visit: **http://eggnog5.embl.de/#/app/downloads**
2. Find and download **"DIAMOND database"** or **"eggnog_proteins.dmnd.gz"**
3. Save to: `/home/ser1dai/eggnog_db_final/`
4. Then run:
   ```bash
   cd /home/ser1dai/eggnog_db_final
   gunzip -f eggnog_proteins.dmnd.gz
   ```

### Option 3: Check if Backup Works

```bash
cd /home/ser1dai/eggnog_db_final

# Test each backup
for backup in eggnog_proteins.dmnd.backup eggnog_proteins.dmnd.broken eggnog_proteins.dmnd.corrupted.*; do
    if [ -f "$backup" ]; then
        echo "Testing $backup..."
        source ~/miniconda3/etc/profile.d/conda.sh
        conda activate eggnog
        echo ">test" > /tmp/test_seq.faa
        echo "MKTAYIAKQR" >> /tmp/test_seq.faa
        
        # Test if it works
        if diamond blastp -d "$backup" -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6 2>&1 | grep -v "Unexpected end" | head -1; then
            echo "✅ $backup WORKS! Copying to main file..."
            cp "$backup" eggnog_proteins.dmnd
            echo "✅ Database restored from backup!"
            exit 0
        fi
    fi
done

echo "❌ No working backup found"
```

## After Download

1. **Verify the database** (using the test command above)
2. **Restart Django server**
3. **Try processing a FASTA file**

## Why This Keeps Happening

1. **Download interrupted**: The .gz file is incomplete (249MB instead of full size)
2. **Server issues**: eggNOG download server returning 404 errors
3. **Network problems**: Connection timeouts during download

## Prevention

The code now automatically:
- ✅ Detects missing database files
- ✅ Tries to decompress .gz files if found
- ✅ Provides clear error messages
- ✅ Attempts automatic rebuild (if server is available)



