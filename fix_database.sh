#!/bin/bash
# Script to rebuild corrupted EggNOG database
# Run this in WSL: bash fix_database.sh

set -e

EGGNOG_DB="/home/ser1dai/eggnog_db_final"

echo "=========================================="
echo "EggNOG Database Rebuild Script"
echo "=========================================="
echo ""
echo "This will:"
echo "  1. Backup corrupted DIAMOND database"
echo "  2. Rebuild DIAMOND database (bacteria-only, ~3-5GB)"
echo "  3. Download MMseqs database"
echo "  4. Download HMMER database"
echo ""
echo "Estimated time: 30-60 minutes"
echo ""

# Activate conda
source ~/miniconda3/etc/profile.d/conda.sh
conda activate eggnog

# Backup corrupted database (if it exists)
if [ -f "$EGGNOG_DB/eggnog_proteins.dmnd" ]; then
    echo "📦 Backing up corrupted database..."
    mv "$EGGNOG_DB/eggnog_proteins.dmnd" "$EGGNOG_DB/eggnog_proteins.dmnd.corrupted.$(date +%Y%m%d_%H%M%S)" || true
    echo "   ✅ Backed up to: eggnog_proteins.dmnd.corrupted.$(date +%Y%m%d_%H%M%S)"
else
    echo "ℹ️  No existing database file found (will download fresh)"
fi

# Rebuild database
echo "🔧 Rebuilding EggNOG database..."
echo "   This will download:"
echo "     - DIAMOND database (default, ~1.2GB)"
echo "     - MMseqs2 database (-M flag)"
echo "     - HMMER database for Bacteria (-H -d 2)"
echo ""
echo "   This may take 30-60 minutes..."
echo ""

# Download DIAMOND (default), MMseqs2, and HMMER (Bacteria, taxid=2) databases
/home/ser1dai/miniconda3/envs/eggnog/bin/download_eggnog_data.py \
    --data_dir "$EGGNOG_DB" \
    -M \
    -H -d 2 \
    -y -f

# Verify the database
echo ""
echo "🔍 Verifying database..."
echo ">test" > /tmp/test_seq.faa
echo "MKTAYIAKQR" >> /tmp/test_seq.faa

if diamond blastp -d "$EGGNOG_DB/eggnog_proteins.dmnd" -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6 2>&1 | grep -q "Unexpected end of input"; then
    echo "❌ Database verification failed - still corrupted"
    exit 1
else
    echo "✅ Database rebuilt and verified successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Restart your Django server"
    echo "  2. Try processing a FASTA file again"
fi

