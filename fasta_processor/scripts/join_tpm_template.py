import pandas as pd

ENZYMES = r"{ENZYMES_CSV}"
TPM = r"{TPM_FILE}"
OUTPUT = r"{OUTPUT_FILE}"

enz = pd.read_csv(ENZYMES)
tpm = pd.read_csv(TPM)

merged = enz.merge(tpm, on="protein_id", how="left")
merged["TPM"] = merged["TPM"].fillna(0)

median = merged["TPM"].median()
merged["TPM_norm"] = merged["TPM"] / median if median > 0 else 0

merged.to_csv(OUTPUT, index=False)
print("TPM joined:", len(merged))
