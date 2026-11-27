"""Unit tests for invoice parsing, VAT calculation, and Excel/CSV export."""

from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoice_pipeline.pdf_parser import parse_invoice_text, parse_localized_amount
from invoice_pipeline.vat_report import build_vat_summary, export_reports


class TestInvoicePipeline(unittest.TestCase):
    def test_parse_localized_amounts(self) -> None:
        self.assertEqual(parse_localized_amount("1.234,56"), 1234.56)
        self.assertEqual(parse_localized_amount("1,234.56"), 1234.56)
        self.assertEqual(parse_localized_amount("EUR 242,00"), 242.00)

    def test_parse_dutch_outgoing_invoice(self) -> None:
        text = (
            "Factuur #2026-005\n"
            "Factuurdatum: 2026-07-10\n"
            "Subtotal: € 1.000,00\n"
            "BTW 21%: € 210,00\n"
            "Totaal: € 1.210,00\n"
        )
        rec = parse_invoice_text(text, direction="outgoing", source_name="out.pdf")
        self.assertEqual(rec.invoice_number, "2026-005")
        self.assertEqual(rec.invoice_date, "2026-07-10")
        self.assertEqual(rec.net_amount, 1000.00)
        self.assertEqual(rec.vat_amount, 210.00)
        self.assertEqual(rec.gross_amount, 1210.00)

    def test_derive_net_and_vat_from_gross_only(self) -> None:
        text = "Számlaszám: SZ-101\nDátum: 2026-08-12\nVAT Rate: 21%\nBruttó: EUR 242,00"
        rec = parse_invoice_text(text, direction="incoming", source_name="in.pdf")
        self.assertEqual(rec.net_amount, 200.00)
        self.assertEqual(rec.vat_amount, 42.00)
        self.assertEqual(rec.gross_amount, 242.00)

    def test_vat_balance_and_export(self) -> None:
        out_rec = parse_invoice_text(
            "Factuur #1\nDate: 2026-07-01\nSubtotal: 1000.00\nVAT 21%: 210.00\nTotal: 1210.00",
            direction="outgoing",
            source_name="o1.pdf",
        )
        in_rec = parse_invoice_text(
            "Invoice #2\nDate: 2026-07-05\nSubtotal: 200.00\nVAT 21%: 42.00\nTotal: 242.00",
            direction="incoming",
            source_name="i1.pdf",
        )
        df, summary = build_vat_summary([out_rec, in_rec])
        self.assertEqual(summary["outgoing_vat_payable_eur"], 210.00)
        self.assertEqual(summary["incoming_vat_deductible_eur"], 42.00)
        self.assertEqual(summary["net_vat_balance_eur"], 168.00)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path, xlsx_path = export_reports(df, summary, Path(tmp))
            self.assertTrue(csv_path.exists())
            self.assertTrue(xlsx_path.exists())
            excel_summary = pd.read_excel(xlsx_path, sheet_name="VAT_Summary")
            self.assertIn("net_vat_balance_eur", set(excel_summary["metric"]))


if __name__ == "__main__":
    unittest.main()
