# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 这不是一个普通应用项目

这是一个 **Claude Code Skill** —— 一个由 SKILL.md 中的指令驱动、调用 scripts/scan.py 执行实际扫描工作的代理工具。**没有构建系统、没有 npm/pip 依赖、没有传统意义上的测试套件**。修改前请先读完整份 SKILL.md。

## Skill 的运行方式

安装到用户级 `~/.claude/skills/Togithub/` 后，用户用 `/Togithub`（或触发词）调用本 skill，Claude Code 代理按 SKILL.md 的 Step 1–9 顺序执行：

1. 摸清当前 git 状态
2. 决定创建新仓库 / 更新已有仓库
3. 调用 `scripts/scan.py` 扫描
4. 报告 + 逐项向用户确认
5. 应用清理（删文件/替换/重写历史）
6. 生成 .gitignore 和 LICENSE
7. 提交并 push
8. 判断是否打包 EXE + 上传 GitHub Release
9. 报告结果

**绝不能跳过 Step 3 扫描**——这是本 skill 的核心价值。任何"先 push 再说"的做法都违背设计意图。

## 项目结构

| 文件 | 作用 | 改它会影响什么 |
|---|---|---|
| `SKILL.md` | 给代理的指令手册（YAML frontmatter + Markdown 流程） | 改流程、改触发词、改硬性规则都改这里 |
| `scripts/scan.py` | 唯一的可执行程序：扫描目录或 git 历史，输出 JSON | 加新检测项、加新严重度、加新文件类型 |
| `references/patterns.md` | `scan.py` 顶部正则清单的人类可读版 | 改正则必须**同步**改 `scan.py` 顶部的列表 |
| `references/gitignore-templates.md` | Step 6 用的 .gitignore 模板 | 加新语言支持时扩这里 |
| `assets/license-*.txt` | 5 种 LICENSE 原文 | 直接拷贝到目标仓库的 `LICENSE` 文件，不改 |

## scan.py 的工作机制（改之前必看）

`scan.py` 把一个项目目录按四类问题扫描，输出 JSON 到 stdout：

- `ai_trace_file` — AI 协作痕迹文件/目录（`.claude/`、`task_plan.md`、`.cursorrules` 等）
- `ai_trace_content` — 文件里出现 `Co-Authored-By: Claude`、`<system-reminder>` 等
- `privacy_pattern` — 邮箱、手机、身份证、API key、本地路径、坐标等
- `dangerous_file` — `.env`、`*.pem`、`id_rsa*` 等绝不能推送的文件

**严重度等级**：`danger`（绝不能推，比如真 key）/`warn`（建议改）/`info`（仅提示，比如公司名）。`_DANGER_PRIVACY` 集合决定哪些 pattern 升到 danger。

**两种扫描模式**：
- 文件扫描：遍历 `SKIP_DIRS` 之外的所有文件
- 历史扫描（`--scan-history`）：走 `git log -p`，对 `+` 行跑同一套 pattern，路径前缀是 `commit:<sha12>:`，snippet 前缀是 `[author <email> <subject>]`

加新 pattern 时，**改完 `scan.py` 顶部列表后必须同步更新 `references/patterns.md`**，否则文档和实现会脱节。

## 开发命令

```bash
# 在某个目标项目目录上跑扫描（dry-run 验证正则）
python scripts/scan.py /path/to/target-project

# 跑历史扫描
python scripts/scan.py /path/to/target-project --scan-history --max-commits 200

# 只跑历史、不扫文件
python scripts/scan.py /path/to/target-project --history-only

# 排除某个 glob
python scripts/scan.py /path/to/target-project --exclude "*.lock" --exclude "fixtures/*"

# 跑一下内置自检（项目自身的扫描，看是否漏报）
python scripts/scan.py .
```

**没有 lint、没有 pytest、没有 CI**。改完 `scan.py` 后用上面最后一条命令在 SKILL.md 上自检一遍——SKILL.md 里的中文术语（如"Co-Authored-By"、`<system-reminder>`）会被自己的扫描器命中，用来反证规则有效。

## 硬性约束（写代码时必须遵守）

1. **不替用户做破坏性操作**：SKILL.md 明确写"绝不自动删除文件、绝不自动 force push"。任何让 agent 能跳过 `AskUserQuestion` 确认的改动都要拒绝。
2. **不在 commit message 里带 `Co-Authored-By: Claude`**：本 skill 自己生成的所有 commit 必须用 Conventional Commits（`feat:` / `fix:` / `docs:` / `refactor:` / `chore:`），不带 AI 归属。
3. **正则改完同步 `references/patterns.md`**：否则文档撒谎。
4. **保持中文一致**：SKILL.md 是中文文档，scan.py 输出的 `suggestion` 字段也是中文。新加的提示保持同样语气。
5. **跨平台**：`scan.py` 跑在 Windows / macOS / Linux，必须用 `pathlib.Path`、`os.walk` 这种跨平台 API，不要假设 `/` 路径分隔符（看 `iter_files` 里 `rel.replace("\\", "/")` 的处理）。

## 失败模式（写新功能前先看 SKILL.md 的对应表格）

- `gh` 未安装 / 未登录：SKILL.md 要求停下来让用户自己跑 `gh auth login`
- `git push` 被拒绝：先 `git pull --rebase`
- 仓库名冲突：让用户改
- 扫到大文件（>10MB）：停下问用户
- 用户拒绝全部清理项：仍可推，但要在最后警告"未清理的隐私项可能仍会上传"

## 常见改动场景

- **加新检测项**：改 `scripts/scan.py` 顶部的 pattern 列表 → 同步 `references/patterns.md` → 跑 `python scripts/scan.py .` 自检
- **加新 .gitignore 语言**：在 `references/gitignore-templates.md` 加一节
- **加新 LICENSE**：把原文加到 `assets/`（保持 `license-<name>.txt` 命名）
- **改 Step 流程**：改 SKILL.md 对应 Step 章节，注意硬性规则（Step 3 不能跳过）
- **改触发词**：改 SKILL.md 顶部 YAML 的 `description` 字段
