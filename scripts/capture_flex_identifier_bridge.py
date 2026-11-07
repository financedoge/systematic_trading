"""Retain a pre-window SEC CUSIP/ISIN bridge for the foreign FLEX identifier."""
from datetime import UTC, datetime
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

import acquire_ten_qualification as sec


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research/p421-crsp-qualification-20261107-v1"
CACHE = ROOT / "var/research/p421-crsp-qualification-20261107-v1/identity"
BASE = "https://www.sec.gov/Archives/edgar/data/202032/000175272423269945/"


def extract_bridge(raw, index_raw):
    root = ET.fromstring(raw)
    matches = []
    for holding in root.iter():
        if holding.tag.split("}")[-1] != "invstOrSec":
            continue
        fields = {n.tag.split("}")[-1]:(n.text or "").strip() for n in holding.iter()}
        isins = [n.attrib.get("value") for n in holding.iter() if n.tag.split("}")[-1] == "isin"]
        if fields.get("cusip") == "Y2573F102" and "SG9999000020" in isins:
            matches.append(dict(name=fields["name"],title=fields.get("title"),cusip=fields["cusip"],
                                isin="SG9999000020",currency=fields.get("curCd")))
    if len(matches) != 1 or "FLEX" not in matches[0]["name"].upper() or matches[0]["currency"] != "USD":
        raise ValueError("Expected unique same-record FLEX identifier bridge")
    soup = BeautifulSoup(index_raw,"html.parser")
    headings = soup.find_all(class_="infoHead")
    info = {h.get_text(strip=True):h.find_next_sibling(class_="info").get_text(strip=True)
            for h in headings if h.find_next_sibling(class_="info") is not None}
    filing = info.get("Filing Date", "")
    if not filing or filing >= "2024-02-27":
        raise ValueError("Identifier bridge was not filed before the pilot window")
    return dict(holding=matches[0],filing_date=filing,accepted=info.get("Accepted"),
                purpose="Identifier corroboration only, never a replacement holdings snapshot",
                historical_vendor_interval_availability_certified=False)


def main():
    sec.CACHE = CACHE
    CACHE.mkdir(parents=True,exist_ok=True)
    request = dict(frozen_at=datetime.now(UTC).isoformat(), urls=[BASE+"primary_doc.xml",
        BASE+"0001752724-23-269945-index.html"],scope="Retain same-record FLEX CUSIP/ISIN and pre-window SEC filing date.")
    request_path = CACHE / "request.json"
    if request_path.exists():
        old = json.loads(request_path.read_text())
        if old["urls"] != request["urls"]:
            raise ValueError("Changed identifier source scope")
    else:
        sec.save(request_path,request)
    raw,receipt = sec.capture("flex-nport",request["urls"][0])
    index,index_receipt = sec.capture("flex-index",request["urls"][1])
    result = dict(**extract_bridge(raw,index),source=receipt,index_source=index_receipt,
                  runner_sha256=sec.sha(Path(__file__).read_bytes()),cache=str(CACHE))
    sec.save(STUDY / "flex-identifier-bridge.json",result)
    print(json.dumps(dict(status="identifier_bridge_retained",filing_date=result["filing_date"])),flush=True)


if __name__ == "__main__":
    main()
