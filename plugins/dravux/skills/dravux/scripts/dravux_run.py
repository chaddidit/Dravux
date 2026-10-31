#!/usr/bin/env python3
"""Preflight a surface, validate a complete Dravux operational run, and place its output."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Importing the sibling contract module would otherwise leave a __pycache__ directory inside an
# installed skill tree, and that tree must stay exactly as the release manifest recorded it.
sys.dont_write_bytecode = True

from dravux_contract import (  # noqa: E402
    INPUT_TYPES,
    _is_absolute_url,
    _is_nonempty_string,
    _is_rfc3339_datetime,
    load_json_path,
    validate_report,
)


PACKAGE_VERSION = "1.0.2"
PREFLIGHT_VERSION = "1.0.0"
RUN_CONTRACT_VERSION = "1.1.0"

REQUEST_MODES = (
    "CONTRACT_ONLY",
    "FILE_STATIC",
    "SOURCE_TEXT",
    "RAW_SOURCE",
    "RENDERED_BROWSER",
    "RENDERED_DOM",
    "INTERACTIVE",
)
ACQUISITION_LEVELS = (
    "NONE",
    "FILES_ONLY",
    "CONVERTED_TEXT",
    "RAW_SOURCE",
    "RENDERED_BROWSER",
    "RENDERED_DOM",
    "INTERACTIVE_BROWSER",
)
ACQUISITION_TO_MODE = {
    "NONE": "CONTRACT_ONLY",
    "FILES_ONLY": "FILE_STATIC",
    "CONVERTED_TEXT": "SOURCE_TEXT",
    "RAW_SOURCE": "RAW_SOURCE",
    "RENDERED_BROWSER": "RENDERED_BROWSER",
    "RENDERED_DOM": "RENDERED_DOM",
    "INTERACTIVE_BROWSER": "INTERACTIVE",
}
ACQUISITION_METHODS = set(ACQUISITION_LEVELS)
MODE_RANK = {name: index for index, name in enumerate(REQUEST_MODES)}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

FAILURE_STAGES = (
    "ACQUISITION",
    "INTERACTION",
    "AUDIT_EXECUTION",
    "EVIDENCE_CAPTURE",
    "REPORT_ASSEMBLY",
    "TOOLING",
)
VERIFIED_PASS_STATUSES = {"VERIFIED PASS", "VERIFIED_PASS"}

GUARD_MARKERS = ("SKILL.md", "RELEASE_MANIFEST.json")
OUTPUT_DIR_NAME = "dravux-audits"
AUDIT_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,64}$")
OUTPUT_DIR_INPUT_EXIT = 2
OUTPUT_DIR_REFUSED_EXIT = 5

PREFLIGHT_REQUIRED = {
    "preflight_version",
    "package_version",
    "surface",
    "target",
    "requested_mode",
    "capabilities",
    "selected_mode",
    "limitation_acknowledged",
    "required_manual_checks",
    "next_action",
}
PREFLIGHT_ALLOWED = PREFLIGHT_REQUIRED | {"$schema"}
SURFACE_KEYS = {"provider", "product", "mode"}
TARGET_KEYS = {"input_type", "location"}
CAPABILITY_KEYS = {
    "code_execution",
    "bundled_files",
    "validator_execution",
    "acquisition",
    "screenshots",
    "manual_evidence",
}
RUN_REQUIRED = {
    "run_contract_version",
    "package_version",
    "preflight",
    "acquisition",
    "execution",
    "report",
}
RUN_ALLOWED = RUN_REQUIRED | {"$schema"}
EXECUTION_KEYS = {"completed", "failure_stage", "error"}
ACQUISITION_KEYS = {
    "attempted",
    "succeeded",
    "method",
    "requested_location",
    "final_location",
    "redirect_chain",
    "response_status",
    "acquired_at",
    "tool",
    "content_sha256",
    "error",
}

WEBSITE_MANUAL_CHECKS = {
    "keyboard",
    "screen-reader",
    "zoom-reflow",
    "color-contrast-rendered",
    "focus-order",
}

MODE_CLAIMS = {
    "CONTRACT_ONLY": (
        ["Report contract validation only."],
        ["No accessibility claim is established by contract validation alone."],
    ),
    "FILE_STATIC": (
        ["Static artifact structure supported by the declared parser."],
        ["Rendered behavior, interaction, computed styles, and assistive-technology output."],
    ),
    "SOURCE_TEXT": (
        ["Retrieved text observations and advisory hypotheses only."],
        [
            "Raw HTML and DOM attributes.",
            "Rendered layout, computed styles, and color contrast.",
            "Keyboard, focus, interaction, and assistive-technology behavior.",
        ],
    ),
    "RAW_SOURCE": (
        ["Static source and markup observations supported by exact source evidence."],
        ["Rendered state, computed styles, interaction, and assistive-technology behavior."],
    ),
    "RENDERED_BROWSER": (
        ["Rendered visual-state and screenshot observations supported by recorded evidence."],
        ["Unrecorded DOM semantics, computed accessibility names, and manual user behavior."],
    ),
    "RENDERED_DOM": (
        ["Rendered DOM, accessibility-tree, and computed-style checks supported by recorded tooling evidence."],
        ["Human keyboard, screen-reader, zoom/reflow, cognition, meaning, and task-completion claims."],
    ),
    "INTERACTIVE": (
        ["Scripted interaction and rendered DOM checks supported by recorded tooling evidence."],
        ["Human assistive-technology usability, cognition, meaning, and complete conformance claims."],
    ),
}


def _reject_unknown(value: Any, allowed: set, label: str, errors: List[str]) -> None:
    if isinstance(value, dict):
        unknown = sorted(set(value) - allowed)
        if unknown:
            errors.append(f"{label} contains unknown properties: {', '.join(unknown)}")


def _require_object(value: Any, required: set, allowed: set, label: str, errors: List[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    missing = sorted(required - set(value))
    if missing:
        errors.append(f"{label} missing required fields: {', '.join(missing)}")
    _reject_unknown(value, allowed, label, errors)


def _validate_string_list(value: Any, label: str, errors: List[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    seen = set()
    for index, item in enumerate(value):
        if not _is_nonempty_string(item):
            errors.append(f"{label}[{index}] must be a non-empty string")
        elif item in seen:
            errors.append(f"{label} contains duplicate entry: {item}")
        else:
            seen.add(item)


def _bundle_self_test() -> Tuple[bool, str]:
    skill_root = Path(__file__).resolve().parents[1]
    required = (
        skill_root / "assets" / "report-template.json",
        skill_root / "schemas" / "dravux-report.schema.json",
        skill_root / "schemas" / "finding.schema.json",
    )
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        return False, f"missing bundled file(s): {', '.join(sorted(missing))}"
    try:
        report = json.loads(required[0].read_text(encoding="utf-8"))
        violations = validate_report(report)
    except (OSError, ValueError, RecursionError, TypeError) as exc:
        return False, f"bundled self-test failed safely: {type(exc).__name__}: {exc}"
    if violations:
        return False, "; ".join(violations)
    return True, "bundled report validator accepted its canonical template"


def validate_preflight(profile: Any) -> List[str]:
    errors: List[str] = []
    _require_object(profile, PREFLIGHT_REQUIRED, PREFLIGHT_ALLOWED, "preflight", errors)
    if not isinstance(profile, dict):
        return errors

    if profile.get("preflight_version") != PREFLIGHT_VERSION:
        errors.append(f"preflight.preflight_version must be {PREFLIGHT_VERSION}")
    if profile.get("package_version") != PACKAGE_VERSION:
        errors.append(f"preflight.package_version must be {PACKAGE_VERSION}")

    surface = profile.get("surface")
    _require_object(surface, SURFACE_KEYS, SURFACE_KEYS, "preflight.surface", errors)
    if isinstance(surface, dict):
        for key in SURFACE_KEYS:
            if not _is_nonempty_string(surface.get(key)):
                errors.append(f"preflight.surface.{key} must be a non-empty string")

    target = profile.get("target")
    _require_object(target, TARGET_KEYS, TARGET_KEYS, "preflight.target", errors)
    if isinstance(target, dict):
        if target.get("input_type") not in INPUT_TYPES:
            errors.append("preflight.target.input_type is invalid")
        if not _is_nonempty_string(target.get("location")):
            errors.append("preflight.target.location must be a non-empty string")
        if target.get("input_type") == "WEBSITE" and not _is_absolute_url(target.get("location")):
            errors.append("preflight.target.location must be an absolute HTTP(S) URL for WEBSITE input")

    capabilities = profile.get("capabilities")
    _require_object(capabilities, CAPABILITY_KEYS, CAPABILITY_KEYS, "preflight.capabilities", errors)
    if isinstance(capabilities, dict):
        for key in ("code_execution", "bundled_files", "screenshots", "manual_evidence"):
            if not isinstance(capabilities.get(key), bool):
                errors.append(f"preflight.capabilities.{key} must be boolean")
        if capabilities.get("validator_execution") not in {"AVAILABLE", "UNAVAILABLE"}:
            errors.append("preflight.capabilities.validator_execution is invalid")
        if capabilities.get("acquisition") not in ACQUISITION_LEVELS:
            errors.append("preflight.capabilities.acquisition is invalid")

    requested = profile.get("requested_mode")
    selected = profile.get("selected_mode")
    if requested not in REQUEST_MODES:
        errors.append("preflight.requested_mode is invalid")
    if selected not in REQUEST_MODES:
        errors.append("preflight.selected_mode is invalid")
    if (
        isinstance(target, dict)
        and target.get("input_type") == "WEBSITE"
        and requested not in {"RENDERED_BROWSER", "RENDERED_DOM", "INTERACTIVE"}
    ):
        errors.append("WEBSITE preflight.requested_mode must require rendered-page evidence")
    if isinstance(capabilities, dict) and capabilities.get("acquisition") in ACQUISITION_TO_MODE:
        maximum = ACQUISITION_TO_MODE[capabilities["acquisition"]]
        if selected in MODE_RANK and MODE_RANK[selected] > MODE_RANK[maximum]:
            errors.append("preflight.selected_mode exceeds the declared acquisition capability")
    if requested in MODE_RANK and selected in MODE_RANK and MODE_RANK[selected] > MODE_RANK[requested]:
        errors.append("preflight.selected_mode exceeds the requested mode")
    if not isinstance(profile.get("limitation_acknowledged"), bool):
        errors.append("preflight.limitation_acknowledged must be boolean")

    checks = profile.get("required_manual_checks")
    _validate_string_list(checks, "preflight.required_manual_checks", errors)
    if isinstance(target, dict) and target.get("input_type") == "WEBSITE" and isinstance(checks, list):
        missing_checks = sorted(WEBSITE_MANUAL_CHECKS - set(item for item in checks if isinstance(item, str)))
        if missing_checks:
            errors.append(f"WEBSITE preflight requires manual checks: {', '.join(missing_checks)}")
    if not _is_nonempty_string(profile.get("next_action")):
        errors.append("preflight.next_action must be a non-empty string")
    return errors


def preflight_decision(profile: Any) -> Dict[str, Any]:
    violations = validate_preflight(profile)
    self_test_passed, self_test_detail = _bundle_self_test()
    if violations:
        return {
            "valid": False,
            "status": "INVALID",
            "exit_code": 1,
            "validator_self_test": "PASS" if self_test_passed else "FAIL",
            "validator_detail": self_test_detail,
            "allowed_claims": [],
            "excluded_claims": [],
            "errors": violations,
        }

    capabilities = profile["capabilities"]
    selected = profile["selected_mode"]
    allowed, excluded = MODE_CLAIMS[selected]
    unavailable = (
        not capabilities["code_execution"]
        or not capabilities["bundled_files"]
        or capabilities["validator_execution"] != "AVAILABLE"
        or not self_test_passed
    )
    if unavailable:
        status = "UNSUPPORTED"
        exit_code = 4
    elif MODE_RANK[selected] < MODE_RANK[profile["requested_mode"]] and not profile["limitation_acknowledged"]:
        status = "LIMITATION_ACK_REQUIRED"
        exit_code = 3
    else:
        status = "READY"
        exit_code = 0
    return {
        "valid": True,
        "status": status,
        "exit_code": exit_code,
        "validator_self_test": "PASS" if self_test_passed else "FAIL",
        "validator_detail": self_test_detail,
        "allowed_claims": allowed,
        "excluded_claims": excluded,
        "errors": [],
    }


def _validate_acquisition(value: Any, errors: List[str]) -> None:
    _require_object(value, ACQUISITION_KEYS, ACQUISITION_KEYS, "acquisition", errors)
    if not isinstance(value, dict):
        return
    for key in ("attempted", "succeeded"):
        if not isinstance(value.get(key), bool):
            errors.append(f"acquisition.{key} must be boolean")
    if value.get("method") not in ACQUISITION_METHODS:
        errors.append("acquisition.method is invalid")
    if not _is_nonempty_string(value.get("requested_location")):
        errors.append("acquisition.requested_location must be a non-empty string")
    redirects = value.get("redirect_chain")
    _validate_string_list(redirects, "acquisition.redirect_chain", errors)
    status = value.get("response_status")
    if status is not None and (not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599):
        errors.append("acquisition.response_status must be null or an HTTP status from 100 through 599")
    timestamp = value.get("acquired_at")
    if timestamp is not None and not _is_rfc3339_datetime(timestamp):
        errors.append("acquisition.acquired_at must be null or an RFC 3339 date-time")
    digest = value.get("content_sha256")
    if digest is not None and (not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest)):
        errors.append("acquisition.content_sha256 must be null or 64 lowercase hexadecimal characters")
    for key in ("final_location", "tool", "error"):
        if value.get(key) is not None and not _is_nonempty_string(value.get(key)):
            errors.append(f"acquisition.{key} must be null or a non-empty string")

    attempted = value.get("attempted")
    succeeded = value.get("succeeded")
    if succeeded is True and attempted is not True:
        errors.append("acquisition.succeeded requires acquisition.attempted")
    if succeeded is True:
        for key in ("final_location", "acquired_at", "tool"):
            if not _is_nonempty_string(value.get(key)):
                errors.append(f"successful acquisition requires acquisition.{key}")
        if value.get("error") is not None:
            errors.append("successful acquisition requires acquisition.error to be null")
    if attempted is True and succeeded is False and not _is_nonempty_string(value.get("error")):
        errors.append("failed acquisition requires acquisition.error")


def _validate_execution(value: Any, errors: List[str]) -> None:
    """Structural rules for the post-acquisition execution receipt.

    Acquiring a target and completing an audit are two different events. The
    execution block records the second one so that "the page was retrieved but
    the audit itself broke" has one honest representation instead of being
    forced into an acquisition failure or, worse, into a silent pass.
    """
    _require_object(value, EXECUTION_KEYS, EXECUTION_KEYS, "execution", errors)
    if not isinstance(value, dict):
        return
    completed = value.get("completed")
    stage = value.get("failure_stage")
    detail = value.get("error")
    if not isinstance(completed, bool):
        errors.append("execution.completed must be boolean")
    if stage is not None and stage not in FAILURE_STAGES:
        errors.append("execution.failure_stage must be null or one of: " + ", ".join(FAILURE_STAGES))
    if detail is not None and not _is_nonempty_string(detail):
        errors.append("execution.error must be null or a non-empty string")
    if completed is True:
        if stage is not None:
            errors.append("completed execution requires execution.failure_stage to be null")
        if detail is not None:
            errors.append("completed execution requires execution.error to be null")
    if completed is False:
        if stage is None:
            errors.append("incomplete execution requires execution.failure_stage")
        if not _is_nonempty_string(detail):
            errors.append("incomplete execution requires execution.error")


def validate_run(envelope: Any) -> List[str]:
    errors: List[str] = []
    _require_object(envelope, RUN_REQUIRED, RUN_ALLOWED, "run", errors)
    if not isinstance(envelope, dict):
        return errors
    if envelope.get("run_contract_version") != RUN_CONTRACT_VERSION:
        errors.append(f"run.run_contract_version must be {RUN_CONTRACT_VERSION}")
    if envelope.get("package_version") != PACKAGE_VERSION:
        errors.append(f"run.package_version must be {PACKAGE_VERSION}")

    profile = envelope.get("preflight")
    decision = preflight_decision(profile)
    if decision["status"] != "READY":
        errors.append(f"run preflight must be READY, received {decision['status']}")
    if isinstance(profile, dict) and profile.get("package_version") != envelope.get("package_version"):
        errors.append("run and preflight package versions disagree")

    acquisition = envelope.get("acquisition")
    _validate_acquisition(acquisition, errors)
    execution = envelope.get("execution")
    _validate_execution(execution, errors)
    report = envelope.get("report")
    report_violations = validate_report(report)
    errors.extend(f"report: {violation}" for violation in report_violations)
    if (
        not isinstance(profile, dict)
        or not isinstance(acquisition, dict)
        or not isinstance(execution, dict)
        or not isinstance(report, dict)
    ):
        return errors

    target = profile.get("target") if isinstance(profile.get("target"), dict) else {}
    report_target = report.get("target") if isinstance(report.get("target"), dict) else {}
    if report_target.get("input_type") != target.get("input_type"):
        errors.append("report target input type does not match preflight")
    if report_target.get("location") != target.get("location"):
        errors.append("report target location does not match preflight")
    if acquisition.get("requested_location") != target.get("location"):
        errors.append("acquisition requested location does not match preflight")

    selected = profile.get("selected_mode")
    expected_method = {
        "CONTRACT_ONLY": "NONE",
        "FILE_STATIC": "FILES_ONLY",
        "SOURCE_TEXT": "CONVERTED_TEXT",
        "RAW_SOURCE": "RAW_SOURCE",
        "RENDERED_BROWSER": "RENDERED_BROWSER",
        "RENDERED_DOM": "RENDERED_DOM",
        "INTERACTIVE": "INTERACTIVE_BROWSER",
    }.get(selected)
    if acquisition.get("method") != expected_method:
        errors.append("acquisition method does not match the selected evidence mode")

    scope = report.get("scope") if isinstance(report.get("scope"), dict) else {}
    required = set(item for item in profile.get("required_manual_checks", []) if isinstance(item, str))
    reported_required = set(item for item in scope.get("required_manual_checks", []) if isinstance(item, str))
    missing_manual = sorted(required - reported_required)
    if missing_manual:
        errors.append(f"report omits preflight manual checks: {', '.join(missing_manual)}")

    completed_manual = {
        item
        for item in scope.get("manual_checks_completed", [])
        if isinstance(item, str)
    }
    capabilities = profile.get("capabilities") if isinstance(profile.get("capabilities"), dict) else {}
    manual_observation_present = any(
        isinstance(item, dict) and item.get("type") == "MANUAL_OBSERVATION"
        for item in report.get("evidence_log", [])
    ) or any(
        isinstance(item, dict) and item.get("type") == "MANUAL_OBSERVATION"
        for finding in report.get("findings", [])
        if isinstance(finding, dict)
        for item in finding.get("evidence", [])
        if isinstance(finding.get("evidence"), list)
    )
    if completed_manual and capabilities.get("manual_evidence") is not True:
        errors.append(
            "report cannot complete manual checks when preflight.capabilities.manual_evidence is false"
        )
    if completed_manual and not manual_observation_present:
        errors.append("completed manual checks require MANUAL_OBSERVATION evidence")
    if capabilities.get("manual_evidence") is False and manual_observation_present:
        errors.append(
            "report cannot contain MANUAL_OBSERVATION evidence when preflight.capabilities.manual_evidence is false"
        )

    completed = execution.get("completed")
    failure_stage = execution.get("failure_stage")
    automated = report.get("automated_result")
    final = report.get("final_status")
    error_codes = {
        item.get("code")
        for item in report.get("errors", [])
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    }

    if completed is False:
        # An audit that never finished cannot have discovered that anything passed.
        if automated == "PASS":
            errors.append("an execution that did not complete cannot report an automated PASS")
        if final in VERIFIED_PASS_STATUSES:
            errors.append("an execution that did not complete cannot end VERIFIED PASS")

    if selected == "CONTRACT_ONLY":
        if acquisition.get("attempted") is not False or acquisition.get("succeeded") is not False:
            errors.append("CONTRACT_ONLY runs must not claim target acquisition")
        if completed is not True:
            errors.append("CONTRACT_ONLY runs must record execution.completed true")
    elif acquisition.get("succeeded") is True:
        if completed is True:
            if automated == "ERROR":
                errors.append("successful acquisition with completed execution cannot end automated ERROR")
        elif completed is False:
            # Acquisition worked and the audit then failed: legal, but only in this exact shape.
            if failure_stage == "ACQUISITION":
                errors.append("acquired target cannot record execution.failure_stage ACQUISITION")
            if automated != "ERROR" or final != "INCOMPLETE":
                errors.append("post-acquisition execution failure requires report ERROR | INCOMPLETE")
            if "EXECUTION_FAILED" not in error_codes:
                errors.append("post-acquisition execution failure requires structured EXECUTION_FAILED error")
    else:
        if completed is not False:
            errors.append("failed acquisition requires execution.completed false")
        elif failure_stage != "ACQUISITION":
            errors.append("failed acquisition requires execution.failure_stage ACQUISITION")
        if automated != "ERROR" or final != "INCOMPLETE":
            errors.append("failed acquisition requires report ERROR | INCOMPLETE")
        if "ACQUISITION_FAILED" not in error_codes:
            errors.append("failed acquisition requires structured ACQUISITION_FAILED error")

    if selected == "SOURCE_TEXT" and acquisition.get("succeeded") is True:
        if report.get("final_status") != "INCOMPLETE":
            errors.append("SOURCE_TEXT live review must end INCOMPLETE")
        excluded = set(item for item in scope.get("excluded", []) if isinstance(item, str))
        missing_exclusions = sorted(set(decision["excluded_claims"]) - excluded)
        if missing_exclusions:
            errors.append("SOURCE_TEXT report must preserve every machine-generated excluded claim")
        for index, finding in enumerate(report.get("findings", [])):
            if not isinstance(finding, dict):
                continue
            if finding.get("classification") != "ADVISORY" or finding.get("standard") is not None:
                errors.append(f"SOURCE_TEXT findings[{index}] must be advisory with no normative standard")
            if finding.get("confidence") != "LOW":
                errors.append(f"SOURCE_TEXT findings[{index}] confidence must be LOW")
            if not isinstance(finding.get("title"), str) or not finding["title"].startswith("Potential: "):
                errors.append(f"SOURCE_TEXT findings[{index}] title must begin 'Potential: '")
            evidence_types = {
                item.get("type")
                for item in finding.get("evidence", [])
                if isinstance(item, dict)
            }
            if not evidence_types or not evidence_types.issubset({"SOURCE", "TOOL_OUTPUT"}):
                errors.append(f"SOURCE_TEXT findings[{index}] may use only SOURCE or TOOL_OUTPUT evidence")
    return errors


def build_receipt(envelope: Dict[str, Any]) -> Dict[str, Any]:
    profile = envelope["preflight"]
    execution = envelope["execution"]
    report = envelope["report"]
    scope = report["scope"]
    required = set(scope["required_manual_checks"])
    completed = set(scope["manual_checks_completed"])
    pending = sorted(required - completed)
    surface = profile["surface"]
    final_status = report["final_status"]
    execution_completed = execution["completed"]
    failure_stage = execution["failure_stage"]
    if not execution_completed and failure_stage == "ACQUISITION":
        meaning = (
            "The target was never acquired, so the audit did not run. "
            "No accessibility conclusion is established."
        )
    elif not execution_completed:
        meaning = (
            "The page was acquired, but the audit itself failed before completion. "
            "No accessibility conclusion is established."
        )
    elif final_status == "INCOMPLETE":
        meaning = "The declared run is valid, but accessibility remains incomplete."
    else:
        meaning = "The declared run and its report passed the operational contract."
    return {
        "package_version": PACKAGE_VERSION,
        "run_contract_version": RUN_CONTRACT_VERSION,
        "report_contract_version": report["contract_version"],
        "surface": f"{surface['provider']} — {surface['product']} ({surface['mode']})",
        "evidence_mode": profile["selected_mode"],
        "limitation_acknowledged": profile["limitation_acknowledged"],
        "validator": "PASS (exit 0)",
        "execution_completed": execution_completed,
        "execution_failure_stage": failure_stage,
        "automated_result": report["automated_result"],
        "final_status": final_status,
        "manual_checks_remaining": pending,
        "meaning": meaning,
        "next_action": profile["next_action"],
    }


def guarded_roots(base: Path) -> List[Path]:
    """Every directory from base upward that carries a Dravux tree marker.

    An installed skill, a source checkout, and an extracted release all carry at
    least one of SKILL.md or RELEASE_MANIFEST.json. Audit output written inside
    such a tree contaminates the very files a manifest verification checks, so
    those directories are off limits. The list runs innermost first.
    """
    roots: List[Path] = []
    for candidate in (base,) + tuple(base.parents):
        if any((candidate / marker).is_file() for marker in GUARD_MARKERS):
            roots.append(candidate)
    return roots


def resolve_output_dir(
    base: Any = None,
    audit_id: Any = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Decide where this run's audit output belongs, and create that directory."""
    result: Dict[str, Any] = {
        "command": "output-dir",
        "status": "CREATED",
        "exit_code": 0,
        "base": None,
        "guarded": False,
        "guarded_root": None,
        "output_dir": None,
        "created": False,
        "message": "",
    }
    if audit_id is not None and (
        not isinstance(audit_id, str) or not AUDIT_ID_PATTERN.fullmatch(audit_id)
    ):
        result.update(
            status="INVALID",
            exit_code=OUTPUT_DIR_INPUT_EXIT,
            message=(
                "The audit name may use only lowercase letters, numbers and hyphens, "
                "and must be 1 to 64 characters long. Nothing was created."
            ),
        )
        return result

    try:
        resolved = Path(base if base is not None else Path.cwd()).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        result.update(
            status="INVALID",
            exit_code=OUTPUT_DIR_INPUT_EXIT,
            message=f"That starting folder could not be read: {exc}. Nothing was created.",
        )
        return result

    result["base"] = str(resolved)
    roots = guarded_roots(resolved)
    outermost = roots[-1] if roots else None
    result["guarded"] = bool(roots)
    result["guarded_root"] = str(outermost) if outermost is not None else None

    if outermost is not None:
        parent = outermost.parent
        suggestion = Path.home() / OUTPUT_DIR_NAME
        if strict:
            result.update(
                status="REFUSED",
                exit_code=OUTPUT_DIR_REFUSED_EXIT,
                message=(
                    f"Refusing to create an audit folder inside the Dravux files at {outermost}. "
                    f"Nothing was created. Choose a folder outside it, for example {suggestion}."
                ),
            )
            return result
        if parent == outermost:
            result.update(
                status="REFUSED",
                exit_code=OUTPUT_DIR_REFUSED_EXIT,
                message=(
                    f"The Dravux files at {outermost} have no folder above them to write beside. "
                    f"Nothing was created. Re-run with --base {suggestion}."
                ),
            )
            return result
    else:
        parent = resolved

    target = parent / OUTPUT_DIR_NAME
    if audit_id:
        target = target / audit_id
    if outermost is not None and (target == outermost or outermost in target.parents):
        result.update(
            status="REFUSED",
            exit_code=OUTPUT_DIR_REFUSED_EXIT,
            message=(
                f"The requested audit folder would sit inside the Dravux files at {outermost}. "
                "Nothing was created."
            ),
        )
        return result

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result.update(
            status="INVALID",
            exit_code=OUTPUT_DIR_INPUT_EXIT,
            output_dir=str(target),
            message=f"The audit folder could not be created: {exc}.",
        )
        return result

    result["output_dir"] = str(target)
    result["created"] = True
    if outermost is not None:
        result.update(
            status="REDIRECTED",
            message=(
                f"{resolved} is inside the Dravux files at {outermost}, which must stay exactly as "
                "installed, so this audit folder was created next to them instead."
            ),
        )
    else:
        result["message"] = "This run's audit folder is ready."
    return result


def _print_output_dir(result: Dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if result["output_dir"] is None or not result["created"]:
        print(result["message"], file=sys.stderr)
        return
    print(result["message"])
    print(result["output_dir"])


def _load_json(path: Path) -> Any:
    return load_json_path(path)


def _print_preflight(result: Dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(f"DRAVUX PREFLIGHT: {result['status']}")
    print(f"Validator self-test: {result['validator_self_test']}")
    for claim in result["allowed_claims"]:
        print(f"Allowed: {claim}")
    for claim in result["excluded_claims"]:
        print(f"Excluded: {claim}")
    for error in result["errors"]:
        print(f"ERROR: {error}", file=sys.stderr)


def _print_run(result: Dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if not result["valid"]:
        print("INVALID Dravux operational run:", file=sys.stderr)
        for error in result["errors"]:
            print(f"- {error}", file=sys.stderr)
        return
    receipt = result["receipt"]
    print("DRAVUX RUN RECEIPT")
    for label, key in (
        ("Package", "package_version"),
        ("Surface", "surface"),
        ("Evidence mode", "evidence_mode"),
        ("Validator", "validator"),
        ("Automated result", "automated_result"),
        ("Final status", "final_status"),
        ("Meaning", "meaning"),
        ("Next action", "next_action"),
    ):
        print(f"{label}: {receipt[key]}")
        if key == "evidence_mode":
            acknowledgement = "accepted" if receipt["limitation_acknowledged"] else "not required"
            print(f"Limitation acknowledgement: {acknowledgement}")
        if key == "validator":
            state = (
                "completed"
                if receipt["execution_completed"]
                else f"did not complete (failure stage: {receipt['execution_failure_stage']})"
            )
            print(f"Execution: {state}")
    remaining = ", ".join(receipt["manual_checks_remaining"]) or "none"
    print(f"Manual checks remaining: {remaining}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preflight a surface, validate a Dravux operational run, or place its output."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("preflight", "validate"):
        child = subparsers.add_parser(command)
        child.add_argument("input", type=Path, help="Path to JSON, or - for stdin")
        child.add_argument("--json", action="store_true", dest="json_output")
    placement = subparsers.add_parser(
        "output-dir",
        help="Create the folder this run's audit files belong in, never inside the Dravux files",
    )
    placement.add_argument(
        "--base",
        type=Path,
        default=None,
        help="Folder the audit output should sit under (default: the current folder)",
    )
    placement.add_argument(
        "--audit-id",
        dest="audit_id",
        default=None,
        help="Optional audit name: lowercase letters, numbers and hyphens, 1 to 64 characters",
    )
    placement.add_argument(
        "--strict",
        action="store_true",
        help="Refuse instead of redirecting when the chosen folder is inside the Dravux files",
    )
    placement.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: List[str] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "output-dir":
        result = resolve_output_dir(args.base, args.audit_id, args.strict)
        _print_output_dir(result, args.json_output)
        return result["exit_code"]
    try:
        payload = _load_json(args.input)
    except (OSError, ValueError, RecursionError) as exc:
        result = {"valid": False, "status": "LOAD_ERROR", "exit_code": 2, "errors": [str(exc)]}
        if args.json_output:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"ERROR: could not load Dravux {args.command} JSON: {exc}", file=sys.stderr)
        return 2
    try:
        if args.command == "preflight":
            result = preflight_decision(payload)
            _print_preflight(result, args.json_output)
            return result["exit_code"]
        violations = validate_run(payload)
        result = {
            "valid": not violations,
            "exit_code": 0 if not violations else 1,
            "errors": violations,
        }
        if not violations:
            result["receipt"] = build_receipt(payload)
        _print_run(result, args.json_output)
        return result["exit_code"]
    except (AttributeError, KeyError, RecursionError, TypeError, ValueError) as exc:
        result = {
            "valid": False,
            "exit_code": 1,
            "errors": [f"operational validator safely rejected hostile structure: {type(exc).__name__}: {exc}"],
        }
        _print_run(result, args.json_output)
        return 1


if __name__ == "__main__":
    sys.exit(main())
