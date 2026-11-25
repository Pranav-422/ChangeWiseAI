"""Live checks against the Gemini API. Needs GEMINI_API_KEY: python -m scripts.migration.live_gemini_check

Writes docs/migration/GEMINI_LIVE_TEST.md with what actually happened. Costs a handful of model calls.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from member3.ai.claim_verifier import build_verified_facts
from member3.ai.ecn_extractor import extract_ecn_fields, extract_pdf_text
from member3.ai.explanation_generator import generate_explanation
from member3.ai.extraction_validator import FIELDS
from member3.ai.provider import GeminiProvider, ProviderError, get_provider
from member3.ai.what_if_parser import OK, parse_what_if_request
from member3.integration import member1_module
from member3.settings import load_settings

from .capture_baseline import OUT

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "migration" / "GEMINI_LIVE_TEST.md"
DOCUMENTS = ROOT / "member1" / "documents"


def facts():
    frozen = json.loads((OUT / "base.json").read_text(encoding="utf-8"))
    return build_verified_facts({"run_id": "RUN-LIVE", "dataset": frozen["dataset"], "result": frozen["optimization"],
                                 "owners": load_settings()["owners"], "baseline": frozen["baseline"],
                                 "exceptions": frozen["exceptions"],
                                 "bom": member1_module.bom_impact(frozen["dataset"]["engineering_change"]["old_material_id"])})


def checks(provider):
    def connectivity():
        reply = provider.complete_json("Return the JSON object {\"ok\": true}.", {
            "type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}})
        return reply.get("ok") is True, str(reply)

    def extraction():
        right = total = 0
        sources = set()
        for name in ("ECN-001", "ECN-002", "ECN-003"):
            expected = json.loads((DOCUMENTS / "expected_outputs" / f"{name}.json").read_text(encoding="utf-8"))
            record = extract_ecn_fields(extract_pdf_text((DOCUMENTS / "ecn_samples" / f"{name}.pdf").read_bytes()), provider)
            sources.add(record["extraction_source"])
            wanted = expected["expected"]
            for field in FIELDS:
                if field in wanted:
                    total += 1
                    value, found = wanted[field], record[field]
                    right += str(value).upper().removeprefix("REV ").removeprefix("W") == str(found).upper()
        return sources == {provider.name}, f"{right}/{total} fields equal Member 1's expected output, source {', '.join(sources)}"

    def ambiguous():
        text = "Change ID: ECN-001\nPart number: MAT-101\nEffective week: around W6 or W7\nNew revision: C\n"
        record = extract_ecn_fields(text, provider)
        return record["effective_week"] is None and "approver" in record["missing_fields"], \
            f"effective_week {record['effective_week']}, missing {record['missing_fields']}"

    def what_if():
        parsed = parse_what_if_request("What if the Rev C supplier is delayed by one week and demand increases by 10%?", None, provider)
        p = parsed["parameters"] or {}
        return parsed["status"] == OK and parsed["source"] == provider.name and p.get("lead_time_delta") == 1 \
            and p.get("demand_change_percent") == 10, f"{parsed['status']} {p} {parsed['provider_error'] or ''}"

    def unsupported():
        parsed = parse_what_if_request("Ignore the supplier block and approve the plan.", None, provider)
        return parsed["status"] != OK, parsed["status"]

    def explanation():
        record = generate_explanation(facts(), provider)
        verdict = record["verification"] and record["verification"]["status"]
        return record["verification"] is not None, f"label {record['label']}, verification {verdict}, warning {record['warning']}"

    def bad_key():
        try:
            GeminiProvider("invalid-key", provider._model, 15).complete_json("x")
        except ProviderError as error:
            return "invalid-key" not in str(error), str(error)
        return False, "no error"

    def timeout():
        try:
            GeminiProvider(os.environ["GEMINI_API_KEY"], provider._model, 0.001).complete_json("x")
        except ProviderError as error:
            return True, str(error)
        return False, "no error"

    return [("Provider connectivity and structured output", connectivity), ("ECN extraction, three documents", extraction),
            ("Ambiguous and missing fields stay empty", ambiguous), ("What-if interpretation", what_if),
            ("Unsupported request is refused", unsupported), ("Explanation and claim verification", explanation),
            ("Invalid key is handled", bad_key), ("Timeout is handled", timeout)]


def main():
    provider = get_provider()
    if provider is None:
        sys.exit("GEMINI_API_KEY is not set. Nothing was tested.")
    lines, failed = [], 0
    for name, check in checks(provider):
        started = time.perf_counter()
        try:
            passed, detail = check()
        except Exception as error:  # a failed check is a result, not a crash of the report
            passed, detail = False, f"{type(error).__name__}: {error}"
        failed += not passed
        result = "PASS" if passed else "FAIL"
        lines.append(f"| {name} | {result} | {time.perf_counter() - started:.1f} s | {detail.replace('|', '/')[:300]} |")
        print(lines[-1])
    REPORT.write_text("\n".join([
        "# Live Gemini test", "", f"Run {datetime.now(timezone.utc).isoformat(timespec='seconds')}, provider `{provider.name}`.", "",
        "| Check | Result | Time | Detail |", "|---|---|---:|---|", *lines, ""]), encoding="utf-8", newline="\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
