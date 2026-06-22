#!/usr/bin/env python3
"""
Togithub: normalize GitHub repository topics.

GitHub topics rules:
  - lowercase only
  - only [a-z0-9-] characters (ASCII; non-ASCII like Chinese -> hyphen -> stripped)
  - no leading/trailing hyphens, no consecutive hyphens
  - max 50 chars per topic
  - max 20 topics total

Usage:
  python normalize_topics.py <topic1> <topic2> ...
  python normalize_topics.py --self-test
  echo "Python web scraper" | python normalize_topics.py

Exit code: 0 = no change (or self-test passed); 1 = some topics were normalized
(warnings on stderr, still use stdout); 2 = usage error.
Outputs: one normalized topic per line on stdout; warnings on stderr.
"""
from __future__ import annotations

import argparse
import re
import sys


MAX_LEN = 50
MAX_COUNT = 20


def normalize_one(topic: str) -> tuple[str, str | None]:
    """Normalize a single topic. Returns (normalized, warning).
    warning is None if no change, else a human-readable warning string."""
    original = topic
    # lowercase
    t = topic.lower()
    # ASCII-only: anything not [a-z0-9-] becomes hyphen (this drops Chinese/Cyrillic/emoji)
    t2 = re.sub(r"[^a-z0-9-]", "-", t)
    chars_replaced = t2 != t
    t = t2
    # collapse consecutive hyphens
    collapsed = "--" in t
    t = re.sub(r"-+", "-", t)
    # strip leading/trailing hyphens
    stripped = t != t.strip("-")
    t = t.strip("-")
    # truncate
    truncated = False
    if len(t) > MAX_LEN:
        t = t[:MAX_LEN].rstrip("-")
        truncated = True
    warning = None
    if t != original:
        if t == "":
            warning = f"'{original}' -> rejected (empty after normalization)"
        else:
            parts = []
            if chars_replaced or collapsed or stripped:
                parts.append("chars normalized")
            if truncated:
                parts.append(f"truncated to {MAX_LEN} chars")
            warning = f"'{original}' -> '{t}'" + (f" ({', '.join(parts)})" if parts else "")
    return t, warning


def normalize_topics(topics: list[str]) -> tuple[list[str], list[str]]:
    """Normalize a list of topics. Returns (normalized_list, warnings).
    Dedupes preserving first-seen order. Caps at MAX_COUNT."""
    seen: set[str] = set()
    result: list[str] = []
    warnings: list[str] = []
    for t in topics:
        norm, warn = normalize_one(t)
        if warn:
            warnings.append(warn)
        if norm == "" or norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
    if len(result) > MAX_COUNT:
        warnings.append(f"too many topics ({len(result)}), truncated to {MAX_COUNT}")
        result = result[:MAX_COUNT]
    return result, warnings


def self_test() -> int:
    """Run built-in self-tests. Returns 0 on pass, 1 on fail."""
    failures: list[str] = []

    def check(topic: str, expected: str) -> None:
        norm, _ = normalize_one(topic)
        if norm != expected:
            failures.append(f"normalize_one({topic!r}) = {norm!r}, expected {expected!r}")

    def check_warn(topic: str, expected_norm: str, warn_contains: str | None, warn_not_contains: str | None = None) -> None:
        norm, warn = normalize_one(topic)
        if norm != expected_norm:
            failures.append(f"normalize_one({topic!r}) norm = {norm!r}, expected {expected_norm!r}")
        if warn_contains is not None and (warn is None or warn_contains not in warn):
            failures.append(f"normalize_one({topic!r}) warn = {warn!r}, expected to contain {warn_contains!r}")
        if warn_not_contains is not None and (warn is not None and warn_not_contains in warn):
            failures.append(f"normalize_one({topic!r}) warn = {warn!r}, expected NOT to contain {warn_not_contains!r}")

    # basic normalization
    check("Python", "python")
    check("Web Scraper", "web-scraper")
    check("C++", "c")  # + becomes hyphen, stripped -> "c"
    check("machine_learning", "machine-learning")
    check("  --weird--  ", "weird")
    check("a--b", "a-b")
    check("-leading", "leading")
    check("trailing-", "trailing")
    # pure ASCII numeric / single char
    check("123", "123")
    check("a", "a")
    check("3d-rendering", "3d-rendering")
    # non-ASCII must be dropped (ASCII-only), not preserved
    check("数据", "")        # Chinese -> all hyphens -> stripped -> empty
    check("🚀rocket", "rocket")  # emoji -> hyphen, rocket kept
    check("数据爬虫", "")
    # warning label correctness
    check_warn("Python", "python", warn_contains=None, warn_not_contains="chars normalized")  # 大小写变化不标 chars normalized
    check_warn("a--b", "a-b", warn_contains="chars normalized")  # 折叠连字符要标
    check_warn("Web Scraper", "web-scraper", warn_contains="chars normalized")  # 空格替换要标
    # empty after normalization
    norm, _ = normalize_one("+++")
    if norm != "":
        failures.append(f"normalize_one('+++') = {norm!r}, expected ''")
    # length truncation
    long_topic = "a" * 60
    norm, _ = normalize_one(long_topic)
    if len(norm) != MAX_LEN:
        failures.append(f"long topic truncated to {len(norm)}, expected {MAX_LEN}")

    # list dedup + cap
    result, warns = normalize_topics(["Python", "python", "PY", "c++"])
    if result != ["python", "py", "c"]:
        failures.append(f"dedup result = {result!r}, expected ['python', 'py', 'c']")
    if not any("c++" in w for w in warns):
        failures.append(f"expected warning about 'c++', got {warns!r}")

    # max count cap
    many = [f"topic{i}" for i in range(25)]
    result, warns = normalize_topics(many)
    if len(result) != MAX_COUNT:
        failures.append(f"cap result count = {len(result)}, expected {MAX_COUNT}")
    if not any("too many" in w for w in warns):
        failures.append(f"expected 'too many' warning, got {warns!r}")

    if failures:
        for f in failures:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    print("all self-tests passed")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Normalize GitHub topics.")
    parser.add_argument("topics", nargs="*", help="topics to normalize")
    parser.add_argument("--self-test", action="store_true", help="run self-tests")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    topics = list(args.topics)
    # also read stdin if piped
    if not sys.stdin.isatty():
        topics += [line for line in sys.stdin.read().splitlines() if line.strip()]

    if not topics:
        parser.error("provide at least one topic (or use --self-test)")

    result, warnings = normalize_topics(topics)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for t in result:
        print(t)
    return 0 if not warnings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
