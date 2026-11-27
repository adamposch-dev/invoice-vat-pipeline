"""Directory scanning, VAT/BTW balance calculation, and CSV/Excel export."""

from dataclasses import asdict
from pathlib import Path
import pandas as pd

from .pdf_parser import InvoiceRecord, extract_text_from_pdf, parse_invoice_text


def scan_invoice_directory(input_dir: Path, direction: str) -> list[InvoiceRecord]:
    """Parse all PDF invoices in a directory into normalized records."""
    if not input_dir.exists():
        return []
    records: list[InvoiceRecord] = []
    for pdf_path in sorted(input_dir.glob("*.pdf")):
        text = extract_text_from_pdf(pdf_path)
        records.append(parse_invoice_text(text, direction=direction, source_name=pdf_path.name))
    return records


def build_vat_summary(records: list[InvoiceRecord]) -> tuple[pd.DataFrame, dict[str, float]]:
    """Aggregate invoice records into a DataFrame and quarterly VAT totals."""
    columns = [
        "source_file",
        "direction",
        "invoice_number",
        "invoice_date",
        "net_amount",
        "vat_amount",
        "gross_amount",
        "vat_rate_pct",
        "currency",
    ]
    df = pd.DataFrame([asdict(r) for r in records], columns=columns)

    outgoing_mask = df["direction"] == "outgoing"
    incoming_mask = df["direction"] == "incoming"

    outgoing_vat = round(float(df.loc[outgoing_mask, "vat_amount"].sum()), 2)
    incoming_vat = round(float(df.loc[incoming_mask, "vat_amount"].sum()), 2)
    outgoing_net = round(float(df.loc[outgoing_mask, "net_amount"].sum()), 2)
    incoming_net = round(float(df.loc[incoming_mask, "net_amount"].sum()), 2)

    summary = {
        "outgoing_net_eur": outgoing_net,
        "incoming_net_eur": incoming_net,
        "outgoing_vat_payable_eur": outgoing_vat,
        "incoming_vat_deductible_eur": incoming_vat,
        "net_vat_balance_eur": round(outgoing_vat - incoming_vat, 2),
        "net_cashflow_excl_vat_eur": round(outgoing_net - incoming_net, 2),
    }
    return df, summary


def export_reports(
    df: pd.DataFrame,
    summary: dict[str, float],
    output_dir: Path,
    prefix: str = "vat_report",
) -> tuple[Path, Path]:
    """Write normalized invoice rows and VAT summary to CSV and Excel."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{prefix}.csv"
    xlsx_path = output_dir / f"{prefix}.xlsx"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    summary_df = pd.DataFrame(
        [{"metric": key, "value": value} for key, value in summary.items()]
    )
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Invoices", index=False)
        summary_df.to_excel(writer, sheet_name="VAT_Summary", index=False)

    return csv_path, xlsx_path
