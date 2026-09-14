"""Reproduce all qualified new-advert cells and trace selected observations offline."""

import gzip
import io
import json

from uk_labour_market_navigator import demand
from uk_labour_market_navigator._demand_source import ADVERT_RELEASE, extract_advertising
from uk_labour_market_navigator._source import reference


def main():
    if not __debug__:
        raise RuntimeError("Source validation must run without Python optimisation")
    records, ref = demand.snapshot()
    body = (demand.RESOURCES / "labourdemandbyoccupation.xlsx").read_bytes()
    actual, places, occupations, suppressed = extract_advertising(body)
    assert actual == records and places == ref["places"] and occupations == ref["occupations"]
    assert suppressed == ref["suppressed"] == 74274
    assert set(occupations) == set(reference()["occupations"])
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as stream:
        stream.write(
            json.dumps(
                {"schema_version": 1, "version": ADVERT_RELEASE, "records": actual},
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode()
        )
    assert output.getvalue() == (demand.RESOURCES / "advertising.json.gz").read_bytes()
    oracles = {
        "E06000038/2134": (71999, "338"),
        "E07000008/2134": (20906, "705"),
        "S12000036/2134": (57354, "455"),
        "N09000003/2134": (53697, "489"),
    }
    for key, (row, value) in oracles.items():
        assert actual[key] == {"row": row, "raw": value}
    print(
        json.dumps(
            {
                "status": "passed",
                "reproduced_records": len(actual),
                "suppressed": suppressed,
                "occupations": len(occupations),
                "manual_trace_oracles": oracles,
                "workbook_sha256": ref["workbook_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
