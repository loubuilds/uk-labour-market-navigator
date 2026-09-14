"""Qualified ONS aggregate new-advert counts; no provider API or raw job adverts."""

from __future__ import annotations

import re

from ._source import sha256, worksheet_rows

ADVERT_VERSION = "ons_textkernel_lad_april2023"
ADVERT_RELEASE = "ons_textkernel_2026-08-21"
WORKBOOK_HASH = "59876a7e480e5b654188401cb1466f2a0ca72f404c31a7c7c987f9bb567cce4e"
SOURCE_PAGE = (
    "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/"
    "employmentandemployeetypes/datasets/labourdemandvolumesbystandardoccupationclassificationsoc2020uk"
)
CAVEATS = [
    "ONS statistics in development, derived from Textkernel online adverts and model-assigned SOC2020 occupations.",
    "New adverts are a demand signal, not unique vacancies, filled jobs, available candidates or proof of shortage.",
    "Q2 2026 includes imputed June observations; increased source uncertainty since November 2025 requires caution.",
    "Source collection changes, duplicates and missing adverts affect coverage. "
    "Counts may not add because of rounding.",
    "March 2026 was suppressed; this pack makes no quarter-on-quarter or year-on-year growth claim.",
    "London is published as a region rather than boroughs; district evidence is not substituted with that total.",
]


def extract_advertising(body: bytes, *, expected_hash: str | None = None):
    if sha256(body) != (WORKBOOK_HASH if expected_hash is None else expected_hash):
        raise ValueError("Unqualified advertising workbook release")
    records, places, occupations, suppressed, london = {}, {}, {}, 0, 0
    for line, cells in worksheet_rows(body, "Table 5", start_row=5):
        if line == 5:
            expected = {
                "C": "Local Authority District",
                "D": "SOC 4 digit code",
                "E": "SOC 4 digit label",
                "F": "Local Authority Code",
                "AR": "2026Q2",
            }
            if any(cells.get(k) != v for k, v in expected.items()):
                raise ValueError("Advertising header, granularity or reference quarter changed")
            continue
        code, geo = cells.get("D", ""), cells.get("F", "")
        if code == "Unknown" and cells.get("E") == "Unknown":
            # Publisher's unclassified adverts cannot be assigned to a role.
            continue
        if not re.fullmatch(r"\d{4}", code):
            raise ValueError("Unexpected advertising occupation row")
        if not geo and cells.get("C") == "London" and cells.get("A") == "London":
            london += 1
            continue
        if not re.fullmatch(r"[ENSW]\d{8}", geo):
            raise ValueError("Unexpected advertising district identity")
        key = geo + "/" + code
        raw = cells.get("AR", "")
        if key in records or (raw != "[x]" and not re.fullmatch(r"\d+", raw)):
            raise ValueError("Duplicate, missing or non-count advertising cell")
        label = cells["E"]
        if code in occupations and occupations[code] != label:
            raise ValueError("Inconsistent advertising occupation labels")
        occupations[code] = label
        place = {
            "id": geo,
            "label": cells["C"],
            "version": ADVERT_VERSION,
            "type": "local_authority_district",
            "boundary": "ONS advertising district as at April 2023",
        }
        if geo in places and places[geo] != place:
            raise ValueError("Inconsistent advertising geography labels")
        places[geo] = place
        records[key] = {"row": line, "raw": raw}
        suppressed += raw == "[x]"
    if len(records) != 133853 or london != 412:
        raise ValueError("Advertising table row coverage differs from its qualified release")
    return records, places, occupations, suppressed
