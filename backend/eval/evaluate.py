"""
Evaluation Harness
==================
Runs the golden test set against the chatbot pipeline and reports metrics.

Modes:
  --mock  : Skip LLM, check guard classification and PII detection only
  --live  : Full pipeline with LLM (requires GROQ_API_KEY)

Usage:
  python -m backend.eval.evaluate --mock
  python -m backend.eval.evaluate --live
  python -m backend.eval.evaluate --mock --output report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent
_BACKEND = _HERE.parent
_PROJECT = _BACKEND.parent
for _p in [str(_PROJECT), str(_BACKEND)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("evaluator")

GOLDEN_SET_PATH = _HERE / "golden_set.yaml"

# PII patterns (duplicated from post_processor to allow standalone eval)
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("Aadhaar", re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")),
    ("phone", re.compile(r"(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)")),
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
]


def _load_golden_set() -> list[dict]:
    import yaml
    with GOLDEN_SET_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("test_cases", [])


def _detect_pii(text: str) -> list[str]:
    found = []
    for pii_type, pattern in _PII_PATTERNS:
        if pattern.search(text):
            found.append(pii_type)
    return found


def _run_mock_test(test_case: dict) -> dict:
    """Run guard-only evaluation (no LLM call)."""
    from backend.core.query_guard import classify, INTENT_FACTUAL

    query = test_case["query"]
    expected_guard = test_case.get("expected_guard", "")
    should_answer = test_case.get("should_answer", True)
    test_type = test_case.get("type", "unknown")

    result: dict[str, Any] = {
        "query": query,
        "type": test_type,
        "expected_guard": expected_guard,
        "should_answer": should_answer,
    }

    t0 = time.time()

    # PII check on the input query
    if test_type == "pii":
        pii_found = _detect_pii(query)
        result["pii_detected"] = pii_found
        result["pii_pass"] = len(pii_found) > 0
        result["guard_pass"] = True  # PII test doesn't test guard classification
        result["answer_pass"] = not should_answer  # PII queries should not be answered
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    # Guard classification
    guard = classify(query, use_llm=False)
    result["actual_guard"] = guard.intent
    result["guard_stage"] = guard.stage
    result["is_refusal"] = guard.is_refusal

    # Guard accuracy
    if expected_guard:
        result["guard_pass"] = guard.intent == expected_guard
    else:
        result["guard_pass"] = True

    # Answer/refusal correctness
    if should_answer:
        result["answer_pass"] = not guard.is_refusal  # should answer but was refused = fail
    else:
        result["answer_pass"] = guard.is_refusal  # should refuse and did refuse = pass

    result["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return result


def _run_live_test(test_case: dict) -> dict:
    """Run full pipeline evaluation (requires GROQ_API_KEY)."""
    from backend.core.generator import generate
    from backend.core.post_processor import process as post_process

    query = test_case["query"]
    expected_guard = test_case.get("expected_guard", "")
    should_answer = test_case.get("should_answer", True)
    expected_contains = test_case.get("expected_contains", [])
    test_type = test_case.get("type", "unknown")

    result: dict[str, Any] = {
        "query": query,
        "type": test_type,
        "expected_guard": expected_guard,
        "should_answer": should_answer,
    }

    t0 = time.time()

    # PII check on input
    if test_type == "pii":
        pii_found = _detect_pii(query)
        result["pii_detected"] = pii_found
        result["pii_pass"] = len(pii_found) > 0
        result["guard_pass"] = True
        result["answer_pass"] = True if pii_found else False
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    # Edge case: empty query
    if not query.strip():
        from backend.core.query_guard import classify
        guard = classify(query, use_llm=False)
        result["actual_guard"] = guard.intent
        result["guard_pass"] = guard.intent == expected_guard if expected_guard else True
        result["answer_pass"] = guard.is_refusal == (not should_answer)
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        return result

    try:
        gen_result = generate(query)

        result["actual_guard"] = gen_result.intent
        result["is_refusal"] = gen_result.is_refusal
        result["retrieval_count"] = gen_result.retrieval_count

        # Guard accuracy
        if expected_guard:
            result["guard_pass"] = gen_result.intent == expected_guard
        else:
            result["guard_pass"] = True

        # Answer correctness
        if should_answer:
            result["answer_pass"] = not gen_result.is_refusal
        else:
            result["answer_pass"] = gen_result.is_refusal

        # Post-process the answer
        if not gen_result.is_refusal:
            pp = post_process(
                gen_result.answer,
                citation_url=gen_result.citation_url,
                last_updated_date=gen_result.last_updated_date,
            )
            result["post_processed"] = True
            result["pp_blocked"] = pp.is_blocked
            result["pp_replaced"] = pp.is_replaced
            result["citation_url"] = pp.citation_url

            # Citation accuracy: check if URL contains groww.in
            result["citation_valid"] = "groww.in" in pp.citation_url if pp.citation_url else False

            # Retrieval relevance: check expected_contains
            if expected_contains:
                answer_lower = pp.answer.lower()
                matched = [kw for kw in expected_contains if kw.lower() in answer_lower]
                result["expected_keywords"] = expected_contains
                result["matched_keywords"] = matched
                result["relevance_pass"] = len(matched) > 0
            else:
                result["relevance_pass"] = True
        else:
            result["post_processed"] = False
            result["relevance_pass"] = True

    except Exception as exc:
        result["error"] = str(exc)
        result["guard_pass"] = False
        result["answer_pass"] = False
        result["relevance_pass"] = False

    result["latency_ms"] = round((time.time() - t0) * 1000, 1)
    return result


def run_evaluation(mode: str = "mock") -> dict[str, Any]:
    """Run full evaluation suite. mode: 'mock' or 'live'."""
    test_cases = _load_golden_set()
    log.info("Loaded %d test cases from golden set", len(test_cases))

    runner = _run_mock_test if mode == "mock" else _run_live_test
    results: list[dict] = []

    for i, tc in enumerate(test_cases, 1):
        log.info("[%d/%d] %s: %r", i, len(test_cases), tc.get("type", "?"), tc["query"][:60])
        r = runner(tc)
        results.append(r)

    # Compute aggregate metrics
    total = len(results)
    guard_results = [r for r in results if "guard_pass" in r]
    guard_correct = sum(1 for r in guard_results if r["guard_pass"])

    factual_tests = [r for r in results if r.get("type") == "factual"]
    advisory_tests = [r for r in results if r.get("type") in ("advisory", "out_of_scope")]
    pii_tests = [r for r in results if r.get("type") == "pii"]

    false_refusals = sum(
        1 for r in factual_tests
        if r.get("should_answer") and not r.get("answer_pass", True)
    )
    false_accepts = sum(
        1 for r in advisory_tests
        if not r.get("should_answer") and not r.get("answer_pass", True)
    )

    pii_detected = sum(1 for r in pii_tests if r.get("pii_pass", False))

    latencies = [r["latency_ms"] for r in results if "latency_ms" in r]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    # Relevance (live mode only)
    relevance_tests = [r for r in results if "relevance_pass" in r]
    relevance_correct = sum(1 for r in relevance_tests if r["relevance_pass"])

    # Citation accuracy (live mode only)
    citation_tests = [r for r in results if "citation_valid" in r]
    citation_correct = sum(1 for r in citation_tests if r["citation_valid"])

    report = {
        "mode": mode,
        "total_tests": total,
        "guard_accuracy": round(guard_correct / max(len(guard_results), 1), 4),
        "guard_correct": guard_correct,
        "guard_total": len(guard_results),
        "false_refusal_rate": round(false_refusals / max(len(factual_tests), 1), 4),
        "false_refusals": false_refusals,
        "factual_tests": len(factual_tests),
        "false_acceptance_rate": round(false_accepts / max(len(advisory_tests), 1), 4),
        "false_accepts": false_accepts,
        "advisory_tests": len(advisory_tests),
        "pii_detection_rate": round(pii_detected / max(len(pii_tests), 1), 4),
        "pii_detected": pii_detected,
        "pii_tests": len(pii_tests),
        "retrieval_relevance": round(relevance_correct / max(len(relevance_tests), 1), 4) if relevance_tests else None,
        "citation_accuracy": round(citation_correct / max(len(citation_tests), 1), 4) if citation_tests else None,
        "avg_latency_ms": round(avg_latency, 1),
        "results": results,
    }

    return report


def _print_summary(report: dict) -> None:
    """Print a human-readable summary table to stdout."""
    print("\n" + "=" * 72)
    print(f"  EVALUATION REPORT  ({report['mode'].upper()} mode)")
    print("=" * 72)
    print(f"  Total test cases       : {report['total_tests']}")
    print(f"  Guard accuracy         : {report['guard_accuracy']:.1%} ({report['guard_correct']}/{report['guard_total']})")
    print(f"  False refusal rate     : {report['false_refusal_rate']:.1%} ({report['false_refusals']}/{report['factual_tests']} factual)")
    print(f"  False acceptance rate  : {report['false_acceptance_rate']:.1%} ({report['false_accepts']}/{report['advisory_tests']} advisory)")
    print(f"  PII detection rate     : {report['pii_detection_rate']:.1%} ({report['pii_detected']}/{report['pii_tests']} PII)")
    if report.get("retrieval_relevance") is not None:
        print(f"  Retrieval relevance    : {report['retrieval_relevance']:.1%}")
    if report.get("citation_accuracy") is not None:
        print(f"  Citation accuracy      : {report['citation_accuracy']:.1%}")
    print(f"  Avg latency            : {report['avg_latency_ms']:.1f} ms")
    print("-" * 72)

    # Per-test breakdown
    for r in report["results"]:
        guard_ok = "PASS" if r.get("guard_pass", True) else "FAIL"
        answer_ok = "PASS" if r.get("answer_pass", True) else "FAIL"
        pii_ok = ""
        if r.get("type") == "pii":
            pii_ok = " PII=" + ("PASS" if r.get("pii_pass") else "FAIL")
        print(
            f"  [{guard_ok}/{answer_ok}]{pii_ok} {r.get('type', '?'):12s} "
            f"| {r['query'][:55]}"
        )
        if r.get("error"):
            print(f"    ERROR: {r['error']}")

    print("=" * 72 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluation Harness")
    parser.add_argument("--mock", action="store_true", help="Mock mode: guard classification only, no LLM")
    parser.add_argument("--live", action="store_true", help="Live mode: full pipeline with LLM")
    parser.add_argument("--output", "-o", default="", help="Path to save JSON report")
    args = parser.parse_args()

    if not args.mock and not args.live:
        args.mock = True

    mode = "live" if args.live else "mock"
    report = run_evaluation(mode)

    _print_summary(report)

    if args.output:
        output_path = Path(args.output)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"Report saved to: {output_path}")

    # Exit with non-zero if any tests failed
    all_pass = all(
        r.get("guard_pass", True) and r.get("answer_pass", True)
        for r in report["results"]
    )
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
