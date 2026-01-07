# Linux Setup Verification - All Paths and Commands

## ✅ **VERIFICATION COMPLETE**

All code has been updated to work in **pure Linux environment** (not Windows calling WSL).

---

## 🔧 **Changes Made:**

### 1. **Removed WSL-specific subprocess calls**
- ✅ Changed `['wsl', 'bash', '-c', ...]` → `['bash', '-c', ...]`
- ✅ All commands now run directly in Linux bash
- **Locations:**
  - Line 1015: KofamScan command
  - Line 1105: DIAMOND command  
  - Line 1250: eggNOG emapper command

### 2. **Simplified path handling**
- ✅ `_to_wsl_path()` now handles Linux paths correctly
- ✅ Returns Linux paths as-is if already Linux format
- ✅ Only converts Windows paths if detected (for compatibility)
- ✅ Removed Windows-specific path checks

### 3. **Updated comments and docstrings**
- ✅ Changed "Windows path" → "Linux path" in docstrings
- ✅ Changed "WSL path" → "Linux path" in comments
- ✅ Updated function descriptions

### 4. **Database paths (already correct)**
- ✅ `EGGNOG_DB_PATH = '/home/ser1dai/eggnog_db_final'` (Linux path)
- ✅ `KOFAM_DB_PATH = '/home/ser1dai/eggnog_db_final/kofam_db'` (Linux path)

---

## 📁 **Database Paths (Linux):**

### **EggNOG Database:**
```
/home/ser1dai/eggnog_db_final/
├── eggnog_proteins.fa
├── eggnog_proteins.dmnd
├── gut_kegg_db/
│   └── gut_db.dmnd
└── your_24_pathways_kos.txt
```

### **KofamScan Database:**
```
/home/ser1dai/eggnog_db_final/kofam_db/
├── profiles.hmm
└── profiles_gut.hmm (auto-created)
```

---

## ✅ **All Commands Now Run in Linux:**

### **1. KofamScan (HMM):**
```bash
bash -c "source ~/miniconda3/etc/profile.d/conda.sh && conda activate kofamscan && export HMMER_NCPU=4 && hmmsearch --cpu 4 --cut_tc --max -o results.hmm profiles_gut.hmm input.faa"
```

### **2. DIAMOND (GUT Search):**
```bash
bash -c "source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && diamond blastp -d /mnt/ramdisk/gut_db -q input.faa -o gut_hits.tsv --threads 4 --block-size 4 --index-chunks 1 --fast --outfmt 6"
```

### **3. eggNOG Annotation:**
```bash
bash -c "source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && emapper.py -i remaining.faa -o emapper_output --data_dir /home/ser1dai/eggnog_db_final -m diamond --cpu 4 --override"
```

---

## 🔍 **Path Handling Logic:**

### **`_to_wsl_path()` Function:**
- ✅ If path starts with `/home/`, `/usr/`, `/opt/`, `/mnt/`, `/tmp/`, `/var/` → Returns as-is (Linux path)
- ✅ If path starts with `/` and no `:` → Returns as-is (Linux path)
- ✅ If path has `:` (Windows drive) → Converts to `/mnt/c/...` format (for compatibility)
- ✅ Otherwise → Returns normalized path

### **All Internal Paths:**
- ✅ Database paths: `/home/ser1dai/eggnog_db_final/...`
- ✅ Temp directories: Linux paths
- ✅ Output files: Linux paths
- ✅ Script paths: Linux paths

---

## ✅ **Verification Checklist:**

- [x] All subprocess calls use `['bash', '-c', ...]` (not `['wsl', ...]`)
- [x] Database paths are Linux paths (`/home/ser1dai/...`)
- [x] Path conversion functions handle Linux paths correctly
- [x] No Windows-specific path conversions for Linux paths
- [x] Comments and docstrings updated to reflect Linux environment
- [x] Settings.py uses Linux paths
- [x] All commands run directly in Linux bash

---

## 🚀 **Ready for Linux Deployment:**

Your project is now **fully configured for Linux environment**:

1. ✅ All commands run in Linux bash (not WSL)
2. ✅ All paths are Linux paths
3. ✅ Database paths point to Linux locations
4. ✅ No Windows/WSL conversions needed
5. ✅ Works in pure Linux (Ubuntu, Debian, etc.)

---

## 📝 **Note:**

The code still has **compatibility code** for Windows paths (in `_to_wsl_path()`), but it will:
- ✅ Use Linux paths directly if they're already Linux format
- ✅ Only convert if Windows paths are detected
- ✅ Work perfectly in pure Linux environment

---

*Last Updated: December 31, 2025*

