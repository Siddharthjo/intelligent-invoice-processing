from decimal import Decimal

from invoice_processing.domain.invoice import LineItem
from invoice_processing.extraction.base import Table
from invoice_processing.parsing.fields import parse_decimal

_DESCRIPTION_HEADERS = {"description", "item", "product", "details"}
_QUANTITY_HEADERS = {"qty", "quantity"}
_UNIT_PRICE_HEADERS = {"unit price", "price", "rate", "unit cost"}
_EXTENDED_PRICE_HEADERS = {"amount", "total", "extended price", "line total"}


def parse_line_items(tables: list[Table]) -> list[LineItem]:
    for table in tables:
        items = _parse_table(table)
        if items:
            return items
    return []


def _parse_table(table: Table) -> list[LineItem]:
    if len(table) < 2:
        return []

    header = [(cell or "").strip().lower() for cell in table[0]]
    columns = _match_columns(header)
    if columns is None:
        return []
    description_i, quantity_i, unit_price_i, extended_price_i = columns

    def cell(row: list[str | None], index: int | None) -> str | None:
        if index is None or index >= len(row):
            return None
        return row[index]

    items: list[LineItem] = []
    for row in table[1:]:
        description = (cell(row, description_i) or "").strip()
        extended_price = parse_decimal(cell(row, extended_price_i))
        if not description or extended_price is None:
            continue

        quantity = parse_decimal(cell(row, quantity_i)) or Decimal(1)
        unit_price = parse_decimal(cell(row, unit_price_i)) or extended_price

        items.append(
            LineItem(
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                extended_price=extended_price,
            )
        )
    return items


def _match_columns(header: list[str]) -> tuple[int, int | None, int | None, int] | None:
    def find(headers: set[str]) -> int | None:
        for index, name in enumerate(header):
            if name in headers:
                return index
        return None

    description_i = find(_DESCRIPTION_HEADERS)
    extended_price_i = find(_EXTENDED_PRICE_HEADERS)
    if description_i is None or extended_price_i is None:
        return None

    return description_i, find(_QUANTITY_HEADERS), find(_UNIT_PRICE_HEADERS), extended_price_i
