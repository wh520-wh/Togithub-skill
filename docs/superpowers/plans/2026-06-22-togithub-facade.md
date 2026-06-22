# Togithub 门面装饰优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `/Togithub` skill 增加门面装饰能力——推送前生成体面的 README（两阶段：起草→扫描清理→刷新），推送后用 `gh` 设置仓库描述和 topics。

**Architecture:** 改 `SKILL.md`（指令手册，插 Step 6.5/6.6/7.5 三节）+ 新增 `scripts/normalize_topics.py`（topics 归一化校验，标准库，含 `--self-test`）。README 生成是 agent 层逻辑（agent 读代码起草 + 刷新），不沉淀成脚本；topics 归一化是确定性规则，沉淀成脚本兜底。scan.py 不动。

**Tech Stack:** Python 3.9+（标准库 argparse/sys/re）、Markdown（README/SKILL.md）、`gh` CLI（仓库设置）。

**项目特殊性（重要）：** 本项目是 Claude Code Skill，**没有 pytest、没有 CI、没有构建系统**。验证方式沿用 `scan.py` 的 `--self-test` 自检模式 + 人工程读 + 实跑 skill 流程。计划里的「测试」步骤用 `python scripts/xxx.py --self-test`，不写 pytest 文件。

**spec 出处：** `docs/superpowers/specs/2026-06-22-togithub-facade-design.md`

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `scripts/normalize_topics.py` | topics 归一化校验（小写、连字符、长度、去重、≤20） | 新建 |
| `SKILL.md` | skill 指令手册 | 改：插 6.5/6.6/7.5，改 Step 2a，补 Step 9/硬性规则/边界 |
| `scripts/scan.py` | 扫描脚本 | 不动 |
| `references/patterns.md` | 正则文档 | 不动 |

---

## Task 1: 新增 `scripts/normalize_topics.py` 归一化脚本

**Files:**
- Create: `scripts/normalize_topics.py`

**说明：** 这是新增的确定性脚本，可以也应当带 `--self-test`。先写脚本再写自检。脚本职责：读入 topic 列表（命令行参数），按 GitHub 规则归一化，输出归一化后的列表 + 改动告警，非零退出码表示有截断/拒绝。

- [ ] **Step 1: 写脚本主体**

创建 `scripts/normalize_topics.py`：

```python
#!/usr/bin/env python3
"""
Togithub: normalize GitHub repository topics.

GitHub topics rules:
  - lowercase only
  - only [a-z0-9-] characters
  - no leading/trailing hyphens, no consecutive hyphens
  - max 50 chars per topic
  - max 20 topics total

Usage:
  python normalize_topics.py <topic1> <topic2> ...
  python normalize_topics.py --self-test

Exit code: 0 if all topics valid (or self-test passed), 1 if any truncation/rejection occurred.
Outputs: one normalized topic per line on stdout; warnings on stderr.
"""
from __future__ import annotations

import sys


MAX_LEN = 50
MAX_COUNT = 20


def normalize_one(topic: str) -> tuple[str, str | None]:
    """Normalize a single topic. Returns (normalized, warning).
    warning is None if no change, else a human-readable warning string."""
    original = topic
    # lowercase
    t = topic.lower()
    # replace any non-[a-z0-9-] with hyphen
    t = "".join(c if (c.isalnum() or c == "-") else "-" for c in t)
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
        parts = []
        if t.lower() != original.lower():
            parts.append(f"chars normalized")
        if truncated:
            parts.append(f"truncated to {MAX_LEN} chars")
        if t == "":
            warning = f"'{original}' -> rejected (empty after normalization)"
        else:
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
    if len(argv) == 2 and argv[1] == "--self-test":
        return self_test()
    if len(argv) < 2:
        print("usage: normalize_topics.py <topic1> <topic2> ...", file=sys.stderr)
        return 2
    topics = argv[1:]
    result, warnings = normalize_topics(topics)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for t in result:
        print(t)
    return 0 if not warnings else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
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
Expected stderr 含 `warning: 'C++' -> 'c'`，退出码 1（因为有改动告警）。

- [ ] **Step 4: 提交**

```bash
git add scripts/normalize_topics.py
git commit -m "feat: add normalize_topics.py for GitHub topics normalization"
```

---

## Task 2: SKILL.md 改 Step 2a——去掉单独问描述

**Files:**
- Modify: `SKILL.md`（Step 2a 小节，约 64-91 行）

**说明：** spec F4 修复——Step 2a 不再单独问描述，`gh repo create` 去掉 `--description`，统一在 Step 7.5 设描述（来源是 Step 6.5 确认的一句话介绍）。避免描述被设两次、删掉「对比哪个准」的模糊逻辑。

- [ ] **Step 1: 改 Step 2a 的询问清单**

读 `SKILL.md`，找到 Step 2a 的询问列表（约 66-70 行）：

```
1. **仓库名**（默认用当前目录名）
2. **公开/私有**（**每次都强制问**，不要默认 public——误推私会出事）
3. **描述**（可选，留空用项目 README 头一行）
4. **LICENSE**（MIT / Apache-2.0 / GPL-3.0 / BSD-3-Clause / 不生成）
5. **是否生成 .gitignore**（按项目类型自动生成 / 我自己提供 / 不要）
```

改成（删掉第 3 项「描述」，重新编号）：

```
1. **仓库名**（默认用当前目录名）
2. **公开/私有**（**每次都强制问**，不要默认 public——误推私会出事）
3. **LICENSE**（MIT / Apache-2.0 / GPL-3.0 / BSD-3-Clause / 不生成）
4. **是否生成 .gitignore**（按项目类型自动生成 / 我自己提供 / 不要）

> 仓库描述不在这一步问——会在 Step 6.5 生成 README 时确认一句话介绍，Step 7.5 统一设置。避免描述被设两次。
```

- [ ] **Step 2: 改 `gh repo create` 命令去掉 `--description`**

找到 Step 2a 末尾的命令（约 88 行）：

```bash
gh repo create <name> --<public|private> --source=. --remote=origin --description="<desc>"
```

改成：

```bash
gh repo create <name> --<public|private> --source=. --remote=origin
```

- [ ] **Step 3: 程读确认改动**

人工程读 Step 2a：确认询问清单只剩 4 项、`gh repo create` 不带 `--description`、有那句说明描述在 7.5 统一设。

- [ ] **Step 4: 提交**

```bash
git add SKILL.md
git commit -m "refactor: move repo description from Step 2a to Step 7.5"
```

---

## Task 3: SKILL.md 新增 Step 6.5 门面装饰·README 起草

**Files:**
- Modify: `SKILL.md`（在 Step 6 之后、Step 7 之前插入新节）

**说明：** spec 的核心改动之一。Step 6.5 在 Step 6（.gitignore/LICENSE 落盘）之后、Step 3 扫描之前执行——README 草稿与 .gitignore/LICENSE 同批落盘进扫描。这是 agent 层逻辑，写成 SKILL.md 指令。

- [ ] **Step 1: 在 Step 6 节末尾插入 Step 6.5 节**

读 `SKILL.md`，找到 Step 6 节的末尾（约 198 行 `LICENSE` 模板见 `assets/license-<name>.txt` 那句之后），在其后、`### Step 7` 之前插入以下整节：

```markdown
### Step 6.5: 门面装饰·README 起草

**执行时机**：在 Step 6（.gitignore/LICENSE 落盘）之后、Step 3 扫描之前。README 草稿与 .gitignore/LICENSE 同批落盘，一起进 Step 3 扫描——这样 AI 不慎写进 README 的邮箱/本地路径会被扫描器抓出来，在 Step 5 清理、Step 6.6 刷新。

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

````markdown
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
````

**License 章节分支**：
- 用户在 Step 2a 选了 LICENSE（MIT/Apache-2.0/...）：写「本项目采用 <LICENSE> 协议，详见 [LICENSE](LICENSE)」。
- 用户选了「不生成」：写「License: 待定」并留占位提示让用户填。

**风格约束**：不堆 badge，不放截图占位，不造图。推断不准的章节留简短占位提示让用户填，不编造内容。
```

- [ ] **Step 2: 程读确认插入位置正确**

人工程读：确认 Step 6.5 在 Step 6 之后、Step 7 之前；执行时机写明「Step 6 之后、Step 3 扫描之前」。

- [ ] **Step 3: 提交**

```bash
git add SKILL.md
git commit -m "feat: add Step 6.5 README drafting to Togithub skill"
```

---

## Task 4: SKILL.md 新增 Step 6.6 门面装饰·README 刷新

**Files:**
- Modify: `SKILL.md`（在 Step 6.5 之后插入新节）

**说明：** spec F1/F5/F6 修复——清理后刷新 README：回填目录树（清理删了文件，目录树需重生成）、把被扫描占位坏掉的示例行改写成通用占位（非 `<REDACTED>`）。这步是 README 两阶段模型的第二阶段。

- [ ] **Step 1: 在 Step 6.5 节之后插入 Step 6.6 节**

读 `SKILL.md`，找到 Step 6.5 节的末尾（风格约束那句之后），在其后、`### Step 7` 之前插入以下整节：

```markdown
### Step 6.6: 门面装饰·README 刷新

**执行时机**：在 Step 5（应用清理）之后、Step 7（commit）之前。**仅当 Step 6.5 生成/重写了 README 草稿时执行**；若用户在 6.5 选了「保留原 README」则跳过本步。

**刷新内容**：

1. **目录树回填**：清理可能删除了 `.claude/`、`task_plan.md`、`findings.md`、`progress.md` 等文件。重新扫描目录，把「## 目录结构」章节回填为清理后的真实两级树，**不列已删文件**。

2. **README 清理可读性复核**：Step 3 扫描可能命中 README 里的隐私行（AI 写用法示例时把真实路径/邮箱抄进去），Step 5 默认按 scan.py 的 suggestion 替换为 `<REDACTED>` 类占位——这对代码合理，对 README 说明性示例会坏掉可读性（如 `python main.py --config <LOCAL-PATH-WIN>`）。
   - 对 README 里的每一处扫描命中，改写为**通用占位示例**而非 `<REDACTED>`：
     - 本地路径 → `/path/to/config.ini` 或 `./config.ini`
     - 邮箱 → `you@example.com`
     - 手机 → `13800000000`
     - API key → `your-api-key-here`
   - 刷新后通读一遍 README，确认示例行仍读得通。
```

- [ ] **Step 2: 程读确认**

人工程读：确认 Step 6.6 在 6.5 之后、Step 7 之前；执行时机「Step 5 之后、Step 7 之前」；跳过条件「保留原 README 时跳过」。

- [ ] **Step 3: 提交**

```bash
git add SKILL.md
git commit -m "feat: add Step 6.6 README refresh after cleanup"
```

---

## Task 5: SKILL.md 新增 Step 7.5 门面装饰·仓库层

**Files:**
- Modify: `SKILL.md`（在 Step 7 之后、Step 8 之前插入新节）

**说明：** spec 仓库层门面——push 后用 `gh` 设描述 + topics。描述统一来源（新建路径复用 6.5 一句话介绍，更新路径读现有 README 首段确认）。topics 走 AI 推断+用户勾选+`normalize_topics.py` 归一化。失败不卡流程。push 失败则跳过本步。

- [ ] **Step 1: 在 Step 7 节之后插入 Step 7.5 节**

读 `SKILL.md`，找到 Step 7 节的末尾（`git push origin <branch>` 那段之后），在其后、`### Step 8` 之前插入以下整节：

```markdown
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
   # 把用户选的 topics 传给脚本，拿到归一化后的列表
   python "$HOME/.claude/skills/Togithub/scripts/normalize_topics.py" <topic1> <topic2> ...
   ```
   脚本输出归一化后的 topic（每行一个）到 stdout，改动告警到 stderr。用 stdout 的结果调 gh。
4. 用 `gh repo edit` 加上：
   ```bash
   gh repo edit <owner>/<repo> --add-topic <topic1> --add-topic <topic2> ...
   ```

**更新路径的 topics 模式**：更新路径问 topics 时多一档选择——「仅追加」/「替换全部」。替换全部时先 `gh repo edit --remove-topic <现有>` 清掉现有 topics，再 `--add-topic` 新的。

**失败处理**：
- Step 7 push 失败：跳过 7.5，进 Step 9 报告失败。
- `gh repo edit` 失败（网络/权限）：不卡流程，记下来在 Step 9 报告提示「仓库描述/topics 设置失败，可手动补」。README 已在仓库里，门面主体不丢。
- topics 推断不出任何候选：跳过 topics，只设描述，报告提一句「未自动设 topics」。
```

- [ ] **Step 2: 程读确认**

人工程读：确认 Step 7.5 在 Step 7 之后、Step 8 之前；push 失败跳过逻辑；描述来源两条路径都写明；topics 走 normalize_topics.py；更新路径有「仅追加/替换全部」。

- [ ] **Step 3: 提交**

```bash
git add SKILL.md
git commit -m "feat: add Step 7.5 repo description and topics setup"
```

---

## Task 6: SKILL.md 补 Step 9 报告、硬性规则、边界

**Files:**
- Modify: `SKILL.md`（Step 9 报告节、硬性规则节、边界节）

**说明：** 把 spec 的报告摘要、两条新硬性规则、边界补充落到 SKILL.md。

- [ ] **Step 1: Step 9 报告节补门面摘要**

读 `SKILL.md`，找到 Step 9 报告的输出清单（约 288-293 行）：

```
输出：
- 仓库 URL（如 `https://github.com/<user>/<name>`）
- 可见性（public/private）
- 提交的文件数
- 清理项摘要（删了 N 个文件、替换了 N 处）
- Release 更新情况（如有）
```

在「清理项摘要」之后、「Release 更新情况」之前插入一行：

```
- 门面装饰摘要（README：新生成/已保留原版/已重写；仓库描述：已设置/失败/跳过；topics：列表或未设置/跳过）
```

- [ ] **Step 2: 硬性规则节补两条**

读 `SKILL.md`，找到「## 硬性规则」节（约 295-304 行），在现有第 7 条之后追加：

```
8. **门面装饰只在新建仓库自动走全套；更新已有仓库必须先问，默认不动**——防把老仓库精心弄的 README/描述/topics 覆盖掉。
9. **重写 README、设置 topics 前至少一次 `AskUserQuestion` 确认**——不替用户决定 README 保留还是重写、不替用户定 topics。确认点合并成多字段一次问询，不逐子项追问。
```

- [ ] **Step 3: 边界节补门面条目**

读 `SKILL.md`，找到「## 边界」节（约 306 行）。在「本 skill **可以**做」列表末尾追加：

```
- 生成/重写 README（含清理后刷新）
- 用 `gh repo edit` 设置仓库描述和 topics
```

- [ ] **Step 4: 程读确认**

人工程读：Step 9 报告有门面摘要行；硬性规则有第 8、9 条；边界「可以做」有两条门面条目。

- [ ] **Step 5: 提交**

```bash
git add SKILL.md
git commit -m "docs: add facade summary to report, rules, and boundaries"
```

---

## Task 7: SKILL.md 文件清单节补 normalize_topics.py

**Files:**
- Modify: `SKILL.md`（文件清单节，约 348-354 行）

**说明：** spec 影响表里新增了 `scripts/normalize_topics.py`，SKILL.md 末尾的「文件清单」节要同步，否则文档撒谎。

- [ ] **Step 1: 文件清单节加一行**

读 `SKILL.md`，找到「## 文件清单」节：

```
- `SKILL.md` — 本文件
- `scripts/scan.py` — 扫描脚本（核心）
- `references/patterns.md` — 完整正则表
- `references/gitignore-templates.md` — 按项目类型的 .gitignore 模板
- `assets/license-*.txt` — 5 种 LICENSE 模板
```

在 `scripts/scan.py` 那行之后插入：

```
- `scripts/normalize_topics.py` — GitHub topics 归一化校验脚本（含 `--self-test`）
```

- [ ] **Step 2: 提交**

```bash
git add SKILL.md
git commit -m "docs: list normalize_topics.py in file manifest"
```

---

## Task 8: 全局自检 + 边界用例走读

**Files:**
- 无改动，纯验证

**说明：** spec 验证 checklist 的最终一道关。跑 scan.py 自检确认没被牵连改坏，人工程读整个改动确认 6.5/6.6/7.5 衔接无断裂，逐条对照 spec 边界用例。

- [ ] **Step 1: 跑 scan.py 自检确认未受牵连**

Run: `python scripts/scan.py --self-test`
Expected: 所有自测通过（scan.py 本任务没改，应原样通过）。

- [ ] **Step 2: 跑 normalize_topics.py 自检**

Run: `python scripts/normalize_topics.py --self-test`
Expected: `all self-tests passed`。

- [ ] **Step 3: 人工程读 SKILL.md 完整改动**

逐项确认：
1. Step 2a 询问清单 4 项、`gh repo create` 无 `--description`。
2. Step 6.5 在 Step 6 后、Step 7 前；执行时机写明「Step 6 后、Step 3 扫描前」。
3. Step 6.6 在 6.5 后、Step 7 前；执行时机「Step 5 后、Step 7 前」；保留原 README 时跳过。
4. Step 7.5 在 Step 7 后、Step 8 前；push 失败跳过；描述两路径来源；topics 走 normalize_topics.py；更新路径「仅追加/替换全部」。
5. Step 9 报告有门面摘要行。
6. 硬性规则有第 8、9 条。
7. 边界「可以做」有两条门面条目。
8. 文件清单有 normalize_topics.py。

- [ ] **Step 4: 对照 spec 边界用例走读**

对照 `docs/superpowers/specs/2026-06-22-togithub-facade-design.md` 的「验证方式」10 条 checklist，逐条确认 SKILL.md 的指令能否覆盖该场景。记录任何覆盖不到的，回头补。

- [ ] **Step 5: 在一个测试项目上实跑（可选，需用户在场）**

找一个测试项目（最好含 `.claude/` 目录和已有 README），实跑 `/Togithub`，确认：
- 新建路径：6.5 生成草稿 → 3 扫描 → 6.6 刷新 → 7 push → 7.5 设描述+topics，全流程通。
- README 草稿含真实路径/邮箱时，6.6 改写为通用占位示例。
- 目录含 `.claude/`、`task_plan.md` 时，6.6 目录树不列这些已删文件。

---

## Self-Review

**1. Spec coverage：**
- README 起草（Step 6.5）→ Task 3 ✅
- README 刷新（Step 6.6，目录树回填 + 通用占位）→ Task 4 ✅
- 描述统一来源（Step 2a 去描述 + 7.5 设）→ Task 2 + Task 5 ✅
- topics 归一化脚本 → Task 1 ✅，Step 7.5 调用 → Task 5 ✅
- 失败处理（push 失败跳过 7.5、gh edit 失败不卡、topics 推断不出跳过）→ Task 5 ✅
- 更新路径「先问」+ topics「仅追加/替换全部」→ Task 5 ✅
- 重写前备份（未跟踪→README.bak.md）→ Task 3 ✅
- README 检测清单扩展 → Task 3 ✅
- 语言判定兜底 → Task 3 ✅
- LICENSE 不生成分支 → Task 3 ✅
- shell 转义 → Task 5 ✅
- Step 9 报告摘要 → Task 6 ✅
- 硬性规则两条 → Task 6 ✅
- 边界条目 → Task 6 ✅
- 文件清单同步 → Task 7 ✅
- 验证 checklist → Task 8 ✅
- commit message 规范 → 各 Task 的 commit 步骤均用 Conventional Commits、不带 Co-Authored-By ✅

**2. Placeholder scan：** 无 TBD/TODO；所有指令步骤都给了具体要插入的文本/代码。✅

**3. Type consistency：** Step 6.5/6.6/7.5 编号在 spec、计划、SKILL.md 三处一致；`normalize_topics.py` 文件名、`--self-test` 子命令、调用路径 `~/.claude/skills/Togithub/scripts/normalize_topics.py` 在 Task 1/5/7 一致。✅

无遗留问题，计划完整。
