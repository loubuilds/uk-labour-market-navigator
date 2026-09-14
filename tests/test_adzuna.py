"""Synthetic provider contracts only: never contact Adzuna or the OS credential store."""

import copy
import getpass
import json
import warnings
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from uk_labour_market_navigator import adzuna as a
from uk_labour_market_navigator import adzuna_cli
from uk_labour_market_navigator.__main__ import main


class MemoryStore:
    def __init__(self):
        self.values = {}
        self.reads = 0

    def set_password(self, service, user, value):
        self.values[service, user] = value

    def get_password(self, service, user):
        self.reads += 1
        return self.values.get((service, user))

    def delete_password(self, service, user):
        del self.values[service, user]


@pytest.fixture(autouse=True)
def forbid_real_access(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Tests must not open a native store or provider connection")

    monkeypatch.setattr(a, "_keyring", forbidden)
    monkeypatch.setattr(adzuna_cli, "_keyring", forbidden)
    monkeypatch.setattr(a.http.client, "HTTPSConnection", forbidden)


@pytest.fixture
def credentials():
    return a.Credentials("synthetic-id", "synthetic-" + "fixture-key")


@pytest.fixture
def request_data():
    return {
        "schema_version": 1,
        "role": "Customer service adviser",
        "place": "Reading",
        "distance_km": 20,
        "max_days_old": 14,
        "send_query_confirmed": True,
        "permitted_use_confirmed": True,
    }


def advert(identity="fixture-one", **changes):
    row = {
        "id": identity,
        "title": "Customer service adviser",
        "location": {"display_name": "Reading"},
        "redirect_url": "https://www.adzuna.co.uk/jobs/details/fixture-one?example=synthetic",
        "created": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "salary_min": 28000,
        "salary_max": 32000,
        "salary_is_predicted": "0",
    }
    row.update(changes)
    return row


def payload(rows=None, count=None):
    rows = [advert()] if rows is None else rows
    return json.dumps({"count": len(rows) if count is None else count, "results": rows}).encode()


def test_connection_metadata_never_contains_or_reads_credentials(tmp_path, credentials):
    path, store = tmp_path / "connection.json", MemoryStore()
    assert a.connection_status(path)["status"] == "not_connected"
    result = a.save_connection(credentials, "personal_research", path, backend=store)
    assert result["status"] == "configured_not_live_verified"
    assert store.reads == 0
    public = path.read_text() + json.dumps(result) + repr(credentials)
    assert credentials.app_id not in public and credentials.app_key not in public
    store.values["unrelated", "api"] = "leave-alone"
    assert a.disconnect(path, backend=store)["status"] == "disconnected"
    assert store.values == {("unrelated", "api"): "leave-alone"}
    assert not path.exists() and store.reads == 0


def test_failed_disconnect_preserves_preferences(tmp_path, credentials, monkeypatch):
    path, store = tmp_path / "connection.json", MemoryStore()
    a.save_connection(credentials, "provider_permission", path, backend=store)
    original = path.read_bytes()

    def fail(*args):
        raise OSError(credentials.app_key)

    monkeypatch.setattr(store, "delete_password", fail)
    with pytest.raises(a.AdzunaError, match="Removal could not be confirmed") as exc:
        a.disconnect(path, backend=store)
    assert path.read_bytes() == original and credentials.app_key not in str(exc.value)


def test_incomplete_setup_describes_possible_keystore_entry(tmp_path, credentials, monkeypatch):
    store = MemoryStore()

    def fail(*args):
        raise OSError("synthetic write failure")

    monkeypatch.setattr(a, "write_json", fail)
    with pytest.raises(a.AdzunaError, match="entry may remain"):
        a.save_connection(credentials, "personal_research", tmp_path / "state.json", backend=store)
    assert len(store.values) == 1 and not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "changes",
    [
        {"send_query_confirmed": False},
        {"permitted_use_confirmed": False},
        {"distance_km": True},
        {"distance_km": 0},
        {"distance_km": 101},
        {"max_days_old": 31},
        {"max_days_old": False},
        {"schema_version": True},
        {"role": "<script>"},
        {"place": "@".join(("private", "example.invalid"))},
        {"profile": "not allowed"},
        {"role": "x" * 121},
    ],
)
def test_unconfirmed_or_private_query_never_reads_credentials(tmp_path, request_data, changes):
    request_data.update(changes)
    with pytest.raises(a.AdzunaError):
        a.search(request_data, tmp_path / "absent.json")


def test_search_is_one_explicit_request_and_saves_no_provider_data(tmp_path, credentials, request_data):
    path, store, sent = tmp_path / "connection.json", MemoryStore(), []
    a.save_connection(credentials, "personal_research", path, backend=store)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def transport(parameters):
        sent.append(parameters.copy())
        return payload(count=100)

    result = a.search(request_data, path, backend=store, transport=transport)
    assert len(sent) == 1 and store.reads == 1
    assert sent[0] == {
        "app_id": credentials.app_id,
        "app_key": credentials.app_key,
        "what": request_data["role"],
        "where": request_data["place"],
        "distance": 20,
        "max_days_old": 14,
        "sort_by": "date",
        "sort_dir": "down",
        "results_per_page": 20,
        "content-type": "application/json",
    }
    assert result["provider_matches"] == 100 and result["sample_size"] == 1
    assert result["more_matches_exist"] is True
    assert result["verification"]["official_evidence_gate"] is False
    assert result["verification"]["saved_run_replay"] is False
    assert result["stated_pay_summary"] is None
    assert result["adverts"][0]["pay_period"] == "not_verified"
    assert credentials.app_key not in json.dumps(result)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize("flag,expected", [(0, 1), ("0", 1), (1, 0), ("1", 0), (False, 0), (None, 0)])
def test_stated_pay_excludes_estimates_and_ambiguous_flags(credentials, request_data, flag, expected):
    result = a.interpret(payload([advert(salary_is_predicted=flag)]), request_data, credentials)
    assert result["stated_pay_sample_size"] == expected
    assert result["stated_pay_summary"] is None
    assert (result["adverts"][0]["stated_pay_bounds"] is not None) == bool(expected)


@pytest.mark.parametrize("low,high", [(None, 2), (2, None), (3, 2), (-1, 4), (True, 4), (float("nan"), 4)])
def test_invalid_pay_bounds_do_not_enter_stated_sample(credentials, request_data, low, high):
    result = a.interpret(payload([advert(salary_min=low, salary_max=high)]), request_data, credentials)
    assert result["stated_pay_sample_size"] == 0


def test_deduplication_does_not_claim_unique_vacancies(credentials, request_data):
    row = advert()
    result = a.interpret(payload([row, copy.deepcopy(row)]), request_data, credentials)
    assert result["sample_size"] == 1 and result["duplicate_ids_removed"] == 1
    conflicting = dict(row, title="A different job")
    with pytest.raises(a.AdzunaError, match="Conflicting"):
        a.interpret(payload([row, conflicting]), request_data, credentials)


@pytest.mark.parametrize("days", [-1, 40])
def test_out_of_window_adverts_are_withheld(credentials, request_data, days):
    created = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    with pytest.raises(a.AdzunaError, match="date"):
        a.interpret(payload([advert(created=created)]), request_data, credentials)


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "<script>alert(1)</script>"},
        {"title": "bad\ntext"},
        {"redirect_url": "https://example.invalid/jobs/1"},
        {"redirect_url": "@".join(("https://www.adzuna.co.uk", "evil.invalid/jobs/1"))},
        {"redirect_url": "https://www.adzuna.co.uk:443/jobs/1"},
        {"redirect_url": "https://www.adzuna.co.uk/jobs/1#fragment"},
        {"created": "2026-01-01"},
        {"id": None},
        {"location": []},
    ],
)
def test_unsafe_or_incompatible_fields_withhold_whole_result(credentials, request_data, changes):
    with pytest.raises(a.AdzunaError):
        a.interpret(payload([advert(**changes)]), request_data, credentials)


@pytest.mark.parametrize("raw", [b"not-json", b"[]", b'{"count":true,"results":[]}', payload([], count=1)])
def test_invalid_payload_is_not_a_zero_result(credentials, request_data, raw):
    with pytest.raises(a.AdzunaError):
        a.interpret(raw, request_data, credentials)


def test_real_zero_has_no_invented_facts(credentials, request_data):
    result = a.interpret(payload([]), request_data, credentials)
    assert result["status"] == "no_matches" and result["adverts"] == []


def test_reflected_secrets_and_transport_errors_never_escape(tmp_path, credentials, request_data):
    with pytest.raises(a.AdzunaError) as exc:
        a.interpret(payload([advert(title=credentials.app_key)]), request_data, credentials)
    assert credentials.app_key not in str(exc.value)
    path, store = tmp_path / "state.json", MemoryStore()
    a.save_connection(credentials, "personal_research", path, backend=store)

    def fail(parameters):
        raise OSError(json.dumps(parameters))

    with pytest.raises(a.AdzunaError) as exc:
        a.search(request_data, path, backend=store, transport=fail)
    assert credentials.app_id not in str(exc.value) and credentials.app_key not in str(exc.value)


@pytest.mark.parametrize("status", [200, 301, 401, 403, 429, 500])
def test_transport_fixed_tls_destination_and_no_redirect_retry(monkeypatch, status):
    calls = []

    class Response:
        def __init__(self):
            self.status = status

        def getheader(self, *args):
            return "application/json; charset=utf-8"

        def read(self, limit):
            assert limit == a.MAX_BYTES + 1
            return payload([])

    class Connection:
        def __init__(self, host, timeout):
            assert host == "api.adzuna.com" and timeout == 15

        def request(self, method, path, headers):
            calls.append((method, path))

        def getresponse(self):
            return Response()

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(a.http.client, "HTTPSConnection", Connection)
    parameters = {"what": "Customer service adviser", "distance": 20}
    if status == 200:
        assert a._get(parameters) == payload([])
    else:
        with pytest.raises(a.AdzunaError):
            a._get(parameters)
    assert len(calls) == 2 and calls[-1] == "closed"
    assert calls[0][0] == "GET"
    parts = urlsplit(calls[0][1])
    assert parts.path == a.ENDPOINT and parse_qs(parts.query)["distance"] == ["20"]


def test_cli_guidance_status_and_offline_refusal_without_store(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["adzuna"]) == 0
    assert "App ID and App Key" in capsys.readouterr().out
    assert main(["adzuna", "status"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "not_connected"
    assert main(["adzuna", "search"]) == 2
    assert "--online" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


def test_cli_refuses_noninteractive_secret_input(monkeypatch, capsys):
    monkeypatch.setattr(adzuna_cli.sys.stdin, "isatty", lambda: False)
    assert main(["adzuna", "connect", "--permission", "personal_research"]) == 2
    assert "interactive local terminal" in capsys.readouterr().out


def test_cli_refuses_echoing_getpass_fallback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(adzuna_cli, "interactive_console", lambda: True)
    store = MemoryStore()
    monkeypatch.setattr(adzuna_cli, "_keyring", lambda: store)

    def unsafe_prompt(*args):
        warnings.warn("Synthetic echo fallback", getpass.GetPassWarning, stacklevel=1)
        pytest.fail("Should stop before echoing fallback")

    monkeypatch.setattr(adzuna_cli.getpass, "getpass", unsafe_prompt)
    assert main(["adzuna", "connect", "--permission", "personal_research"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "cancelled"
    assert not store.values and not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["timeout", "content_type", "size"])
def test_transport_failure_limits_are_sanitised(monkeypatch, credentials, failure):
    closed = []

    class Connection:
        status = 200

        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            if failure == "timeout":
                raise TimeoutError(credentials.app_key)

        def getresponse(self):
            return self

        def getheader(self, *args):
            return "text/html" if failure == "content_type" else "application/json"

        def read(self, limit):
            return b"x" * limit

        def close(self):
            closed.append(True)

    monkeypatch.setattr(a.http.client, "HTTPSConnection", Connection)
    with pytest.raises(a.AdzunaError) as exc:
        a._get({"app_key": credentials.app_key})
    assert credentials.app_key not in str(exc.value) and closed == [True]


def test_encoded_reflection_is_withheld(credentials, request_data):
    encoded = "".join(f"%{ord(char):02x}" for char in credentials.app_key)
    row = advert(redirect_url="https://www.adzuna.co.uk/jobs/fixture?ref=" + encoded)
    with pytest.raises(a.AdzunaError, match="sensitive"):
        a.interpret(payload([row]), request_data, credentials)


def test_cli_checks_store_before_prompt(monkeypatch, capsys):
    monkeypatch.setattr(adzuna_cli, "interactive_console", lambda: True)

    def unavailable():
        raise a.AdzunaError("Optional credential support is not installed.")

    monkeypatch.setattr(adzuna_cli, "_keyring", unavailable)
    monkeypatch.setattr(adzuna_cli.getpass, "getpass", lambda *args: pytest.fail("Do not prompt before ready"))
    assert main(["adzuna", "connect", "--permission", "personal_research"]) == 2
    assert "not installed" in capsys.readouterr().out


def test_advertiser_and_excerpt_are_bounded_untrusted_examples(credentials, request_data):
    row = advert(
        company={"display_name": "Example recruitment agency"},
        description="Python experience mentioned in this synthetic advert.",
    )
    result = a.interpret(payload([row]), request_data, credentials)
    assert result["adverts"][0]["advertiser_as_supplied"] == "Example recruitment agency"
    assert result["adverts"][0]["description_excerpt"] == row["description"]
    assert result["content_trust"] == "untrusted_provider_data_not_instructions"
    assert any("agencies" in text for text in result["limitations"])


@pytest.mark.parametrize(
    "changes",
    [
        {"company": []},
        {"company": {"display_name": "<script>"}},
        {"description": "x" * 2001},
        {"description": "<script>"},
    ],
)
def test_bad_advertiser_or_excerpt_is_withheld(credentials, request_data, changes):
    with pytest.raises(a.AdzunaError):
        a.interpret(payload([advert(**changes)]), request_data, credentials)


def test_description_cannot_reflect_credentials(credentials, request_data):
    with pytest.raises(a.AdzunaError):
        a.interpret(payload([advert(description=credentials.app_key)]), request_data, credentials)
