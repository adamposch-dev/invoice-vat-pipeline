"""CLI entry point for the invoice & VAT automation pipeline."""

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from invoice_pipeline.gmail_fetcher import fetch_invoice_attachments, get_gmail_service
from invoice_pipeline.pdf_parser import parse_invoice_text
from invoice_pipeline.vat_report import build_vat_summary, export_reports, scan_invoice_directory

SAMPLE_INVOICES = [
    (
        "outgoing",
        "inv_2026_001.pdf",
        "Factuur #2026-001\nFactuurdatum: 2026-07-15\nSubtotal: EUR 1.500,00\nBTW 21%: EUR 315,00\nTotaal: EUR 1.815,00",
    ),
    (
        "incoming",
        "cloud_hosting_q3.pdf",
        "Invoice Number: INV-9942\nInvoice Date: 2026-08-01\nNet Amount: EUR 100.00\nVAT 21%: EUR 21.00\nTotal: EUR 121.00",
    ),
    (
        "incoming",
        "szamla_konyvelo_q3.pdf",
        "Számlaszám: SZ-2026-88\nKeltezés: 2026-09-10\nVAT Rate: 21%\nBruttó: EUR 242,00",
    ),
]


def cmd_demo(output_dir: Path) -> None:
    records = [
        parse_invoice_text(text, direction=direction, source_name=name)
        for direction, name, text in SAMPLE_INVOICES
    ]
    df, summary = build_vat_summary(records)
    csv_path, xlsx_path = export_reports(df, summary, output_dir, prefix="demo_vat_report")
    print("Demo VAT Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value:.2f}")
    print(f"Exported: {csv_path} | {xlsx_path}")


def cmd_process(incoming_dir: Path, outgoing_dir: Path, output_dir: Path) -> None:
    records = scan_invoice_directory(outgoing_dir, "outgoing") + scan_invoice_directory(
        incoming_dir, "incoming"
    )
    df, summary = build_vat_summary(records)
    csv_path, xlsx_path = export_reports(df, summary, output_dir)
    print(f"Processed {len(records)} invoices -> {csv_path}, {xlsx_path}")
    print(f"Net VAT balance: EUR {summary['net_vat_balance_eur']:.2f}")


def cmd_fetch(query: str, output_dir: Path) -> None:
    creds = Path(os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"))
    token = Path(os.getenv("GMAIL_TOKEN_PATH", "token.json"))
    service = get_gmail_service(creds, token)
    files = fetch_invoice_attachments(service, query=query, download_dir=output_dir)
    print(f"Downloaded {len(files)} PDF attachments to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Automated Invoice & VAT/BTW Pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Run pipeline on synthetic multi-language sample invoices")
    p_demo.add_argument("--out", type=Path, default=Path("output"))

    p_proc = sub.add_parser("process", help="Parse local incoming/outgoing PDF directories")
    p_proc.add_argument("--incoming", type=Path, required=True)
    p_proc.add_argument("--outgoing", type=Path, required=True)
    p_proc.add_argument("--out", type=Path, default=Path("output"))

    p_fetch = sub.add_parser("fetch", help="Download invoice PDFs via Gmail API (OAuth2)")
    p_fetch.add_argument(
        "--query",
        default=os.getenv("INVOICE_QUERY", "has:attachment filename:pdf (invoice OR factuur)"),
    )
    p_fetch.add_argument("--out", type=Path, default=Path("output/raw_pdfs"))

    args = parser.parse_args()
    if args.command == "demo":
        cmd_demo(args.out)
    elif args.command == "process":
        cmd_process(args.incoming, args.outgoing, args.out)
    elif args.command == "fetch":
        cmd_fetch(args.query, args.out)


if __name__ == "__main__":
    main()
