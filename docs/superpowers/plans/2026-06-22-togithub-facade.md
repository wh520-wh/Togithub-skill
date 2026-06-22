# Togithub 门面装饰优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `/Togithub` skill 增加门面装饰能力——推送前生成体面的 README（两阶段：起草→扫描清理→刷新），推送后用 `gh` 设置仓库描述和 topics。

**Architecture:** 改 `SKILL.md`（指令手册，插 Step 6.5/6.6/7.5 三节 + 重写 Step 2a 时序 + 流程总览）+ 新增 `scripts/normalize_topics.py`（topics 归一化校验，标准库，含 `--self-test`）。README 生成是 agent 层逻辑，不沉淀成脚本；topics 归一化是确定性规则，沉淀成脚本兜底。scan.py 不动。

**Tech Stack:** Python 3.9+（标准库 argparse/sys/re）、Markdown（README/SKILL.md）、`gh` CLI（仓库设置）。

**项目特殊性（重要）：** 本项目是 Claude Code Skill，**没有 pytest、没有 CI、没有构建系统**。验证方式沿用 `scan.py` 的 `--self-test` 自检模式 + 人工程读 + 实跑 skill 流程。计划里的「测试」步骤用 `python scripts/xxx.py --self-test`，不写 pytest 文件。

**spec 出处：** `docs/superpowers/specs/2026-06-22-togithub-facade-design.md`

**v2 修订（按对抗式审查）：** 修复 v1 的致命时序缺陷——重写 Step 2a 把 commit/push defer 到 Step 7、在落盘与扫描之间插入 6.5 钩子；新增流程总览 Task；修 normalize_topics.py 中文 bug；修 markdown 围栏嵌套；修 6.6 与用户清理决策冲突；显式退出码语义；合并碎 commit。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `scripts/normalize_topics.py` | topics 归一化校验（ASCII-only、连字符、长度、去重、≤20） | 新建 |
| `SKILL.md` | skill 指令手册 | 改：流程总览 + Step 2a/2b 时序重写 + 插 6.5/6.6/7.5 + Step 9/硬性规则/边界/测试/文件清单 |
| `scripts/scan.py` | 扫描脚本 | 不动 |
| `references/patterns.md` | 正则文档 | 不动 |

---

## Task 1: 新增 `scripts/normalize_topics.py` 归一化脚本

**Files:**
- Create: `scripts/normalize_topics.py`

**说明：** 新增确定性脚本，带 `--self-test`。用 argparse（与 scan.py 一致）。ASCII-only 判定（v1 的 `c.isalnum()` 会放行中文，已修）。退出码：0=无改动或 self-test 通过；1=有归一化改动（常态，非失败）；2=用法错误（真失败）。支持 argv + stdin。

- [ ] **Step 1: 写脚本主体**

创建 `scripts/normalize_topics.py`：

```python
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
    t = re.sub(r"[^a-z0-9-]", "-", t)
    # collapse consecutive hyphens
    while "--" in t:
        t = t.replace("--", "-")
    # strip leading/trailing hyphens
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
            if re.sub(r"[^a-z0-9-]", "-", original.lower()).strip("-") != original:
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
        topics += sys.stdin.read().split()

    if not topics:
        print("usage: normalize_topics.py <topic1> <topic2> ...", file=sys.stderr)
        return 2

    result, warnings = normalize_topics(topics)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for t in result:
        print(t)
    return 0 if not warnings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 2: 跑自检验证通过**

Run: `python scripts/normalize_topics.py --self-test`
Expected: 输出 `all self-tests passed`，退出码 0。

- [ ] **Step 3: 手动验证几条真实输入**

Run: `python scripts/normalize_topics.py Python "Web Scraper" C++ machine_learning`
Expected stdout:
```
python
web-scraper
c
machine-learning
```
Expected stderr 含 `warning: 'C++' -> 'c'`，退出码 1（有改动告警，正常非失败）。

- [ ] **Step 4: 验证非 ASCII 被拒**

Run: `python scripts/normalize_topics.py 数据 Python`
Expected stdout: 只有 `python`（`数据` 被归一化为空、丢弃）
Expected stderr 含 `warning: '数据' -> rejected`，退出码 1。

- [ ] **Step 5: 提交**

```bash
git add scripts/normalize_topics.py
git commit -m "feat: add normalize_topics.py for GitHub topics normalization"
```

---

## Task 2: SKILL.md 写「流程总览」+ 重写 Step 2a/2b 时序

**Files:**
- Modify: `SKILL.md`（「## 流程」节、Step 2a、Step 2b）

**说明：** 修复 v1 致命缺陷 F1/F2。现有 Step 2a 内联代码块把 `.gitignore/LICENSE 落盘 → 扫描 → commit → push` 全做了，导致 Step 6.5 永远插不进扫描之前。本任务：(1) 在「## 流程」节顶部写两条执行顺序总览；(2) 重写 Step 2a——把内联的 commit/push 拆出来 defer 到 Step 7，在「落盘 .gitignore/LICENSE」和「Step 3 扫描」之间显式插入「执行 Step 6.5 起草 README」钩子；(3) Step 2b 同理加 6.5 钩子；(4) Step 2a 去掉单独问描述、`gh repo create` 去 `--description`。

这是整个门面时序能成立的前提，必须先于 Task 3/4/5 完成。

- [ ] **Step 1: 在「## 流程」节写执行顺序总览**

读 `SKILL.md`，找到「## 流程」节（约第 37-40 行）：

```
## 流程

按顺序执行，每步结果决定下一步。
```

改成：

```
## 流程

按顺序执行，每步结果决定下一步。

### 执行顺序总览（含门面装饰）

门面装饰插入后，两条路径的完整执行顺序：

**新建仓库路径（Step 2a）**：
```
Step 1 摸状态 → Step 2a 选配置(名/可见性/LICENSE/gitignore) → 落盘 .gitignore + LICENSE + Step 6.5 README 草稿 → Step 3 扫描(含 README) → Step 4/5 确认清理 → Step 6.6 刷新 README → Step 7 commit/push → Step 7.5 设描述+topics → Step 8/9
```

**更新已有仓库路径（Step 2b）**：
```
Step 1 摸状态 → Step 2b 问要不要重写 README(要则 Step 6.5 落盘草稿) → Step 3 扫描 → Step 4/5 确认清理 → Step 6.6 刷新 README(若重写过) → Step 7 commit/push → Step 7.5 问要不要更新描述/topics → Step 8/9
```

关键：README 草稿必须在 Step 3 扫描**之前**落盘，否则其自身成为扫描盲区。
```

- [ ] **Step 2: 重写 Step 2a——拆内联 commit/push、插 6.5 钩子、去描述**

读 `SKILL.md`，找到整个 Step 2a 节（约第 62-91 行）。整节替换为：

````markdown
### Step 2a: 新建仓库

问用户（用 AskUserQuestion）：

1. **仓库名**（默认用当前目录名）
2. **公开/私有**（**每次都强制问**，不要默认 public——误推私会出事）
3. **LICENSE**（MIT / Apache-2.0 / GPL-3.0 / BSD-3-Clause / 不生成）
4. **是否生成 .gitignore**（按项目类型自动生成 / 我自己提供 / 不要）

> 仓库描述不在这一步问——会在 Step 6.5 生成 README 时确认一句话介绍，Step 7.5 统一设置。避免描述被设两次。

**⚠️ 关键顺序**（严格遵守，否则门面和扫描都会失效）：

```bash
# 1. 仅当状态 A 时初始化
git init

# 2. 落盘 .gitignore 和 LICENSE（按用户选择生成，模板见 references/gitignore-templates.md 和 assets/license-*.txt）

# 3. 执行 Step 6.5 起草 README 草稿并落盘（与 .gitignore/LICENSE 同批）
#    ——必须在 Step 3 扫描之前，否则 README 自身成扫描盲区

# 4. 走 Step 3 扫描 + Step 4 确认 + Step 5 清理（扫描覆盖 .gitignore/LICENSE/README）

# 5. 执行 Step 6.6 刷新 README（清理后回填目录树、修被占位坏掉的示例）

# 6. 提交（Step 7）
git add .
git commit -m "chore: initial commit"

# 7. 最后才创建远程仓库并推送（Step 7）
gh repo create <name> --<public|private> --source=. --remote=origin
```

**注意**：`gh repo create --source=.` 会在本地已提交后直接 push 现有 commits，不再重复 commit，也不带 `--description`（描述统一在 Step 7.5 设）。**绝不能先跑 `gh repo create`**，它会隐式 `git init && add -A && commit`，绕过扫描、绕过 .gitignore、绕过 README 起草，吞掉 `.env`/大文件。
````

- [ ] **Step 3: Step 2b 加 6.5 钩子**

读 `SKILL.md`，找到 Step 2b 节（约第 93-101 行）：

```bash
git status            # 看未提交改动
git log --oneline -5  # 看最近 commits（初判有没有 Co-Authored-By）
git fetch origin      # 同步远端
```

```
进入 Step 3 清理后再 add/commit/push。
```

把「进入 Step 3 清理后再 add/commit/push。」那句改成：

```
进入 Step 3 清理后再 add/commit/push。

> 门面：更新路径下，先执行 Step 6.5 问「要不要重写 README」，要重写则落盘草稿（在 Step 3 扫描之前）；Step 3 扫描 → Step 5 清理后执行 Step 6.6 刷新 README（若重写过）；Step 7 push 后执行 Step 7.5 问「要不要更新描述/topics」。详见「执行顺序总览」。
```

- [ ] **Step 4: 程读确认时序结构成立**

人工程读确认：
1. 「## 流程」节有两条执行顺序总览，都写明「README 草稿在 Step 3 扫描之前落盘」。
2. Step 2a 内联流程的顺序是：`git init → 落盘 .gitignore/LICENSE → Step 6.5 README 草稿 → Step 3 扫描 → Step 5 清理 → Step 6.6 刷新 → Step 7 commit/push`。**没有**在内联里提前 commit/push（push 已 defer 到 Step 7）。
3. Step 2a 询问清单 4 项、`gh repo create` 无 `--description`。
4. Step 2b 末尾有 6.5 钩子引用。

- [ ] **Step 5: 提交**

```bash
git add SKILL.md
git commit -m "refactor: rewrite Step 2a/2b timing for facade + execution overview"
```

---

## Task 3: SKILL.md 一次性插 Step 6.5/6.6/7.5 + 补 Step 9/规则/边界/测试/清单

**Files:**
- Modify: `SKILL.md`

**说明：** 按 spec 建议（单 commit）合并 v1 的碎 commit（避免中间态引用悬空）。一次性插完 6.5/6.6/7.5 三节，并补 Step 9 报告、硬性规则 8/9、边界「可做/不做」、测试节、文件清单。markdown 围栏：插入新节时外层不用 fence 包裹（直接给原文），避免围栏嵌套问题（v1 I3）。

- [ ] **Step 1: 在 Step 6 节之后插入 Step 6.5 节**

读 `SKILL.md`，找到 Step 6 节末尾（`LICENSE` 模板见 `assets/license-<name>.txt`，直接拷贝到 `LICENSE` 文件。` 那句，约第 198 行）。在该句之后、`### Step 7` 之前，插入以下内容（直接原文，不用 fence 包裹）：

---

### Step 6.5: 门面装饰·README 起草

**执行时机**：见「执行顺序总览」——新建路径在落盘 .gitignore/LICENSE 之后、Step 3 扫描之前；更新路径在 Step 2b 之后、Step 3 扫描之前（先问要不要重写）。README 草稿与 .gitignore/LICENSE 同批落盘，一起进 Step 3 扫描——这样 AI 不慎写进 README 的邮箱/本地路径会被扫描器抓出来，在 Step 5 清理、Step 6.6 刷新。

**触发条件**：
- 新建仓库路径（Step 2a）：自动执行。
- 更新已有仓库路径（Step 2b）：先问「要不要重写 README」，默认不动。

**已有 README 检测**：检测根目录及 `docs/` 下的 README 文件（`README.md` / `README.rst` / `README` / `README.markdown` / `README.txt` / `README.zh.md` / `README.cn.md`，大小写不敏感）。多处存在时优先根目录。检测到则问用户「保留 / 重写」。

**重写前备份**：判断 README 是否已被 git 跟踪（`git ls-files <README路径>` 有输出即已跟踪）：
- 已跟踪：可直接重写，内容可从 git 历史恢复。
- 未跟踪：先备份为 `README.bak.md`，再重写。报告里提示「原 README 已备份为 README.bak.md，确认无误后可删除」。

无 README 时直接走生成流程。

**起草流程**：

1. **AI 读代码起草**（读码范围有界，避免大项目读爆 context）：
   - 必读：入口文件（`main.py`/`index.js`/`app.py`/`main.go` 等）、依赖清单（`requirements.txt`/`package.json`/`go.mod`/`Cargo.toml` 等）、顶层目录结构、现有 README/文档。
   - 按需：配置文件、CLI 参数定义。

2. **合并确认**（用**一次** `AskUserQuestion` 多字段问询，不逐子项问）：
   - 项目一句话介绍（AI 给草稿，用户可改）
   - 核心功能亮点 2–4 条（AI 从代码推断，用户勾选/增删）
   - README 语言（AI 判定，用户确认）

3. 用户确认后，AI 生成 README 草稿落盘。

**README 语言判定**：
- 有代码注释：按注释主体语言判定。
- 无注释/无法判定（纯数据、配置项目、空仓库）：默认中文，在确认问询里让用户可改。
- 中英混合：按注释主体语言；旗鼓相当时默认中文并让用户确认。

**README 结构模板**（固定骨架）：

```markdown
# <项目名>

<一句话介绍>

## 功能
- <亮点 1>
- <亮点 2>

## 安装
<从依赖清单+入口文件推断的最小安装步骤>

## 使用
<从代码/CLI 参数推断的最小用法；推断不准留占位让用户填>

## 目录结构
<占位：Step 6.6 清理后回填定稿>

## License
<见下文分支>
```

**License 章节分支**：
- 用户在 Step 2a 选了 LICENSE（MIT/Apache-2.0/...）：写「本项目采用 <LICENSE> 协议，详见 [LICENSE](LICENSE)」。
- 用户选了「不生成」：写「License: 待定」并留占位提示让用户填。

**风格约束**：不堆 badge，不放截图占位，不造图。推断不准的章节留简短占位提示让用户填，不编造内容。

---

- [ ] **Step 2: 在 Step 6.5 节之后插入 Step 6.6 节**

在 Step 6.5 节末尾（`**风格约束**：不堆 badge……不编造内容。` 那句）之后、`### Step 7` 之前，插入以下内容：

---

### Step 6.6: 门面装饰·README 刷新

**执行时机**：在 Step 5（应用清理）之后、Step 7（commit）之前。**仅当 Step 6.5 生成/重写了 README 草稿时执行**；若用户在 6.5 选了「保留原 README」则跳过本步。

**刷新内容**：

1. **目录树回填**：清理可能删除了 `.claude/`、`task_plan.md`、`findings.md`、`progress.md` 等文件。重新扫描目录，把「## 目录结构」章节回填为清理后的真实两级树，**不列已删文件**。

2. **README 清理可读性复核**：Step 5 把扫描命中的隐私行按 scan.py suggestion 替换为 `<REDACTED>` 类占位——这对代码合理，对 README 说明性示例会坏掉可读性（如 `python main.py --config <LOCAL-PATH-WIN>`）。
   - **仅把 Step 5 产生的 `<REDACTED>` 类默认占位**（即用户在 Step 4 没特别指定、走默认替换的那些行）改写为通用占位示例：
     - 本地路径 → `/path/to/config.ini` 或 `./config.ini`
     - 邮箱 → `you@example.com`
     - 手机 → `13800000000`
     - API key → `your-api-key-here`
   - **用户在 Step 4 选了「保留」或给了自定义占位的行，6.6 不动**——尊重用户的清理决策。
   - 刷新后通读一遍 README，确认示例行仍读得通。

---

- [ ] **Step 3: 在 Step 7 节之后插入 Step 7.5 节**

读 `SKILL.md`，找到 Step 7 节末尾（`git push origin <branch>  # 或 git push -u origin main（首次）` 那段，约第 218 行）。在该段之后、`### Step 8` 之前，插入以下内容：

---

### Step 7.5: 门面装饰·仓库层（描述 + topics）

**执行时机**：在 Step 7（push）之后、Step 8（EXE/Release）之前。**Step 7 push 失败则跳过本步**，直接进 Step 9 报告失败——仓库不存在时 `gh repo edit` 必然失败，不白跑。

**触发条件**：
- 新建仓库路径：push 成功后自动执行。
- 更新已有仓库路径：先问「要不要顺便更新仓库描述/topics」，说要才跑。

**仓库描述（description）**：

来源（统一，不重复问、不做「对比哪个准」的主观判断）：
- 新建路径：复用 Step 6.5 里用户确认过的「项目一句话介绍」。
- 更新路径：读现有 README 第一段作草稿，用 `AskUserQuestion` 让用户确认或改。

设置：
```bash
gh repo edit <owner>/<repo> --description "<描述>"
```
**shell 转义**：描述若含 `"`/`$`/反引号等 shell 元字符，用单引号包裹或经 gh 参数传递避免展开；设置前校验内容。

**topics 话题标签**：

来源：AI 推断 + 用户勾选。

1. AI 读代码推断候选 topics：主语言（`python`/`typescript`/`go`…）、框架/依赖名（`customtkinter`/`fastapi`/`react`…）、项目类型词（`automation`/`cli`/`gui`/`web-scraper`…），凑 4–8 个候选。
2. 用 `AskUserQuestion` 把候选列出来让用户多选勾选，也可自己补。
3. 用户选完，经 `normalize_topics.py` 归一化校验：
   ```bash
   python "$HOME/.claude/skills/Togithub/scripts/normalize_topics.py" <topic1> <topic2> ...
   ```
   **退出码语义**：0=无改动；1=有归一化改动（**正常，非失败**，仍取 stdout 结果继续调 gh）；2=用法错误（真失败，停下报告）。stderr 是改动告警。无论 0 还是 1，都用 stdout 的归一化结果调 gh；仅 2 才中止。
4. 用 `gh repo edit` 加上（取 stdout 结果，每行一个 topic）：
   ```bash
   gh repo edit <owner>/<repo> --add-topic <topic1> --add-topic <topic2> ...
   ```

**更新路径的 topics 模式**：更新路径问 topics 时多一档选择——「仅追加」/「替换全部」。替换全部时先 `gh repo edit --remove-topic <现有>` 清掉现有 topics，再 `--add-topic` 新的。

**失败处理**：
- Step 7 push 失败：跳过 7.5，进 Step 9 报告失败。
- `gh repo edit` 失败（网络/权限）：不卡流程，记下来在 Step 9 报告提示「仓库描述/topics 设置失败，可手动补」。README 已在仓库里，门面主体不丢。
- topics 推断不出任何候选：跳过 topics，只设描述，报告提一句「未自动设 topics」。

---

- [ ] **Step 4: Step 9 报告节补门面摘要**

读 `SKILL.md`，找到 Step 9 报告的输出清单（约第 288-293 行）：

```
输出：
- 仓库 URL（如 `https://github.com/<user>/<name>`）
- 可见性（public/private）
- 提交的文件数
- 清理项摘要（删了 N 个文件、替换了 N 处）
- Release 更新情况（如有）
```

在「清理项摘要」之后、「Release 更新情况」之前插入：

```
- 门面装饰摘要：
  - README：新生成 / 已保留原版 / 已重写（原版备份于 README.bak.md）
  - 仓库描述：已设置 "<描述>" / 设置失败 / 已跳过
  - topics：python, automation, gui（共 3 个）/ 未设置（推断失败）/ 已跳过
```

- [ ] **Step 5: 硬性规则节补两条**

读 `SKILL.md`，找到「## 硬性规则」节末尾（约第 303 行，现有第 7 条之后），追加：

```
8. **门面装饰只在新建仓库自动走全套；更新已有仓库必须先问，默认不动**——防把老仓库精心弄的 README/描述/topics 覆盖掉。
9. **重写 README、设置 topics 前至少一次 `AskUserQuestion` 确认**——不替用户决定 README 保留还是重写、不替用户定 topics。确认点合并成多字段一次问询，不逐子项追问。Step 6.6 不得改动用户在 Step 4 选了「保留」或给了自定义占位的行。
```

- [ ] **Step 6: 边界节补「可做」+「不做」**

读 `SKILL.md`，找到「## 边界」节。

在「本 skill **可以**做」列表末尾追加：
```
- 生成/重写 README（含清理后刷新）
- 用 `gh repo edit` 设置仓库描述和 topics
```

在「本 skill **不**做」列表末尾追加：
```
- 生成封面图 / social preview / badge / CONTRIBUTING 等配套文档
- 改 default branch / pages / wiki
```

- [ ] **Step 7: 测试节同步 normalize_topics.py**

读 `SKILL.md`，找到「## 测试」节（约第 328 行），在 scan.py 自检说明之后追加：

```
normalize_topics.py 自带回归测试，改完归一化规则后必跑：

```bash
python scripts/normalize_topics.py --self-test
```

`--self-test` 验证：基本归一化（大小写/连字符/连续连字符/首尾连字符）、非 ASCII（中文/emoji）被丢弃、长度截断（50 字符）、dedup、总数上限（20）、纯数字/单字符 topic。
```

- [ ] **Step 8: 文件清单节补 normalize_topics.py**

读 `SKILL.md`，找到「## 文件清单」节，在 `scripts/scan.py` 那行之后插入：

```
- `scripts/normalize_topics.py` — GitHub topics 归一化校验脚本（含 `--self-test`）
```

- [ ] **Step 9: 程读确认整批改动**

人工程读确认：
1. Step 6.5 在 Step 6 后、Step 7 前；执行时机引用「执行顺序总览」。
2. Step 6.6 在 6.5 后、Step 7 前；明确「仅改 Step 5 产生的 `<REDACTED>`，不动用户保留/自定义项」。
3. Step 7.5 在 Step 7 后、Step 8 前；push 失败跳过；退出码 0/1/2 语义写明；描述两路径来源；topics 走 normalize_topics.py；更新路径「仅追加/替换全部」。
4. Step 9 报告有 3 行门面摘要（含备份提示、topics 计数）。
5. 硬性规则有第 8、9 条（第 9 条含 6.6 不动用户决策）。
6. 边界「可做」+「不做」都有门面条目。
7. 测试节有 normalize_topics.py 自检说明。
8. 文件清单有 normalize_topics.py。

- [ ] **Step 10: 提交（单 commit，合并 v1 碎 commit）**

```bash
git add SKILL.md
git commit -m "feat: add facade decoration (Step 6.5/6.6/7.5) to Togithub skill"
```

---

## Task 4: 全局自检 + 结构性核查 + 实跑

**Files:**
- 无改动，纯验证

**说明：** spec 验证 checklist 的最终关。v1 的 Task 8 只查字面文字、放过致命时序缺陷——本任务补结构性核查（确认 6.5 真的接到 Step 3 之前、Step 2a 没提前 commit/push），并把实跑从「可选」提为必做。

- [ ] **Step 1: 跑 scan.py 自检确认未受牵连**

Run: `python scripts/scan.py --self-test`
Expected: 所有自测通过（scan.py 本任务没改，应原样通过）。

- [ ] **Step 2: 跑 normalize_topics.py 自检**

Run: `python scripts/normalize_topics.py --self-test`
Expected: `all self-tests passed`，退出码 0。

- [ ] **Step 3: 结构性核查 SKILL.md（不只查字面）**

逐项确认：
1. 「## 流程」节有两条执行顺序总览，写明 README 草稿在 Step 3 扫描之前落盘。
2. **Step 2a 内联流程**：`git init → 落盘 .gitignore/LICENSE → Step 6.5 README 草稿 → Step 3 扫描 → Step 5 清理 → Step 6.6 刷新 → Step 7 commit/push`。**确认 Step 2a 内联没有提前 commit/push**（push 必须 defer 到 Step 7）——这是 v1 致命缺陷的修复点，重点核查。
3. Step 2a `gh repo create` 无 `--description`。
4. Step 2b 末尾有 6.5 钩子引用。
5. Step 6.5/6.6/7.5 各自执行时机写明、相互引用一致。
6. Step 6.6 明确只改 Step 5 产生的 `<REDACTED>`，不动用户保留/自定义项。
7. Step 7.5 退出码 0/1/2 语义写明。
8. Step 9 报告、硬性规则 8/9、边界、测试节、文件清单均补全。

- [ ] **Step 4: 对照 spec 边界用例走读**

对照 `docs/superpowers/specs/2026-06-22-togithub-facade-design.md` 的「验证方式」10 条 checklist，逐条确认 SKILL.md 指令能覆盖。记录任何覆盖不到的，回头补。重点核查 #1（全流程通，依赖 6.5 真在 3 之前）、#2（README 含真实路径被扫→6.6 改写，依赖 README 进扫描）。

- [ ] **Step 5: 实跑（必做，需用户在场）**

**前置**：把 skill 装到用户级 `~/.claude/skills/Togithub/`（拷贝 SKILL.md + scripts/），或用项目级 `.claude/skills/Togithub/` 覆盖。

找一个测试项目（最好含 `.claude/` 目录和已有 README），实跑 `/Togithub`，确认：
- 新建路径：6.5 生成草稿 → 3 扫描（含 README）→ 6.6 刷新 → 7 push → 7.5 设描述+topics，全流程通。
- README 草稿含真实路径/邮箱时，被扫描命中 → 6.6 改写为通用占位示例（非 `<REDACTED>`），README 可读。
- 目录含 `.claude/`、`task_plan.md` 时，清理删除后 6.6 目录树不列这些已删文件。
- topics 含 `C++`/中文时，normalize_topics.py 归一化/丢弃，gh 不报错。

实跑发现问题则回到对应 Task 修复。

---

## Self-Review

**1. Spec coverage：**
- README 起草（6.5）→ Task 3 Step 1 ✅
- README 刷新（6.6，目录树回填 + 通用占位 + 不动用户决策）→ Task 3 Step 2 ✅
- 描述统一来源（Step 2a 去描述 + 7.5 设）→ Task 2 Step 2 + Task 3 Step 3 ✅
- topics 归一化脚本 → Task 1 ✅，7.5 调用 + 退出码语义 → Task 3 Step 3 ✅
- 失败处理（push 失败跳过 7.5、gh edit 失败不卡、topics 推断不出跳过）→ Task 3 Step 3 ✅
- 更新路径「先问」+ topics「仅追加/替换全部」→ Task 3 Step 3 ✅
- 重写前备份（未跟踪→README.bak.md）→ Task 3 Step 1 ✅
- README 检测清单扩展 → Task 3 Step 1 ✅
- 语言判定兜底 → Task 3 Step 1 ✅
- LICENSE 不生成分支 → Task 3 Step 1 ✅
- shell 转义 → Task 3 Step 3 ✅
- Step 9 报告摘要（多行，含备份/计数）→ Task 3 Step 4 ✅
- 硬性规则两条（含 6.6 不动用户决策）→ Task 3 Step 5 ✅
- 边界「可做」+「不做」→ Task 3 Step 6 ✅
- 测试节同步 → Task 3 Step 7 ✅
- 文件清单同步 → Task 3 Step 8 ✅
- 执行顺序总览 → Task 2 Step 1 ✅
- Step 2a/2b 时序重写（F1 修复）→ Task 2 ✅
- 验证 checklist（含结构性核查）→ Task 4 ✅
- commit 规范（Conventional Commits、不带 Co-Authored-By）→ 各 Task commit 步骤 ✅

**2. Placeholder scan：** 无 TBD/TODO；所有步骤给具体插入文本/代码。✅

**3. Type consistency：** Step 6.5/6.6/7.5 编号在 spec/计划/SKILL.md 一致；`normalize_topics.py` 文件名、`--self-test`、调用路径 `$HOME/.claude/skills/Togithub/scripts/normalize_topics.py` 在 Task 1/3 一致；退出码 0/1/2 在脚本和 7.5 正文一致。✅

**4. 对抗式审查 v1 反馈落实：**
- F1（时序不可实现）→ Task 2 重写 Step 2a/2b ✅
- F2（执行总览未写）→ Task 2 Step 1 ✅
- I1（中文 topic bug）→ Task 1 ASCII-only + self-test ✅
- I2（退出码歧义）→ Task 3 Step 3 显式 0/1/2 语义 ✅
- I3（围栏嵌套）→ Task 3 插入内容直接原文不用外层 fence ✅
- I4（6.6 覆盖用户决策）→ Task 3 Step 2 限定只改 `<REDACTED>` ✅
- I5（不做项未写边界）→ Task 3 Step 6 ✅
- I6（测试节未同步）→ Task 3 Step 7 ✅
- I7（stdin）→ Task 1 加 stdin 读取 ✅
- I8（碎 commit）→ Task 3 合并单 commit ✅
- I9（测试抓不到缺陷）→ Task 4 补结构性核查 + 实跑必做 ✅
- S1（报告多行）→ Task 3 Step 4 ✅
- S2（argparse）→ Task 1 ✅
- S4（锚点原文）→ 各 Step 给原文锚点 ✅
- S6（skill 安装前置）→ Task 4 Step 5 ✅

无遗留问题，计划完整。
