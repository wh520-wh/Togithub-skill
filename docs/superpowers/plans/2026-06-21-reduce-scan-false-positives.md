# 降低 scan.py 误报 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不削弱 danger/warn 真问题检测的前提下，大幅降低 scan.py 的 info 级 org-name-hint 误报洪水，并为邮箱/本地路径/私有 IP 加入占位符白名单。

**Architecture:** 改动集中在 `scripts/scan.py` 单文件。核心三件事：(1) 新增 `ATTRIBUTION_LINE` 门控 + 收紧 `ORG_NAME_HINT` 正则，让 org-name-hint 只在署名行触发；(2) 抽出 `aggregate_info_findings()` 函数对文件扫描和历史扫描的 info 级 finding 做聚合；(3) 在 `scan_line` 的 email/local-path/ipv4-private 命中分支加白名单，白名单命中走 `continue` 不中断同行其他隐私检测。所有改动以 `_self_test` 内的回归用例驱动（TDD），无 pytest，无外部依赖。

**Tech Stack:** Python 3 标准库（re/json/argparse/pathlib），无第三方依赖。测试载体是 `scan.py --self-test`。

**Spec:** `docs/superpowers/specs/2026-06-21-reduce-scan-false-positives-design.md`

**约定：**
- "跑自检"统一指 `python scripts/scan.py --self-test`，在仓库根目录执行。
- 每个任务的"写测试"步骤是往 `_self_test()` 里加 `check_scan_line` / `check_*` 调用；"实现"步骤是改正则/逻辑。
- commit message 用 Conventional Commits，**不带** `Co-Authored-By: Claude`（本 skill 硬性约束）。
- 改完正则必须同步 `references/patterns.md`（硬性约束第 3 条）。

---

## File Structure

只改一个源文件 + 一个文档：

| 文件 | 责任 | 改动 |
|---|---|---|
| `scripts/scan.py` | 唯一可执行扫描器 | 加 `ATTRIBUTION_LINE`、收紧 `ORG_NAME_HINT*`、加白名单常量、加 `aggregate_info_findings()`、`scan_line` 分支改 `continue`、`main()` 调用聚合、`Finding` 加 `count` 字段、`_self_test` 加用例与 helper |
| `references/patterns.md` | 人类可读正则清单 | 同步说明署名行门控、白名单、聚合行为 |

`Finding` dataclass 加 `count: int | None = None` 字段（Task 0），后续聚合任务写入它。

---

## Task 0: 给 Finding 加 count 字段 + 新增 check_scan_line helper

为后续所有任务打地基：`Finding` 加 `count` 字段；`_self_test` 新增 `check_scan_line` helper（跑 `scan_line` 比对 pattern 集合），后续误报用例都靠它。此任务只加结构、不加新正则，所有现有 27 个用例必须仍通过。

**Files:**
- Modify: `scripts/scan.py`（`Finding` dataclass 约 225-234 行；`_self_test` 内）

- [ ] **Step 1: 给 Finding 加 count 字段**

定位 `@dataclass class Finding`（约 225 行），在 `suggestion` 字段后加 `count` 字段：

```python
@dataclass
class Finding:
    category: str           # ai_trace_file | ai_trace_content | privacy_pattern | dangerous_file | large_file
    severity: str           # info | warn | danger
    path: str
    line: int | None = None
    pattern: str | None = None
    snippet: str | None = None
    size_bytes: int | None = None
    suggestion: str = ""
    count: int | None = None
```

- [ ] **Step 2: 在 _self_test 里新增 check_scan_line helper**

在 `_self_test` 内部、现有 `check_pattern` 函数定义之后，新增：

```python
    def check_scan_line(label: str, text: str, expected_patterns: set) -> None:
        """Run scan_line on text and compare the set of matched pattern names.

        expected_patterns is the set of Finding.pattern values expected.
        Empty set means the line should produce NO finding.
        """
        nonlocal passed, failed
        actual = {f.pattern for f in scan_line(text, 1, "test")}
        if actual == expected_patterns:
            passed += 1
            print(f"  PASS  {label}")
        else:
            failed += 1
            print(f"  FAIL  {label}")
            print(f"        expected patterns: {expected_patterns}")
            print(f"        actual patterns:   {actual}")
```

- [ ] **Step 3: 跑自检验证基线不破**

Run: `python scripts/scan.py --self-test`
Expected: `Self-test complete: 27/27 passed, 0 failed.`（新 helper 还没被调用，不影响计数）

- [ ] **Step 4: Commit**

```bash
git add scripts/scan.py
git commit -m "refactor: add count field to Finding and check_scan_line helper"
```

---

## Task 1: org-name-hint 收窄到署名行 + 收紧正则

核心误报治理。先写期望"不报"的失败用例（此刻会 FAIL，因为正文词仍命中），再改正则让它们通过。

**Files:**
- Modify: `scripts/scan.py`（`ORG_NAME_HINT`/`ORG_NAME_HINT_MIT`/`MIT_FOLLOWED_BY_LICENSE` 约 204-219 行；`scan_line` 的 org-name 段约 357-372 行；新增 `ATTRIBUTION_LINE`）

- [ ] **Step 1: 写失败用例（正文词不应命中 org-name-hint）**

在 `_self_test` 的 `[1] Pattern tests` 段末尾、`print()` 之前，加一个新子段。先加"正文词不报"用例（此刻应 FAIL，因为现状会把 metadata 报成 org-name-hint）：

```python
    print()
    print("[1b] org-name-hint attribution gating")
    # 正文词不应触发 org-name-hint
    for word in ["metadata", "metaphor", "apple pie", "viewport",
                 "und mit Liebe", "Google Maps SDK", "Microsoft YaHei",
                 "本项目采用MIT协议"]:
        check_scan_line(f"non-attribution: {word!r}", word, set())
```

- [ ] **Step 2: 跑自检验证上述用例 FAIL**

Run: `python scripts/scan.py --self-test`
Expected: 多个 `FAIL  non-attribution: ...`，因为现状 `metadata`→`org-name-hint`、`und mit Liebe`→`org-name-hint` 等仍命中。（`apple pie`/`viewport` 现状可能已不命中，没关系。）

- [ ] **Step 3: 新增 ATTRIBUTION_LINE 常量**

定位 `ORG_NAME_HINT` 定义之前（约 204 行前），插入：

```python
# A line that looks like an attribution / signature line. org-name-hint and
# real-name-hint only fire on these lines, so that "metadata" / "apple pie" in
# running prose never triggers a company-name hint.
ATTRIBUTION_LINE = re.compile(
    r"^[\s#/*\-]*(?:作者|Author|Maintainer|Owner|Created\s+by|By|by)\s*[:：]?"
)
```

- [ ] **Step 4: 收紧 ORG_NAME_HINT 正则（去 IGNORECASE）**

把现有 `ORG_NAME_HINT`（约 204-210 行）改为去掉 `re.IGNORECASE`。原样保留学校名/公司名内容、`EXCLUDE_CONTEXT` 负向断言，只删 flags 参数：

```python
ORG_NAME_HINT = re.compile(
    r"(?<![A-Za-z0-9])(武汉大学|清华大学|北京大学|复旦大学|上海交通大学|浙江大学|中山大学|华中科技大学)"
    r"|(?<![A-Za-z0-9])(Wuhan\s+University|Tsinghua\s+University|Peking\s+University|Fudan\s+University)"
    r"|(?<![A-Za-z0-9])(Stanford\s+NLP|Berkeley\s+DB)"
    r"|(?<![A-Za-z0-9])(Microsoft|Google|Apple|Amazon|Meta|Tencent|Alibaba|Baidu|Bytedance|Huawei|NetEase|Meituan)(?!" + EXCLUDE_CONTEXT + r")",
)
```

- [ ] **Step 5: 收紧 MIT 规则（去 IGNORECASE + 补无空格变体）**

把 `ORG_NAME_HINT_MIT` 和 `MIT_FOLLOWED_BY_LICENSE`（约 212-219 行）改为：

```python
ORG_NAME_HINT_MIT = re.compile(
    r"(?<![A-Za-z0-9])MIT(?![A-Za-z0-9])",
)
MIT_FOLLOWED_BY_LICENSE = re.compile(
    r"MIT(?:\s*(?:License|许可证|协议|许可))",
)
```

（去掉 `re.IGNORECASE`；`MIT_FOLLOWED_BY_LICENSE` 的 `\s+` 改 `\s*` 以覆盖 `本项目采用MIT协议`。）

- [ ] **Step 6: 在 scan_line 里给 org-name-hint 加署名行门控**

定位 `scan_line` 里的 org-name 段（约 357-372 行）：

```python
    # Org hint (with special-case filters)
    m = ORG_NAME_HINT.search(line)
    org_match = bool(m) or (
        bool(ORG_NAME_HINT_MIT.search(line))
        and not bool(MIT_FOLLOWED_BY_LICENSE.search(line))
    )
    if org_match:
        findings.append(Finding(
            category="privacy_pattern",
            severity="info",
            path=rel,
            line=line_no,
            pattern="org-name-hint",
            snippet=stripped,
            suggestion="确认是否需要匿名化（学校/公司）",
        ))
```

改为先判署名行：

```python
    # Org hint: only on attribution lines (Author/Maintainer/...), so prose
    # words like "metadata" / "apple pie" never trigger it.
    if ATTRIBUTION_LINE.search(line):
        m = ORG_NAME_HINT.search(line)
        org_match = bool(m) or (
            bool(ORG_NAME_HINT_MIT.search(line))
            and not bool(MIT_FOLLOWED_BY_LICENSE.search(line))
        )
        if org_match:
            findings.append(Finding(
                category="privacy_pattern",
                severity="info",
                path=rel,
                line=line_no,
                pattern="org-name-hint",
                snippet=stripped,
                suggestion="确认是否需要匿名化（学校/公司）",
            ))
```

- [ ] **Step 7: 跑自检验证正文词用例通过 + 老用例不破**

Run: `python scripts/scan.py --self-test`
Expected: `[1b]` 子段全 PASS，总数仍 ≥ 27 passed, 0 failed。（注：现有 `check_pattern` 的 org 相关用例若有的话应不受影响，因为它们测的是裸正则；若发现某老用例 FAIL，需具体分析——但本任务未删任何正则分支，不应破老用例。）

- [ ] **Step 8: 补"署名行应命中"用例**

在 `[1b]` 子段里追加正向用例：

```python
    # 署名行应触发 org-name-hint
    check_scan_line("attribution: 张三 Tencent",
                    "Author: 张三 Tencent", {"real-name-hint", "org-name-hint"})
    check_scan_line("attribution: Apple Inc.",
                    "Author: Zhang San, Apple Inc.", {"real-name-hint", "org-name-hint"})
    check_scan_line("attribution: pure org",
                    "Maintainer: Alibaba", {"org-name-hint"})
```

- [ ] **Step 9: 跑自检全绿**

Run: `python scripts/scan.py --self-test`
Expected: 全 PASS，0 failed。

- [ ] **Step 10: Commit**

```bash
git add scripts/scan.py
git commit -m "fix: gate org-name-hint to attribution lines and tighten regex

去掉 ORG_NAME_HINT/MIT 的 IGNORECASE，新增 ATTRIBUTION_LINE 门控，
使 metadata/apple pie/und mit 等正文词不再误报；署名行仍能报。"
```

---

## Task 2: 邮箱白名单

email 命中后按 TLD/保留域名/保留整地址过滤，命中白名单走 `continue` 不中断同行其他隐私。

**Files:**
- Modify: `scripts/scan.py`（新增 `SAFE_EMAIL_*` 常量；`scan_line` email 分支约 327-342 行）

- [ ] **Step 1: 写失败用例（白名单邮箱不应报 email）**

在 `_self_test` 加新子段 `[1c] email whitelist`：

```python
    print()
    print("[1c] email whitelist")
    for addr in ["noreply@github.com", "user@example.com", "foo@test.com",
                 "admin@example.invalid"]:
        check_scan_line(f"safe email: {addr!r}", addr, set())
    # 真实邮箱仍报
    check_scan_line("real email .cn", "zhangsan@realcompany.cn", {"email"})
    check_scan_line("real email apple.com", "zhangsan@apple.com", {"email"})
    # 同行白名单邮箱 + 真手机号：邮箱不报、手机号仍报
    check_scan_line("mixed line keeps phone",
                    "contact: noreply@github.com 或 13812345678", {"phone-cn"})
```

- [ ] **Step 2: 跑自检验证 FAIL**

Run: `python scripts/scan.py --self-test`
Expected: `safe email:` 用例 FAIL（现状全报 email）；`mixed line keeps phone` 可能也 FAIL（现状 break 在 email 上，手机号漏报）。

- [ ] **Step 3: 新增邮箱白名单常量**

在 `PRIVACY_PATTERNS` 定义之前（约 115 行前），插入：

```python
# Email whitelist: addresses that are not real personal emails.
# - Reserved TLDs (RFC 6761/2606): .example .test .invalid .localhost
# - Reserved example domains
# - Specific no-reply addresses
SAFE_EMAIL_TLDS = {".example", ".test", ".invalid", ".localhost"}
SAFE_EMAIL_DOMAINS = {"example.com", "example.org", "example.net", "test.com"}
SAFE_EMAIL_FULL = {"noreply@github.com"}
# When domain is a reserved example domain, these local parts are also placeholders.
SAFE_EMAIL_LOCALS_ON_RESERVED = {
    "user", "foo", "bar", "your-email", "your.email", "email",
    "test", "example", "admin", "noreply",
}


def _is_safe_email(addr: str) -> bool:
    """Return True if addr is a placeholder/example email that should not be reported."""
    addr = addr.strip().lower()
    if addr in SAFE_EMAIL_FULL:
        return True
    if "@" not in addr:
        return False
    local, _, domain = addr.rpartition("@")
    # reserved TLD
    for tld in SAFE_EMAIL_TLDS:
        if domain.endswith(tld):
            return True
    if domain in SAFE_EMAIL_DOMAINS:
        return True
    if domain in {"github.com", "users.noreply.github.com"} and local in SAFE_EMAIL_LOCALS_ON_RESERVED:
        return True
    return False
```

- [ ] **Step 4: 在 scan_line email 分支接入白名单 + 改 continue**

定位 `scan_line` 的隐私循环（约 327-342 行）。现状 email 命中后直接 append 并 `break`。改为：email 命中后先判白名单，白名单则 `continue`（继续试同行其他模式），否则 append 并 `break`。

把这段：

```python
    # Privacy (one match per line — we pick the first/loudest)
    for name, pat in PRIVACY_PATTERNS:
        m = pat.search(line)
        if m:
            # bank-card: reject all-same-digit strings (e.g. 1111111111111111)
            if name == "bank-card" and len(set(m.group())) == 1:
                continue
            findings.append(Finding(
                category="privacy_pattern",
                severity="danger" if name in _DANGER_PRIVACY else "warn",
                path=rel,
                line=line_no,
                pattern=name,
                snippet=stripped,
                suggestion=f"替换为占位符（如 `<{name.upper()}>`）或删除",
            ))
            break
```

改为：

```python
    # Privacy (one match per line — we pick the first/loudest).
    # Whitelisted matches (placeholder emails/paths/IPs) `continue` so other
    # real privacy on the same line is still caught, instead of `break`ing.
    for name, pat in PRIVACY_PATTERNS:
        m = pat.search(line)
        if m:
            # bank-card: reject all-same-digit strings (e.g. 1111111111111111)
            if name == "bank-card" and len(set(m.group())) == 1:
                continue
            if name == "email" and _is_safe_email(m.group()):
                continue
            if name in ("local-path-win", "local-path-unix") and _is_safe_path_user(m):
                continue
            if name == "ipv4-private" and _is_safe_private_ip(m.group()):
                continue
            findings.append(Finding(
                category="privacy_pattern",
                severity="danger" if name in _DANGER_PRIVACY else "warn",
                path=rel,
                line=line_no,
                pattern=name,
                snippet=stripped,
                suggestion=f"替换为占位符（如 `<{name.upper()}>`）或删除",
            ))
            break
```

（`_is_safe_path_user` / `_is_safe_private_ip` 在后续 Task 3/4 定义。**本任务**先只接 email 分支，path/ip 两个 `if` 暂时不要加——为避免引用未定义函数，本步骤先只加 email 那一行 `continue`，path/ip 两行留到 Task 3/4 再加。）

**本任务实际只插入这一行**（在 bank-card continue 之后）：

```python
            if name == "email" and _is_safe_email(m.group()):
                continue
```

- [ ] **Step 5: 跑自检验证 email 用例通过**

Run: `python scripts/scan.py --self-test`
Expected: `[1c]` 全 PASS，老用例不破，0 failed。

- [ ] **Step 6: Commit**

```bash
git add scripts/scan.py
git commit -m "fix: whitelist placeholder/example emails in scan_line

noreply@github.com、example/test/invalid TLD、保留域名不报；
白名单命中走 continue，保证同行真实隐私仍被检测。"
```

---

## Task 3: 本地路径占位用户名白名单

`local-path-win`/`local-path-unix` 加捕获组取用户名段，占位符不报。

**Files:**
- Modify: `scripts/scan.py`（`PRIVACY_PATTERNS` 里两条 local-path 正则约 137-138 行；新增 `_is_safe_path_user`；`scan_line` 接入）

- [ ] **Step 1: 写失败用例**

在 `_self_test` 加 `[1d] local-path whitelist`：

```python
    print()
    print("[1d] local-path whitelist")
    for p in ["/home/user/x", "/home/alice/.ssh", "C:\\Users\\user\\x"]:
        check_scan_line(f"safe path: {p!r}", p, set())
    check_scan_line("real path unix", "/home/zhangsan/x", {"local-path-unix"})
    check_scan_line("real path win", r"C:\Users\zhangsan\x", {"local-path-win"})
```

- [ ] **Step 2: 跑自检验证 FAIL**

Run: `python scripts/scan.py --self-test`
Expected: `safe path:` 用例 FAIL（现状全报）。

- [ ] **Step 3: 给 local-path 正则加捕获组 + 新增 _is_safe_path_user**

定位 `PRIVACY_PATTERNS` 中（约 137-138 行）：

```python
    ("local-path-win", re.compile(r"[A-Z]:\\Users\\[\w\-\. ]+\\", re.IGNORECASE)),
    ("local-path-unix", re.compile(r"/(?:Users|home)/[\w\-\. ]+/")),
```

改为加捕获组（组 1 = 用户名段）：

```python
    ("local-path-win", re.compile(r"[A-Z]:\\Users\\([\w\-\. ]+)\\", re.IGNORECASE)),
    ("local-path-unix", re.compile(r"/(?:Users|home)/([\w\-\. ]+)/")),
```

在 `_is_safe_email` 函数之后新增：

```python
# Placeholder usernames in example local paths.
SAFE_PATH_USERS = {
    "user", "username", "user-name", "alice", "bob", "foo", "bar",
    "yourname", "your-name", "name", "project", "app", "home",
    "example", "default", "guest", "admin", "test",
}


def _is_safe_path_user(m: re.Match) -> bool:
    """True if the matched local path's user segment is a placeholder."""
    try:
        user = m.group(1).lower()
    except (IndexError, AttributeError):
        return False
    return user in SAFE_PATH_USERS
```

- [ ] **Step 4: 在 scan_line 接入 path 白名单**

在 Task 2 Step 4 插入的 email `continue` 行之后，加：

```python
            if name in ("local-path-win", "local-path-unix") and _is_safe_path_user(m):
                continue
```

- [ ] **Step 5: 跑自检验证通过**

Run: `python scripts/scan.py --self-test`
Expected: `[1d]` 全 PASS，0 failed。

- [ ] **Step 6: Commit**

```bash
git add scripts/scan.py
git commit -m "fix: whitelist placeholder usernames in local-path scan

/home/user、C:\\Users\\user 等教科书示例路径不报；真实用户名仍报。"
```

---

## Task 4: 私有 IP 教科书默认值白名单

`ipv4-private` 命中后，完整 IP 在默认网关集合内则不报。

**Files:**
- Modify: `scripts/scan.py`（新增 `SAFE_PRIVATE_IPS` + `_is_safe_private_ip`；`scan_line` 接入）

- [ ] **Step 1: 写失败用例**

在 `_self_test` 加 `[1e] ipv4-private whitelist`：

```python
    print()
    print("[1e] ipv4-private whitelist")
    for ip in ["192.168.0.1", "192.168.1.1", "10.0.0.1", "10.0.0.2"]:
        check_scan_line(f"safe ip: {ip!r}", ip, set())
    check_scan_line("real private ip", "192.168.1.100", {"ipv4-private"})
```

- [ ] **Step 2: 跑自检验证 FAIL**

Run: `python scripts/scan.py --self-test`
Expected: `safe ip:` 用例 FAIL（现状全报）。

- [ ] **Step 3: 新增 SAFE_PRIVATE_IPS + _is_safe_private_ip**

在 `_is_safe_path_user` 之后新增：

```python
# Default-gateway / generic private IPs that are textbook examples, not leaks.
SAFE_PRIVATE_IPS = {"192.168.0.1", "192.168.1.1", "10.0.0.1", "10.0.0.2"}


def _is_safe_private_ip(ip_str: str) -> bool:
    return ip_str in SAFE_PRIVATE_IPS
```

- [ ] **Step 4: 在 scan_line 接入 ip 白名单**

在 Task 3 Step 4 插入的 path `continue` 行之后，加：

```python
            if name == "ipv4-private" and _is_safe_private_ip(m.group()):
                continue
```

- [ ] **Step 5: 跑自检验证通过**

Run: `python scripts/scan.py --self-test`
Expected: `[1e]` 全 PASS，0 failed。

- [ ] **Step 6: Commit**

```bash
git add scripts/scan.py
git commit -m "fix: whitelist textbook default-gateway private IPs

192.168.0.1 等默认网关不报；真实内网主机 IP 仍报。"
```

---

## Task 5: info 级聚合函数 aggregate_info_findings

抽出聚合函数，按 `(path, pattern)` 合并 info 级 finding，写入 `count`。先单元测试该函数，再在 Task 6 接入 main。

**Files:**
- Modify: `scripts/scan.py`（新增 `aggregate_info_findings` 函数，放 `scan_line` 之后约 375 行处；`_self_test` 加用例）

- [ ] **Step 1: 写失败用例（聚合函数单元测试）**

在 `_self_test` 的 `[2] File scan integration test` 段之前，加新段 `[1f] aggregate_info_findings`：

```python
    print()
    print("[1f] aggregate_info_findings")
    raw = [
        Finding(category="privacy_pattern", severity="info", path="a.py",
                line=1, pattern="org-name-hint", snippet="Author: Tencent"),
        Finding(category="privacy_pattern", severity="info", path="a.py",
                line=2, pattern="org-name-hint", snippet="Author: Alibaba"),
        Finding(category="privacy_pattern", severity="info", path="a.py",
                line=3, pattern="real-name-hint", snippet="Author: Zhang San"),
        Finding(category="privacy_pattern", severity="warn", path="a.py",
                line=4, pattern="email", snippet="real@x.cn"),
        Finding(category="privacy_pattern", severity="info", path="b.py",
                line=1, pattern="org-name-hint", snippet="Author: Baidu"),
    ]
    agg = aggregate_info_findings(raw)
    # info 按 (path,pattern) 聚合：a.py/org-name-hint 合并为1条 count=2
    a_org = [f for f in agg if f.path == "a.py" and f.pattern == "org-name-hint"]
    check("a.py org-name-hint aggregated to 1", len(a_org), 1)
    check("a.py org-name-hint count==2", a_org[0].count if a_org else None, 2)
    check("a.py org-name-hint keeps first line", a_org[0].line if a_org else None, 1)
    # real-name-hint 单条也走聚合路径（count=1）
    a_name = [f for f in agg if f.path == "a.py" and f.pattern == "real-name-hint"]
    check("a.py real-name-hint count==1", a_name[0].count if a_name else None, 1)
    # warn 不聚合，原样保留
    check("warn email not aggregated",
          sum(1 for f in agg if f.severity == "warn"), 1)
    # b.py 独立
    check("b.py org-name-hint present",
          sum(1 for f in agg if f.path == "b.py" and f.pattern == "org-name-hint"), 1)
```

- [ ] **Step 2: 跑自检验证 FAIL**

Run: `python scripts/scan.py --self-test`
Expected: `NameError: name 'aggregate_info_findings' is not defined`（函数还没写）。

- [ ] **Step 3: 实现 aggregate_info_findings**

在 `scan_line` 函数之后（约 375 行、`scan_history` 之前）新增：

```python
def aggregate_info_findings(findings: list[Finding]) -> list[Finding]:
    """Merge info-severity findings sharing the same (path, pattern) into one.

    Non-info findings pass through unchanged. The merged finding keeps the
    first occurrence's line/snippet/suggestion and sets `count` to the number
    merged. Order: non-info findings keep original relative order; info
    findings are emitted at the position of their first occurrence.
    """
    result: list[Finding] = []
    seen: dict[tuple[str, str | None], int] = {}  # (path, pattern) -> index in result
    for f in findings:
        if f.severity != "info" or f.pattern is None:
            result.append(f)
            continue
        key = (f.path, f.pattern)
        if key in seen:
            idx = seen[key]
            result[idx].count = (result[idx].count or 1) + 1
        else:
            seen[key] = len(result)
            f_copy = Finding(**asdict(f))
            f_copy.count = 1
            result.append(f_copy)
    return result
```

- [ ] **Step 4: 跑自检验证通过**

Run: `python scripts/scan.py --self-test`
Expected: `[1f]` 全 PASS，0 failed。

- [ ] **Step 5: Commit**

```bash
git add scripts/scan.py
git commit -m "feat: add aggregate_info_findings to dedupe info-level hints

同一 (path,pattern) 的 info 级 finding 合并为一条带 count；
warn/danger 不聚合。"
```

---

## Task 6: 在 main 接入聚合（文件扫描 + 历史扫描）

把 `aggregate_info_findings` 分别作用于文件扫描结果和历史扫描结果。历史 path 形如 `commit:<sha>:<file>:<line>`，需先按 `commit:<sha>:<file>` 归一化再聚合，归一化通过临时改 path 实现。

**Files:**
- Modify: `scripts/scan.py`（`main` 的聚合接入约 681-732 行；新增历史 path 归一化逻辑）

- [ ] **Step 1: 写文件级聚合集成用例**

在 `_self_test` 的 `[2] File scan integration test` 段内、`check("safe.txt has no findings", ...)` 之前，加一个多行署名文件的聚合断言。先在 fixture 创建处（约 582 行 `(tmpdir / "README.md")...` 之后）加：

```python
        (tmpdir / "CREDITS.md").write_text(
            "Author: Zhang San Tencent\n"
            "Author: Li Si Tencent\n"
            "Author: Wang Wu Tencent\n"
        )
```

然后在断言区（`check("safe.txt has no findings", ...)` 之前）加：

```python
        check("CREDITS.md org-name-hint aggregated to 1",
              sum(1 for f in findings if f.path == "CREDITS.md"
                  and f.pattern == "org-name-hint"), 1)
        cred = [f for f in findings if f.path == "CREDITS.md"
                and f.pattern == "org-name-hint"]
        check("CREDITS.md org-name-hint count==3",
              cred[0].count if cred else None, 3)
```

- [ ] **Step 2: 跑自检验证 FAIL**

Run: `python scripts/scan.py --self-test`
Expected: `CREDITS.md org-name-hint aggregated to 1` FAIL（现状是 3 条，因为还没接入聚合）。

- [ ] **Step 3: 在 main 文件扫描后接入聚合**

定位 `main` 中文件扫描与历史扫描的合并处（约 681-732 行）。现状：

```python
    findings: list[Finding] = []

    # File scan
    if not args.history_only:
        seen_dirs: set[str] = set()
        for p in iter_files(root):
            ...
            if is_scannable(p):
                findings.extend(scan_file_content(p, rel))

    # History scan
    if args.scan_history or args.history_only:
        findings.extend(scan_history(root, max_commits=args.max_commits))
```

改为：文件扫描先收集到独立列表 `file_findings`，聚合后再 extend 到 `findings`；历史扫描同理，但先把每条 info finding 的 path 归一化到 `commit:<sha>:<file>` 再聚合。

```python
    findings: list[Finding] = []

    # File scan
    if not args.history_only:
        seen_dirs: set[str] = set()
        file_findings: list[Finding] = []
        for p in iter_files(root):
            rel = str(p.relative_to(root))

            if any(pat.search(rel) for pat in excludes):
                continue

            try:
                sz = p.stat().st_size
            except OSError:
                continue

            if sz > LARGE_FILE_BYTES:
                file_findings.append(Finding(
                    category="large_file",
                    severity="warn",
                    path=rel,
                    size_bytes=sz,
                    suggestion="考虑加入 .gitignore / git-lfs / 拆分",
                ))

            if match_dangerous_file(rel):
                file_findings.append(Finding(
                    category="dangerous_file",
                    severity="danger",
                    path=rel,
                    size_bytes=sz,
                    suggestion="绝不推送：加入 .gitignore 或改用环境变量",
                ))

            if match_ai_trace_file(rel):
                top = rel.split("/", 1)[0] if "/" in rel else rel
                if top not in seen_dirs:
                    seen_dirs.add(top)
                    file_findings.append(Finding(
                        category="ai_trace_file",
                        severity="warn",
                        path=top,
                        suggestion="删除整个目录/文件（AI 协作痕迹或开发过程文件）",
                    ))
                continue

            if is_scannable(p):
                file_findings.extend(scan_file_content(p, rel))

        findings.extend(aggregate_info_findings(file_findings))

    # History scan
    if args.scan_history or args.history_only:
        hist_findings = scan_history(root, max_commits=args.max_commits)
        # Normalize history info-finding paths from commit:<sha>:<file>:<line>
        # to commit:<sha>:<file> so multi-line hints in one file aggregate.
        for f in hist_findings:
            if f.severity == "info" and f.path.startswith("commit:"):
                parts = f.path.split(":")
                # parts: [commit, <sha>, <file>, <line>...]
                if len(parts) >= 3:
                    f.path = ":".join(parts[:3])
        findings.extend(aggregate_info_findings(hist_findings))
```

- [ ] **Step 4: 跑自检验证文件聚合用例通过**

Run: `python scripts/scan.py --self-test`
Expected: `[2]` 段 `CREDITS.md` 聚合断言 PASS，全 0 failed。

- [ ] **Step 5: 写历史聚合手动验证脚本**

历史扫描无法在 `_self_test` 里造 git 仓库（成本高），用一个独立的一次性验证：在本项目跑历史扫描，肉眼确认 info 项被聚合。先跑基线命令记录聚合前后的 info 数量对比：

Run: `python scripts/scan.py . --history-only --max-commits 50 > /tmp/hist.json 2>&1; python -c "import json; d=json.load(open('/tmp/hist.json')); s=d['summary']['by_severity']; print(s)"`
Expected: 能正常输出 severity 计数字典，不报错。（info 数应明显小于"每行一条"，证明历史也聚合了。）

- [ ] **Step 6: Commit**

```bash
git add scripts/scan.py
git commit -m "feat: apply info aggregation to file and history scans

文件扫描与历史扫描结果分别经 aggregate_info_findings 聚合；
历史 info path 归一化到 commit:<sha>:<file> 以跨行聚合。"
```

---

## Task 7: 同步 references/patterns.md + 本项目自检 + SKILL.md 文案核对

硬性约束：正则改了文档必须同步。最后整体回归。

**Files:**
- Modify: `references/patterns.md`

- [ ] **Step 1: 更新 patterns.md 的"姓名/组织名提示"小节**

定位 `references/patterns.md` 的 `## 姓名/组织名提示` 小节（约 86-91 行）。在末尾追加一段说明署名行门控：

```markdown

**署名行门控（2026-06 改动）**：`org-name-hint` 与 `real-name-hint` **只在署名行上触发**。署名行定义为行首匹配 `^[\s#/*\-]*(?:作者|Author|Maintainer|Owner|Created\s+by|By|by)\s*[:：]?`。正文里的 `metadata`/`apple pie`/`und mit`/`Google Maps SDK` 不再误报。`ORG_NAME_HINT` 与 `MIT` 规则已去掉大小写不敏感，按真实大小写匹配。
```

- [ ] **Step 2: 更新 patterns.md 的隐私模式表，加白名单说明**

定位 `## 隐私模式` 小节末尾（约 84 行后），追加：

```markdown

**占位符白名单（2026-06 改动，命中不报）**：
- `email`：保留 TLD（`.example`/`.test`/`.invalid`/`.localhost`）、保留域名（`example.com`/`example.org`/`example.net`/`test.com`）、`noreply@github.com`。真实邮箱（含 `apple.com`）仍按 warn 报。
- `local-path-win`/`local-path-unix`：用户名段为占位符（`user`/`alice`/`foo`/`default`/`guest` 等）时不报；真实用户名仍报。
- `ipv4-private`：默认网关（`192.168.0.1`/`192.168.1.1`/`10.0.0.1`/`10.0.0.2`）不报；其余私有 IP 仍报。
- 白名单命中走 `continue`，**不中断**同行其他真实隐私的检测。
```

- [ ] **Step 3: 更新 patterns.md 的历史扫描小节，提聚合**

定位 `## 历史扫描` 小节（约 110-120 行），在末尾追加：

```markdown

**info 级聚合（2026-06 改动）**：文件扫描与历史扫描的 `info` 级 finding 按 `(path, pattern)` 聚合成一条（带 `count` 字段）。历史 path 归一化到 `commit:<sha>:<file>` 再聚合。`warn`/`danger` 不聚合。
```

- [ ] **Step 4: 跑完整自检**

Run: `python scripts/scan.py --self-test`
Expected: 全 PASS，0 failed。

- [ ] **Step 5: 在本项目自检（反证不再洪水）**

Run: `python scripts/scan.py . 2>&1 | python -c "import sys,json; d=json.load(sys.stdin); print(d['summary'])"`
Expected: `by_category` 中 `privacy_pattern` 的 info 项大幅下降；不再有大量 `org-name-hint` 命中 `metadata` 之类。记下实际数字贴回 PR 描述。

- [ ] **Step 6: 核对 SKILL.md Step 4 文案**

读 `SKILL.md` 的 Step 4（报告 + 确认）章节。若其措辞假设"每个 info 项逐条列出"，改为体现"info 项已按文件聚合，每类一条带次数"。**只改文案，不改流程**。若原文案已足够通用则不动，并在 commit message 注明"无需改动"。

- [ ] **Step 7: Commit**

```bash
git add references/patterns.md SKILL.md
git commit -m "docs: sync patterns.md with scan.py false-positive reductions

说明署名行门控、邮箱/路径/IP 白名单、info 聚合行为；
按需微调 SKILL.md Step 4 文案。"
```

---

## Self-Review 结果

**1. Spec coverage 核对：**

| Spec 条目 | 对应 Task |
|---|---|
| §1 org-name-hint 署名行门控 + 收紧正则 + MIT 无空格变体 | Task 1 |
| §1 EXCLUDE_CONTEXT 不修（保留原样） | Task 1 Step 4 保留 EXCLUDE_CONTEXT 负向断言不动 |
| §2 info 聚合（文件+历史，抽函数，count 字段，首条 line/snippet） | Task 5（函数）+ Task 6（接入）+ Task 0（count 字段） |
| §3 邮箱白名单（TLD/域名/整地址，apple.com 不在内，continue） | Task 2 |
| §4 本地路径占位用户名白名单（含 default/guest/admin/test，捕获组） | Task 3 |
| §5 私有 IP 白名单（无 0.0.0.0 死代码，无需新捕获组） | Task 4 |
| §6 自检 check_scan_line helper + 反向/正向/聚合/同行多隐私用例 | Task 0（helper）+ 各 Task 用例 + Task 5/6 聚合用例 |
| §6 文档同步 patterns.md | Task 7 |
| §6 SKILL.md 文案核对 | Task 7 Step 6 |
| §验收 1-7 | Task 7 Step 4-5 跑自检+本项目自检验证 1/2/4/5；Task 6 Step 5 验证 3（历史聚合）；Task 2 用例验证 6（同行多隐私）；Task 7 验证 7（文档一致） |

无遗漏。

**2. Placeholder scan：** 无 TBD/TODO；每个代码步骤都给了完整代码。

**3. Type consistency：**
- `Finding.count` 在 Task 0 定义为 `int | None = None`，Task 5 聚合写入 int，Task 6 不涉及。
- `aggregate_info_findings(findings) -> list[Finding]` 签名在 Task 5 定义、Task 6 调用一致。
- `_is_safe_email(addr: str) -> bool`、`_is_safe_path_user(m: re.Match) -> bool`、`_is_safe_private_ip(ip_str: str) -> bool` 三者在 Task 2/3/4 定义、在 `scan_line` 调用名一致。
- `ATTRIBUTION_LINE` 在 Task 1 Step 3 定义、Step 6 调用名一致。
- local-path 正则捕获组组 1，`_is_safe_path_user` 用 `m.group(1)` 一致。

**4. 顺序依赖：** Task 0 必须先（提供 count 字段与 helper）；Task 1-4 互相独立可任意序（但都依赖 Task 0 的 helper）；Task 5 依赖 Task 0 的 count 字段；Task 6 依赖 Task 5 的函数；Task 7 最后。当前编号顺序满足依赖。
