"""
Django management command to reset a stuck processing job.
"""
from django.core.management.base import BaseCommand
from fasta_processor.models import ProcessingJob
from django.utils import timezone


class Command(BaseCommand):
    help = 'Reset a stuck processing job by ID'

    def add_arguments(self, parser):
        parser.add_argument('job_id', type=int, help='ProcessingJob ID to reset')

    def handle(self, *args, **options):
        job_id = options['job_id']
        
        try:
            job = ProcessingJob.objects.get(id=job_id)
            
            if job.status == 'running':
                job.status = 'pending'
                job.error_message = 'Job was manually reset via management command'
                job.completed_at = None
                job.save()
                
                job.fasta_file.status = 'uploaded'
                job.fasta_file.save()
                
                self.stdout.write(self.style.SUCCESS(f'✅ Job {job_id} has been reset to pending'))
                self.stdout.write(f'   You can now upload the file again or run: python manage.py process_fasta_job {job_id}')
            elif job.status == 'completed':
                self.stdout.write(self.style.WARNING(f'⚠️  Job {job_id} is already completed. Cannot reset.'))
            elif job.status == 'failed':
                self.stdout.write(self.style.WARNING(f'⚠️  Job {job_id} is already failed. Resetting anyway...'))
                job.status = 'pending'
                job.error_message = 'Job was manually reset via management command'
                job.completed_at = None
                job.save()
                job.fasta_file.status = 'uploaded'
                job.fasta_file.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Job {job_id} has been reset to pending'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠️  Job {job_id} status is "{job.status}". Resetting anyway...'))
                job.status = 'pending'
                job.error_message = 'Job was manually reset via management command'
                job.completed_at = None
                job.save()
                job.fasta_file.status = 'uploaded'
                job.fasta_file.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Job {job_id} has been reset to pending'))
                
        except ProcessingJob.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Job {job_id} not found'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error resetting job {job_id}: {str(e)}'))

