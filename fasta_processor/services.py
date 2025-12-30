"""
Service layer for integrating with eggnog database processing
"""
import os
import subprocess
import sys
import time
import shutil
import logging
from pathlib import Path
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import FastaFile, ProcessingJob

# Set up logging
logger = logging.getLogger(__name__)


def start_next_job_in_queue():
    """
    Queue management: Start the next pending job only if no job is currently running.
    This ensures only one file processes at a time.
    
    Returns:
        ProcessingJob instance if started, None if no job to start or one already running
    """
    # Check if any job is currently running (not stuck)
    running_jobs = ProcessingJob.objects.filter(status='running')
    
    # Filter out stuck jobs (running for more than 6 hours)
    active_running = running_jobs.filter(
        started_at__gt=timezone.now() - timedelta(hours=6)
    )
    
    if active_running.exists():
        logger.info(f"Queue: {active_running.count()} job(s) currently running. Waiting for completion...")
        return None  # Don't start new job, one is already running
    
    # Get the oldest pending job
    next_job = ProcessingJob.objects.filter(status='pending').order_by('started_at').first()
    
    if not next_job:
        logger.info("Queue: No pending jobs to process")
        return None
    
    # Start the next job
    logger.info(f"Queue: Starting next job {next_job.id} ({next_job.fasta_file.original_filename})")
    
    # Start processing in background
    manage_py = Path(settings.BASE_DIR) / 'manage.py'
    
    try:
        if sys.platform == 'win32':
            subprocess.Popen(
                [sys.executable, str(manage_py), 'process_fasta_job', str(next_job.id)],
                stdout=None,
                stderr=None,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=False
            )
        else:
            subprocess.Popen(
                [sys.executable, str(manage_py), 'process_fasta_job', str(next_job.id)],
                stdout=None,
                stderr=None,
                start_new_session=True
            )
        logger.info(f"Queue: Successfully started job {next_job.id} in background")
        return next_job
    except Exception as e:
        logger.error(f"Queue: Failed to start job {next_job.id}: {str(e)}")
        return None


class EggnogProcessor:
    """Service class to handle eggnog processing"""
    
    def __init__(self, eggnog_db_path=None, kofam_db_path=None):
        """
        Initialize processor with eggnog and kofam database paths
        
        Args:
            eggnog_db_path: Path to eggnog_db_final folder
            kofam_db_path: Path to kofam_db folder
        """
        self.eggnog_db_path = eggnog_db_path or getattr(settings, 'EGGNOG_DB_PATH', None)
        if not self.eggnog_db_path:
            # Default WSL path
            self.eggnog_db_path = '/home/ser1dai/eggnog_db_final'
        
        # Normalize eggnog_db_path to WSL format
        self.eggnog_db_path = self._normalize_path_to_wsl(self.eggnog_db_path)
        
        # Initialize kofam_db_path
        self.kofam_db_path = kofam_db_path or getattr(settings, 'KOFAM_DB_PATH', None)
        if not self.kofam_db_path:
            # Default WSL path
            self.kofam_db_path = '/home/ser1dai/eggnog_db_final/kofam_db'
        
        # Normalize kofam_db_path to WSL format
        self.kofam_db_path = self._normalize_path_to_wsl(self.kofam_db_path)
    
    def process_fasta(self, fasta_file_instance):
        """
        Process a FASTA file using eggnog
        
        Args:
            fasta_file_instance: FastaFile model instance
            
        Returns:
            ProcessingJob instance
        """
        # Create or get processing job
        job, created = ProcessingJob.objects.get_or_create(
            fasta_file=fasta_file_instance,
            defaults={
                'user': fasta_file_instance.user,
                'status': 'pending'
            }
        )
        
        # Check if job is already running (and not stuck)
        if not created and job.status == 'running':
            # Check if job has been running for more than 2 hours (likely stuck)
            if job.started_at and (timezone.now() - job.started_at) > timedelta(hours=2):
                logger.warning(f"Job {job.id} has been running for more than 2 hours, resetting to pending")
                job.status = 'pending'
                job.error_message = 'Job was stuck and has been reset'
                job.save()
            else:
                logger.info(f"Job {job.id} is already running, skipping")
                return job  # Already processing
        
        # Reset job if it was previously failed
        if not created and job.status == 'failed':
            logger.info(f"Retrying failed job {job.id}")
            job.error_message = ''
            job.result_file = None
            job.completed_at = None
            job.processing_time = None
        
        # Update status
        job.status = 'running'
        job.started_at = timezone.now()
        job.progress = 0
        job.progress_message = 'Starting processing...'
        job.save()
        
        fasta_file_instance.status = 'processing'
        fasta_file_instance.save()
        
        try:
            logger.info(f"Starting processing for file: {fasta_file_instance.original_filename} (Job ID: {job.id})")
            
            # Get file path
            fasta_path = fasta_file_instance.file.path
            logger.info(f"FASTA file path: {fasta_path}")
            
            # Check file size and provide resource estimate
            file_size_mb = os.path.getsize(fasta_path) / (1024 * 1024)
            logger.info(f"FASTA file size: {file_size_mb:.2f} MB")
            
            if file_size_mb > 50:
                logger.warning(f"⚠️  Large file detected ({file_size_mb:.2f} MB). Processing may take 1-4 hours and use significant resources.")
            elif file_size_mb > 10:
                logger.warning(f"⚠️  Medium file detected ({file_size_mb:.2f} MB). Processing may take 30-60 minutes.")
            
            # Prepare output path
            media_root = Path(settings.MEDIA_ROOT) if not isinstance(settings.MEDIA_ROOT, Path) else settings.MEDIA_ROOT
            date_path = timezone.now().strftime('%Y/%m/%d')
            output_dir = media_root / 'results' / date_path
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Output as CSV (enzymes.csv format)
            base_name = Path(fasta_file_instance.original_filename).stem
            output_file = output_dir / f"enzymes_{job.id}_{base_name}.csv"
            logger.info(f"Output file will be: {output_file}")
            
            # Run eggnog processing
            logger.info("Calling _run_eggnog()...")
            result = self._run_eggnog(fasta_path, str(output_file), job)
            logger.info(f"_run_eggnog() returned: success={result.get('success')}, error={result.get('error', 'None')}")
            
            if result['success']:
                # Update job with results
                job.status = 'completed'
                job.completed_at = timezone.now()
                job.progress = 100
                job.progress_message = 'Processing completed successfully!'
                # Use existing media_root variable (no need to recalculate)
                job.result_file.name = str(output_file.relative_to(media_root))
                job.processing_time = result.get('processing_time', 0)
                job.eggnog_version = result.get('version', 'unknown')
                job.save()
                
                fasta_file_instance.status = 'completed'
                fasta_file_instance.save()
                
                # Log final FASTA file location if available
                final_fasta = result.get('final_fasta_file')
                if final_fasta:
                    logger.info(f"✅ Final merged FASTA file saved to: {final_fasta}")
                    logger.info(f"   This file contains sequences annotated by eggnog and/or kofamscan")
                
                logger.info(f"✅ Processing completed successfully for job {job.id}")
                
                # Queue management: Start next job in queue
                logger.info("Queue: Job completed, checking for next job in queue...")
                start_next_job_in_queue()
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Processing failed: {error_msg}")
                raise Exception(error_msg)
                
        except Exception as e:
            # Handle errors
            error_msg = str(e)
            logger.exception(f"Exception during processing: {error_msg}")
            try:
                job.status = 'failed'
                job.completed_at = timezone.now()
                job.error_message = error_msg
                job.save(update_fields=['status', 'completed_at', 'error_message'])
            except Exception as db_error:
                logger.error(f"Failed to save job status to database: {db_error}")
            
            try:
                fasta_file_instance.status = 'failed'
                fasta_file_instance.save(update_fields=['status'])
            except Exception as db_error:
                logger.error(f"Failed to save fasta file status to database: {db_error}")
            
            logger.error(f"❌ Processing failed for job {job.id}: {error_msg}")
            
            # Queue management: Start next job in queue even if this one failed
            logger.info("Queue: Job failed, checking for next job in queue...")
            start_next_job_in_queue()
        
        return job
    
    def _extract_protein_ids_from_kofamscan(self, kofamscan_results_file):
        """
        Extract protein IDs from KofamScan results file.
        
        Args:
            kofamscan_results_file: Path to kofamscan results file
            
        Returns:
            set: Set of protein IDs found by KofamScan (high confidence only)
        """
        protein_ids = set()
        
        if not os.path.exists(kofamscan_results_file):
            return protein_ids
        
        with open(kofamscan_results_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # High confidence hits start with "*"
                confident = line.startswith("*")
                if confident:
                    line = line.lstrip("* ").strip()
                
                parts = line.split()
                if len(parts) >= 2:
                    protein_id = parts[0]
                    # Only include high confidence hits
                    if confident:
                        protein_ids.add(protein_id)
        
        logger.info(f"Extracted {len(protein_ids)} protein IDs from KofamScan results")
        return protein_ids
    
    def _filter_fasta_by_proteins(self, input_fasta, protein_ids_to_exclude, output_fasta):
        """
        Create a filtered FASTA file excluding specified protein IDs.
        
        Args:
            input_fasta: Path to input FASTA file
            protein_ids_to_exclude: Set of protein IDs to exclude
            output_fasta: Path to output filtered FASTA file
            
        Returns:
            int: Number of sequences in filtered file
        """
        excluded_count = 0
        included_count = 0
        
        with open(input_fasta, 'r') as infile, open(output_fasta, 'w') as outfile:
            current_seq = None
            current_id = None
            write_current = False
            
            for line in infile:
                if line.startswith('>'):
                    # Save previous sequence if needed
                    if current_seq and write_current:
                        outfile.write(current_seq)
                        included_count += 1
                    
                    # Parse new sequence header
                    current_id = line[1:].split()[0].strip()  # Get first word after >
                    current_seq = line
                    write_current = current_id not in protein_ids_to_exclude
                    
                    if not write_current:
                        excluded_count += 1
                else:
                    if current_seq:
                        current_seq += line
                    else:
                        # Handle case where file doesn't start with >
                        current_seq = line
                        write_current = True
            
            # Write last sequence if needed
            if current_seq and write_current:
                outfile.write(current_seq)
                included_count += 1
        
        logger.info(f"Filtered FASTA: {included_count} sequences included, {excluded_count} excluded")
        return included_count
    
    def _calculate_timeout(self, file_size_mb, tool='emapper'):
        """
        Calculate timeout based on file size and tool type.
        Optimized for small files to prevent excessive wait times.
        
        Args:
            file_size_mb: File size in MB
            tool: Tool name ('emapper' or 'kofamscan')
            
        Returns:
            Timeout in seconds
        """
        if tool == 'kofamscan':
            if file_size_mb < 0.01:  # < 10KB - very small
                return 15 * 60  # 15 minutes
            elif file_size_mb < 0.1:  # < 100KB - small
                return 30 * 60  # 30 minutes
            elif file_size_mb < 1:
                return 1 * 3600  # 1 hour
            elif file_size_mb < 10:
                return 2 * 3600  # 2 hours
            else:
                return 4 * 3600  # 4 hours
        else:  # emapper
            if file_size_mb < 0.01:  # < 10KB - very small (like 2KB)
                return 10 * 60  # 10 minutes (should complete in 2-5 min)
            elif file_size_mb < 0.1:  # < 100KB - small
                return 20 * 60  # 20 minutes
            elif file_size_mb < 1:
                return 45 * 60  # 45 minutes (reduced from 2 hours)
            elif file_size_mb < 10:
                return 2 * 3600  # 2 hours (reduced from 4 hours)
            else:
                return 4 * 3600  # 4 hours (reduced from 6 hours)
    
    def _monitor_process(self, process, timeout_seconds, job=None, step_message='Processing', check_interval=60, file_size_mb=None):
        """
        Monitor a subprocess with timeout and periodic progress updates.
        Optimized check intervals for small files.
        
        Args:
            process: subprocess.Popen instance
            timeout_seconds: Maximum time to wait
            job: ProcessingJob instance (optional)
            step_message: Message to display in progress updates
            check_interval: Seconds between progress updates (default 60)
            file_size_mb: File size in MB for optimization (optional)
            
        Returns:
            tuple: (return_code, timed_out)
        """
        # Optimize check interval for small files - check more frequently
        if file_size_mb is not None and file_size_mb < 0.1:  # < 100KB
            check_interval = 10  # Check every 10 seconds for very small files
        elif file_size_mb is not None and file_size_mb < 1:  # < 1MB
            check_interval = 30  # Check every 30 seconds for small files
        
        process_start_time = time.time()
        last_progress_update = time.time()
        
        try:
            while True:
                return_code = process.poll()
                if return_code is not None:
                    return return_code, False
                
                elapsed = time.time() - process_start_time
                if elapsed > timeout_seconds:
                    timeout_minutes = timeout_seconds / 60
                    logger.warning(f"{step_message} exceeded timeout of {timeout_minutes:.1f} minutes")
                    process.kill()
                    process.wait()
                    return -1, True
                
                # Update progress message periodically
                if time.time() - last_progress_update > check_interval:
                    elapsed_minutes = int(elapsed / 60)
                    elapsed_seconds = int(elapsed % 60)
                    if job:
                        if elapsed_minutes > 0:
                            job.progress_message = f'{step_message}... Elapsed: {elapsed_minutes}m {elapsed_seconds}s'
                        else:
                            job.progress_message = f'{step_message}... Elapsed: {elapsed_seconds}s'
                        try:
                            job.save(update_fields=['progress_message'])
                        except Exception as e:
                            logger.warning(f"Could not update job progress message: {e}")
                    logger.info(f"{step_message} still running... ({elapsed_minutes}m {elapsed_seconds}s elapsed)")
                    last_progress_update = time.time()
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.warning(f"Received KeyboardInterrupt during {step_message}, terminating process...")
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            return -1, False
    
    def _read_log_files(self, stdout_file, stderr_file):
        """
        Read stdout and stderr log files.
        
        Args:
            stdout_file: Path to stdout log file
            stderr_file: Path to stderr log file
            
        Returns:
            tuple: (stdout_content, stderr_content)
        """
        stdout_content = ""
        stderr_content = ""
        
        if stdout_file.exists():
            with open(stdout_file, 'r', encoding='utf-8') as f:
                stdout_content = f.read()
        
        if stderr_file.exists():
            with open(stderr_file, 'r', encoding='utf-8') as f:
                stderr_content = f.read()
        
        return stdout_content, stderr_content
    
    def _load_script_template(self, template_name, replacements):
        """
        Load a script template from the scripts directory and replace placeholders.
        
        Args:
            template_name: Name of template file (without .py extension)
            replacements: Dict of placeholder -> value replacements
            
        Returns:
            Script content with replacements applied
        """
        template_path = Path(__file__).parent / "scripts" / f"{template_name}_template.py"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Replace placeholders
        for placeholder, value in replacements.items():
            template_content = template_content.replace(f"{{{placeholder}}}", str(value))
        
        return template_content
    
    def _run_script_template(self, template_name, replacements, temp_dir, conda_env='eggnog', timeout=300, step_name='Script'):
        """
        Helper method to load, write, and execute a script template.
        
        Args:
            template_name: Name of template file (without .py extension)
            replacements: Dict of placeholder -> value replacements
            temp_dir: Temporary directory to write script
            conda_env: Conda environment name (default: 'eggnog')
            timeout: Timeout in seconds (default: 300)
            step_name: Name for logging (default: 'Script')
            
        Returns:
            tuple: (success: bool, result: subprocess.CompletedProcess or None)
        """
        script_file = temp_dir / f"run_{template_name}.py"
        script_content = self._load_script_template(template_name, replacements)
        
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        script_wsl = self._to_wsl_path(str(script_file))
        cmd = f"""source ~/miniconda3/etc/profile.d/conda.sh && conda activate {conda_env} && python3 {script_wsl}"""
        
        logger.info(f"Running {step_name}: {cmd}")
        result = subprocess.run(
            ['wsl', 'bash', '-c', cmd],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {step_name} completed successfully")
            if result.stdout:
                logger.info(f"{step_name} stdout: {result.stdout[-500:]}")
            return True, result
        else:
            error_msg = f"{step_name} failed (return code {result.returncode}): {result.stderr[-1000:] if result.stderr else 'No error output'}"
            logger.error(error_msg)
            return False, result
    
    def _normalize_path_to_wsl(self, path):
        """
        Normalize a path string to WSL format (helper for __init__).
        This is a simplified version that doesn't require _to_wsl_path.
        
        Args:
            path: Path string or Path object
            
        Returns:
            Normalized WSL path string
        """
        if isinstance(path, Path):
            path_str = str(path)
        else:
            path_str = path
        
        # Already WSL path
        if path_str.startswith(('/home/', '/mnt/', '/usr/', '/opt/')):
            return path_str.replace('\\', '/')
        
        # Windows path - simple conversion (full conversion done later if needed)
        if ':' in path_str or path_str.startswith('\\'):
            # Simple fallback conversion
            normalized = path_str.replace('\\', '/')
            # Convert drive letters (C: -> /mnt/c)
            if ':' in normalized:
                parts = normalized.split(':', 1)
                if len(parts) == 2:
                    drive = parts[0].lower()
                    rest = parts[1].lstrip('/')
                    return f"/mnt/{drive}/{rest}"
            return normalized
        
        # Already forward slashes
        return path_str.replace('\\', '/')
    
    def _setup_ramdisk(self):
        """
        Setup RAM disk for fast database access (10GB tmpfs).
        Returns RAM disk path if successful, None otherwise.
        This is optional - pipeline will work without it, just slower.
        """
        ramdisk_path = "/mnt/ramdisk"
        
        # First check if already mounted (fast check)
        check_cmd = f"mountpoint -q {ramdisk_path} 2>/dev/null && echo 'mounted' || echo 'not_mounted'"
        try:
            check_result = subprocess.run(['wsl', 'bash', '-c', check_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=5)
            if 'mounted' in check_result.stdout:
                logger.info(f"✅ RAM disk already available at {ramdisk_path}")
                return ramdisk_path
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️  RAM disk check timed out. Continuing without RAM disk optimization.")
            return None
        except Exception as e:
            logger.warning(f"⚠️  Could not check RAM disk status: {e}. Continuing without RAM disk optimization.")
            return None
        
        # Try to setup RAM disk (non-blocking, with shorter timeout)
        # Use a simpler approach that doesn't require sudo if directory exists
        setup_cmd = f"""
        # Try to create directory first (may not need sudo)
        mkdir -p {ramdisk_path} 2>/dev/null || true
        # Check if already mounted
        if mountpoint -q {ramdisk_path} 2>/dev/null; then
            echo "already_mounted"
        else
            # Try mounting without sudo first (if user has permissions)
            mount -t tmpfs -o size=10G tmpfs {ramdisk_path} 2>/dev/null && echo "mounted" || echo "mount_failed"
        fi
        """
        
        try:
            result = subprocess.run(['wsl', 'bash', '-c', setup_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if 'mounted' in result.stdout or 'already_mounted' in result.stdout:
                logger.info(f"✅ RAM disk available at {ramdisk_path}")
                return ramdisk_path
            else:
                logger.info(f"ℹ️  RAM disk setup skipped (requires sudo permissions). Pipeline will continue without RAM disk optimization.")
                return None
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️  RAM disk setup timed out. Continuing without RAM disk optimization.")
            return None
        except Exception as e:
            logger.warning(f"⚠️  Could not setup RAM disk: {e}. Continuing without RAM disk optimization.")
            return None
    
    def _rebuild_eggnog_database(self, eggnog_db_wsl):
        """
        Rebuild corrupted EggNOG database using download_eggnog_data.py.
        This fixes "Unexpected end of input" errors from corrupted DIAMOND database.
        """
        logger.warning(f"⚠️  DIAMOND database is corrupted. Attempting to rebuild...")
        
        # Backup corrupted database
        backup_cmd = f"mv {eggnog_db_wsl}/eggnog_proteins.dmnd {eggnog_db_wsl}/eggnog_proteins.dmnd.corrupted 2>/dev/null || true"
        subprocess.run(['wsl', 'bash', '-c', backup_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        
        # Rebuild database (DIAMOND, MMseqs, and HMMER for Bacteria)
        logger.info(f"🔧 Rebuilding EggNOG database (~30-60 minutes)...")
        logger.info(f"   This will download: DIAMOND (default), MMseqs2 (-M), and HMMER Bacteria (-H -d 2)")
        logger.info(f"   Command: download_eggnog_data.py --data_dir {eggnog_db_wsl} -M -H -d 2 -y -f")
        
        rebuild_cmd = f"""
        source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && \
        /home/ser1dai/miniconda3/envs/eggnog/bin/download_eggnog_data.py \
        --data_dir {eggnog_db_wsl} -M -H -d 2 -y -f 2>&1
        """
        
        # Run rebuild in background with progress logging
        logger.info(f"⏳ Starting database rebuild (this may take 30-60 minutes)...")
        rebuild_result = subprocess.run(['wsl', 'bash', '-c', rebuild_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=7200)
        
        if rebuild_result.returncode == 0:
            # Verify the database was rebuilt correctly
            verify_cmd = f"source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && echo '>test' > /tmp/test_seq.faa && echo 'MKTAYIAKQR' >> /tmp/test_seq.faa && diamond blastp -d {eggnog_db_wsl}/eggnog_proteins.dmnd -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6 2>&1 | head -1"
            verify_result = subprocess.run(['wsl', 'bash', '-c', verify_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
            
            if 'Unexpected end of input' not in verify_result.stdout and 'Unexpected end of input' not in verify_result.stderr:
                logger.info(f"✅ EggNOG database rebuilt and verified successfully")
                return True
            else:
                logger.error(f"❌ Database rebuild completed but verification failed. Database may still be corrupted.")
                return False
        else:
            error_output = rebuild_result.stderr[-1000:] if rebuild_result.stderr else rebuild_result.stdout[-1000:]
            logger.error(f"❌ Failed to rebuild EggNOG database. Error: {error_output}")
            logger.error(f"   Please run manually: download_eggnog_data.py --data_dir {eggnog_db_wsl} -M -H -d 2 -y -f")
            return False
    
    def _ensure_gut_database(self, eggnog_db_wsl):
        """
        Ensure gut database exists. Create it if missing.
        Returns path to gut_db.dmnd if successful, None otherwise.
        """
        gut_db_path = f"{eggnog_db_wsl}/gut_kegg_db/gut_db.dmnd"
        ko_list_file = f"{eggnog_db_wsl}/your_24_pathways_kos.txt"
        eggnog_proteins_fa = f"{eggnog_db_wsl}/eggnog_proteins.fa"
        
        # Check if gut database already exists
        check_cmd = f"test -f {gut_db_path} && echo 'exists' || echo 'missing'"
        check_result = subprocess.run(['wsl', 'bash', '-c', check_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'exists' in check_result.stdout:
            logger.info(f"✅ Gut database found at {gut_db_path}")
            return gut_db_path
        
        # Check if we have the required files to build it
        check_ko_cmd = f"test -f {ko_list_file} && echo 'exists' || echo 'missing'"
        ko_check = subprocess.run(['wsl', 'bash', '-c', check_ko_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'missing' in ko_check.stdout:
            logger.warning(f"⚠️  KO list file not found at {ko_list_file}. Skipping gut database creation.")
            return None
        
        # Check if eggnog_proteins.fa exists (needed to build gut database)
        check_fa_cmd = f"test -f {eggnog_proteins_fa} && echo 'exists' || echo 'missing'"
        fa_check = subprocess.run(['wsl', 'bash', '-c', check_fa_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'missing' in fa_check.stdout:
            logger.warning(f"⚠️  eggnog_proteins.fa not found at {eggnog_proteins_fa}. Cannot build gut database.")
            return None
        
        # Create gut database
        logger.info(f"🔧 Creating gut database (this may take a few minutes)...")
        gut_proteins_fa = f"{eggnog_db_wsl}/gut_proteins.fa"
        gut_db_dir = f"{eggnog_db_wsl}/gut_kegg_db"
        
        create_cmd = f"""
        mkdir -p {gut_db_dir} && \
        grep -Ff {ko_list_file} {eggnog_proteins_fa} > {gut_proteins_fa} && \
        source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && \
        diamond makedb -p 4 --in {gut_proteins_fa} -d {gut_db_dir}/gut_db
        """
        
        create_result = subprocess.run(['wsl', 'bash', '-c', create_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3600)
        
        if create_result.returncode == 0 and os.path.exists(gut_db_path.replace('/mnt/c/', 'C:\\').replace('/', '\\')):
            logger.info(f"✅ Gut database created successfully at {gut_db_path}")
            return gut_db_path
        else:
            logger.warning(f"⚠️  Failed to create gut database: {create_result.stderr[-500:] if create_result.stderr else 'Unknown error'}")
            return None
    
    def _copy_to_ramdisk(self, source_file, ramdisk_path):
        """
        Copy database file to RAM disk for faster access.
        Returns path in RAM disk if successful, original path otherwise.
        """
        if not ramdisk_path:
            return source_file
        
        filename = os.path.basename(source_file)
        ramdisk_file = f"{ramdisk_path}/{filename}"
        
        # Check if already in RAM disk
        check_cmd = f"test -f {ramdisk_file} && echo 'exists' || echo 'missing'"
        check_result = subprocess.run(['wsl', 'bash', '-c', check_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'exists' in check_result.stdout:
            # Verify file is not empty
            size_cmd = f"test -s {ramdisk_file} && echo 'has_data' || echo 'empty'"
            size_result = subprocess.run(['wsl', 'bash', '-c', size_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if 'has_data' in size_result.stdout:
                logger.info(f"✅ Database already in RAM disk: {ramdisk_file}")
                return ramdisk_file
        
        # Copy to RAM disk
        logger.info(f"📦 Copying database to RAM disk (this may take a minute)...")
        copy_cmd = f"cp {source_file} {ramdisk_file} 2>&1"
        copy_result = subprocess.run(['wsl', 'bash', '-c', copy_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        
        if copy_result.returncode == 0:
            logger.info(f"✅ Database copied to RAM disk: {ramdisk_file}")
            return ramdisk_file
        else:
            logger.warning(f"⚠️  Could not copy to RAM disk: {copy_result.stderr}. Using original location.")
            return source_file
    
    def _create_gut_hmm_subset(self, kofam_db_wsl, eggnog_db_wsl):
        """
        Create a smaller HMM database subset containing only gut-related KOs.
        This dramatically speeds up KofamScan (from 20+ minutes to 2-3 minutes).
        """
        ko_list_file = f"{eggnog_db_wsl}/your_24_pathways_kos.txt"
        full_profiles_hmm = f"{kofam_db_wsl}/profiles.hmm"
        gut_profiles_hmm = f"{kofam_db_wsl}/profiles_gut.hmm"
        
        # Check if gut subset already exists
        check_cmd = f"test -f {gut_profiles_hmm} && test -s {gut_profiles_hmm} && echo 'exists' || echo 'missing'"
        check_result = subprocess.run(['wsl', 'bash', '-c', check_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'exists' in check_result.stdout:
            logger.info(f"✅ Gut HMM subset already exists at {gut_profiles_hmm}")
            return gut_profiles_hmm
        
        # Check if KO list file exists
        check_ko_cmd = f"test -f {ko_list_file} && echo 'exists' || echo 'missing'"
        ko_check = subprocess.run(['wsl', 'bash', '-c', check_ko_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'missing' in ko_check.stdout:
            logger.warning(f"⚠️  KO list file not found. Using full HMM database (will be slower).")
            return full_profiles_hmm
        
        # Use hmmfetch (CORRECT method) to extract HMM profiles
        # This preserves the binary HMM structure correctly - DO NOT use grep/Python extraction
        logger.info(f"🔧 Creating gut HMM subset using hmmfetch (correct method, preserves binary structure)...")
        
        # First, ensure the full HMM database is indexed
        self._ensure_hmmpress(full_profiles_hmm)
        
        # Extract profiles using hmmfetch -f (reads KO names from file)
        # This is the ONLY correct way to extract HMM profiles without corrupting binary structure
        extract_cmd = f"""
        source ~/miniconda3/etc/profile.d/conda.sh && conda activate kofamscan && \
        hmmfetch -f {full_profiles_hmm} {ko_list_file} > {gut_profiles_hmm} 2>&1
        """
        
        extract_result = subprocess.run(['wsl', 'bash', '-c', extract_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
        
        # Verify the extracted file is valid (must have HMMER3 header)
        verify_cmd = f"test -f {gut_profiles_hmm} && test -s {gut_profiles_hmm} && head -1 {gut_profiles_hmm} 2>/dev/null | grep -q 'HMMER3' && echo 'valid' || echo 'invalid'"
        verify_result = subprocess.run(['wsl', 'bash', '-c', verify_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'valid' in verify_result.stdout:
            logger.info(f"✅ Gut HMM subset created successfully using hmmfetch")
            # Index the subset
            self._ensure_hmmpress(gut_profiles_hmm)
            return gut_profiles_hmm
        else:
            error_msg = extract_result.stderr[-500:] if extract_result.stderr else extract_result.stdout[-500:] if extract_result.stdout else 'Unknown error'
            logger.warning(f"⚠️  Failed to create gut HMM subset with hmmfetch: {error_msg}. Using full database.")
            # Clean up invalid file
            subprocess.run(['wsl', 'bash', '-c', f"rm -f {gut_profiles_hmm} {gut_profiles_hmm}.*"], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            return full_profiles_hmm
    
    def _ensure_hmmpress(self, profiles_hmm):
        """
        Ensure HMM database is pressed (indexed) for faster searches.
        """
        h3i_file = f"{profiles_hmm}.h3i"
        check_cmd = f"test -f {h3i_file} && test -s {h3i_file} && echo 'exists' || echo 'missing'"
        check_result = subprocess.run(['wsl', 'bash', '-c', check_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
        
        if 'exists' in check_result.stdout:
            logger.info(f"✅ HMM database already indexed")
            return True
        
        # Run hmmpress
        logger.info(f"🔧 Indexing HMM database (this may take 5-10 minutes)...")
        press_cmd = f"source ~/miniconda3/etc/profile.d/conda.sh && conda activate kofamscan && cd $(dirname {profiles_hmm}) && rm -f {profiles_hmm}.h3i && hmmpress -f {profiles_hmm} 2>&1"
        press_result = subprocess.run(['wsl', 'bash', '-c', press_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=1800)
        
        if press_result.returncode == 0:
            logger.info(f"✅ HMM database indexed successfully")
            return True
        else:
            logger.warning(f"⚠️  Failed to index HMM database: {press_result.stderr[-500:] if press_result.stderr else 'Unknown error'}")
            return False
    
    def _run_eggnog(self, input_file, output_file, job=None):
        """
        Run optimized annotation pipeline:
        1. KofamScan (HMM) - hmmsearch with prebuilt profiles.hmm (FAST - runs first)
        2. GUT FAST SEARCH (Tier-1) - Mini eggNOG database in RAM (10x faster)
        3. FILTER FASTA - Remove proteins found in gut hits
        4. eggNOG Annotation (Tier-2) - Full eggNOG database on remaining sequences
        5. MERGE RESULTS - Combine all sources
        6. Pathway scoring and final FASTA creation
        
        Args:
            input_file: Path to input FASTA file (Windows path)
            output_file: Path to output file (Windows path)
            job: ProcessingJob instance to update progress (optional)
            
        Returns:
            dict with 'success', 'error', 'processing_time', 'version'
        """
        start_time = time.time()
        
        # Initialize result file variables
        emapper_enzymes_file = None
        kofamscan_kos_file = None
        
        try:
            # Convert Windows paths to WSL paths if needed
            input_file_wsl = self._to_wsl_path(input_file)
            output_file_wsl = self._to_wsl_path(output_file)
            
            # Create temporary directory for intermediate files
            temp_dir = Path(output_file).parent / f"temp_{int(time.time())}"
            temp_dir.mkdir(exist_ok=True)
            temp_dir_wsl = self._to_wsl_path(str(temp_dir))
            
            # Resource configuration: Get from settings (default: 4 cores, 12 GB RAM)
            cpu_cores = getattr(settings, 'FASTA_PROCESSING_CPU_CORES', 4)
            ram_limit_gb = getattr(settings, 'FASTA_PROCESSING_RAM_GB', 12)
            
            # Cache file size (used multiple times)
            file_size_mb = os.path.getsize(input_file) / (1024 * 1024) if os.path.exists(input_file) else 10
            
            # Ensure eggnog_db_wsl uses forward slashes and is a proper WSL path
            eggnog_db_str = str(self.eggnog_db_path).replace('\\', '/')
            if eggnog_db_str.startswith('/home/') or eggnog_db_str.startswith('/mnt/'):
                eggnog_db_wsl = eggnog_db_str
            elif eggnog_db_str.startswith('/') and not ':' in eggnog_db_str:
                eggnog_db_wsl = eggnog_db_str
            else:
                eggnog_db_wsl = self._to_wsl_path(eggnog_db_str)
            
            # Prepare kofam database path
            kofam_db_wsl = str(self.kofam_db_path).replace('\\', '/')
            if ':' in kofam_db_wsl or kofam_db_wsl.startswith('\\'):
                kofam_db_wsl = self._to_wsl_path(str(self.kofam_db_path))
            elif not (kofam_db_wsl.startswith('/home/') or kofam_db_wsl.startswith('/mnt/')):
                kofam_db_wsl = self._to_wsl_path(kofam_db_wsl)
            
            # ============================================================================
            # DATABASE VALIDATION: Check if DIAMOND database is corrupted
            # ============================================================================
            eggnog_proteins_dmnd = f"{eggnog_db_wsl}/eggnog_proteins.dmnd"
            # Test database by actually running a search (not just dbinfo, which can pass on corrupted DBs)
            test_db_cmd = f"source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && echo '>test' > /tmp/test_seq.faa && echo 'MKTAYIAKQR' >> /tmp/test_seq.faa && diamond blastp -d {eggnog_proteins_dmnd} -q /tmp/test_seq.faa --threads 1 --max-target-seqs 1 --outfmt 6 2>&1"
            db_test = subprocess.run(['wsl', 'bash', '-c', test_db_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
            
            # Check for corruption in both stdout and stderr (error can appear in either)
            db_output = db_test.stdout + db_test.stderr
            
            # Check if file doesn't exist - try to decompress .gz file if it exists
            if 'No such file or directory' in db_output:
                logger.warning(f"⚠️  DIAMOND database file not found. Checking for compressed file...")
                gz_file = f"{eggnog_proteins_dmnd}.gz"
                check_gz_cmd = f"test -f {gz_file} && test -s {gz_file} && echo 'exists' || echo 'missing'"
                gz_check = subprocess.run(['wsl', 'bash', '-c', check_gz_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                
                if 'exists' in gz_check.stdout:
                    logger.info(f"🔧 Found compressed database file. Decompressing...")
                    decompress_cmd = f"cd {eggnog_db_wsl} && gunzip -f {gz_file} 2>&1"
                    decompress_result = subprocess.run(['wsl', 'bash', '-c', decompress_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
                    
                    if decompress_result.returncode == 0:
                        logger.info(f"✅ Database decompressed successfully")
                        # Re-test the database
                        db_test = subprocess.run(['wsl', 'bash', '-c', test_db_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
                        db_output = db_test.stdout + db_test.stderr
                    else:
                        logger.error(f"❌ Failed to decompress database: {decompress_result.stderr[:200]}")
                
                # If still missing after decompression attempt
                if 'No such file or directory' in db_output:
                    logger.error(f"❌ DIAMOND database file is missing!")
                    logger.error(f"   File not found: {eggnog_proteins_dmnd}")
                    logger.error(f"   Attempting to download database (this may take 30-60 minutes)...")
                    if not self._rebuild_eggnog_database(eggnog_db_wsl):
                        return {
                            'success': False,
                            'error': f'DIAMOND database file is missing and could not be downloaded. The download server may be unavailable (404 errors). Please download manually from: http://eggnog5.embl.de/#/app/downloads',
                            'processing_time': time.time() - start_time
                        }
            elif 'Unexpected end of input' in db_output or (db_test.returncode != 0 and 'Unexpected end of input' not in db_output):
                logger.error(f"❌ DIAMOND database is corrupted!")
                logger.error(f"   Error: Unexpected end of input (return code {db_test.returncode})")
                logger.error(f"   Database test output: {db_output[:300]}")
                logger.error(f"   Attempting to rebuild database (this may take 30-60 minutes)...")
                if not self._rebuild_eggnog_database(eggnog_db_wsl):
                    return {
                        'success': False,
                        'error': 'DIAMOND database is corrupted and could not be rebuilt. Please run: download_eggnog_data.py --data_dir /home/ser1dai/eggnog_db_final -M -H -d 2 -y -f',
                        'processing_time': time.time() - start_time
                    }
            
            # ============================================================================
            # OPTIMIZATION SETUP: RAM Disk and Gut Database
            # ============================================================================
            # NOTE: Only copy SMALL gut_db to RAM disk, NEVER copy main EggNOG database (causes corruption)
            ramdisk_path = self._setup_ramdisk()
            gut_db_path = self._ensure_gut_database(eggnog_db_wsl)
            gut_db_ramdisk = None
            if gut_db_path and ramdisk_path:
                # Only copy small gut_db to RAM disk (not the main EggNOG database)
                # Main EggNOG database should NEVER be copied to RAM disk (causes corruption)
                gut_db_ramdisk = self._copy_to_ramdisk(gut_db_path, ramdisk_path) if gut_db_path else None
            
            # ============================================================================
            # STEP 1: KofamScan (HMM) - RUN FIRST (Smart Pipeline Order)
            # ============================================================================
            if job:
                try:
                    job.progress = 10
                    job.progress_message = 'Running KofamScan (HMM) (Step 1/5)...'
                    job.save(update_fields=['progress', 'progress_message'])
                except Exception as e:
                    logger.warning(f"Could not update job progress: {e}")
            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 1: Running KofamScan (HMM) with {cpu_cores} CPU cores...")
            
            # Verify input file has sequences and is valid FASTA
            check_input_cmd = f"test -s {input_file_wsl} && echo 'has_data' || echo 'empty'"
            input_check = subprocess.run(['wsl', 'bash', '-c', check_input_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if 'empty' in input_check.stdout:
                error_msg = "Input FASTA file is empty or has no sequences"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'processing_time': time.time() - start_time
                }
            
            # Check if file has valid FASTA sequences (at least one sequence header)
            check_fasta_cmd = f"grep -c '^>' {input_file_wsl} 2>/dev/null || echo '0'"
            fasta_check = subprocess.run(['wsl', 'bash', '-c', check_fasta_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            try:
                sequence_count = int(fasta_check.stdout.strip())
                if sequence_count == 0:
                    error_msg = "Input file does not contain valid FASTA sequences (no sequence headers found)"
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'processing_time': time.time() - start_time
                    }
                logger.info(f"Input file contains {sequence_count} FASTA sequence(s)")
            except (ValueError, AttributeError):
                logger.warning("Could not verify FASTA sequence count, continuing anyway...")
            
            kofamscan_results_file = str(temp_dir / "kofamscan.txt")
            kofamscan_results_wsl = self._to_wsl_path(kofamscan_results_file)
            
            # Use gut HMM subset if available (10x faster), otherwise use full database
            profiles_hmm = self._create_gut_hmm_subset(kofam_db_wsl, eggnog_db_wsl)
            check_hmm_cmd = f"test -f {profiles_hmm} && test -r {profiles_hmm} && echo 'exists' || echo 'not_exists'"
            check_result = subprocess.run(['wsl', 'bash', '-c', check_hmm_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            
            if 'exists' in check_result.stdout:
                # Ensure HMM database is indexed (hmmpress)
                self._ensure_hmmpress(profiles_hmm)
                # Optimize KofamScan: Use faster options
                # --max: Stop after first hit per sequence (faster, ~2x speedup)
                # --cpu: Use all available cores
                # --cut_tc: Use trusted cutoffs (faster than E-value)
                # Note: Using gut subset is already 10x faster than full database
                kofamscan_cmd = f"""source ~/miniconda3/etc/profile.d/conda.sh && conda activate kofamscan && export HMMER_NCPU={cpu_cores} && hmmsearch --cpu {cpu_cores} --cut_tc --max -o {kofamscan_results_wsl} {profiles_hmm} {input_file_wsl}"""
                
                logger.info(f"Command: {kofamscan_cmd}")
                print(f"[{time.strftime('%H:%M:%S')}] Running KofamScan (optimized with gut subset): hmmsearch --cpu {cpu_cores} --cut_tc --max -o {kofamscan_results_wsl} {profiles_hmm} {input_file_wsl}")
                
                # Run KofamScan (non-blocking, will process results later)
                kofamscan_stdout_file = temp_dir / "kofamscan_stdout.log"
                kofamscan_stderr_file = temp_dir / "kofamscan_stderr.log"
                
                with open(kofamscan_stdout_file, 'w', encoding='utf-8') as stdout_file, \
                     open(kofamscan_stderr_file, 'w', encoding='utf-8') as stderr_file:
                    
                    kofamscan_process = subprocess.Popen(
                        ['wsl', 'bash', '-c', kofamscan_cmd],
                        stdout=stdout_file,
                        stderr=stderr_file,
                        text=True
                    )
                    
                    timeout_seconds = self._calculate_timeout(file_size_mb, 'kofamscan')
                    return_code, timed_out = self._monitor_process(
                        kofamscan_process, timeout_seconds, job,
                        step_message='Running KofamScan (Step 1/6)',
                        file_size_mb=file_size_mb
                    )
                    
                    # Read error output for diagnostics
                    stderr_content = ""
                    if os.path.exists(kofamscan_stderr_file):
                        try:
                            with open(kofamscan_stderr_file, 'r', encoding='utf-8', errors='ignore') as f:
                                stderr_content = f.read()
                        except Exception as e:
                            logger.warning(f"Could not read KofamScan stderr: {e}")
                    
                    # Check if results file exists and has data, even if return code is non-zero
                    if os.path.exists(kofamscan_results_file):
                        # Check if file has data (not empty)
                        check_kofam_data_cmd = f"test -s {kofamscan_results_wsl} && echo 'has_data' || echo 'empty'"
                        kofam_data_check = subprocess.run(['wsl', 'bash', '-c', check_kofam_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                        if 'has_data' in kofam_data_check.stdout:
                            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 1: KofamScan completed successfully (found results despite return code {return_code})")
                        else:
                            error_details = stderr_content[-500:] if stderr_content else "No error details"
                            logger.warning(f"KofamScan results file is empty (return code {return_code}). Error: {error_details}")
                            kofamscan_results_file = None
                    else:
                        error_details = stderr_content[-500:] if stderr_content else "No error details"
                        logger.warning(f"KofamScan results file not generated (return code {return_code}). Error: {error_details}")
                        # Check for common errors
                        if 'not found' in stderr_content or 'File existence' in stderr_content:
                            logger.error(f"❌ KofamScan database file not accessible. Check: {profiles_hmm}")
                        kofamscan_results_file = None
            else:
                logger.warning(f"Prebuilt profiles.hmm not found at {profiles_hmm}, skipping KofamScan")
                kofamscan_results_file = None
            
            # ============================================================================
            # STEP 2: EGGNOG ANNOTATION (emapper)
            # ============================================================================
            if job:
                try:
                    job.progress = 20
                    job.progress_message = 'Running eggNOG annotation (Step 2/4)...'
                    job.save(update_fields=['progress', 'progress_message'])
                except Exception as e:
                    logger.warning(f"Could not update job progress: {e}")
            # ============================================================================
            # STEP 2: GUT FAST SEARCH (PRIMARY - Tier-1) - 10x Speedup
            # ============================================================================
            gut_hits_file = None
            remaining_fasta_wsl = None
            gut_hits_found = False
            
            if gut_db_ramdisk or gut_db_path:
                if job:
                    try:
                        job.progress = 20
                        job.progress_message = 'Running GUT fast search (Tier-1) (Step 2/5)...'
                        job.save(update_fields=['progress', 'progress_message'])
                    except Exception as e:
                        logger.warning(f"Could not update job progress: {e}")
                
                db_to_use = gut_db_ramdisk if gut_db_ramdisk else gut_db_path
                logger.info(f"[{time.strftime('%H:%M:%S')}] Step 2: Running GUT fast search (Tier-1) with {cpu_cores} CPU cores...")
                logger.info(f"[{time.strftime('%H:%M:%S')}] Using database: {db_to_use}")
                
                gut_hits_file = str(temp_dir / "gut_hits.tsv")
                gut_hits_wsl = self._to_wsl_path(gut_hits_file)
                
                # Optimized DIAMOND parameters for speed
                diamond_cmd = f"""source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && diamond blastp -d {db_to_use} -q {input_file_wsl} -o {gut_hits_wsl} --threads {cpu_cores} --block-size 4 --index-chunks 1 --fast --outfmt 6"""
                
                logger.info(f"Command: {diamond_cmd}")
                print(f"[{time.strftime('%H:%M:%S')}] Running GUT DIAMOND (Tier-1): diamond blastp -d {db_to_use} -q {input_file_wsl} -o {gut_hits_wsl} --threads {cpu_cores} --fast")
                
                diamond_stdout_file = temp_dir / "gut_diamond_stdout.log"
                diamond_stderr_file = temp_dir / "gut_diamond_stderr.log"
                
                with open(diamond_stdout_file, 'w', encoding='utf-8') as stdout_file, \
                     open(diamond_stderr_file, 'w', encoding='utf-8') as stderr_file:
                    
                    diamond_process = subprocess.Popen(
                        ['wsl', 'bash', '-c', diamond_cmd],
                        stdout=stdout_file,
                        stderr=stderr_file,
                        text=True
                    )
                    
                    timeout_seconds = min(self._calculate_timeout(file_size_mb, 'diamond'), 1800)  # Max 30 min for gut search
                    return_code, timed_out = self._monitor_process(
                        diamond_process, timeout_seconds, job,
                        step_message='Running GUT DIAMOND (Tier-1)',
                        file_size_mb=file_size_mb
                    )
                
                # Check if we got hits
                if os.path.exists(gut_hits_file):
                    check_hits_cmd = f"wc -l < {gut_hits_wsl} 2>/dev/null || echo '0'"
                    hits_check = subprocess.run(['wsl', 'bash', '-c', check_hits_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                    try:
                        hit_count = int(hits_check.stdout.strip())
                        if hit_count > 0:
                            gut_hits_found = True
                            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 2: GUT fast search completed successfully ({hit_count} hits)")
                        else:
                            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 2: GUT fast search completed (no hits found)")
                    except (ValueError, AttributeError):
                        logger.warning("Could not verify GUT hits count")
                else:
                    logger.warning(f"GUT DIAMOND search failed (return code {return_code})")
            
            # ============================================================================
            # STEP 3: FILTER FASTA - Remove proteins found in gut hits
            # ============================================================================
            fasta_for_eggnog = input_file_wsl
            if gut_hits_found and gut_hits_file:
                if job:
                    try:
                        job.progress = 30
                        job.progress_message = 'Filtering FASTA to remove gut hits (Step 3/5)...'
                        job.save(update_fields=['progress', 'progress_message'])
                    except Exception as e:
                        logger.warning(f"Could not update job progress: {e}")
                
                logger.info(f"[{time.strftime('%H:%M:%S')}] Step 3: Filtering FASTA to remove gut hits...")
                
                # Extract protein IDs from gut hits
                extract_ids_cmd = f"cut -f1 {self._to_wsl_path(gut_hits_file)} | sort -u > {temp_dir_wsl}/gut_hit_ids.txt"
                subprocess.run(['wsl', 'bash', '-c', extract_ids_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
                
                # Create filtered FASTA (sequences NOT in gut hits)
                remaining_fasta = str(temp_dir / "remaining.faa")
                remaining_fasta_wsl = self._to_wsl_path(remaining_fasta)
                
                filter_cmd = f"""
                python3 -c "
                hit_ids = set()
                with open('{temp_dir_wsl}/gut_hit_ids.txt', 'r') as f:
                    hit_ids = set(line.strip() for line in f if line.strip())
                
                current_id = None
                current_seq = []
                write_current = False
                
                with open('{input_file_wsl}', 'r') as infile, open('{remaining_fasta_wsl}', 'w') as outfile:
                    for line in infile:
                        if line.startswith('>'):
                            if current_id and current_id not in hit_ids:
                                outfile.write('>' + current_id + '\\n')
                                outfile.write(''.join(current_seq))
                            header = line[1:].strip()
                            current_id = header.split()[0]
                            current_seq = []
                            write_current = current_id not in hit_ids
                        elif write_current:
                            current_seq.append(line)
                    if current_id and current_id not in hit_ids:
                        outfile.write('>' + current_id + '\\n')
                        outfile.write(''.join(current_seq))
                "
                """
                
                filter_result = subprocess.run(['wsl', 'bash', '-c', filter_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300)
                
                if filter_result.returncode == 0 and os.path.exists(remaining_fasta):
                    # Check how many sequences remain
                    check_remaining_cmd = f"grep -c '^>' {remaining_fasta_wsl} 2>/dev/null || echo '0'"
                    remaining_check = subprocess.run(['wsl', 'bash', '-c', check_remaining_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                    try:
                        remaining_count = int(remaining_check.stdout.strip())
                        logger.info(f"✅ Filtered FASTA: {remaining_count} sequences remaining (removed gut hits)")
                        fasta_for_eggnog = remaining_fasta_wsl
                    except (ValueError, AttributeError):
                        fasta_for_eggnog = remaining_fasta_wsl
                else:
                    logger.warning("Could not filter FASTA, using original file for eggNOG")
                    fasta_for_eggnog = input_file_wsl
            
            # ============================================================================
            # STEP 4: EGGNOG ANNOTATION (Tier-2) - Full database on remaining sequences
            # ============================================================================
            if job:
                try:
                    job.progress = 40
                    job.progress_message = 'Running eggNOG annotation (Tier-2) (Step 4/5)...'
                    job.save(update_fields=['progress', 'progress_message'])
                except Exception as e:
                    logger.warning(f"Could not update job progress: {e}")
            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 4: Running eggNOG annotation (Tier-2) with {cpu_cores} CPU cores...")
            
            emapper_output = str(temp_dir / "emapper_output")
            emapper_output_wsl = self._to_wsl_path(emapper_output)
            emapper_annotations_file = None
            emapper_has_output = False
            
            # Check if we have sequences to process
            if fasta_for_eggnog != input_file_wsl:
                check_seq_cmd = f"grep -c '^>' {fasta_for_eggnog} 2>/dev/null || echo '0'"
                seq_check = subprocess.run(['wsl', 'bash', '-c', check_seq_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                try:
                    seq_count = int(seq_check.stdout.strip())
                    if seq_count == 0:
                        logger.info(f"[{time.strftime('%H:%M:%S')}] Step 4: Skipping eggNOG (remaining.faa is empty - all sequences found in gut database)")
                        emapper_annotations_file = None
                        emapper_has_output = False
                except (ValueError, AttributeError):
                    pass
            
            if not emapper_annotations_file:  # Only run if we haven't skipped
                # Try different search methods in order: diamond -> mmseqs -> hmmer
                search_methods = ['diamond', 'mmseqs', 'hmmer']
                return_code = None
                
                for search_method in search_methods:
                    # Run emapper on filtered file (or original if no filtering)
                    emapper_cmd = f"""source ~/miniconda3/etc/profile.d/conda.sh && conda activate eggnog && emapper.py -i {fasta_for_eggnog} -o {emapper_output_wsl} --data_dir {eggnog_db_wsl} -m {search_method} --cpu {cpu_cores} --override"""
                    
                    logger.info(f"Command: {emapper_cmd}")
                    print(f"[{time.strftime('%H:%M:%S')}] Running eggNOG annotation with {search_method}: emapper.py -i {input_file_wsl} -o {emapper_output_wsl} --data_dir {eggnog_db_wsl} -m {search_method} --cpu {cpu_cores} --override")
                    
                    emapper_stdout_file = temp_dir / f"emapper_stdout_{search_method}.log"
                    emapper_stderr_file = temp_dir / f"emapper_stderr_{search_method}.log"
                    
                    with open(emapper_stdout_file, 'w', encoding='utf-8') as stdout_file, \
                         open(emapper_stderr_file, 'w', encoding='utf-8') as stderr_file:
                        
                        emapper_process = subprocess.Popen(
                            ['wsl', 'bash', '-c', emapper_cmd],
                            stdout=stdout_file,
                            stderr=stderr_file,
                            text=True
                        )
                        
                        timeout_seconds = self._calculate_timeout(file_size_mb, 'emapper')
                        return_code, timed_out = self._monitor_process(
                            emapper_process, timeout_seconds, job,
                            step_message=f'Running eggNOG annotation with {search_method} (Step 4/6)',
                            file_size_mb=file_size_mb
                        )
                        
                        if timed_out:
                            logger.warning(f"emapper with {search_method} exceeded timeout, trying next method...")
                            continue
                        
                    if return_code == -1:
                        logger.warning(f"emapper with {search_method} was interrupted, trying next method...")
                        continue
                    
                    # Read output files
                    stdout_content, stderr_content = self._read_log_files(emapper_stdout_file, emapper_stderr_file)
                    
                    logger.info(f"[{time.strftime('%H:%M:%S')}] emapper ({search_method}) return code: {return_code}")
                    if stdout_content:
                        logger.info(f"emapper ({search_method}) stdout (last 500 chars): {stdout_content[-500:]}")
                    if stderr_content:
                        logger.info(f"emapper ({search_method}) stderr (last 500 chars): {stderr_content[-500:]}")
                    
                    # Check if emapper produced output files
                    emapper_annotations_file = f"{emapper_output_wsl}.emapper.annotations"
                    
                    if return_code == 0:
                        # Success - check if file has data
                        check_data_cmd = f"test -s {emapper_annotations_file} && echo 'has_data' || echo 'empty'"
                        data_check = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                        if 'has_data' in data_check.stdout:
                            emapper_has_output = True
                            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 4: eggNOG annotation completed successfully with {search_method}")
                            break
                        else:
                            logger.warning(f"emapper ({search_method}) succeeded but output file is empty, trying next method...")
                            emapper_annotations_file = None
                    else:
                        # Check if annotation file exists despite error
                        check_annotations_cmd = f"test -f {emapper_annotations_file} && echo 'exists' || echo 'not_exists'"
                        annotations_check = subprocess.run(['wsl', 'bash', '-c', check_annotations_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                        
                        if 'exists' in annotations_check.stdout:
                            # Check if file has data
                            check_data_cmd = f"test -s {emapper_annotations_file} && echo 'has_data' || echo 'empty'"
                            data_check = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                            if 'has_data' in data_check.stdout:
                                emapper_has_output = True
                                logger.info(f"emapper ({search_method}) failed (return code {return_code}) but produced output file, continuing...")
                                break
                        
                        # Check if it's a database error that we can retry with another method
                        # Check both stdout and stderr for database errors
                        combined_output = (stdout_content or '') + (stderr_content or '')
                        is_database_error = (
                            'Unexpected end of input' in combined_output or 
                            'Error running diamond' in combined_output or
                            'not present' in combined_output.lower() or
                            ('database' in combined_output.lower() and 'error' in combined_output.lower()) or
                            ('eggnog_proteins.dmnd' in combined_output and 'not present' in combined_output.lower()) or
                            ('mmseqs.db' in combined_output and 'not present' in combined_output.lower())
                        )
                        
                        if is_database_error and search_method != search_methods[-1]:
                            logger.warning(f"emapper ({search_method}) failed with database error, trying next method ({search_methods[search_methods.index(search_method) + 1]})...")
                            emapper_annotations_file = None
                            continue
                        else:
                            logger.warning(f"emapper ({search_method}) failed (return code {return_code}), trying next method...")
                            emapper_annotations_file = None
            
            # If all methods failed, log final error
            if not emapper_has_output:
                logger.warning(f"⚠️  All emapper search methods ({', '.join(search_methods)}) failed. Continuing without emapper results.")
                emapper_annotations_file = None
            
            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 4: Tier-2 processing completed")
            
            # ============================================================================
            # STEP 5: MERGE RESULTS - Combine gut hits + emapper + kofamscan
            # ============================================================================
            if job:
                try:
                    job.progress = 50
                    job.progress_message = 'Merging results (Step 5/6)...'
                    job.save(update_fields=['progress', 'progress_message'])
                except Exception as e:
                    logger.warning(f"Could not update job progress: {e}")
            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 5: Merging results from all sources...")
            
            # Process emapper annotations if available
            emapper_enzymes_file = None
            if emapper_annotations_file and os.path.exists(emapper_annotations_file):
                emapper_enzymes_file = str(temp_dir / "emapper_enzymes.csv")
                emapper_enzymes_wsl = self._to_wsl_path(emapper_enzymes_file)
                
                success, result = self._run_script_template(
                    "extract_enzymes",
                    {
                        "EGGNOG_DB_PATH": eggnog_db_wsl,
                        "ANNOTATIONS_FILE": emapper_annotations_file,
                        "OUTPUT_FILE": emapper_enzymes_wsl
                    },
                    temp_dir,
                    conda_env='eggnog',
                    timeout=300,
                    step_name='extract emapper enzymes'
                )
                
                # Check if processed file has data (more than just headers)
                if success and os.path.exists(emapper_enzymes_file):
                    check_data_cmd = f"wc -l < {emapper_enzymes_wsl}"
                    line_count_result = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                    try:
                        line_count = int(line_count_result.stdout.strip())
                        if line_count <= 1:  # Only headers, no data
                            logger.warning("Warning: emapper_enzymes.csv has no data rows, skipping")
                            emapper_enzymes_file = None
                        else:
                            logger.info(f"✅ Extracted {line_count - 1} enzyme annotations from emapper")
                    except (ValueError, AttributeError):
                        logger.warning("Warning: Could not verify emapper_enzymes.csv data, skipping")
                        emapper_enzymes_file = None
                else:
                    logger.warning("Warning: Could not extract emapper enzymes, continuing without them")
                    emapper_enzymes_file = None
            
            # Process kofamscan results if available
            kofamscan_kos_file = None
            if kofamscan_results_file and os.path.exists(kofamscan_results_file):
                # Convert hmmsearch output first
                converted_results_file = str(temp_dir / "kofamscan_results_converted.txt")
                converted_results_wsl = self._to_wsl_path(converted_results_file)
                
                success, result = self._run_script_template(
                    "convert_hmmsearch",
                    {
                        "INPUT_FILE": kofamscan_results_wsl,
                        "OUTPUT_FILE": converted_results_wsl
                    },
                    temp_dir,
                    conda_env='kofamscan',
                    timeout=300,
                    step_name='convert hmmsearch'
                )
                
                if success and os.path.exists(converted_results_file):
                    kofamscan_kos_file = str(temp_dir / "kofamscan_kos.csv")
                    kofamscan_kos_wsl = self._to_wsl_path(kofamscan_kos_file)
                    
                    success, result = self._run_script_template(
                        "process_kofam",
                        {
                            "INPUT_FILE": converted_results_wsl,
                            "OUTPUT_FILE": kofamscan_kos_wsl
                        },
                        temp_dir,
                        conda_env='kofamscan',
                        timeout=600,
                        step_name='process kofamscan'
                    )
                    
                    # Check if processed file has data (more than just headers)
                    if success and os.path.exists(kofamscan_kos_file):
                        check_data_cmd = f"wc -l < {kofamscan_kos_wsl}"
                        line_count_result = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                        try:
                            line_count = int(line_count_result.stdout.strip())
                            if line_count <= 1:  # Only headers, no data
                                logger.warning("Warning: kofamscan_kos.csv has no data rows, skipping")
                                kofamscan_kos_file = None
                            else:
                                logger.info(f"✅ Processed {line_count - 1} KOs from kofamscan")
                        except (ValueError, AttributeError):
                            logger.warning("Warning: Could not verify kofamscan_kos.csv data, skipping")
                            kofamscan_kos_file = None
                    else:
                        kofamscan_kos_file = None
            
            # Process gut hits if available
            gut_enzymes_file = None
            if gut_hits_file and os.path.exists(gut_hits_file) and gut_hits_found:
                # Process gut DIAMOND hits to extract enzyme annotations
                gut_enzymes_file = str(temp_dir / "gut_enzymes.csv")
                gut_enzymes_wsl = self._to_wsl_path(gut_enzymes_file)
                
                # Use the existing process_diamond_hits script template
                ko2genes_file = f"{eggnog_db_wsl}/gut_kegg_db/ko2genes.txt"
                success, result = self._run_script_template(
                    "process_diamond_hits",
                    {
                        "DIAMOND_HITS": self._to_wsl_path(gut_hits_file),
                        "KO2GENES_FILE": ko2genes_file,
                        "OUTPUT_FILE": gut_enzymes_wsl
                    },
                    temp_dir,
                    conda_env='eggnog',
                    timeout=300,
                    step_name='process gut hits'
                )
                
                if success and os.path.exists(gut_enzymes_file):
                    check_data_cmd = f"wc -l < {gut_enzymes_wsl}"
                    line_count_result = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                    try:
                        line_count = int(line_count_result.stdout.strip())
                        if line_count > 1:
                            logger.info(f"✅ Processed {line_count - 1} enzyme annotations from GUT hits")
                        else:
                            gut_enzymes_file = None
                    except (ValueError, AttributeError):
                        gut_enzymes_file = None
                else:
                    gut_enzymes_file = None
            
            # Merge all available sources
            merged_file = str(temp_dir / "enzymes_merged.csv")
            merged_file_wsl = self._to_wsl_path(merged_file)
            
            # Check if at least one source has data
            has_gut_data = gut_enzymes_file and os.path.exists(gut_enzymes_file)
            has_emapper_data = emapper_enzymes_file and os.path.exists(emapper_enzymes_file)
            has_kofam_data = kofamscan_kos_file and os.path.exists(kofamscan_kos_file)
            
            # Verify gut data file has actual data
            if has_gut_data:
                check_data_cmd = f"wc -l < {self._to_wsl_path(gut_enzymes_file)}"
                line_count_result = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                try:
                    if int(line_count_result.stdout.strip()) <= 1:
                        has_gut_data = False
                except (ValueError, AttributeError):
                    has_gut_data = False
            
            # Verify files have actual data (not just headers)
            if has_emapper_data:
                check_data_cmd = f"wc -l < {self._to_wsl_path(emapper_enzymes_file)}"
                line_count_result = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                try:
                    if int(line_count_result.stdout.strip()) <= 1:
                        has_emapper_data = False
                except (ValueError, AttributeError):
                    has_emapper_data = False
            
            if has_kofam_data:
                check_data_cmd = f"wc -l < {self._to_wsl_path(kofamscan_kos_file)}"
                line_count_result = subprocess.run(['wsl', 'bash', '-c', check_data_cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
                try:
                    if int(line_count_result.stdout.strip()) <= 1:
                        has_kofam_data = False
                except (ValueError, AttributeError):
                    has_kofam_data = False
            
            skip_merge = False
            if not (has_gut_data or has_emapper_data or has_kofam_data):
                # Create empty output file with headers instead of failing
                error_summary = []
                if not has_gut_data and gut_hits_file:
                    error_summary.append("GUT DIAMOND: No hits found (sequences may not match gut database)")
                if not has_emapper_data:
                    error_summary.append("eggNOG emapper: All search methods failed (diamond/mmseqs/hmmer databases missing or corrupted)")
                if not has_kofam_data:
                    error_summary.append("KofamScan: Database file not accessible or no matches found")
                
                error_msg = "⚠️  No annotation data found from any source:\n" + "\n".join(f"  - {err}" for err in error_summary)
                error_msg += "\n\nPossible solutions:"
                error_msg += "\n  1. Verify input file contains valid protein sequences"
                error_msg += "\n  2. Check eggNOG databases are properly installed at: /home/ser1dai/eggnog_db_final"
                error_msg += "\n  3. Verify KofamScan database exists: /home/ser1dai/eggnog_db_final/kofam_db/profiles.hmm"
                error_msg += "\n  4. Run: download_eggnog_data.py to fetch missing databases"
                
                logger.error(error_msg)
                
                # Create empty CSV with headers
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('protein_id,contig_id,EC_number,KEGG_KO,enzyme_name,pathway,confidence_score,annotation_source\n')
                logger.warning(f"Created empty output file: {output_file}")
                logger.warning("⚠️  Processing will continue but no annotation data is available.")
                # Continue to pathway scoring and final FASTA creation (they will handle empty data)
                # But skip the merge step
                merged_file = output_file
                merged_file_wsl = output_file_wsl
                # Skip merge and go directly to pathway scoring
                skip_merge = True
            
            # Determine which merge template to use based on available sources
            if not skip_merge:
                # Build list of available data sources
                sources = []
                if has_gut_data:
                    sources.append(("gut", gut_enzymes_file))
                if has_emapper_data:
                    sources.append(("emapper", emapper_enzymes_file))
                if has_kofam_data:
                    sources.append(("kofam", kofamscan_kos_file))
                
                # Merge all available sources (simplified: use merge_eggnog_only for single source,
                # or merge_annotations for multiple sources - will combine all)
                if len(sources) == 1:
                    # Single source
                    source_name, source_file = sources[0]
                    source_wsl = self._to_wsl_path(source_file)
                    success, result = self._run_script_template(
                        "merge_eggnog_only",
                        {
                            "EGGNOG_FILE": source_wsl,
                            "OUTPUT_FILE": merged_file_wsl
                        },
                        temp_dir,
                        conda_env='eggnog',
                        timeout=600,
                        step_name=f'merge {source_name} only'
                    )
                elif len(sources) >= 2:
                    # Multiple sources - combine emapper and kofam first, then add gut if present
                    # For now, prioritize emapper + kofam if both exist, otherwise use first two
                    if has_emapper_data and has_kofam_data:
                        emapper_enzymes_wsl = self._to_wsl_path(emapper_enzymes_file)
                        kofamscan_kos_wsl = self._to_wsl_path(kofamscan_kos_file)
                        success, result = self._run_script_template(
                            "merge_annotations",
                            {
                                "EGGNOG_FILE": emapper_enzymes_wsl,
                                "KOFAM_FILE": kofamscan_kos_wsl,
                                "OUTPUT_FILE": merged_file_wsl
                            },
                            temp_dir,
                            conda_env='eggnog',
                            timeout=600,
                            step_name='merge emapper + kofamscan'
                        )
                        # TODO: If gut data exists, merge it in a second pass
                        # For now, gut data will be included if emapper/kofam don't have it
                    else:
                        # Use first two sources
                        source1_name, source1_file = sources[0]
                        source2_name, source2_file = sources[1]
                        source1_wsl = self._to_wsl_path(source1_file)
                        source2_wsl = self._to_wsl_path(source2_file)
                        # Use merge_annotations with both files
                        success, result = self._run_script_template(
                            "merge_annotations",
                            {
                                "EGGNOG_FILE": source1_wsl,
                                "KOFAM_FILE": source2_wsl,
                                "OUTPUT_FILE": merged_file_wsl
                            },
                            temp_dir,
                            conda_env='eggnog',
                            timeout=600,
                            step_name=f'merge {source1_name} + {source2_name}'
                        )
                else:
                    # This should not happen due to check above, but keep as safety
                    error_msg = "No results from any source (emapper or kofamscan)"
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'processing_time': time.time() - start_time
                    }
                
                if not success:
                    error_msg = f'merge failed: {result.stderr[-1000:] if result.stderr else "No error output"}'
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'processing_time': time.time() - start_time
                    }
                
                # Copy final merged result to output location
                if os.path.exists(merged_file):
                    shutil.copy2(merged_file, output_file)
                    logger.info(f"[{time.strftime('%H:%M:%S')}] Step 3: Merge completed successfully")
                    logger.info(f"Final CSV output saved to: {output_file}")
                else:
                    error_msg = 'merged enzymes.csv not generated'
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'error': error_msg,
                        'processing_time': time.time() - start_time
                    }
            else:
                # Skip merge - empty file already created
                logger.info(f"[{time.strftime('%H:%M:%S')}] Step 3: Skipped merge (no data found), using empty output file")
            
            # ============================================================================
            # STEP 4: Calculate Pathway-Level Scores and Create Final FASTA
            # ============================================================================
            if job:
                try:
                    job.progress = 75
                    job.progress_message = 'Calculating pathway-level scores (Step 4/4)...'
                    job.save(update_fields=['progress', 'progress_message'])
                except Exception as e:
                    logger.warning(f"Could not update job progress: {e}")
            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 6: Calculating pathway-level scores...")
            
            # Create pathway scoring script using ChatGPT's approach
            base_name = Path(output_file).stem  # e.g., "enzymes_36_final_multiple_fasta"
            if '_' in base_name:
                parts = base_name.split('_', 2)
                if len(parts) >= 3:
                    filename_part = '_'.join(parts[2:])
                else:
                    filename_part = base_name
            else:
                filename_part = base_name
            
            pathway_output_file = str(Path(output_file).parent / f"pathways_{job.id if job else 'unknown'}_{filename_part}.csv")
            pathway_output_file_wsl = self._to_wsl_path(pathway_output_file)
            
            # Path to pathway_definitions.csv (in fasta_processor directory)
            pathway_defs_path = Path(__file__).parent / "pathway_definitions.csv"
            pathway_defs_wsl = self._to_wsl_path(str(pathway_defs_path))
            
            # Calculate pathway scores using template
            success, result = self._run_script_template(
                "pathway_scoring",
                {
                    "ENZYMES_CSV": merged_file_wsl,
                    "PATHWAY_DEFS": pathway_defs_wsl,
                    "OUTPUT_FILE": pathway_output_file_wsl
                },
                temp_dir,
                conda_env='eggnog',
                timeout=600,
                step_name='pathway scoring'
            )
            
            if not success:
                logger.warning(f"Warning: Pathway scoring failed: {result.stderr[-1000:] if result.stderr else 'No error output'}")
            elif os.path.exists(pathway_output_file):
                logger.info(f"[{time.strftime('%H:%M:%S')}] Pathway scoring completed successfully")
                logger.info(f"Pathway scores saved to: {pathway_output_file}")
                # Save pathway file reference to job
                if job:
                    media_root = Path(settings.MEDIA_ROOT) if not isinstance(settings.MEDIA_ROOT, Path) else settings.MEDIA_ROOT
                    pathway_file_relative = Path(pathway_output_file).relative_to(media_root)
                    job.pathway_file.name = str(pathway_file_relative)
                    try:
                        job.save(update_fields=['pathway_file'])
                    except Exception as e:
                        logger.warning(f"Could not update job pathway_file: {e}")
            else:
                logger.warning("Warning: Pathway scores file was not created, but processing will continue")
            
            # ============================================================================
            # Create final merged FASTA file with annotated sequences (optional)
            # ============================================================================
            if job:
                try:
                    job.progress = 90
                    job.progress_message = 'Creating final FASTA file (Step 4/4)...'
                    job.save(update_fields=['progress', 'progress_message'])
                except Exception as e:
                    logger.warning(f"Could not update job progress: {e}")
            logger.info(f"[{time.strftime('%H:%M:%S')}] Step 7: Creating final merged FASTA file...")
            
            # Create final FASTA file path (same location as CSV, with .fasta extension)
            final_fasta_file = str(Path(output_file).with_suffix('.fasta'))
            final_fasta_file_wsl = self._to_wsl_path(final_fasta_file)
            
            # Create final FASTA file using template
            success, result = self._run_script_template(
                "create_fasta",
                {
                    "MERGED_CSV": merged_file_wsl,
                    "INPUT_FASTA": input_file_wsl,
                    "OUTPUT_FASTA": final_fasta_file_wsl
                },
                temp_dir,
                conda_env='eggnog',
                timeout=600,
                step_name='create final FASTA'
            )
            
            if not success:
                logger.warning(f"Warning: Final FASTA file creation failed: {result.stderr[-1000:] if result.stderr else 'No error output'}")
            elif os.path.exists(final_fasta_file):
                logger.info(f"[{time.strftime('%H:%M:%S')}] Final merged FASTA file created successfully")
                logger.info(f"Final FASTA file saved to: {final_fasta_file}")
            else:
                logger.warning("Warning: Final FASTA file was not created, but processing will continue")
            
            processing_time = time.time() - start_time
            logger.info(f"[{time.strftime('%H:%M:%S')}] ✅ All processing completed in {processing_time:.2f} seconds")
            
            # Return final FASTA file path if it was created
            final_fasta_path = None
            if os.path.exists(final_fasta_file):
                final_fasta_path = final_fasta_file
                logger.info(f"Final merged FASTA file available at: {final_fasta_path}")
            
            return {
                'success': True,
                'processing_time': processing_time,
                'version': 'emapper-2.1.13 + kofamscan',
                'final_fasta_file': final_fasta_path
            }
                
        except subprocess.TimeoutExpired as e:
            error_msg = f'Processing was interrupted: {str(e)}'
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'processing_time': time.time() - start_time
            }
        except KeyboardInterrupt as e:
            error_msg = 'Processing was interrupted (KeyboardInterrupt). This may occur if the process takes too long or is manually terminated.'
            logger.error(error_msg)
            logger.exception(str(e))
            return {
                'success': False,
                'error': error_msg,
                'processing_time': time.time() - start_time
            }
        except Exception as e:
            error_msg = f'Unexpected error: {str(e)}'
            logger.exception(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'processing_time': time.time() - start_time
            }
    
    def _to_wsl_path(self, windows_path):
        """
        Convert Windows path to WSL path
        
        Args:
            windows_path: Windows-style path (e.g., C:\\Users\\...) or WSL path (e.g., /home/...)
            
        Returns:
            WSL-style path (e.g., /mnt/c/Users/... or /home/...)
        """
        if isinstance(windows_path, Path):
            windows_path = str(windows_path)
        
        # Normalize backslashes
        windows_path = windows_path.replace('\\', '/')
        
        # If already a WSL path (starts with /home, /usr, /opt, etc.), return as is
        if windows_path.startswith('/home/') or windows_path.startswith('/usr/') or windows_path.startswith('/opt/'):
            return windows_path
        # If starts with / but not /mnt/, it's likely a WSL path
        if windows_path.startswith('/') and ':' not in windows_path and not windows_path.startswith('/mnt/'):
            return windows_path
        if windows_path.startswith('\\wsl') or windows_path.startswith('/wsl'):
            return windows_path.replace('\\', '/')
        
        # Convert Windows path to WSL
        try:
            path = Path(windows_path.replace('/', '\\'))  # Use backslash for Windows Path
            drive = path.drive.replace(':', '').lower()
            if not drive:
                # No drive letter, might already be a WSL path
                return windows_path
            rest = str(path.relative_to(path.anchor)).replace('\\', '/')
            return f"/mnt/{drive}/{rest}"
        except:
            # If path conversion fails, return as is with forward slashes
            return windows_path
    
    def get_eggnog_info(self):
        """Get information about eggnog database"""
        if not os.path.exists(self.eggnog_db_path):
            return {'error': 'eggnog_db_final folder not found'}
        
        return {
            'path': str(self.eggnog_db_path),
            'exists': True,
            'files': list(Path(self.eggnog_db_path).glob('*'))[:10]  # First 10 files
        }

