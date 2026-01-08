from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class FastaFile(models.Model):
    """Model to store uploaded FASTA files"""
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fasta_files')
    file = models.FileField(upload_to='fasta_files/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    description = models.TextField(blank=True, help_text="Optional description")
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'FASTA File'
        verbose_name_plural = 'FASTA Files'
    
    def __str__(self):
        return f"{self.original_filename} - {self.user.username}"
    
    def get_file_size_mb(self):
        """Return file size in MB"""
        return round(self.file_size / (1024 * 1024), 2)


class ProcessingJob(models.Model):
    """Model to track eggnog processing jobs"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    fasta_file = models.OneToOneField(FastaFile, on_delete=models.CASCADE, related_name='job')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processing_jobs')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_file = models.FileField(upload_to='results/%Y/%m/%d/', null=True, blank=True, help_text="Enzyme-level results CSV file")
    pathway_file = models.FileField(upload_to='results/%Y/%m/%d/', null=True, blank=True, help_text="Pathway-level scores CSV file")
    error_message = models.TextField(blank=True)
    eggnog_version = models.CharField(max_length=50, blank=True)
    processing_time = models.FloatField(null=True, blank=True, help_text="Processing time in seconds")
    progress = models.IntegerField(default=0, help_text="Processing progress percentage (0-100)")
    progress_message = models.CharField(max_length=255, blank=True, help_text="Current processing step message")
    tpm_file = models.FileField(
    upload_to='tpm_tables/%Y/%m/%d/',
    null=True, blank=True,
    help_text="RNA TPM expression table (gene_id, TPM)"
)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Processing Job'
        verbose_name_plural = 'Processing Jobs'
    
    def __str__(self):
        return f"Job {self.id} - {self.fasta_file.original_filename} - {self.status}"
    
    def get_processing_time_formatted(self):
        """Return formatted processing time"""
        if self.processing_time:
            if self.processing_time < 60:
                return f"{self.processing_time:.1f} seconds"
            elif self.processing_time < 3600:
                return f"{self.processing_time / 60:.1f} minutes"
            else:
                return f"{self.processing_time / 3600:.1f} hours"
        return "N/A"
