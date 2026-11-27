# Invoice & Quarterly VAT/BTW Automation Pipeline

Python CLI pipeline that automates quarterly freelance/SME bookkeeping preparation:
1. Fetches invoice PDF attachments from Gmail via **OAuth2 (Gmail API)**.
2. Extracts invoice numbers, dates, and multi-language numeric totals (**EN / NL / HU**) from PDF text.
3. Aggregates payable vs. deductible **VAT/BTW** and cashflow balances in **Pandas**, exporting structured **CSV** and multi-sheet **Excel** reports.

## Architecture

```text
Gmail API (OAuth2) ──▶ gmail_fetcher.py ──▶ Raw PDFs
                                               │
Local PDF Folders  ────────────────────────▶ pdf_parser.py (pypdf + regex)
                                               │
                                               ▼
                                          vat_report.py (Pandas)
                                               │
                                               ▼
                                    CSV & Excel (Invoices + VAT_Summary)
```

## Quickstart (No Credentials Required)

Run the built-in synthetic multi-language demo:

```bash
pip install -r requirements.txt
python cli.py demo
```

Or run with Docker:

```bash
docker build -t invoice-vat-pipeline .
docker run --rm -v "$(pwd)/output:/app/output" invoice-vat-pipeline
```

## Usage with Local PDFs & Gmail API

1. **Process local incoming/outgoing invoice directories:**
   ```bash
   python cli.py process --incoming ./invoices/in --outgoing ./invoices/out --out ./output
   ```

2. **Fetch invoice PDFs from Gmail (OAuth2):**
   - Copy `.env.example` to `.env` and place your Google Cloud OAuth `credentials.json` in the project root (ignored by `.gitignore`).
   ```bash
   python cli.py fetch --query 'after:2026/07/01 before:2026/10/01 (invoice OR factuur)' --out ./invoices/raw
   ```

## Tests

```bash
python -m unittest discover -s tests -v
```
