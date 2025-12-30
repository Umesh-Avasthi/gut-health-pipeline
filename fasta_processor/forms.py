from django import forms
from .models import FastaFile


class MultipleFileInput(forms.FileInput):
    """Custom widget that supports multiple file uploads"""
    def __init__(self, attrs=None):
        super().__init__(attrs)
        if attrs is not None:
            self.attrs = attrs.copy()
        else:
            self.attrs = {}
        self.attrs['multiple'] = True

    def value_from_datadict(self, data, files, name):
        # Return None to let the view handle multiple files via request.FILES.getlist()
        return None


class FastaFileUploadForm(forms.Form):
    """Form for uploading multiple FASTA files (up to 3)"""
    
    files = forms.FileField(
        widget=MultipleFileInput(attrs={
            'accept': '.fasta,.fa,.fas,.fna,.ffn,.faa,.frn',
            'class': 'form-control',
        }),
        required=True,
        help_text='You can upload up to 3 FASTA files at once'
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': 'Optional: Add a description for these files...'
        }),
        required=False,
        help_text='Optional description (applies to all files)'
    )
    
    def clean_files(self):
        # Get files from form data
        file = self.cleaned_data.get('files')
        
        # For multiple file uploads, we need to get all files from request.FILES
        # This will be handled in the view, but we validate the single file here
        if file:
            valid_extensions = ['.fasta', '.fa', '.fas', '.fna', '.ffn', '.faa', '.frn']
            max_size = 100 * 1024 * 1024  # 100MB
            
            # Check file extension
            if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
                raise forms.ValidationError(
                    f'Invalid file type for "{file.name}". Please upload a FASTA file (.fasta, .fa, .fas, .fna, .ffn, .faa, .frn)'
                )
            
            # Check file size
            if file.size > max_size:
                raise forms.ValidationError(
                    f'File "{file.name}" exceeds 100MB. Your file is {file.size / (1024*1024):.2f}MB'
                )
        
        return file

