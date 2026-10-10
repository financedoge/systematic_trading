"""Strict parsers for the qualified State Street equity ETF snapshot formats."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from io import BytesIO
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
MISSING = {"", "-", "--", "N/A", "N.A.", "—"}


def clean(value):
    return " ".join(value.replace("\ufeff", "").split())


class Tables(HTMLParser):
    """Read displayed cells, excluding glossary/tooltips and their duplicate labels."""
    def __init__(self, raw):
        super().__init__(convert_charrefs=True)
        self.tables, self.heading, self.table = [], "", None
        self.cell, self.row, self.heading_parts = None, None, None
        self.stack = []
        self.feed(raw.decode("utf-8-sig"))

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if tag not in {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area", "base", "embed", "param", "col"}:
            self.stack.append((tag, "info" in classes or tag in {"script", "style"}))
        if any(skip for _, skip in self.stack):
            return
        if tag in {"h2", "h3"}:
            self.heading_parts = []
        elif tag == "table":
            if self.table is not None:
                raise ValueError("Nested issuer table")
            self.table = dict(heading=self.heading, rows=[])
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        suppressed = any(skip for _, skip in self.stack)
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if suppressed:
            return
        if tag in {"h2", "h3"} and self.heading_parts is not None:
            self.heading = clean(" ".join(self.heading_parts))
            self.heading_parts = None
        elif tag in {"td", "th"} and self.cell is not None:
            self.row.append(clean(" ".join(self.cell)))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None

    def handle_data(self, data):
        if any(skip for _, skip in self.stack):
            return
        if self.cell is not None:
            self.cell.append(data)
        if self.heading_parts is not None:
            self.heading_parts.append(data)


def section(tables, titles):
    found = [t for t in tables if any(t["heading"].startswith(title + " as of ") for title in titles)]
    if len(found) != 1:
        raise ValueError("Missing or ambiguous issuer section: " + titles[0])
    table = found[0]
    asof = datetime.strptime(table["heading"].rsplit(" as of ", 1)[1], "%b %d %Y").date().isoformat()
    return asof, table["rows"]


def number(raw, units):
    if raw in MISSING:
        return None
    patterns = {"ratio": r"(-?[\d,]+(?:\.\d+)?)", "count": r"(\d+)",
                "percent": r"(-?[\d,]+(?:\.\d+)?)%", "USD/share": r"\$([\d,]+(?:\.\d+)?)",
                "USD": r"\$([\d,]+(?:\.\d+)?) M", "shares": r"([\d,]+(?:\.\d+)?) M"}
    match = re.fullmatch(patterns[units], raw)
    if not match:
        raise ValueError("Unsupported issuer numeric value or units: " + raw)
    value = Decimal(match[1].replace(",", ""))
    if units in {"USD", "shares"}:
        value *= 1_000_000
    return str(value)


def workbook_rows(raw):
    with ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(set(names)) != len(names) or sum(i.file_size for i in archive.infolist()) > 20_000_000:
            raise ValueError("Invalid issuer workbook size or members")
        sheets = [n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+.xml", n)]
        if sheets != ["xl/worksheets/sheet1.xml"]:
            raise ValueError("Unexpected issuer worksheet schema")
        strings = []
        if "xl/sharedStrings.xml" in names:
            strings = ["".join(x.itertext()) for x in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        sheet = ET.fromstring(archive.read(sheets[0]))
    if sheet.findall(".//s:f", NS):
        raise ValueError("Formula cells are unsupported in issuer holdings")
    rows = []
    for row in sheet.findall(".//s:row", NS):
        cells = {}
        for cell in row:
            coordinate = re.fullmatch(r"([A-Z]+)\d+", cell.get("r", ""))
            if not coordinate or coordinate[1] in cells:
                raise ValueError("Invalid issuer cell coordinate")
            value = cell.find("s:v", NS)
            value = value.text if value is not None else ""
            if cell.get("t") == "s":
                if not value.isdigit() or int(value) >= len(strings):
                    raise ValueError("Invalid shared string")
                value = strings[int(value)]
            elif cell.get("t") == "inlineStr":
                value = "".join(cell.find("s:is", NS).itertext())
            elif cell.get("t") not in {None, "n", "str"}:
                raise ValueError("Unsupported issuer cell type")
            cells[coordinate[1]] = clean(value)
        rows.append(cells)
    return rows


def holdings(raw, fund):
    rows = workbook_rows(raw)
    if len(rows) < 5 or rows[0].get("A") != "Fund Name:" or rows[1] != {"A": "Ticker Symbol:", "B": fund["symbol"]}:
        raise ValueError("Issuer holdings identity mismatch")
    if not all(t.casefold() in rows[0].get("B", "").casefold() for t in fund["name_tokens"]):
        raise ValueError("Issuer holdings fund name mismatch")
    if rows[2].get("A") != "Holdings:":
        raise ValueError("Missing issuer holdings date")
    asof = datetime.strptime(rows[2]["B"], "As of %d-%b-%Y").date().isoformat()
    header = dict(zip("ABCDEFGH", ["Name", "Ticker", "Identifier", "SEDOL", "Weight", "Sector", "Shares Held", "Local Currency"]))
    indices = [i for i, row in enumerate(rows) if row == header]
    if len(indices) != 1:
        raise ValueError("Unsupported issuer holdings columns")
    records, ended = [], False
    for row in rows[indices[0]+1:]:
        if not any(row.get(k) for k in "BCDEFGH"):
            ended = True
            continue
        if ended or not all(row.get(k) for k in "ABCDEFGH"):
            raise ValueError("Incomplete or interrupted holdings table")
        if any(v for k, v in row.items() if k not in header) or row["H"] != fund["currency"]:
            raise ValueError("Unsupported holdings currency or extra columns")
        try:
            weight, shares = Decimal(row["E"]), Decimal(row["G"])
        except InvalidOperation as exc:
            raise ValueError("Missing or invalid holdings weight/shares") from exc
        if not weight.is_finite() or not shares.is_finite() or abs(weight) > 100 or abs(shares) > Decimal("1e15"):
            raise ValueError("Invalid holdings weight/shares")
        records.append(dict(name=row["A"], ticker=None if row["B"] in MISSING else row["B"],
                            identifier=row["C"], sedol=None if row["D"] in MISSING else row["D"],
                            weight_percent=str(weight), sector=None if row["F"] in MISSING else row["F"],
                            shares_held=str(shares), currency=row["H"]))
    identifiers = [r["identifier"] for r in records]
    total = sum(Decimal(r["weight_percent"]) for r in records)
    if not records or any(i in MISSING for i in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Missing or duplicate holdings identity")
    # Record unexplained cash/valuation residuals; never rescale them to 100%.
    # Six displayed decimal places only justify half a last-place unit per row.
    reconciled = abs(total-100) <= Decimal("0.0000005") * len(records)
    top10 = sum(sorted((Decimal(r["weight_percent"]) for r in records), reverse=True)[:10])
    return dict(as_of=asof, fund_name=rows[0]["B"], rows=records, weight_sum_percent=str(total),
                weight_residual_percent=str(100-total), weights_reconciled=reconciled,
                top10_reported_weight_percent=str(top10))


def parse_snapshot(files, fund):
    tables = Tables(files["fund.html"]).tables
    listing_date, listing = section(tables, ["Listing Information"])
    headers = ["Exchange", "Listing Date", "Trading Currency", "Ticker", "CUSIP", "ISIN"]
    if len(listing) != 2 or listing[0] != headers or len(listing[1]) != len(headers):
        raise ValueError("Unsupported issuer listing schema")
    identity = dict(zip(["exchange", "listing_date", "currency", "symbol", "cusip", "isin"], listing[1]))
    if any(identity[k] != fund[k] for k in ["exchange", "currency", "symbol", "cusip", "isin"]):
        raise ValueError("Issuer listing identity mismatch")
    identity["listing_date"] = datetime.strptime(identity["listing_date"], "%b %d %Y").date().isoformat()
    metrics, dates = [], dict(listing=listing_date)
    specs = [
        ("nav", "Fund Net Asset Value", [("nav", "NAV", "USD/share"), ("shares", "Shares Outstanding", "shares"), ("aum", "Assets Under Management", "USD")]),
        ("characteristics", "Fund Characteristics", [("eps_growth", "Est. 3-5 Year EPS Growth", "percent"), ("holding_count", "Number of Holdings", "count"), ("price_book", "Price/Book Ratio", "ratio"), ("forward_pe", "Price/Earnings Ratio FY1", "ratio"), ("weighted_market_cap", "Weighted Average Market Cap", "USD")])]
    for group, title, fields in specs:
        asof, rows = section(tables, [title])
        if any(len(row) != 2 for row in rows) or len({r[0] for r in rows}) != len(rows):
            raise ValueError("Invalid issuer key/value schema")
        values = dict(rows)
        dates[group] = asof
        for key, label, units in fields:
            if label not in values:
                raise ValueError("Missing issuer metric: " + label)
            metrics.append(dict(id=key, name=label, group=group, value=number(values[label], units),
                                units=units, source_text=values[label], as_of=asof))
    values = {m["id"]: Decimal(m["value"]) if m["value"] is not None else None for m in metrics}
    nav_values = [values[k] for k in ["nav", "shares", "aum"]]
    if any(v is not None and v <= 0 for v in nav_values):
        raise ValueError("Nonpositive NAV, shares or AUM")
    # Display rounding: NAV to cents, shares and assets to 0.01 million.
    reconciled = all(v is not None for v in nav_values)
    if reconciled:
        nav, shares, aum = nav_values
        tolerance = shares*Decimal("0.005") + nav*5000 + Decimal("5025")
        if abs(nav*shares-aum) > tolerance:
            raise ValueError("NAV times shares does not reconcile to AUM within displayed precision")
    dates["allocation"], allocation = section(tables, ["Fund Industry Allocation", "Fund Sub-Industry Allocation"])
    if allocation[0] != ["Sector", "Weight"] or any(len(row) != 2 for row in allocation[1:]):
        raise ValueError("Invalid issuer industry allocation schema")
    groups = [dict(name=r[0], weight_percent=number(r[1], "percent")) for r in allocation[1:]]
    if not groups or len({g["name"] for g in groups}) != len(groups):
        raise ValueError("Missing or duplicate industry allocation")
    if any(g["weight_percent"] is None or not 0 <= Decimal(g["weight_percent"]) <= 100 for g in groups):
        raise ValueError("Invalid industry allocation weights")
    if abs(sum(Decimal(g["weight_percent"]) for g in groups)-100) > Decimal("0.1"):
        raise ValueError("Industry weights do not reconcile to 100 percent")
    positions = holdings(files["holdings.xlsx"], fund)
    dates["holdings"] = positions["as_of"]
    count = values["holding_count"]
    if count is not None and (count <= 0 or (dates["holdings"] == dates["characteristics"] and count > len(positions["rows"]))):
        raise ValueError("Holdings count is inconsistent")
    return dict(symbol=fund["symbol"], identity=identity, dates=dates, metrics=metrics,
                holdings=positions, industry_allocation=groups, nav_reconciled=reconciled)
