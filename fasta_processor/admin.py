from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from .models import FastaFile, ProcessingJob


@admin.register(FastaFile)
class FastaFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'user', 'status', 'file_size', 'uploaded_at')
    list_filter = ('status', 'uploaded_at')
    search_fields = ('original_filename', 'user__username', 'user__email')
    readonly_fields = ('uploaded_at', 'file_size')
    date_hierarchy = 'uploaded_at'


@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'fasta_file', 'user', 'status', 'started_at', 'completed_at', 'processing_time')
    list_filter = ('status', 'started_at')
    search_fields = ('fasta_file__original_filename', 'user__username')
    readonly_fields = ('started_at', 'completed_at', 'processing_time')
    date_hierarchy = 'started_at'
    actions = ['reset_stuck_jobs']
    
    @admin.action(description='Reset stuck jobs (running > 2 hours)')
    def reset_stuck_jobs(self, request, queryset):
        """Reset jobs that have been running for more than 2 hours"""
        reset_count = 0
        for job in queryset.filter(status='running'):
            if job.started_at and (timezone.now() - job.started_at) > timedelta(hours=2):
                job.status = 'failed'
                job.error_message = 'Job was stuck and has been reset by admin'
                job.completed_at = timezone.now()
                job.save()
                
                # Also update the associated fasta file
                job.fasta_file.status = 'failed'
                job.fasta_file.save()
                reset_count += 1
        
        self.message_user(request, f'{reset_count} stuck job(s) have been reset.')
