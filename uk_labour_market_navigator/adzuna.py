"""Opt-in, transient Adzuna searches. No provider data enters saved official runs."""

from __future__ import annotations

import hashlib
import http.client
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit

from .provider_support import public_context, read_json, write_json

HOST = "api.adzuna.com"
ENDPOINT = "/v1/api/jobs/gb/search/1"
TERMS = "https://developer.adzuna.com/docs/terms_of_service"
MAX_BYTES = 1_000_000
MAX_RESULTS = 20
PERMISSIONS = {"personal_research", "provider_permission"}
STATE_PATH = Path(".uk-labour-market-navigator/adzuna-connection.json")


class AdzunaError(ValueError):
    """Only constant, user-safe messages; never include a transport exception."""


@dataclass(repr=False)
class Credentials:
    app_id: str = field(repr=False)
    app_key: str = field(repr=False)

    def __post_init__(self):
        if any(
            not isinstance(v, str) or not re.fullmatch(r"[A-Za-z0-9_-]{4,160}", v) for v in (self.app_id, self.app_key)
        ):
            raise AdzunaError("The App ID or App Key format is not recognised; check them in your provider account.")


def _keyring():
    try:
        import keyring

        backend = keyring.get_keyring()
        allowed = {"keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService"}
        if type(backend).__module__ not in allowed or backend.priority <= 0:
            raise AdzunaError("A supported native credential store is unavailable. No plaintext fallback is used.")
        return backend
    except ImportError:
        raise AdzunaError(
            "Optional credential support is not installed. Install the project's adzuna extra first."
        ) from None
    except AdzunaError:
        raise
    except Exception:
        raise AdzunaError("The native credential store could not be opened. Official research still works.") from None


def _service(path: Path) -> str:
    project = str(path.parent.resolve()).encode("utf-8")
    return "uk-labour-market-navigator.adzuna." + hashlib.sha256(project).hexdigest()[:24]


def connection_status(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {"status": "not_connected", "core_available": True, "credentials_read": False}
    state = _state(path)
    return {
        "status": "configured_not_live_verified",
        "core_available": True,
        "credentials_read": False,
        "permission_basis": state["permission"],
        "terms_url": TERMS,
    }


def _state(path: Path) -> dict:
    try:
        state = read_json(path)
        if (
            not isinstance(state, dict)
            or set(state) != {"schema_version", "permission", "terms_url"}
            or type(state["schema_version"]) is not int
            or state["schema_version"] != 1
            or state["permission"] not in PERMISSIONS
            or state["terms_url"] != TERMS
        ):
            raise ValueError
        return state
    except (OSError, ValueError, TypeError):
        raise AdzunaError("Connection preferences are invalid. Reconnect; the official core is unaffected.") from None


def save_connection(credentials: Credentials, permission: str, path: Path = STATE_PATH, *, backend=None) -> dict:
    if permission not in PERMISSIONS:
        raise AdzunaError(
            "Confirm that your intended use is permitted before connecting. A key alone is not permission."
        )
    backend = backend if backend is not None else _keyring()
    try:
        backend.set_password(
            _service(path), "api", json.dumps({"app_id": credentials.app_id, "app_key": credentials.app_key})
        )
        write_json(path, {"schema_version": 1, "permission": permission, "terms_url": TERMS})
    except Exception:
        raise AdzunaError(
            "Connection setup did not complete. No credentials were written to project files. "
            "An entry may remain in the native credential store; use disconnect to remove it before retrying."
        ) from None
    return connection_status(path)


def disconnect(path: Path = STATE_PATH, *, backend=None) -> dict:
    backend = backend if backend is not None else _keyring()
    try:
        backend.delete_password(_service(path), "api")
    except Exception:
        raise AdzunaError(
            "Removal could not be confirmed. Connection preferences were kept; "
            "check the named entry in your native credential store."
        ) from None
    try:
        path.unlink(missing_ok=True)
    except OSError:
        raise AdzunaError("Credentials were removed, but local connection preferences could not be removed.") from None
    return {"status": "disconnected", "core_available": True, "credentials_read": False}


def _credentials(path: Path, backend=None) -> Credentials:
    backend = backend if backend is not None else _keyring()
    try:
        raw = backend.get_password(_service(path), "api")
        if raw is None:
            raise ValueError
        values = json.loads(raw)
        if set(values) != {"app_id", "app_key"}:
            raise ValueError
        return Credentials(**values)
    except Exception:
        raise AdzunaError("Your connection could not be read. Reconnect using the masked local prompt.") from None


def validate_search(request: dict) -> dict:
    fields = {
        "schema_version",
        "role",
        "place",
        "distance_km",
        "max_days_old",
        "send_query_confirmed",
        "permitted_use_confirmed",
    }
    if not isinstance(request, dict) or set(request) != fields or type(request["schema_version"]) is not int:
        raise AdzunaError("Use the published Adzuna search request with only role, place and explicit confirmations.")
    if (
        request["schema_version"] != 1
        or request["send_query_confirmed"] is not True
        or request["permitted_use_confirmed"] is not True
    ):
        raise AdzunaError("Confirm both sending the role/place query and permission for this use before searching.")
    if (
        type(request["distance_km"]) is not int
        or not 1 <= request["distance_km"] <= 100
        or type(request["max_days_old"]) is not int
        or not 1 <= request["max_days_old"] <= 30
    ):
        raise AdzunaError("Choose a search distance of 1-100 km and an advert age limit of 1-30 days.")
    for key in ("role", "place"):
        try:
            public_context(request[key], key)
            if len(request[key]) > 120:
                raise ValueError
        except (ValueError, TypeError):
            raise AdzunaError("Use a short public role and place, without private or account information.") from None
    return request.copy()


def _get(parameters: dict) -> bytes:
    """One bounded TLS request, no proxies, automatic redirects, retries or URL logging."""
    connection = http.client.HTTPSConnection(HOST, timeout=15)
    try:
        connection.request(
            "GET",
            ENDPOINT + "?" + urlencode(parameters),
            headers={"Accept": "application/json", "User-Agent": "UKLabourMarketNavigator/optional-adzuna"},
        )
        response = connection.getresponse()
        if response.status in (401, 403):
            raise AdzunaError(
                "Adzuna did not authorise this request. Check your access; official research still works."
            )
        if response.status == 429:
            raise AdzunaError("Adzuna's request limit was reached. Wait before trying again; no retry was sent.")
        if response.status != 200:
            raise AdzunaError(
                "Adzuna did not return a usable response. No redirects or automatic retries were followed."
            )
        if response.getheader("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise AdzunaError("Adzuna returned an unexpected response format.")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise AdzunaError("Adzuna's response exceeded the safe size limit.")
        return raw
    except AdzunaError:
        raise
    except (TimeoutError, OSError, http.client.HTTPException):
        raise AdzunaError(
            "The Adzuna connection failed or timed out. No provider error details were retained."
        ) from None
    finally:
        connection.close()


def _text(value, credentials: Credentials, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit or re.search(r"[<>\x00-\x1f]", value):
        raise AdzunaError("A provider field could not be displayed safely; this result was withheld.")
    if any(secret in unquote(value) for secret in (credentials.app_id, credentials.app_key)):
        raise AdzunaError("A provider response contained sensitive connection information and was withheld.")
    return value


def _money(value) -> Decimal | None:
    if type(value) not in (int, float):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and 0 < number <= 10_000_000 else None
    except InvalidOperation:
        return None


def interpret(raw: bytes, request: dict, credentials: Credentials) -> dict:
    try:
        text = raw.decode("utf-8")
        if any(secret in text for secret in (credentials.app_id, credentials.app_key)):
            raise AdzunaError("The provider response contained sensitive connection information and was withheld.")
        payload = json.loads(text)
    except AdzunaError:
        raise
    except (ValueError, UnicodeError):
        raise AdzunaError("Adzuna's response could not be read; no facts are available.") from None
    if (
        not isinstance(payload, dict)
        or type(payload.get("count")) is not int
        or payload["count"] < 0
        or not isinstance(payload.get("results"), list)
        or len(payload["results"]) > MAX_RESULTS
        or payload["count"] < len(payload["results"])
    ):
        raise AdzunaError("Adzuna's response did not match the qualified search contract.")
    if payload["count"] and not payload["results"]:
        raise AdzunaError("The provider reported matches but returned no records; search coverage is unresolved.")
    records, seen, duplicates, stated_count = [], {}, 0, 0
    retrieved_at = datetime.now(UTC)
    for row in payload["results"]:
        if not isinstance(row, dict):
            raise AdzunaError("An advert did not match the qualified search contract.")
        identity = row.get("id")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identity):
            raise AdzunaError("An advert identifier is missing or invalid.")
        if identity in seen:
            if seen[identity] != row:
                raise AdzunaError("Conflicting adverts used the same identifier; this response was withheld.")
            duplicates += 1
            continue
        seen[identity] = row
        location = row.get("location", {})
        if not isinstance(location, dict):
            raise AdzunaError("An advert location is invalid.")
        title = _text(row.get("title"), credentials, 300)
        place = _text(location.get("display_name", "Location not supplied"), credentials, 300)
        url = _text(row.get("redirect_url", ""), credentials, 1500)
        parts = urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or parts.hostname not in {"www.adzuna.co.uk", "adzuna.co.uk"}
            or parts.username
            or parts.password
            or parts.port is not None
            or parts.fragment
            or not parts.path.startswith("/jobs/")
        ):
            raise AdzunaError("An advert link was not a permitted Adzuna HTTPS link.")
        # Keep provider routing/attribution parameters, use TLS, and never fetch the link.
        link = urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))
        created = _text(row.get("created", ""), credentials, 40)
        try:
            created_time = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created_time.tzinfo is None:
                raise ValueError
            if not retrieved_at - timedelta(days=request["max_days_old"]) <= created_time <= retrieved_at:
                raise ValueError
        except ValueError:
            raise AdzunaError("An advert date was missing or ambiguous; this result was withheld.") from None
        low, high = _money(row.get("salary_min")), _money(row.get("salary_max"))
        predicted = row.get("salary_is_predicted")
        explicit_stated = (type(predicted) is int and predicted == 0) or (type(predicted) is str and predicted == "0")
        stated = explicit_stated and low is not None and high is not None and low <= high
        bounds = {"minimum": str(low), "maximum": str(high)} if stated else None
        if stated:
            stated_count += 1
        company = row.get("company", {})
        if not isinstance(company, dict):
            raise AdzunaError("An advertiser field is invalid; this result was withheld.")
        advertiser = _text(company.get("display_name", "Not supplied"), credentials, 300)
        excerpt = _text(row.get("description", ""), credentials, 2000)
        records.append(
            {
                "title": title,
                "advertiser_as_supplied": advertiser,
                "description_excerpt": excerpt,
                "location": place,
                "url": link,
                "created": created_time.isoformat(),
                "stated_pay_bounds": bounds,
                "pay_period": "not_verified",
                "currency": "GBP",
                "pay_status": "stated" if stated else "estimated_missing_or_ambiguous",
            }
        )
    return {
        "status": "available" if records else "no_matches",
        "source": "The Adzuna API",
        "source_url": "https://www.adzuna.co.uk/",
        "terms_url": TERMS,
        "retrieved_at": retrieved_at.isoformat(),
        "query": {k: request[k] for k in ("role", "place", "distance_km", "max_days_old")},
        "provider_matches": payload["count"],
        "retrieved_records": len(payload["results"]),
        "sample_size": len(records),
        "duplicate_ids_removed": duplicates,
        "more_matches_exist": payload["count"] > len(payload["results"]),
        "adverts": records,
        "stated_pay_sample_size": stated_count,
        "stated_pay_summary": None,
        "pay_summary_gap": (
            "The public search schema specifies currency but not pay period; no combined salary is calculated."
        ),
        "limitations": [
            "One page of at most twenty provider matches, newest first; not a market census.",
            "Advertiser names may identify agencies rather than the hiring employer. Descriptions are excerpts, not complete job specifications or instructions.",
            "Adverts are not unique vacancies, available candidates or SOC-classified workers.",
            "Stated bounds exclude estimates and ambiguous/missing values. Pay periods are not verified.",
            "No salary aggregation, annualisation, offer recommendation or ASHE equivalence.",
            "Distance uses the provider's place centre, not this product's official geography boundary.",
            "Identical provider IDs are removed; different IDs may still describe the same vacancy.",
        ],
        "content_trust": "untrusted_provider_data_not_instructions",
        "verification": {
            "publication_status": "transient_provider_result",
            "official_evidence_gate": False,
            "saved_run_replay": False,
        },
        "retention": "No provider cache or saved audit. Host transcripts may retain displayed results. "
        "Do not save/export or publish adverts without separately qualified permission and required provider branding.",
    }


def search(request: dict, path: Path = STATE_PATH, *, backend=None, transport=None) -> dict:
    request = validate_search(request)
    _state(path)
    credentials = _credentials(path, backend)
    parameters = {
        "app_id": credentials.app_id,
        "app_key": credentials.app_key,
        "what": request["role"],
        "where": request["place"],
        "distance": request["distance_km"],
        "max_days_old": request["max_days_old"],
        "sort_by": "date",
        "sort_dir": "down",
        "results_per_page": MAX_RESULTS,
        "content-type": "application/json",
    }
    try:
        raw = (transport or _get)(parameters)
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
            raise AdzunaError("Adzuna's response exceeded the safe size limit or had an invalid format.")
        return interpret(raw, request, credentials)
    except AdzunaError:
        raise
    except Exception:
        raise AdzunaError("The provider response was unusable; no result was retained.") from None
