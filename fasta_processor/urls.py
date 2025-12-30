from django.urls import path
from . import views

app_name = 'fasta_processor'

urlpatterns = [
    path('upload/', views.upload_fasta, name='upload'),
    path('jobs/', views.fasta_jobs, name='jobs'),
    path('download/<int:job_id>/', views.download_result, name='download'),
    path('download-pathway/<int:job_id>/', views.download_pathway, name='download_pathway'),
    path('pathway-dashboard/<int:job_id>/', views.pathway_dashboard, name='pathway_dashboard'),
    path('reset/<int:job_id>/', views.reset_job, name='reset'),
    path('delete/<int:file_id>/', views.delete_fasta, name='delete'),
    path('progress/<int:job_id>/', views.get_job_progress, name='progress'),
]

