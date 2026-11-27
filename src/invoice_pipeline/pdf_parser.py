"""PDF text extraction and multi-language invoice field parser."""

from dataclasses import dataclass
from pathlib import Path
import re
import pypdf


@dataclass(frozen=True)
class InvoiceRecord:
    """Normalized invoice fields extracted from a document."""

    source_file: str
    direction: str
    invoice_number: str
    invoice_date: str
    net_amount: float
    vat_amount: float
    gross_amount: float
    vat_rate_pct: float
    currency: str = "EUR"


def parse_localized_amount(raw: str) -> float:
    """Normalize European (1.234,56) and US (1,234.56) numeric strings to float."""
    cleaned = re.sub(r"[^\d,.\-]", "", raw.strip())
    if not cleaned:
        raise ValueError(f"Empty numeric string: {raw!r}")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts[-1]) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    return round(float(cleaned), 2)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract concatenated text from all pages of a PDF file."""
    reader = pypdf.PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _extract_labeled_amount(labels: list[str], text: str) -> float | None:
    joined = "|".join(labels)
    pattern = (
        rf"\b(?:{joined})\b"
        rf"(?:\s*\(?\d{{1,2}}\s*%\)?)?"
        rf"\s*[:\-]?\s*"
        rf"(?:EUR|€|HUF|Ft)?\s*"
        rf"([\d.,]+)(?!\s*%)"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return parse_localized_amount(match.group(1))


def parse_invoice_text(
    text: str,
    direction: str = "incoming",
    source_name: str = "unknown.pdf",
) -> InvoiceRecord:
    """Extract invoice number, date, and net/VAT/gross totals from text."""
    if direction not in ("incoming", "outgoing"):
        raise ValueError(f"direction must be 'incoming' or 'outgoing', got {direction!r}")

    invoice_number = _first_match(
        [
            r"(?:Invoice\s*(?:No\.?|Number|#)|Factuurnummer|Factuur\s*#|Számlaszám)\s*[:#]?\s*([A-Z0-9\-_/]{3,})",
        ],
        text,
    ) or "UNKNOWN"

    invoice_date = _first_match(
        [
            r"(?:Date|Invoice Date|Factuurdatum|Keltezés|Dátum)\s*[:\-]?\s*(\d{4}[-./]\d{2}[-./]\d{2}|\d{2}[-./]\d{2}[-./]\d{4})",
            r"\b(\d{4}-\d{2}-\d{2})\b",
        ],
        text,
    ) or "UNKNOWN"

    rate_raw = _first_match([r"(?:VAT|BTW|ÁFA)\s*(?:Rate)?\s*[:\(]?\s*(\d{1,2})\s*%"], text)
    vat_rate = float(rate_raw) if rate_raw is not None else 21.0

    net = _extract_labeled_amount(["Subtotal", "Netto", "Nettó", "Excl\\.? BTW", "Net Amount"], text)
    vat = _extract_labeled_amount(["VAT Amount", "BTW\\s*21%", "BTW\\s*9%", "BTW", "ÁFA", "VAT"], text)
    gross = _extract_labeled_amount(["Total Incl\\.?", "Grand Total", "Totaal", "Bruttó", "Total"], text)

    # shortcut: derive missing fields from gross/net when rate is known; upgrade to line-item parser if mixed rates appear.
    if gross is not None and net is None and vat is None:
        net = round(gross / (1.0 + vat_rate / 100.0), 2)
        vat = round(gross - net, 2)
    elif gross is not None and net is None and vat is not None:
        net = round(gross - vat, 2)
    elif net is not None and vat is None:
        vat = round(net * (vat_rate / 100.0), 2)
        gross = round(net + vat, 2) if gross is None else gross
    elif net is not None and vat is not None and gross is None:
        gross = round(net + vat, 2)

    return InvoiceRecord(
        source_file=source_name,
        direction=direction,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        net_amount=round(net or 0.0, 2),
        vat_amount=round(vat or 0.0, 2),
        gross_amount=round(gross or 0.0, 2),
        vat_rate_pct=vat_rate,
    )
