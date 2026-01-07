# Linux Path Fixes - Remove Windows/WSL Conversions

## Issues Found:

1. **Subprocess calls use `['wsl', 'bash', '-c', ...]`** - Should be `['bash', '-c', ...]` in Linux
2. **Path conversion functions** - Converting paths even when already Linux paths
3. **Windows path checks** - `sys.platform == 'win32'` checks
4. **Unnecessary path conversions** - Converting Linux paths to WSL paths

## Files to Fix:

1. `fasta_processor/services.py` - Remove WSL-specific code
2. `gut_auth/settings.py` - Already using Linux paths ✅

## Changes Needed:

### 1. Remove `['wsl', ...]` from subprocess calls
- Line 1015: `['wsl', 'bash', '-c', kofamscan_cmd]` → `['bash', '-c', kofamscan_cmd]`
- Line 1105: `['wsl', 'bash', '-c', diamond_cmd]` → `['bash', '-c', diamond_cmd]`
- Line 1250: `['wsl', 'bash', '-c', emapper_cmd]` → `['bash', '-c', emapper_cmd]`

### 2. Simplify path handling
- `_to_wsl_path()` should just return Linux paths as-is if already Linux
- Remove Windows path conversion logic

### 3. Remove Windows-specific checks
- Keep `sys.platform == 'win32'` check in `start_next_job_in_queue()` (for background process handling)
- But simplify path handling elsewhere

