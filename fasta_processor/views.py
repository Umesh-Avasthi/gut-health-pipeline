from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.db.models import Q
import os
import subprocess
import sys
import logging
import csv
import json
from pathlib import Path
from .models import FastaFile, ProcessingJob
from .forms import FastaFileUploadForm
from .services import EggnogProcessor, start_next_job_in_queue

logger = logging.getLogger(__name__)


@login_required
def upload_fasta(request):
    """View for uploading FASTA files (up to 3 at once)"""
    if request.method == 'POST':
        # Get all files from request
        uploaded_files_list = request.FILES.getlist('files')
        
        # Validate number of files
        if not uploaded_files_list:
            messages.error(request, 'Please select at least one file to upload.')
            form = FastaFileUploadForm()
            return render(request, 'fasta_processor/upload.html', {'form': form})
        
        if len(uploaded_files_list) > 3:
            messages.error(request, f'You can upload a maximum of 3 files at once. You selected {len(uploaded_files_list)} files.')
            form = FastaFileUploadForm()
            return render(request, 'fasta_processor/upload.html', {'form': form})
        
        # Validate each file
        valid_extensions = ['.fasta', '.fa', '.fas', '.fna', '.ffn', '.faa', '.frn']
        max_size = 100 * 1024 * 1024  # 100MB
        
        for file in uploaded_files_list:
            # Check file extension
            if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
                messages.error(request, f'Invalid file type for "{file.name}". Please upload a FASTA file.')
                form = FastaFileUploadForm()
                return render(request, 'fasta_processor/upload.html', {'form': form})
            
            # Check file size
            if file.size > max_size:
                messages.error(request, f'File "{file.name}" exceeds 100MB. Your file is {file.size / (1024*1024):.2f}MB')
                form = FastaFileUploadForm()
                return render(request, 'fasta_processor/upload.html', {'form': form})
        
        # Get description from form
        description = request.POST.get('description', '')
        
        uploaded_files = []
        jobs_created = []
        
        # Process each uploaded file
        for file in uploaded_files_list:
            # Create FastaFile instance
            fasta_file = FastaFile(
                user=request.user,
                file=file,
                original_filename=file.name,
                file_size=file.size,
                description=description if description else ''
            )
            fasta_file.save()
            uploaded_files.append(fasta_file)
            
            # Create job
            tpm_file = request.FILES.get('tpm_file')
            job, created = ProcessingJob.objects.get_or_create(
                fasta_file=fasta_file,
                defaults={
                    'user': request.user,
                    'status': 'pending',
                    'tpm_file': tpm_file
                }
            )
            jobs_created.append(job)
            # Jobs are added to queue with status='pending'
            # They will be processed one at a time automatically
        
        # Queue management: Try to start the first job (only if none running)
        # This ensures only one file processes at a time
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Queue: {len(uploaded_files)} file(s) added to queue. Checking if processing can start...")
        started_job = start_next_job_in_queue()
        
        if started_job:
            logger.info(f"Queue: Started processing job {started_job.id}")
        else:
            # Count pending jobs to show queue position
            pending_count = ProcessingJob.objects.filter(status='pending').count()
            if pending_count > 0:
                logger.info(f"Queue: {pending_count} job(s) in queue waiting to start")
        
        # Success message with queue information
        pending_count = ProcessingJob.objects.filter(status='pending').count()
        running_count = ProcessingJob.objects.filter(status='running').count()
        
        if len(uploaded_files) == 1:
            if running_count > 0:
                messages.success(request, f'File "{uploaded_files[0].original_filename}" uploaded successfully! Added to queue. {pending_count} file(s) waiting to process.')
            else:
                messages.success(request, f'File "{uploaded_files[0].original_filename}" uploaded successfully! Processing started.')
        else:
            file_names = ', '.join([f'"{f.original_filename}"' for f in uploaded_files])
            if running_count > 0:
                messages.success(request, f'{len(uploaded_files)} files uploaded successfully! ({file_names}) Added to queue. {pending_count} file(s) waiting to process.')
            else:
                messages.success(request, f'{len(uploaded_files)} files uploaded successfully! ({file_names}) Processing started.')
        
        return redirect('fasta_processor:jobs')
    else:
        form = FastaFileUploadForm()
    
    # Check if any job is currently running (for this user)
    from django.utils import timezone
    from datetime import timedelta
    
    running_jobs = ProcessingJob.objects.filter(
        user=request.user,
        status='running',
        started_at__gt=timezone.now() - timedelta(hours=6)  # Only count recent jobs
    )
    
    has_running_job = running_jobs.exists()
    running_job_info = None
    if has_running_job:
        running_job = running_jobs.first()
        running_job_info = {
            'filename': running_job.fasta_file.original_filename,
            'started_at': running_job.started_at
        }
    
    context = {
        'form': form,
        'has_running_job': has_running_job,
        'running_job_info': running_job_info
    }
    
    return render(request, 'fasta_processor/upload.html', context)


@login_required
def fasta_jobs(request):
    """View to list user's FASTA files and processing jobs"""
    from django.utils import timezone
    from datetime import timedelta
    
    fasta_files = FastaFile.objects.filter(user=request.user)
    all_jobs = ProcessingJob.objects.filter(user=request.user)
    
    # Automatically detect and reset stuck jobs (running for more than 3 hours)
    # Increased from 2 to 3 hours to account for large files
    stuck_jobs = all_jobs.filter(
        status='running',
        started_at__lt=timezone.now() - timedelta(hours=3)
    )
    
    for job in stuck_jobs:
        # Check if result file exists (processing might have completed but status wasn't updated)
        if job.result_file and os.path.exists(job.result_file.path):
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.save()
            job.fasta_file.status = 'completed'
            job.fasta_file.save()
            logger.info(f"Job {job.id} was marked as stuck but result file exists - marking as completed")
        else:
            # Job is actually stuck - reset it and start next job
            logger.warning(f"Job {job.id} has been running for more than 3 hours - resetting to failed")
            job.status = 'failed'
            job.error_message = 'Job was stuck (running for more than 3 hours) and has been reset. Please try uploading again.'
            job.completed_at = timezone.now()
            job.save()
            job.fasta_file.status = 'failed'
            job.fasta_file.save()
            
            # Try to start next job in queue
            from .services import start_next_job_in_queue
            start_next_job_in_queue()
    
    # Get latest 5 jobs and their associated fasta files
    # Get fasta_file IDs from the latest 5 jobs (before slicing to keep it as queryset)
    latest_fasta_file_ids = list(all_jobs.order_by('-started_at').values_list('fasta_file_id', flat=True)[:5])
    latest_fasta_file_ids = [fid for fid in latest_fasta_file_ids if fid is not None]
    
    # Limit fasta_files to only those associated with latest 5 jobs
    if latest_fasta_file_ids:
        fasta_files = fasta_files.filter(id__in=latest_fasta_file_ids)
    else:
        fasta_files = fasta_files.none()  # Return empty queryset if no jobs
    
    # Categorize jobs into tabs (only for latest 5 jobs)
    # Completed: status is 'completed'
    completed_files = fasta_files.filter(status='completed')
    
    # Incomplete: status is 'failed' or 'uploaded' (not started processing)
    incomplete_files = fasta_files.filter(status__in=['failed', 'uploaded'])
    
    # Processing: status is 'processing' OR job status is 'pending' or 'running'
    # Get unique file IDs first to avoid duplicates from JOIN
    processing_file_ids = set()
    # Files with status='processing'
    processing_file_ids.update(fasta_files.filter(status='processing').values_list('id', flat=True))
    # Files with job status='pending' or 'running'
    processing_file_ids.update(fasta_files.filter(job__status__in=['pending', 'running']).values_list('id', flat=True))
    # Get the actual files
    processing_files = fasta_files.filter(id__in=processing_file_ids)
    
    # Limit jobs to latest 5 for display
    jobs = all_jobs.order_by('-started_at')[:5]
    
    context = {
        'fasta_files': fasta_files,
        'jobs': jobs,
        'completed_files': completed_files,
        'incomplete_files': incomplete_files,
        'processing_files': processing_files,
    }
    return render(request, 'fasta_processor/jobs.html', context)


@login_required
def download_result(request, job_id):
    """View to download enzyme-level processing results"""
    job = get_object_or_404(ProcessingJob, id=job_id, user=request.user)
    
    if job.status != 'completed' or not job.result_file:
        messages.error(request, 'Result file not available.')
        return redirect('fasta_processor:jobs')
    
    try:
        file_path = job.result_file.path
        if os.path.exists(file_path):
            response = FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=f"enzymes_{job.fasta_file.original_filename}.csv"
            )
            return response
        else:
            raise Http404("File not found")
    except Exception as e:
        messages.error(request, f'Error downloading file: {str(e)}')
        return redirect('fasta_processor:jobs')


@login_required
def download_pathway(request, job_id):
    """View to download pathway-level scores"""
    job = get_object_or_404(ProcessingJob, id=job_id, user=request.user)
    
    if job.status != 'completed' or not job.pathway_file:
        messages.error(request, 'Pathway scores file not available.')
        return redirect('fasta_processor:jobs')
    
    try:
        file_path = job.pathway_file.path
        if os.path.exists(file_path):
            response = FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=f"pathways_{job.fasta_file.original_filename}.csv"
            )
            return response
        else:
            raise Http404("File not found")
    except Exception as e:
        messages.error(request, f'Error downloading pathway file: {str(e)}')
        return redirect('fasta_processor:jobs')


@login_required
def reset_job(request, job_id):
    """View to manually reset a stuck job"""
    from django.utils import timezone
    job = get_object_or_404(ProcessingJob, id=job_id, user=request.user)
    
    if job.status == 'running':
        job.status = 'pending'
        job.error_message = 'Job was manually reset. Please try uploading again.'
        job.completed_at = None
        job.save()
        job.fasta_file.status = 'uploaded'
        job.fasta_file.save()
        messages.success(request, f'Job {job_id} has been reset. You can now upload the file again.')
    else:
        messages.info(request, f'Job {job_id} is not in running status, so it cannot be reset.')
    
    return redirect('fasta_processor:jobs')


@login_required
def delete_fasta(request, file_id):
    """View to delete a FASTA file and its job"""
    fasta_file = get_object_or_404(FastaFile, id=file_id, user=request.user)
    
    if request.method == 'POST':
        # Delete associated job and result files
        if hasattr(fasta_file, 'job'):
            job = fasta_file.job
            if job.result_file:
                try:
                    os.remove(job.result_file.path)
                except:
                    pass
            if job.pathway_file:
                try:
                    os.remove(job.pathway_file.path)
                except:
                    pass
            job.delete()
        
        # Delete FASTA file
        try:
            os.remove(fasta_file.file.path)
        except:
            pass
        
        fasta_file.delete()
        messages.success(request, 'File deleted successfully.')
        return redirect('fasta_processor:jobs')
    
    return render(request, 'fasta_processor/delete_confirm.html', {'fasta_file': fasta_file})


@login_required
@require_http_methods(["GET"])
def get_job_progress(request, job_id):
    """API endpoint to get job progress"""
    try:
        job = ProcessingJob.objects.get(id=job_id, user=request.user)
        return JsonResponse({
            'status': job.status,
            'progress': job.progress,
            'progress_message': job.progress_message,
            'completed': job.status == 'completed',
            'failed': job.status == 'failed',
        })
    except ProcessingJob.DoesNotExist:
        return JsonResponse({'error': 'Job not found'}, status=404)


@login_required
def pathway_dashboard(request, job_id):
    """View to display pathway scores in a visual dashboard"""
    job = get_object_or_404(ProcessingJob, id=job_id, user=request.user)
    
    if job.status != 'completed' or not job.pathway_file:
        messages.error(request, 'Pathway scores not available. Please wait for processing to complete.')
        return redirect('fasta_processor:jobs')
    
    try:
        # Read pathway scores CSV
        pathway_file_path = job.pathway_file.path
        if not os.path.exists(pathway_file_path):
            messages.error(request, 'Pathway scores file not found.')
            return redirect('fasta_processor:jobs')
        
        # Read CSV file using built-in csv module
        pathways_data = []
        with open(pathway_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                if 'pathway_score' in row and row['pathway_score']:
                    try:
                        row['pathway_score'] = float(row['pathway_score'])
                    except (ValueError, TypeError):
                        row['pathway_score'] = 0.0
                if 'coverage' in row and row['coverage']:
                    try:
                        row['coverage'] = float(row['coverage'])
                    except (ValueError, TypeError):
                        row['coverage'] = 0.0
                if 'enzymes_detected_count' in row and row['enzymes_detected_count']:
                    try:
                        row['enzymes_detected_count'] = int(row['enzymes_detected_count'])
                    except (ValueError, TypeError):
                        row['enzymes_detected_count'] = 0
                if 'enzymes_expected_count' in row and row['enzymes_expected_count']:
                    try:
                        row['enzymes_expected_count'] = int(row['enzymes_expected_count'])
                    except (ValueError, TypeError):
                        row['enzymes_expected_count'] = 0
                if 'pathway_weight' in row and row['pathway_weight']:
                    try:
                        row['pathway_weight'] = float(row['pathway_weight'])
                    except (ValueError, TypeError):
                        row['pathway_weight'] = 1.0
                pathways_data.append(row)
        
        # Calculate summary statistics
        total_pathways = len(pathways_data)
        critical_count = sum(1 for p in pathways_data if p.get('health_status') == 'CRITICAL')
        low_count = sum(1 for p in pathways_data if p.get('health_status') == 'LOW')
        normal_count = sum(1 for p in pathways_data if p.get('health_status') == 'NORMAL')
        optimal_count = sum(1 for p in pathways_data if p.get('health_status') == 'OPTIMAL')
        
        # Sort by score (highest first)
        pathways_data.sort(key=lambda x: float(x.get('pathway_score', 0) or 0), reverse=True)
        
        context = {
            'job': job,
            'fasta_file': job.fasta_file,
            'pathways': pathways_data,
            'total_pathways': total_pathways,
            'critical_count': critical_count,
            'low_count': low_count,
            'normal_count': normal_count,
            'optimal_count': optimal_count,
            'pathways_json': json.dumps(pathways_data)  # For JavaScript charts
        }
        
        return render(request, 'fasta_processor/pathway_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading pathway dashboard: {str(e)}")
        messages.error(request, f'Error loading pathway dashboard: {str(e)}')
        return redirect('fasta_processor:jobs')
