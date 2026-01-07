# Smart Database Search - Optimized Logic

## ✅ **Updated Logic:**

### **Search Strategy:**

1. **Step 1**: Search **small gut database** first (fast)
   - Uses optimized gut-specific database (1-2 GB)
   - Fast search with DIAMOND
   - No timeout limit - ensures complete results

2. **Step 2**: Check results
   - If sequences found in gut database → Extract results
   - Filter out found sequences from FASTA file

3. **Step 3**: Conditional full eggNOG search
   - **If sequences found in gut database AND all sequences found** → **SKIP** full eggNOG database search
   - **If sequences NOT found in gut database OR some sequences remain** → **SEARCH** full eggNOG database
   - No timeout limit - ensures complete results

---

## 🔄 **Processing Flow:**

```
1. Upload FASTA File
   ↓
2. Search Small Gut Database (NO TIMEOUT)
   - Fast search in gut-specific database
   - Finds gut-related enzymes quickly
   ↓
3. Check Results
   - If all sequences found → Use gut database results only
   - If some sequences NOT found → Continue to Step 4
   ↓
4. Filter FASTA (if needed)
   - Remove sequences found in gut database
   - Keep sequences NOT found in gut database
   ↓
5. Search Full eggNOG Database (ONLY IF NEEDED - NO TIMEOUT)
   - Only searches if sequences NOT found in gut database
   - Comprehensive search in complete 40+ GB database
   - Skips if all sequences already found
   ↓
6. Merge All Results
   - Combine KofamScan results
   - Combine GUT database results (if found)
   - Combine eggNOG database results (if searched)
   ↓
7. Generate Complete Enzyme CSV
   - All enzymes from all sources
   - Complete annotations
   - No missing data
```

---

## ⚡ **Performance Benefits:**

### **Scenario 1: All sequences found in gut database**
- ✅ Fast gut database search (minutes)
- ✅ **SKIPS** slow full eggNOG search (saves hours)
- ✅ Complete results from gut database
- **Total time: 10-30 minutes** (instead of 2-8 hours)

### **Scenario 2: Some sequences NOT found in gut database**
- ✅ Fast gut database search (minutes)
- ✅ Full eggNOG search for remaining sequences (hours)
- ✅ Complete results from both databases
- **Total time: 2-8 hours** (depending on file size)

### **Scenario 3: No sequences found in gut database**
- ✅ Fast gut database search (minutes)
- ✅ Full eggNOG search for all sequences (hours)
- ✅ Complete results from full eggNOG database
- **Total time: 2-8 hours** (depending on file size)

---

## ✅ **Guarantees:**

1. ✅ **Always searches small gut database first** (fast)
2. ✅ **Only searches full eggNOG database if needed** (efficient)
3. ✅ **No timeout limits** - processing completes naturally
4. ✅ **Complete enzyme CSV files** - no missing data
5. ✅ **All sequences processed** - nothing skipped

---

## 📊 **What You Get:**

### **Enzyme CSV File Contains:**
- ✅ All enzymes found in **small gut database** (if found)
- ✅ All enzymes found in **full eggNOG database** (if searched)
- ✅ All enzymes found by **KofamScan (HMM)**
- ✅ Complete annotations for all sequences
- ✅ No incomplete results

### **Processing Time:**
- **If all found in gut database**: 10-30 minutes ⚡
- **If need full eggNOG search**: 2-8 hours (depends on file size)

**No time limits - processing will complete naturally to ensure complete results.**

---

*Last Updated: December 31, 2025*

