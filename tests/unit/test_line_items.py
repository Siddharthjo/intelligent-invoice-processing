from decimal import Decimal

from invoice_processing.parsing.line_items import parse_line_items


def test_parse_line_items_from_table():
    table = [
        ["Description", "Qty", "Unit Price", "Amount"],
        ["Widget A", "2", "10.00", "20.00"],
        ["Widget B", "1", "30.00", "30.00"],
    ]
    items = parse_line_items([table])
    assert len(items) == 2
    assert items[0].description == "Widget A"
    assert items[0].quantity == Decimal("2")
    assert items[0].unit_price == Decimal("10.00")
    assert items[0].extended_price == Decimal("20.00")


def test_parse_line_items_returns_empty_for_unrecognized_headers():
    table = [["A", "B"], ["1", "2"]]
    assert parse_line_items([table]) == []


def test_parse_line_items_skips_tables_without_a_match():
    bad_table = [["Foo", "Bar"], ["1", "2"]]
    good_table = [
        ["Description", "Amount"],
        ["Service Fee", "99.00"],
    ]
    items = parse_line_items([bad_table, good_table])
    assert len(items) == 1
    assert items[0].description == "Service Fee"
