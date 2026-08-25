#!/usr/bin/env python3
"""Run bounded deterministic checks for Dravux's synthetic HTML demo."""

import argparse
import json
import math
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()
REPORT_SCHEMA = PACKAGE_ROOT / "schemas" / "dravux-report.schema.json"
SKILL_SCRIPTS = PACKAGE_ROOT / "plugins" / "dravux" / "skills" / "dravux" / "scripts"
# Importing the skill's validator would otherwise leave a __pycache__ directory inside the
# manifest-verified skill tree; dravux_run.py carries the same guard for the same reason.
sys.dont_write_bytecode = True
sys.path.insert(0, str(SKILL_SCRIPTS))

from dravux_contract import validate_report  # noqa: E402


class DemoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang: Optional[str] = None
        self.images: List[Dict[str, Optional[str]]] = []
        self.buttons: List[Dict[str, str]] = []
        self._button: Optional[Dict[str, str]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang")
        elif tag == "img":
            self.images.append({"src": values.get("src"), "alt": values.get("alt")})
        elif tag == "button":
            self._button = {"style": values.get("style") or "", "text": ""}

    def handle_data(self, data: str) -> None:
        if self._button is not None:
            self._button["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self._button is not None:
            self.buttons.append(self._button)
            self._button = None


def _hex_rgb(value: str) -> Tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(character * 2 for character in value)
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError(f"unsupported color {value!r}")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _luminance(color: str) -> float:
    channels = []
    for channel in _hex_rgb(color):
        value = channel / 255.0
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: str, background: str) -> float:
    first, second = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (first + 0.05) / (second + 0.05)


def _style_map(style: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for declaration in style.split(";"):
        if ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        result[key.strip().lower()] = value.strip()
    return result


def _pixels(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)px", value.strip())
    return float(match.group(1)) if match else None


def _standard(criterion: str, fragment: str) -> Dict[str, str]:
    return {
        "name": "Web Content Accessibility Guidelines",
        "version": "2.2",
        "success_criterion": criterion,
        "url": f"https://www.w3.org/TR/WCAG22/#{fragment}",
    }


def _finding(
    finding_id: str,
    criterion: str,
    fragment: str,
    title: str,
    evidence: str,
    locator: str,
    impact: str,
    repair: str,
    verification: List[str],
    severity: str = "HIGH",
) -> Dict[str, object]:
    return {
        "finding_id": finding_id,
        "target_and_state": locator,
        "input_type": "SOURCE_CODE",
        "standard": _standard(criterion, fragment),
        "classification": "NORMATIVE",
        "severity": severity,
        "title": title,
        "evidence": [{"type": "SOURCE", "description": evidence, "locator": locator}],
        "reproduction_steps": [f"Open {locator}.", evidence],
        "user_impact": impact,
        "recommended_repair": repair,
        "verification_steps": verification,
        "confidence": "HIGH",
        "manual_review_required": True,
        "source": {
            "title": f"WCAG 2.2 {criterion}",
            "url": f"https://www.w3.org/TR/WCAG22/#{fragment}",
        },
        "status": "OPEN",
    }


def audit_html(source: Path, state: str) -> Dict[str, object]:
    text = source.read_text(encoding="utf-8")
    parser = DemoParser()
    parser.feed(text)
    locator = source.as_posix()
    findings: List[Dict[str, object]] = []

    if not parser.html_lang or not parser.html_lang.strip():
        findings.append(
            _finding(
                "DRV-DEMO-LANG-001",
                "3.1.1 Language of Page",
                "language-of-page",
                "Page language is missing",
                "The html element has no non-empty lang attribute.",
                locator,
                "Screen readers may use the wrong pronunciation rules.",
                "Set the page's primary language with a valid lang attribute.",
                ["Re-run this audit.", "Confirm pronunciation with a screen reader."],
                "MEDIUM",
            )
        )

    for index, image in enumerate(parser.images, start=1):
        if image.get("alt") is None:
            findings.append(
                _finding(
                    f"DRV-DEMO-ALT-{index:03d}",
                    "1.1.1 Non-text Content",
                    "non-text-content",
                    "Image has no text alternative",
                    f"Image {index} has no alt attribute.",
                    f"{locator} image[{index}]",
                    "Screen-reader users may miss the image's purpose or hear an unhelpful filename.",
                    "Add a purpose-appropriate alt value; use alt=\"\" only when the image is decorative.",
                    ["Re-run this audit.", "Review the alternative in page context with a screen reader."],
                )
            )

    undersized_targets: List[Dict[str, object]] = []
    for index, button in enumerate(parser.buttons, start=1):
        styles = _style_map(button.get("style", ""))
        foreground = styles.get("color")
        background = styles.get("background-color") or styles.get("background")
        if foreground and background:
            try:
                ratio = contrast_ratio(foreground, background)
            except ValueError:
                ratio = None
            if ratio is not None and ratio < 4.5:
                findings.append(
                    _finding(
                        f"DRV-DEMO-CONTRAST-{index:03d}",
                        "1.4.3 Contrast (Minimum)",
                        "contrast-minimum",
                        "Button text contrast is below 4.5:1",
                        f"Button {index} uses {foreground} on {background}, calculated at {ratio:.2f}:1.",
                        f"{locator} button[{index}]",
                        "People with low vision may be unable to read the primary action.",
                        "Use a foreground/background pair that meets at least 4.5:1 for normal text.",
                        ["Re-run this audit.", "Verify every interactive state and real text size."],
                    )
                )

        width = _pixels(styles.get("min-width") or styles.get("width"))
        height = _pixels(styles.get("min-height") or styles.get("height"))
        if width is not None and height is not None and (width < 24 or height < 24):
            undersized_targets.append(
                {
                    "index": index,
                    "width": width,
                    "height": height,
                    "left": _pixels(styles.get("left")),
                    "top": _pixels(styles.get("top")),
                }
            )

    spacing_pair: Optional[Tuple[Dict[str, object], Dict[str, object], float]] = None
    for first_index, first in enumerate(undersized_targets):
        for second in undersized_targets[first_index + 1 :]:
            positions = (first["left"], first["top"], second["left"], second["top"])
            if any(value is None for value in positions):
                continue
            first_center = (float(first["left"]) + float(first["width"]) / 2, float(first["top"]) + float(first["height"]) / 2)
            second_center = (float(second["left"]) + float(second["width"]) / 2, float(second["top"]) + float(second["height"]) / 2)
            distance = math.dist(first_center, second_center)
            if distance < 24:
                spacing_pair = (first, second, distance)
                break
        if spacing_pair:
            break

    if spacing_pair:
        first, second, distance = spacing_pair
        findings.append(
            _finding(
                "DRV-DEMO-TARGET-SPACING-001",
                "2.5.8 Target Size (Minimum)",
                "target-size-minimum",
                "Undersized pointer targets fail the spacing exception",
                f"Buttons {first['index']} and {second['index']} are under 24 by 24 CSS pixels and their centers are {distance:.1f}px apart, so the synthetic 24px spacing circles intersect.",
                f"{locator} buttons[{first['index']},{second['index']}]",
                "People with limited dexterity or touch precision may activate the adjacent control by mistake.",
                "Increase each target to at least 24 by 24 CSS pixels or provide enough spacing for the criterion's exception.",
                ["Re-run this audit.", "Verify computed target boxes and activation on a real touch device."],
                "MEDIUM",
            )
        )

    focus_blocks = re.findall(r"[^{}]*:focus(?:-visible)?[^{}]*\{([^{}]*)\}", text, flags=re.IGNORECASE)
    focus_suppressed_without_replacement = False
    for block in focus_blocks:
        styles = _style_map(block)
        outline = styles.get("outline", "").lower()
        replacement_properties = {"box-shadow", "border", "border-color", "background", "background-color", "text-decoration"}
        if outline in {"none", "0", "0px"} and not replacement_properties.intersection(styles):
            focus_suppressed_without_replacement = True
            break

    if parser.buttons and focus_suppressed_without_replacement:
        findings.append(
            _finding(
                "DRV-DEMO-FOCUS-001",
                "2.4.7 Focus Visible",
                "focus-visible",
                "Focus styling explicitly removes the indicator without replacement",
                "The synthetic source sets outline: none in a button focus rule and defines no replacement indicator in that state.",
                locator,
                "Keyboard users may not know which control is active.",
                "Remove the suppression or add a clear :focus-visible indicator that remains visible against adjacent colors.",
                ["Re-run this audit.", "Navigate the page manually with the keyboard and inspect every focus state."],
            )
        )

    automated = "FAIL" if findings else "PASS"
    final = "VERIFIED FAIL" if findings else "INCOMPLETE"
    audit_slug = re.sub(r"[^A-Z0-9]+", "-", state.upper()).strip("-") or "STATE"
    report: Dict[str, object] = {
        "contract_version": "0.2.0",
        "audit_id": f"DRV-DEMO-{audit_slug}-001",
        "target": {
            "name": "Dravux synthetic GitHub demo page",
            "state": state,
            "location": locator,
            "input_type": "SOURCE_CODE",
        },
        "scope": {
            "included": ["page language", "image alt presence", "button text contrast", "button target size", "visible focus rule presence"],
            "excluded": ["browser runtime", "framework behavior", "external resources"],
            "required_manual_checks": ["keyboard", "screen-reader", "zoom-reflow", "state-coverage"],
            "manual_checks_completed": [],
            "applicability_reason": None,
        },
        "automated_result": automated,
        "final_status": final,
        "findings": findings,
        "errors": [],
        "evidence_log": [
            {
                "type": "COMMAND_OUTPUT",
                "description": f"Bounded deterministic demo audit completed with {len(findings)} normative finding(s).",
                "locator": "scripts/audit_demo_html.py",
            }
        ],
        "run": {
            "started_at": "1970-01-01T00:00:00Z",
            "completed_at": "1970-01-01T00:00:00Z",
            "tooling": [f"Dravux demo HTML audit {PACKAGE_VERSION}", "Python standard library"],
            "environment": "Deterministic offline source fixture",
        },
    }
    violations = validate_report(report)
    if violations:
        raise RuntimeError("internal report contract violation: " + "; ".join(violations))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit Dravux's bounded synthetic HTML demo.")
    parser.add_argument("source", type=Path, help="Synthetic HTML source to audit")
    parser.add_argument("--state", required=True, help="Human-readable target state")
    parser.add_argument("--output", type=Path, help="Optional report JSON output path; otherwise print to stdout")
    parser.add_argument("--fail-on-findings", action="store_true", help="Exit 1 when the automated result is FAIL")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = audit_html(args.source, args.state)
    except (OSError, UnicodeError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        resolved_output = args.output.resolve()
        try:
            resolved_output.relative_to(PACKAGE_ROOT)
        except ValueError:
            pass
        else:
            report["$schema"] = Path(os.path.relpath(REPORT_SCHEMA, resolved_output.parent)).as_posix()
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(f"Wrote {args.output}: {report['automated_result']} | {report['final_status']}")
    else:
        print(payload, end="")
    if args.fail_on_findings and report["automated_result"] == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
