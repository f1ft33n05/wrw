import asyncio

import pytest
from fastapi import HTTPException

from routes import reports


@pytest.fixture
def report_export_data(monkeypatch):
    columns = ["Invoice", "Total"]
    rows = [{"Invoice": "INV-1", "Total": "10.00"}]
    monkeypatch.setattr(reports, "report_data", lambda *args: (columns, rows))
    monkeypatch.setattr(reports, "report_totals", lambda *args: {"Invoice": "", "Total": "10.00"})
    monkeypatch.setattr(
        reports,
        "financial_summary",
        lambda *args: {
            "total_sales": 10,
            "total_payments": 10,
            "receipts": 1,
            "total_purchases": 0,
            "supplier_payments": 0,
            "inventory_value": 0,
            "accounts_receivable": 0,
        },
    )


@pytest.mark.parametrize(
    ("file_format", "content_type", "filename"),
    [
        ("csv", "text/csv", "sales.csv"),
        (
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "sales.xlsx",
        ),
    ],
)
def test_report_export_formats_remain_available(
    report_export_data,
    file_format,
    content_type,
    filename,
):
    response = asyncio.run(reports.export_report(file_format, None, "sales", None, None))

    assert response.media_type == content_type
    assert filename in response.headers["content-disposition"]


def test_report_pdf_export_is_removed(report_export_data):
    with pytest.raises(HTTPException) as error:
        asyncio.run(reports.export_report("pdf", None, "sales", None, None))

    assert error.value.status_code == 404
