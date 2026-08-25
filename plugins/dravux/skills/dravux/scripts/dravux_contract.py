#!/usr/bin/env python3
"""Validate Dravux reports with Python's standard library."""

import argparse
from collections import Counter
import datetime
import json
import math
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Collection, Dict, List


AUTOMATED_RESULTS = {"PASS", "FAIL", "ERROR"}
CONTRACT_VERSION = "0.2.0"
FINAL_STATUSES = {"VERIFIED PASS", "VERIFIED FAIL", "INCOMPLETE", "NOT APPLICABLE"}
INPUT_TYPES = {
    "WEBSITE",
    "SOURCE_CODE",
    "MARKDOWN",
    "STRUCTURED_CONTENT",
    "SVG",
    "IMAGE_METADATA",
    "PDF",
    "SCREENSHOT",
    "GITHUB_ARTIFACT",
    "UNSUPPORTED",
}
CLASSIFICATIONS = {"NORMATIVE", "ADVISORY"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}
FINDING_STATUSES = {"OPEN", "REPAIRED", "VERIFIED"}
EVIDENCE_TYPES = {
    "DOM",
    "SOURCE",
    "SCREENSHOT",
    "TOOL_OUTPUT",
    "COMMAND_OUTPUT",
    "MANUAL_OBSERVATION",
    "DOCUMENT_STRUCTURE",
}

MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JSON_CONTAINER_ITEMS = 10_000
MAX_JSON_AGGREGATE_ITEMS = 100_000
MAX_JSON_STRING_CHARACTERS = 256 * 1024
MAX_JSON_NUMBER_CHARACTERS = 128
MAX_JSON_STRUCTURAL_TOKENS = 300_000

# references/manual-checks.md names manual-check categories in prose only; it defines
# no machine-readable baseline token set. The two shipped VERIFIED PASS fixtures declare
# disjoint tokens ({"keyboard", "screen-reader"} for source code, {"content-purpose"} for
# markdown), so no non-empty token baseline holds for both. The baseline is therefore a
# minimum count of declared manual checks: automation alone can never earn VERIFIED PASS.
MINIMUM_BASELINE_MANUAL_CHECKS = 1

REPORT_REQUIRED = {
    "contract_version",
    "audit_id",
    "target",
    "scope",
    "automated_result",
    "final_status",
    "findings",
    "errors",
    "evidence_log",
    "run",
}
FINDING_REQUIRED = {
    "finding_id",
    "target_and_state",
    "input_type",
    "standard",
    "classification",
    "severity",
    "title",
    "evidence",
    "reproduction_steps",
    "user_impact",
    "recommended_repair",
    "verification_steps",
    "confidence",
    "manual_review_required",
    "source",
    "status",
}

REPORT_ALLOWED = REPORT_REQUIRED | {"$schema"}
TARGET_KEYS = {"name", "state", "location", "input_type"}
SCOPE_KEYS = {"included", "excluded", "required_manual_checks", "manual_checks_completed", "applicability_reason"}
STANDARD_KEYS = {"name", "version", "success_criterion", "url"}
SOURCE_KEYS = {"title", "url"}
EVIDENCE_REQUIRED = {"type", "description", "locator"}
EVIDENCE_ALLOWED = EVIDENCE_REQUIRED | {"manual_check_id"}
ERROR_KEYS = {"code", "message", "stage"}
RUN_KEYS = {"started_at", "completed_at", "tooling", "environment"}

SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ID_PATTERN = re.compile(r"^DRV-[A-Z0-9][A-Z0-9._-]*$")
DATE_TIME_PATTERN = re.compile(
    r"^(?P<base>[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?(?P<zone>[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)
SUPPORTED_WCAG_22_CRITERIA = {
    "1.1.1 Non-text Content": "non-text-content",
    "1.2.2 Captions (Prerecorded)": "captions-prerecorded",
    "1.3.1 Info and Relationships": "info-and-relationships",
    "1.4.1 Use of Color": "use-of-color",
    "1.4.3 Contrast (Minimum)": "contrast-minimum",
    "1.4.10 Reflow": "reflow",
    "1.4.11 Non-text Contrast": "non-text-contrast",
    "1.4.13 Content on Hover or Focus": "content-on-hover-or-focus",
    "2.1.1 Keyboard": "keyboard",
    "2.1.2 No Keyboard Trap": "no-keyboard-trap",
    "2.4.3 Focus Order": "focus-order",
    "2.4.7 Focus Visible": "focus-visible",
    "2.4.11 Focus Not Obscured (Minimum)": "focus-not-obscured-minimum",
    "2.5.8 Target Size (Minimum)": "target-size-minimum",
    "3.1.1 Language of Page": "language-of-page",
    "3.2.1 On Focus": "on-focus",
    "3.2.2 On Input": "on-input",
    "3.3.1 Error Identification": "error-identification",
    "3.3.2 Labels or Instructions": "labels-or-instructions",
    "4.1.2 Name, Role, Value": "name-role-value",
}
WCAG_NAME = "Web Content Accessibility Guidelines"
WCAG_VERSION = "2.2"
URL_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]+$")


def _quoted(value: Any) -> str:
    """Render untrusted text as a single-line ASCII JSON literal for a diagnostic.

    Error messages quote attacker-authored key names and list items. Escaping every control
    character and non-ASCII codepoint keeps a hostile value from forging an extra line in the
    validator's own output or reordering the line it sits on.
    """
    return json.dumps(str(value))


def _reject_unknown(obj: Any, allowed: set, label: str, errors: List[str]) -> None:
    if not isinstance(obj, dict):
        return
    unknown = sorted(set(obj) - allowed)
    if unknown:
        errors.append(f"{label} contains unknown properties: {', '.join(_quoted(key) for key in unknown)}")


def _parse_rfc3339_datetime(value: Any):
    if not isinstance(value, str):
        return None
    match = DATE_TIME_PATTERN.match(value)
    if not match:
        return None
    fraction = match.group("fraction")
    normalized_fraction = f".{fraction[:6].ljust(6, '0')}" if fraction else ""
    zone = "+00:00" if match.group("zone") in "Zz" else match.group("zone")
    candidate = f"{match.group('base')}{normalized_fraction}{zone}"
    try:
        return datetime.datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _is_rfc3339_datetime(value: Any) -> bool:
    return _parse_rfc3339_datetime(value) is not None


def _is_absolute_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip() or any(ch.isspace() for ch in value):
        return False
    try:
        parsed = urllib.parse.urlparse(value)
        _ = parsed.hostname
        _ = parsed.port
    except ValueError:
        return False
    return (
        value.startswith(("http://", "https://"))
        and parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and bool(parsed.hostname)
        and bool(URL_HOST_PATTERN.fullmatch(parsed.hostname or ""))
        and parsed.username is None
        and parsed.password is None
    )


def _is_wcag_22_criterion_url(value: Any) -> bool:
    if not _is_absolute_url(value):
        return False
    parsed = urllib.parse.urlparse(value)
    return (
        value.startswith("https://")
        and parsed.scheme == "https"
        and parsed.netloc == "www.w3.org"
        and parsed.port is None
        and parsed.path == "/TR/WCAG22/"
        and not parsed.query
        and bool(parsed.fragment)
    )


def _is_w3c_url(value: Any) -> bool:
    if not _is_absolute_url(value):
        return False
    parsed = urllib.parse.urlparse(value)
    return (
        value.startswith("https://")
        and parsed.scheme == "https"
        and parsed.port is None
        and bool(parsed.path)
        and (parsed.netloc == "w3.org" or parsed.netloc.endswith(".w3.org"))
    )


def _string_set(value: Any) -> set:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _reject_duplicates(value: Any, label: str, errors: List[str]) -> None:
    if not isinstance(value, list):
        return
    strings = [item for item in value if isinstance(item, str)]
    duplicates = sorted(item for item, count in Counter(strings).items() if count > 1)
    if duplicates:
        errors.append(f"{label} contains duplicate entries: {', '.join(_quoted(item) for item in duplicates)}")


# Codepoints outside the C0 range that still break a rendered receipt into
# extra lines under str.splitlines(): DEL, NEL, LINE SEPARATOR, PARAGRAPH SEPARATOR.
_FORBIDDEN_CODEPOINTS = frozenset({0x7F, 0x85, 0x2028, 0x2029})


def _is_nonempty_string(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    return not any(ord(ch) < 0x20 or ord(ch) in _FORBIDDEN_CODEPOINTS for ch in value)


def _is_string_member(value: Any, allowed: Collection[str]) -> bool:
    return isinstance(value, str) and value in allowed


def _require_keys(obj: Any, required: set, label: str, errors: List[str]) -> None:
    if not isinstance(obj, dict):
        errors.append(f"{label} must be an object")
        return
    missing = sorted(required - set(obj))
    if missing:
        errors.append(f"{label} missing required fields: {', '.join(missing)}")


def _validate_string_list(value: Any, label: str, errors: List[str], minimum: int = 0) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    if len(value) < minimum:
        errors.append(f"{label} must contain at least {minimum} item(s)")
    for index, item in enumerate(value):
        if not _is_nonempty_string(item):
            errors.append(f"{label}[{index}] must be a non-empty string")


def _validate_evidence(value: Any, label: str, errors: List[str], minimum: int = 1) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    if len(value) < minimum:
        errors.append(f"{label} must contain at least {minimum} item(s)")
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        _require_keys(item, EVIDENCE_REQUIRED, item_label, errors)
        _reject_unknown(item, EVIDENCE_ALLOWED, item_label, errors)
        if not isinstance(item, dict):
            continue
        if not _is_string_member(item.get("type"), EVIDENCE_TYPES):
            errors.append(f"{item_label}.type is invalid")
        for key in ("description", "locator"):
            if not _is_nonempty_string(item.get(key)):
                errors.append(f"{item_label}.{key} must be a non-empty string")
        if item.get("type") == "MANUAL_OBSERVATION":
            if not _is_nonempty_string(item.get("manual_check_id")):
                errors.append(f"{item_label}.manual_check_id is required for MANUAL_OBSERVATION evidence")
        elif "manual_check_id" in item:
            errors.append(f"{item_label}.manual_check_id is allowed only for MANUAL_OBSERVATION evidence")


def _validate_finding(finding: Any, index: int, errors: List[str]) -> None:
    label = f"findings[{index}]"
    _require_keys(finding, FINDING_REQUIRED, label, errors)
    _reject_unknown(finding, FINDING_REQUIRED, label, errors)
    if not isinstance(finding, dict):
        return
    for key in ("finding_id", "target_and_state", "title", "user_impact", "recommended_repair"):
        if not _is_nonempty_string(finding.get(key)):
            errors.append(f"{label}.{key} must be a non-empty string")
    if _is_nonempty_string(finding.get("finding_id")) and not ID_PATTERN.match(finding["finding_id"]):
        errors.append(f"{label}.finding_id must match the DRV- uppercase ID pattern")
    if not _is_string_member(finding.get("input_type"), INPUT_TYPES):
        errors.append(f"{label}.input_type is invalid")
    if not _is_string_member(finding.get("classification"), CLASSIFICATIONS):
        errors.append(f"{label}.classification is invalid")
    if not _is_string_member(finding.get("severity"), SEVERITIES):
        errors.append(f"{label}.severity is invalid")
    if not _is_string_member(finding.get("confidence"), CONFIDENCE):
        errors.append(f"{label}.confidence is invalid")
    if not _is_string_member(finding.get("status"), FINDING_STATUSES):
        errors.append(f"{label}.status is invalid")
    if not isinstance(finding.get("manual_review_required"), bool):
        errors.append(f"{label}.manual_review_required must be boolean")

    standard = finding.get("standard")
    if finding.get("classification") == "NORMATIVE" and not isinstance(standard, dict):
        errors.append(f"{label}.standard is required for normative findings")
    if standard is not None:
        _require_keys(standard, STANDARD_KEYS, f"{label}.standard", errors)
        _reject_unknown(standard, STANDARD_KEYS, f"{label}.standard", errors)
        if isinstance(standard, dict):
            for key in ("name", "version", "success_criterion", "url"):
                if not _is_nonempty_string(standard.get(key)):
                    errors.append(f"{label}.standard.{key} must be a non-empty string")
            if _is_nonempty_string(standard.get("url")) and not _is_absolute_url(standard.get("url")):
                errors.append(f"{label}.standard.url must be an absolute HTTP(S) URL")
            if finding.get("classification") == "NORMATIVE":
                if standard.get("name") != WCAG_NAME:
                    errors.append(f"{label}.standard.name must identify WCAG for normative findings")
                if standard.get("version") != WCAG_VERSION:
                    errors.append(f"{label}.standard.version must be 2.2 for normative findings")
                criterion = standard.get("success_criterion")
                criterion_supported = _is_string_member(criterion, SUPPORTED_WCAG_22_CRITERIA)
                if not criterion_supported:
                    errors.append(f"{label}.standard.success_criterion must use a supported WCAG 2.2 criterion")
                standard_url = standard.get("url")
                if _is_nonempty_string(standard_url):
                    if not _is_wcag_22_criterion_url(standard_url):
                        errors.append(f"{label}.standard.url must be a W3C WCAG 2.2 criterion URL")
                    elif criterion_supported:
                        expected_fragment = SUPPORTED_WCAG_22_CRITERIA[criterion]
                        actual_fragment = urllib.parse.urlparse(standard_url).fragment
                        if actual_fragment != expected_fragment:
                            errors.append(f"{label}.standard.url fragment must match the declared WCAG criterion")

    source = finding.get("source")
    _require_keys(source, SOURCE_KEYS, f"{label}.source", errors)
    _reject_unknown(source, SOURCE_KEYS, f"{label}.source", errors)
    if isinstance(source, dict):
        for key in ("title", "url"):
            if not _is_nonempty_string(source.get(key)):
                errors.append(f"{label}.source.{key} must be a non-empty string")
        if _is_nonempty_string(source.get("url")) and not _is_absolute_url(source.get("url")):
            errors.append(f"{label}.source.url must be an absolute HTTP(S) URL")
        if (
            finding.get("classification") == "NORMATIVE"
            and _is_nonempty_string(source.get("url"))
            and not _is_w3c_url(source.get("url"))
        ):
            errors.append(f"{label}.source.url must use an authoritative W3C source for normative findings")

    _validate_evidence(finding.get("evidence"), f"{label}.evidence", errors)
    _validate_string_list(finding.get("reproduction_steps"), f"{label}.reproduction_steps", errors, 1)
    _validate_string_list(finding.get("verification_steps"), f"{label}.verification_steps", errors, 1)


def validate_report(report: Any) -> List[str]:
    """Return all contract violations. An empty list means valid."""
    errors: List[str] = []
    _require_keys(report, REPORT_REQUIRED, "report", errors)
    if not isinstance(report, dict):
        return errors
    _reject_unknown(report, REPORT_ALLOWED, "report", errors)
    if "$schema" in report and not _is_nonempty_string(report.get("$schema")):
        errors.append("report.$schema must be a non-empty string when present")

    for key in ("contract_version", "audit_id"):
        if not _is_nonempty_string(report.get(key)):
            errors.append(f"report.{key} must be a non-empty string")
    if _is_nonempty_string(report.get("contract_version")):
        if not SEMVER_PATTERN.match(report["contract_version"]):
            errors.append("report.contract_version must be a semantic version (MAJOR.MINOR.PATCH)")
        elif report["contract_version"] != CONTRACT_VERSION:
            errors.append(f"report.contract_version must be the supported version {CONTRACT_VERSION}")
    if _is_nonempty_string(report.get("audit_id")) and not ID_PATTERN.match(report["audit_id"]):
        errors.append("report.audit_id must match the DRV- uppercase ID pattern")

    target = report.get("target")
    _require_keys(target, TARGET_KEYS, "target", errors)
    _reject_unknown(target, TARGET_KEYS, "target", errors)
    if isinstance(target, dict):
        for key in ("name", "state", "location"):
            if not _is_nonempty_string(target.get(key)):
                errors.append(f"target.{key} must be a non-empty string")
        if not _is_string_member(target.get("input_type"), INPUT_TYPES):
            errors.append("target.input_type is invalid")

    scope = report.get("scope")
    _require_keys(
        scope,
        {"included", "excluded", "required_manual_checks", "manual_checks_completed", "applicability_reason"},
        "scope",
        errors,
    )
    _reject_unknown(scope, SCOPE_KEYS, "scope", errors)
    if isinstance(scope, dict):
        _validate_string_list(scope.get("included"), "scope.included", errors, 1)
        _validate_string_list(scope.get("excluded"), "scope.excluded", errors)
        _validate_string_list(scope.get("required_manual_checks"), "scope.required_manual_checks", errors)
        _validate_string_list(scope.get("manual_checks_completed"), "scope.manual_checks_completed", errors)
        _reject_duplicates(scope.get("required_manual_checks"), "scope.required_manual_checks", errors)
        _reject_duplicates(scope.get("manual_checks_completed"), "scope.manual_checks_completed", errors)
        reason = scope.get("applicability_reason")
        if reason is not None and not _is_nonempty_string(reason):
            errors.append("scope.applicability_reason must be null or a non-empty string without control characters")
        required = scope.get("required_manual_checks")
        completed = scope.get("manual_checks_completed")
        if isinstance(required, list) and isinstance(completed, list):
            unknown = sorted(_string_set(completed) - _string_set(required))
            if unknown:
                errors.append(
                    "scope.manual_checks_completed includes undeclared checks: "
                    + ", ".join(_quoted(item) for item in unknown)
                )

    automated = report.get("automated_result")
    final = report.get("final_status")
    if not _is_string_member(automated, AUTOMATED_RESULTS):
        errors.append("report.automated_result is invalid")
    if not _is_string_member(final, FINAL_STATUSES):
        errors.append("report.final_status is invalid")

    findings = report.get("findings")
    if not isinstance(findings, list):
        errors.append("report.findings must be an array")
        findings = []
    for index, finding in enumerate(findings):
        _validate_finding(finding, index, errors)

    ids = [f.get("finding_id") for f in findings if isinstance(f, dict) and _is_nonempty_string(f.get("finding_id"))]
    duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append(f"finding IDs must be unique: {', '.join(_quoted(item) for item in duplicates)}")

    error_items = report.get("errors")
    if not isinstance(error_items, list):
        errors.append("report.errors must be an array")
        error_items = []
    for index, item in enumerate(error_items):
        label = f"errors[{index}]"
        _require_keys(item, ERROR_KEYS, label, errors)
        _reject_unknown(item, ERROR_KEYS, label, errors)
        if isinstance(item, dict):
            for key in ("code", "message", "stage"):
                if not _is_nonempty_string(item.get(key)):
                    errors.append(f"{label}.{key} must be a non-empty string")

    _validate_evidence(report.get("evidence_log"), "evidence_log", errors)

    manual_observations = [
        item
        for item in (report.get("evidence_log") if isinstance(report.get("evidence_log"), list) else [])
        if isinstance(item, dict) and item.get("type") == "MANUAL_OBSERVATION"
    ] + [
        item
        for finding in findings
        if isinstance(finding, dict) and isinstance(finding.get("evidence"), list)
        for item in finding["evidence"]
        if isinstance(item, dict) and item.get("type") == "MANUAL_OBSERVATION"
    ]
    required_manual = _string_set(scope.get("required_manual_checks")) if isinstance(scope, dict) else set()
    completed_manual = _string_set(scope.get("manual_checks_completed")) if isinstance(scope, dict) else set()
    bound_manual = {
        item.get("manual_check_id")
        for item in manual_observations
        if _is_nonempty_string(item.get("manual_check_id"))
    }
    for manual_id in sorted(bound_manual):
        if manual_id not in required_manual:
            errors.append(f"MANUAL_OBSERVATION manual_check_id is not declared: {_quoted(manual_id)}")
        if manual_id not in completed_manual:
            errors.append(f"MANUAL_OBSERVATION manual_check_id is not completed: {_quoted(manual_id)}")
    unbound_completed = sorted(completed_manual - bound_manual)
    if unbound_completed:
        errors.append(
            "each completed manual check requires matching MANUAL_OBSERVATION evidence: "
            + ", ".join(_quoted(item) for item in unbound_completed)
        )

    run = report.get("run")
    _require_keys(run, RUN_KEYS, "run", errors)
    _reject_unknown(run, RUN_KEYS, "run", errors)
    if isinstance(run, dict):
        for key in ("started_at", "completed_at", "environment"):
            if not _is_nonempty_string(run.get(key)):
                errors.append(f"run.{key} must be a non-empty string")
        for key in ("started_at", "completed_at"):
            if _is_nonempty_string(run.get(key)) and not _is_rfc3339_datetime(run[key]):
                errors.append(f"run.{key} must be an RFC 3339 date-time with timezone")
        started = _parse_rfc3339_datetime(run.get("started_at"))
        completed = _parse_rfc3339_datetime(run.get("completed_at"))
        if started is not None and completed is not None and completed < started:
            errors.append("run.completed_at must not be earlier than run.started_at")
        _validate_string_list(run.get("tooling"), "run.tooling", errors, 1)

    normative = [f for f in findings if isinstance(f, dict) and f.get("classification") == "NORMATIVE"]
    if automated == "FAIL" and not normative:
        errors.append("automated FAIL requires at least one normative finding")
    if automated == "PASS" and normative and final != "VERIFIED FAIL":
        errors.append(
            "automated PASS cannot contain normative findings unless final status is "
            "VERIFIED FAIL backed by completed manual evidence"
        )
    if automated == "FAIL" and not _is_string_member(final, {"VERIFIED FAIL", "INCOMPLETE"}):
        errors.append("automated FAIL can only map to VERIFIED FAIL or INCOMPLETE")
    if automated == "ERROR" and not error_items:
        errors.append("automated ERROR requires at least one structured error")
    if automated == "PASS" and error_items:
        errors.append("automated PASS cannot contain structured errors")
    if automated == "ERROR" and not _is_string_member(final, {"VERIFIED FAIL", "INCOMPLETE", "NOT APPLICABLE"}):
        errors.append("automated ERROR can only map to VERIFIED FAIL, INCOMPLETE, or NOT APPLICABLE")
    if isinstance(target, dict) and target.get("input_type") == "UNSUPPORTED":
        if automated != "ERROR":
            errors.append("UNSUPPORTED input requires automated ERROR")
        if final != "INCOMPLETE":
            errors.append("UNSUPPORTED input can only end INCOMPLETE")
    if final == "VERIFIED FAIL" and not normative:
        errors.append("VERIFIED FAIL requires reproducible normative evidence")
    if final == "VERIFIED FAIL" and not any(finding.get("status") == "OPEN" for finding in normative):
        errors.append("VERIFIED FAIL requires at least one OPEN normative finding")
    if final == "VERIFIED FAIL" and _is_string_member(automated, {"PASS", "ERROR"}):
        completed_checks = _string_set(scope.get("manual_checks_completed")) if isinstance(scope, dict) else set()
        manual_normative = [
            finding
            for finding in normative
            if finding.get("manual_review_required") is True
            and any(
                isinstance(item, dict) and item.get("type") == "MANUAL_OBSERVATION"
                for item in (finding.get("evidence") if isinstance(finding.get("evidence"), list) else [])
            )
        ]
        if not completed_checks or not manual_normative:
            errors.append(
                "VERIFIED FAIL after automated PASS or ERROR requires a completed manual check "
                "and normative MANUAL_OBSERVATION evidence"
            )
    if final == "VERIFIED PASS":
        if automated != "PASS":
            errors.append("VERIFIED PASS requires automated PASS")
        if error_items:
            errors.append("VERIFIED PASS cannot contain errors")
        if findings:
            errors.append("VERIFIED PASS cannot contain findings; preserve resolved history in a separate before report")
        if isinstance(scope, dict):
            required = _string_set(scope.get("required_manual_checks"))
            completed = _string_set(scope.get("manual_checks_completed"))
            pending = sorted(required - completed)
            if pending:
                errors.append(
                    "VERIFIED PASS requires completed manual checks: " + ", ".join(_quoted(item) for item in pending)
                )
            if len(required) < MINIMUM_BASELINE_MANUAL_CHECKS:
                errors.append(
                    "VERIFIED PASS requires at least "
                    f"{MINIMUM_BASELINE_MANUAL_CHECKS} declared manual check(s) in "
                    "scope.required_manual_checks; automation alone cannot verify a pass"
                )
    if final == "NOT APPLICABLE":
        reason = scope.get("applicability_reason") if isinstance(scope, dict) else None
        if not _is_nonempty_string(reason):
            errors.append("NOT APPLICABLE requires scope.applicability_reason")
        if automated != "ERROR":
            errors.append("NOT APPLICABLE requires automated ERROR")
        if not error_items or any(item.get("code") != "NOT_APPLICABLE" for item in error_items if isinstance(item, dict)):
            errors.append("NOT APPLICABLE requires only structured NOT_APPLICABLE errors")
        if findings:
            errors.append("NOT APPLICABLE cannot contain findings")
    return errors


def _reject_duplicate_keys(pairs: List[Any]) -> Dict[str, Any]:
    """Build an object from JSON key/value pairs, rejecting any repeated key.

    Repeated keys let a report display one verdict to a human reader while the last
    occurrence silently decides the parsed value.
    """
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {_quoted(key)}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise ValueError(f"invalid JSON constant: {value}")


def _parse_json_integer(token: str) -> int:
    if len(token) > MAX_JSON_NUMBER_CHARACTERS:
        raise ValueError(
            f"JSON number exceeds the {MAX_JSON_NUMBER_CHARACTERS}-character limit"
        )
    return int(token)


def _parse_json_float(token: str) -> float:
    if len(token) > MAX_JSON_NUMBER_CHARACTERS:
        raise ValueError(
            f"JSON number exceeds the {MAX_JSON_NUMBER_CHARACTERS}-character limit"
        )
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("JSON number must be finite")
    return value


def _enforce_json_lexical_limits(text: str) -> None:
    """Bound nesting and structural work before the standard parser allocates objects."""
    depth = 0
    structural_tokens = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character in "{}[],:":
            structural_tokens += 1
            if structural_tokens > MAX_JSON_STRUCTURAL_TOKENS:
                raise ValueError(
                    "JSON input exceeds the "
                    f"{MAX_JSON_STRUCTURAL_TOKENS}-structural-token limit"
                )
        if character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError(f"JSON input exceeds the depth limit of {MAX_JSON_DEPTH}")
        elif character in "]}":
            depth -= 1


def _enforce_json_value_limits(value: Any) -> None:
    """Validate decoded values iteratively so hostile nesting cannot recurse here."""
    aggregate_items = 0
    stack = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"JSON input exceeds the depth limit of {MAX_JSON_DEPTH}")
        if isinstance(current, str):
            if len(current) > MAX_JSON_STRING_CHARACTERS:
                raise ValueError(
                    "JSON string exceeds the "
                    f"{MAX_JSON_STRING_CHARACTERS}-character limit"
                )
            continue
        if isinstance(current, dict):
            size = len(current)
            if size > MAX_JSON_CONTAINER_ITEMS:
                raise ValueError(
                    f"JSON object exceeds the {MAX_JSON_CONTAINER_ITEMS}-item limit"
                )
            aggregate_items += size
            if aggregate_items > MAX_JSON_AGGREGATE_ITEMS:
                raise ValueError(
                    "JSON input exceeds the "
                    f"{MAX_JSON_AGGREGATE_ITEMS}-aggregate-item limit"
                )
            for key, item in current.items():
                if len(key) > MAX_JSON_STRING_CHARACTERS:
                    raise ValueError(
                        "JSON object key exceeds the "
                        f"{MAX_JSON_STRING_CHARACTERS}-character limit"
                    )
                stack.append((item, depth + 1))
            continue
        if isinstance(current, list):
            size = len(current)
            if size > MAX_JSON_CONTAINER_ITEMS:
                raise ValueError(
                    f"JSON array exceeds the {MAX_JSON_CONTAINER_ITEMS}-item limit"
                )
            aggregate_items += size
            if aggregate_items > MAX_JSON_AGGREGATE_ITEMS:
                raise ValueError(
                    "JSON input exceeds the "
                    f"{MAX_JSON_AGGREGATE_ITEMS}-aggregate-item limit"
                )
            stack.extend((item, depth + 1) for item in current)


def _read_json_bytes(handle: Any) -> bytes:
    payload = handle.read(MAX_JSON_BYTES + 1)
    if isinstance(payload, str):
        payload = payload.encode("utf-8", "strict")
    if not isinstance(payload, bytes):
        raise ValueError("JSON input stream did not return bytes")
    if len(payload) > MAX_JSON_BYTES:
        raise ValueError(f"JSON input exceeds the {MAX_JSON_BYTES}-byte limit")
    return payload


def strict_json_load(handle: Any) -> Any:
    """Parse JSON from an open handle under the single strict ingress policy.

    Rejects duplicate object keys and the non-standard NaN/Infinity constants.
    Every external JSON ingress point must route through this function so one
    entry point cannot be more permissive than another.
    """
    payload = _read_json_bytes(handle)
    text = payload.decode("utf-8", "strict")
    _enforce_json_lexical_limits(text)
    value = json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_int=_parse_json_integer,
        parse_float=_parse_json_float,
        parse_constant=_reject_json_constant,
    )
    _enforce_json_value_limits(value)
    return value


def load_json_path(path: Path) -> Any:
    """Strictly load JSON from a filesystem path, or from stdin when path is '-'."""
    if str(path) == "-":
        return strict_json_load(getattr(sys.stdin, "buffer", sys.stdin))
    with path.open("rb") as handle:
        return strict_json_load(handle)


def load_report(path: Path) -> Dict[str, Any]:
    return load_json_path(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a Dravux report contract.")
    parser.add_argument("report", type=Path, help="Path to a Dravux report JSON file, or - to read JSON from stdin")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit a machine-readable validation summary")
    return parser


def main(argv: List[str] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = load_report(args.report)
    except (OSError, ValueError, RecursionError) as exc:
        if args.json_output:
            print(json.dumps({"valid": False, "exit_code": 2, "errors": [str(exc)]}, indent=2))
        else:
            print(f"ERROR: could not load report: {exc}", file=sys.stderr)
        return 2

    try:
        violations = validate_report(report)
    except (AttributeError, RecursionError, TypeError, ValueError) as exc:
        violations = [f"validator safely rejected hostile structure: {type(exc).__name__}: {exc}"]
    report_fields = report if isinstance(report, dict) else {}
    if args.json_output:
        print(
            json.dumps(
                {
                    "valid": not violations,
                    "audit_id": report_fields.get("audit_id"),
                    "automated_result": report_fields.get("automated_result"),
                    "final_status": report_fields.get("final_status"),
                    "errors": violations,
                },
                indent=2,
            )
        )
    elif violations:
        print("INVALID Dravux report:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
    else:
        print(
            f"VALID Dravux report: {report.get('audit_id')} | "
            f"{report.get('automated_result')} | {report.get('final_status')}"
        )
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
