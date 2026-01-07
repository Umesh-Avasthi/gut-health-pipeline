# FASTA File Upload & Processing Flow - Complete Analysis

## Overview
This document describes the complete step-by-step process that occurs when a user uploads a FASTA file to the Gut Health Pipeline application.

---

## 📤 **PHASE 1: File Upload & Validation**

### Step 1.1: User Uploads File(s)
- **Location**: `fasta_processor/views.py` → `upload_fasta()` function
- **URL**: `/fasta/upload/`
- **Max Files**: Up to 3 files at once
- **Max Size**: 100MB per file
- **Valid Extensions**: `.fasta`, `.fa`, `.fas`, `.fna`, `.ffn`, `.faa`, `.frn`

### Step 1.2: File Validation
The system validates:
1. **Number of files**: Must be 1-3 files
2. **File extension**: Must be a valid FASTA extension
3. **File size**: Each file must be ≤ 100MB

### Step 1.3: Database Record Creation
For each valid file:
- **FastaFile Model** created with:
  - User reference
  - File stored in `media/fasta_files/YYYY/MM/DD/`
  - Original filename
  - File size
  - Status: `'uploaded'`
  - Optional description

- **ProcessingJob Model** created with:
  - Link to FastaFile
  - User reference
  - Status: `'pending'`
  - Progress: 0%
  - Started timestamp

### Step 1.4: Queue Management
- **Function**: `start_next_job_in_queue()` in `services.py`
- **Logic**: 
  - Checks if any job is currently running
  - If no job running → starts the oldest pending job
  - If job running → new files wait in queue
  - **Ensures only ONE file processes at a time**

### Step 1.5: Background Job Start
- **Command**: `python manage.py process_fasta_job <job_id>`
- **Process**: Runs in separate background process (survives server restarts)
- **Location**: `fasta_processor/management/commands/process_fasta_job.py`

---

## 🔄 **PHASE 2: Processing Pipeline**

### Step 2.1: Job Initialization
- **Location**: `services.py` → `EggnogProcessor.process_fasta()`
- **Actions**:
  - Updates job status to `'running'`
  - Updates FastaFile status to `'processing'`
  - Sets progress to 0%
  - Records start time
  - Creates output directory: `media/results/YYYY/MM/DD/`

### Step 2.2: Database Validation
- **Location**: `services.py` → `_run_eggnog()` → Database validation section
- **Checks**:
  - Tests DIAMOND database integrity (300 second timeout)
  - If corrupted → attempts to rebuild (30-60 minutes)
  - If missing → attempts to download
  - Validates KofamScan database

### Step 2.3: Resource Setup
- **RAM Disk**: Creates temporary RAM disk for fast I/O (if available)
- **Gut Database**: Prepares optimized gut-specific database subset
- **CPU Cores**: Uses 4 cores (configurable in settings)
- **RAM Limit**: 12 GB (configurable in settings)

---

## 🧬 **PHASE 3: Multi-Tier Annotation Pipeline**

### **STEP 1: KofamScan (HMM) - Step 1/5**
- **Progress**: 10%
- **Tool**: `hmmsearch` with HMM profiles
- **Database**: Gut-specific HMM subset (10x faster than full database)
- **Command**: 
  ```bash
  hmmsearch --cpu 4 --cut_tc --max -o results.hmm profiles.hmm input.faa
  ```
- **Output**: `kofamscan.txt` (KEGG Orthologs found)
- **Timeout**: Based on file size (15 min - 4 hours)
- **Purpose**: Find KEGG Orthologs using Hidden Markov Models

### **STEP 2: GUT Fast Search (Tier-1) - Step 2/5**
- **Progress**: 20%
- **Tool**: DIAMOND BLASTP
- **Database**: Small gut-specific protein database (in RAM if possible)
- **Command**:
  ```bash
  diamond blastp -d gut_db.dmnd -q input.faa -o gut_hits.tsv --threads 4 --fast
  ```
- **Output**: `gut_hits.tsv` (protein matches)
- **Timeout**: Max 30 minutes
- **Purpose**: Fast initial search against gut-specific database (10x faster)

### **STEP 3: Filter FASTA - Step 3/5**
- **Progress**: 30%
- **Action**: Remove proteins already found in gut hits
- **Logic**:
  - Extract protein IDs from `gut_hits.tsv`
  - Filter input FASTA to exclude matched proteins
  - Create `remaining.faa` with unmatched sequences
- **Purpose**: Reduce sequences for expensive eggNOG search

### **STEP 4: eggNOG Annotation (Tier-2) - Step 4/5**
- **Progress**: 40%
- **Tool**: `emapper.py` (eggNOG-mapper)
- **Database**: Full eggNOG database (large, comprehensive)
- **Input**: Filtered FASTA (remaining sequences)
- **Command**:
  ```bash
  emapper.py -i remaining.faa -o emapper_output --cpu 4 --database eggnog
  ```
- **Output**: `emapper_output.emapper.annotations` (comprehensive annotations)
- **Timeout**: Based on file size (10 min - 4 hours)
- **Purpose**: Comprehensive functional annotation of remaining sequences

### **STEP 5: Merge Results - Step 5/5**
- **Progress**: 50-90%
- **Action**: Combine all annotation sources
- **Sources**:
  1. KofamScan results (HMM)
  2. GUT fast search results (DIAMOND)
  3. eggNOG annotation results (emapper)
- **Process**:
  - Extract enzymes from each source
  - Merge by protein ID
  - Resolve conflicts (priority: KofamScan > eggNOG > GUT)
  - Create unified enzyme annotations

---

## 📊 **PHASE 4: Pathway Scoring**

### Step 4.1: Pathway Analysis
- **Progress**: 90%
- **Location**: `services.py` → Pathway scoring section
- **Process**:
  - Maps enzymes to metabolic pathways
  - Calculates pathway scores based on:
    - Enzyme coverage
    - Biological weights
    - Pathway completeness
  - Categorizes pathways:
    - **CRITICAL**: Score < 0.1 (requires attention)
    - **LOW**: Score 0.1-0.5 (below optimal)
    - **NORMAL**: Score 0.5-2.0 (adequate)
    - **OPTIMAL**: Score > 2.0 (excellent)

### Step 4.2: Output File Generation
- **Enzyme-Level CSV**: `enzymes_<job_id>_<filename>.csv`
  - Columns: Protein ID, EC Number, KEGG KO, Confidence, Source
- **Pathway-Level CSV**: `pathways_<job_id>_<filename>.csv`
  - Columns: Pathway Name, Score, Coverage, Health Status, Enzymes

---

## ✅ **PHASE 5: Completion**

### Step 5.1: Job Completion
- **Status Update**:
  - Job status → `'completed'`
  - FastaFile status → `'completed'`
  - Progress → 100%
  - Completed timestamp recorded
  - Processing time calculated

### Step 5.2: File Storage
- **Result Files**:
  - Enzyme CSV saved to `media/results/YYYY/MM/DD/`
  - Pathway CSV saved to `media/results/YYYY/MM/DD/`
  - Files linked to ProcessingJob model

### Step 5.3: Queue Management
- **Next Job**: Automatically starts next pending job in queue
- **Function**: `start_next_job_in_queue()` called automatically

---

## 📈 **PHASE 6: User Interface Updates**

### Step 6.1: Progress Polling
- **Endpoint**: `/fasta/progress/<job_id>/`
- **Method**: JavaScript polls every 3 seconds
- **Returns**: JSON with status, progress %, message
- **Location**: `fasta_processor/static/fasta_processor/js/jobs.js`

### Step 6.2: Job Status Display
- **Jobs Page**: `/fasta/jobs/`
- **Tabs**:
  - ✅ **Completed**: Finished jobs with download links
  - 🔄 **Processing**: Active jobs with progress bars
  - ❌ **Incomplete**: Failed or stuck jobs

### Step 6.3: Results Access
- **Download Enzymes**: `/fasta/download/<job_id>/`
- **Download Pathways**: `/fasta/download-pathway/<job_id>/`
- **Pathway Dashboard**: `/fasta/pathway-dashboard/<job_id>/`
  - Visual dashboard with pathway health scores
  - Summary cards (Critical, Low, Normal, Optimal)
  - Detailed pathway metrics

---

## 🔧 **Technical Details**

### Database Paths (WSL)
- **EggNOG DB**: `/home/ser1dai/eggnog_db_final`
- **Kofam DB**: `/home/ser1dai/eggnog_db_final/kofam_db`
- **Gut DB**: Created dynamically from eggNOG subset

### Resource Configuration
- **CPU Cores**: 4 (configurable in `settings.py`)
- **RAM Limit**: 12 GB (configurable in `settings.py`)
- **Process Priority**: Uses `nice` command to prevent system hang

### Timeout Calculation
Timeouts are calculated based on file size:
- **< 10KB**: 10-15 minutes
- **< 100KB**: 20-30 minutes
- **< 1MB**: 45-60 minutes
- **< 10MB**: 2 hours
- **> 10MB**: 4 hours

### Error Handling
- **Stuck Jobs**: Auto-detected after 3 hours, reset to failed
- **Database Errors**: Auto-rebuild attempted
- **Timeout Errors**: Job marked as failed, next job starts
- **File Errors**: Validation before processing

---

## 📝 **Summary Flow Diagram**

```
User Uploads File
    ↓
File Validation (size, extension, count)
    ↓
Create FastaFile + ProcessingJob (status: pending)
    ↓
Queue Check → Start Background Process
    ↓
Job Status: running
    ↓
[STEP 1] KofamScan (HMM) - 10%
    ↓
[STEP 2] GUT Fast Search (Tier-1) - 20%
    ↓
[STEP 3] Filter FASTA - 30%
    ↓
[STEP 4] eggNOG Annotation (Tier-2) - 40%
    ↓
[STEP 5] Merge Results - 50-90%
    ↓
Pathway Scoring - 90%
    ↓
Generate CSV Files - 95%
    ↓
Job Status: completed - 100%
    ↓
Start Next Job in Queue
    ↓
User Downloads Results / Views Dashboard
```

---

## 🎯 **Key Features**

1. **Queue System**: Only one file processes at a time
2. **Multi-Tier Pipeline**: Fast gut search → Full eggNOG search
3. **Progress Tracking**: Real-time progress updates (0-100%)
4. **Error Recovery**: Auto-detection and recovery from stuck jobs
5. **Resource Optimization**: RAM disk, gut database subset, multi-core
6. **Pathway Analysis**: Health scoring and visualization
7. **Background Processing**: Survives server restarts

---

## 📚 **Related Files**

- **Views**: `fasta_processor/views.py`
- **Models**: `fasta_processor/models.py`
- **Services**: `fasta_processor/services.py`
- **Management Command**: `fasta_processor/management/commands/process_fasta_job.py`
- **Templates**: `fasta_processor/templates/fasta_processor/`
- **Static Files**: `fasta_processor/static/fasta_processor/`

---

*Last Updated: December 31, 2025*

