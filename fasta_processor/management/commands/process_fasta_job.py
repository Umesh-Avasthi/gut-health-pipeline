"""
Django management command to process a FASTA file job.
This runs in a separate process, so it survives Django server reloads.
"""
from django.core.management.base import BaseCommand
from fasta_processor.models import ProcessingJob
from fasta_processor.services import EggnogProcessor
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process a FASTA file job by ID'

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=int, help='ProcessingJob ID to process')

    def handle(self, *args, **options):
        job_id = options['job_id']
        
        try:
            job = ProcessingJob.objects.get(id=job_id)
            self.stdout.write(f'Processing job {job_id} for file: {job.fasta_file.original_filename}')
            
            processor = EggnogProcessor()
            # process_fasta returns the ProcessingJob object
            updated_job = processor.process_fasta(job.fasta_file)
            
            # Refresh from database to get latest status
            updated_job.refresh_from_db()
            
            if updated_job.status == 'completed':
                self.stdout.write(self.style.SUCCESS(f'✅ Job {job_id} completed successfully'))
            elif updated_job.status == 'failed':
                self.stdout.write(self.style.ERROR(f'❌ Job {job_id} failed: {updated_job.error_message}'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️ Job {job_id} status: {updated_job.status}'))
                
        except ProcessingJob.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Job {job_id} not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error processing job {job_id}: {str(e)}'))
            logger.exception(f'Error in process_fasta_job command: {str(e)}')

