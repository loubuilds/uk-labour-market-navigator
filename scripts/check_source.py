"""Reproduce every qualified Census cell and SOC entry, entirely offline."""

import csv
import io
import zipfile

from uk_labour_market_navigator._source import RESOURCES, encode_cells, extract_cells, sha256, snapshot


def main():
    if not __debug__:
        raise RuntimeError("Source validation must run without Python optimisation")
    from uk_labour_market_navigator.demand import reference as advert_reference
    from uk_labour_market_navigator.evidence import CENSUS_LABELS
    from uk_labour_market_navigator.identities import reference as identities
    from uk_labour_market_navigator.pay import snapshot as pay_snapshot

    body, ref = snapshot()
    assert identities() == {
        "schema_version": 1,
        "advertising_places": advert_reference()["places"],
        "advertising_occupations": advert_reference()["occupations"],
        "pay_occupations": {v["occupation_code"]: v["occupation_label"] for v in pay_snapshot()[0].values()},
        "occupations": ref["occupations"],
        "places": {**advert_reference()["places"], **ref["places"]},
    }
    raw = (RESOURCES / "source.xlsx").read_bytes()
    assert sha256(raw) == ref["evidence"]["source_sha256"]
    rows = extract_cells(raw)
    assert encode_cells(rows) == body
    soc = (RESOURCES / "soc2020.zip").read_bytes()
    assert sha256(soc) == ref["soc_source"]["sha256"]
    with zipfile.ZipFile(io.BytesIO(soc)) as archive:
        reader = csv.DictReader(
            io.StringIO(archive.read("SOC2020_volume1_descriptionofunitgroups.csv").decode("cp1252"))
        )
        official = {
            r["SOC2020 Unit Group"]: r
            for r in reader
            if len(r["SOC2020 Unit Group"]) == 4 and r["SOC2020 Unit Group"].isdigit()
        }
    assert set(official) == set(ref["occupations"])
    for code, role in ref["occupations"].items():
        assert role["label"] == official[code]["SOC2020\nGroup Title"].strip()
        assert role["related_titles"] == official[code]["Related Job Titles"].strip()
    for row in rows:
        assert (
            row["soc_label"].casefold()
            == CENSUS_LABELS.get(row["soc_code"], ref["occupations"][row["soc_code"]]["label"]).casefold()
        )
        assert row["geography_label"] == ref["places"][row["geography_id"]]["label"]
    print(
        f"PASS: {len(rows)} literal Census observations, 412 SOC entries and geography labels reproduce from qualified originals."
    )


if __name__ == "__main__":
    main()
