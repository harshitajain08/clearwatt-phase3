from pathlib import Path
import re
import fitz
from PIL import Image
import pytesseract

SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

def read_bill(path: Path) -> tuple[str, str]:
    """Extract text; OCR is used for image-only PDFs and image uploads."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED: raise ValueError("Unsupported file type. Upload a PDF, PNG, JPG or WEBP bill.")
    if suffix == ".pdf":
        doc = fitz.open(path)
        text = "\n".join(page.get_text("text") for page in doc)
        if len(text.strip()) < 40:
            text = "\n".join(pytesseract.image_to_string(page.get_pixmap(dpi=220).pil_image()) for page in doc)
    else:
        text = pytesseract.image_to_string(Image.open(path))
    return text, "pymupdf+pytesseract" if len(text.strip()) else "no_text"

def _amount(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        m = re.search(pattern, text, re.I | re.M)
        if m:
            try: return float(m.group(1).replace(",", ""))
            except ValueError: pass
    return None

def extract_fields(text: str) -> dict:
    """Conservative field extraction. Uncertain fields remain null for user review."""
    clean = text.replace("\u20b9", "Rs.")
    units = _amount(clean, [r"(?:units\s+consumed|consumption|energy\s+consumed|total\s+units)\s*[:\-]?\s*([\d,]+(?:\.\d+)?)\s*(?:kwh|units)?"])
    amount = _amount(clean, [r"(?:net\s+amount\s+payable|total\s+amount\s+payable|amount\s+payable|bill\s+amount|grand\s+total)\s*[:\-]?\s*(?:Rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)"])
    prev = _amount(clean, [r"(?:previous|old|last)\s+reading\s*[:\-]?\s*([\d,]+(?:\.\d+)?)"])
    curr = _amount(clean, [r"(?:current|present|latest)\s+reading\s*[:\-]?\s*([\d,]+(?:\.\d+)?)"])
    def date(label: str) -> str | None:
        m = re.search(label + r"\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", clean, re.I)
        if not m: return None
        from datetime import datetime
        raw=m.group(1)
        for fmt in ("%d/%m/%Y","%d-%m-%Y","%d/%m/%y","%d-%m-%y","%m/%d/%Y"):
            try: return datetime.strptime(raw,fmt).date().isoformat()
            except ValueError: continue
        return None
    return {"period_start":date(r"(?:billing\s+period\s+from|from\s+date|bill\s+period\s+start)"),"period_end":date(r"(?:billing\s+period\s+to|to\s+date|bill\s+date|reading\s+date)"),"units":units,"amount":amount,"meter_reading_previous":prev,"meter_reading_current":curr,"consumer_category":"domestic"}
