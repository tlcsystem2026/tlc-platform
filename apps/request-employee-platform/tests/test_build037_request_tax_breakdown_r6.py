from src.services.request_tax_breakdown_service import (
    compare_tax_breakdowns,
    finalize_tax_breakdown,
)


def test_missing_excel_inclusive_is_derived_from_taxable_and_tax():
    pdf = finalize_tax_breakdown({
        "taxable_amount_10": "637",
        "tax_amount_10": "63",
        "tax_inclusive_amount_10": "700",
        "taxable_amount_8": "20371",
        "tax_amount_8": "1629",
        "tax_inclusive_amount_8": "22000",
        "non_taxable_amount": "",
        "tax_exempt_amount": "",
    })
    excel = finalize_tax_breakdown({
        "taxable_amount_10": "637",
        "tax_amount_10": "63",
        "tax_inclusive_amount_10": "700",
        "taxable_amount_8": "20371",
        "tax_amount_8": "1629",
        "tax_inclusive_amount_8": "",
        "non_taxable_amount": "",
        "tax_exempt_amount": "",
    })

    assert excel["tax_inclusive_amount_8"] == "22000"
    assert compare_tax_breakdowns(pdf, excel) == ([], [])


def test_missing_excel_tax_is_derived_from_inclusive_minus_taxable():
    pdf = finalize_tax_breakdown({
        "taxable_amount_10": "0",
        "tax_amount_10": "0",
        "tax_inclusive_amount_10": "0",
        "taxable_amount_8": "462963",
        "tax_amount_8": "37037",
        "tax_inclusive_amount_8": "500000",
        "non_taxable_amount": "",
        "tax_exempt_amount": "",
    })
    excel = finalize_tax_breakdown({
        "taxable_amount_10": "",
        "tax_amount_10": "",
        "tax_inclusive_amount_10": "0",
        "taxable_amount_8": "462963",
        "tax_amount_8": "",
        "tax_inclusive_amount_8": "500000",
        "non_taxable_amount": "",
        "tax_exempt_amount": "",
    })

    assert excel["taxable_amount_10"] == "0"
    assert excel["tax_amount_10"] == "0"
    assert excel["tax_amount_8"] == "37037"
    assert compare_tax_breakdowns(pdf, excel) == ([], [])
