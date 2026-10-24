from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = str(BASE_DIR / "uploads")
ALLOWED_TYPES = {"pdf", "csv", "xlsx", "xls"}
