# Generated migration for pathway_file field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fasta_processor', '0002_processingjob_progress_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='processingjob',
            name='pathway_file',
            field=models.FileField(blank=True, help_text='Pathway-level scores CSV file', null=True, upload_to='results/%Y/%m/%d/'),
        ),
    ]

