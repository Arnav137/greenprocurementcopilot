import fitz  # PyMuPDF
import pandas as pd


def extract_text(path: str, file_type: str) -> str:
    """Raw text out of an uploaded file. The AI workflow structures it."""
    file_type = file_type.lower()
    if file_type == "pdf":
        with fitz.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    if file_type == "csv":
        return pd.read_csv(path).to_csv(index=False)
    if file_type in ("xlsx", "xls"):
        return pd.read_excel(path).to_csv(index=False)
    raise ValueError(f"Unsupported file type: {file_type}")
