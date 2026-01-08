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

    # def value_from_datadict(self, data, files, name):
          # Return None to let the view handle multiple files via request.FILES.getlist()
         # return None
    
    def value_from_datadict(self, data, files, name):
        return files.getlist(name)


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
    
    tpm_file = forms.FileField(
    required=False,
    widget=forms.FileInput(attrs={'accept': '.csv'}),
    help_text="Optional RNA TPM table for real metabolic scoring"
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

def clean_tpm_file(self):
    tpm = self.cleaned_data.get("tpm_file")
    if not tpm:
        return None

    if not tpm.name.lower().endswith(".csv"):
        raise forms.ValidationError("TPM file must be a CSV file")

    import pandas as pd
    try:
        df = pd.read_csv(tpm)
    except Exception:
        raise forms.ValidationError("TPM file is not a valid CSV")

    required = {"protein_id"}
    if not required.issubset(df.columns):
        raise forms.ValidationError("TPM CSV must contain protein_id column")

    if "TPM" not in df.columns and "TPM_norm" not in df.columns:
        raise forms.ValidationError("TPM CSV must contain TPM or TPM_norm column")

    return tpm

