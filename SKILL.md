---
name: Togithub
description: 把当前项目推送到 GitHub。推送前自动扫描并清理个人隐私信息（邮箱/手机/真实姓名/API key/本地路径/组织名/地址坐标）、AI 协作痕迹（.claude/ 目录、planning 类文件、Co-Authored-By: Claude、AI 自述注释）、开发过程文件（task_plan/findings/progress/NOTES 等）。如无 GitHub 仓库则创建（询问 public/private、LICENSE、.gitignore），如有则增量提交并推送。统一用 gh CLI 认证。触发词：推送到 GitHub、推上 github、publish to github、上传到 GitHub、发布到 GitHub、推到远程、/Togithub。
---

# /Togithub — 推送项目到 GitHub（带预清理）

## 概述

把当前目录的项目推上 GitHub。**永远先扫描、再询问、再清理、再推送**——不偷跑任何破坏性操作。

适合：想把本地项目（含未提交改动）发布到 GitHub、希望顺手清掉隐私和 AI 痕迹、不希望推完后才发现 `Co-Authored-By: Claude` 还挂在 commit 上。

不适合：只想 commit 一次、只想切换 remote、想推到 GitLab/Gitee/自建 Gitea。

## 前置检查

依次执行，确认环境就绪：

```bash
gh --version                       # gh CLI 是否安装
gh auth status                     # 是否已登录 GitHub
git --version
python --version                   # 需要 Python 3.9+（scan.py 用了 `int | str` 语法）
```

如果 `gh auth status` 失败，停下来告诉用户：

> `gh` 未登录。请在终端运行 `gh auth login` 完成认证后，再让我重试。

不要替用户做 `gh auth login`（交互式登录），改用提示让用户自己跑。

如果 Python 版本低于 3.9，停下来告诉用户：

> scan.py 需要 Python 3.9 或更高版本。请升级 Python 后重试。

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

### Step 1: 摸清当前状态

并行跑：

```bash
pwd
git rev-parse --is-inside-work-tree 2>/dev/null
git status --porcelain
git remote -v
gh repo view --json name,visibility,isPrivate,url 2>/dev/null
```

把结果归类到以下几种：

| 状态 | 含义 | 后续 |
|---|---|---|
| A. 不是 git 仓库 | 全新本地 | 走 Step 2a（创建）|
| B. 是 git 仓库，无 remote | 现有本地 | 走 Step 2a（创建）|
| C. 是 git 仓库，remote 指向 GitHub | 现有远程 | 走 Step 2b（更新）|
| D. 是 git 仓库，remote 指向别处 | 异常 | 停下来问用户 |

### Step 2a: 新建仓库

问用户（用 AskUserQuestion）：

1. **仓库名**（默认用当前目录名）
2. **公开/私有**（**每次都强制问**，不要默认 public——误推私会出事）
3. **LICENSE**（MIT / Apache-2.0 / GPL-3.0 / BSD-3-Clause / 不生成）
4. **是否生成 .gitignore**（按项目类型自动生成 / 我自己提供 / 不要）

> 仓库描述不在这一步问——会在 Step 6.5 生成 README 时确认一句话介绍，Step 7.5 统一设置。避免描述被设两次。

**⚠️ 关键顺序**（严格遵守，否则门面和扫描都会失效）：先落盘 `.gitignore` 和 `LICENSE` → 执行 Step 6.5 起草 README 草稿 → 再走 Step 3 扫描（覆盖 .gitignore/LICENSE/README）→ Step 5 清理 → Step 6.6 刷新 README → Step 7 add/commit/push。**绝不能先跑 `gh repo create --source=.`**，它会隐式 `git init && add -A && commit`，绕过扫描、绕过 .gitignore、绕过 README 起草，吞掉 `.env`/大文件。

```bash
# 1. 仅当状态 A 时初始化
git init

# 2. 落盘 .gitignore 和 LICENSE（按用户选择生成，模板见 references/gitignore-templates.md 和 assets/license-*.txt）

# 3. 执行 Step 6.5 起草 README 草稿并落盘（与 .gitignore/LICENSE 同批）
#    ——必须在 Step 3 扫描之前，否则 README 自身成扫描盲区

# 4. 走 Step 3 扫描 + Step 4 确认 + Step 5 清理（扫描覆盖 .gitignore/LICENSE/README）

# 5. 执行 Step 6.6 刷新 README（清理后回填目录树、修被占位坏掉的示例）

# 6. 提交（push 由下一步 gh repo create 完成，Step 7）
git add .
git commit -m "chore: initial commit"

# 7. 最后才创建远程仓库并推送（Step 7）
gh repo create <name> --<public|private> --source=. --remote=origin
```

**注意**：`gh repo create --source=.` 会在本地已提交后直接 push 现有 commits，不再重复 commit，也不带 `--description`（描述统一在 Step 7.5 设）。commit 和 push 都在 Step 7 完成，Step 2a 只负责选配置 + 落盘 .gitignore/LICENSE + 触发 Step 6.5。

### Step 2b: 已有仓库，更新

```bash
git status            # 看未提交改动
git log --oneline -5  # 看最近 commits（初判有没有 Co-Authored-By）
git fetch origin      # 同步远端
```

进入 Step 3 清理后再 add/commit/push。

> 门面：更新路径下，先执行 Step 6.5 问「要不要重写 README」，要重写则落盘草稿（在 Step 3 扫描之前）；Step 3 扫描 → Step 4/5 确认清理后执行 Step 6.6 刷新 README（若重写过）；Step 7 push 后执行 Step 7.5 问「要不要更新描述/topics」。详见「执行顺序总览」。

### Step 3: 扫描待清理项

调用 `scripts/scan.py`（位于 `~/.claude/skills/Togithub/scripts/scan.py`）：

```bash
# 文件扫描（必跑）
python "$HOME/.claude/skills/Togithub/scripts/scan.py" .

# 历史扫描（状态 B/C 必跑——能查出旧 commit 里的密钥、Co-Authored-By 等）
python "$HOME/.claude/skills/Togithub/scripts/scan.py" . --scan-history --max-commits 200
```

文件扫描会扫四类问题，历史扫描会扫 `git log -p` 里所有被添加/修改的行。两者结果合并后再向用户报告。

1. **AI 痕迹文件**（建议删除）
   - `.claude/` 目录
   - `task_plan.md` / `findings.md` / `progress.md` / `NOTES.md` / `SCRATCH*.md` / `TODO*.md` / `RETRO*.md`
   - `.cursorrules` / `.windsurfrules` / `.aider*` / `AGENTS.md`
2. **AI 痕迹内容**（建议替换或确认删除）
   - 包含 `Co-Authored-By: Claude` / `Generated with Claude Code` / `由 Claude 生成` / `claude code` / `<system-reminder>` 的行
3. **个人隐私模式**（建议替换为占位符或删除）
   - 邮箱、国内手机号（含 `+86`、带分隔符、座机）、身份证、银行卡
   - `D:\Users\<name>\` / `C:\Users\<name>\` / `/Users/<name>/` / `/home/<name>/` / `~/...`
   - 国内云密钥（阿里云 LTAI / 腾讯云 AKID / 华为云）和国际云（AWS / Stripe / Slack / Telegram / Anthropic / OpenAI / npm / PyPI / Discord webhook）
   - 学校/公司/组织名（仅在署名行如 Author/Maintainer 触发，**仅 info 级**）
   - 坐标 `(lat|lng)[\s]*[=:][\s]*[\d.-]+`、硬编码地址、私有 IP（10.x/192.168/172.16-31/loopback/ULA IPv6）
4. **危险文件**（必须加入 .gitignore，绝不推送）
   - `.env` / `.env.*` / `.envrc` / `*.pem` / `*.key` / `id_rsa*` / `service-account*.json`

完整正则表见 `references/patterns.md`。

历史扫描的 finding 路径形如 `commit:<sha12>:<file>:<line>`，snippet 前缀是 `[author <email>]`，便于判断"是谁、何时、加了什么"。

### Step 4: 报告 + 确认

把扫描结果整理成清单（**不要**直接动手）：

```
扫描结果（共 N 项）：
  注：info 级提示（如学校/公司名）已按文件聚合，同类合并为一条并标注次数；warn/danger 仍逐条列出。

  [建议删除] .claude/ 目录（包含 12 个文件，247KB）
  [建议删除] task_plan.md, findings.md, progress.md
  [建议替换] README.md:42 — 含 "由 Claude 生成的自动签到脚本"
  [建议替换] config.ini.example:8 — 含邮箱 xxx@example.com
  [建议替换] main.py:120 — 含本地路径 D:\wh520\...
  [建议检查] CREDITS.md — 含 3 处组织名署名（org-name-hint，已聚合）
  [建议检查] 历史 commit:a8b224f:config.py:1 — 旧 commit 包含 API key

  逐项确认处理方式（删除 / 替换为 <REDACTED> / 跳过）？
```

**确认规则**：
- 用 `AskUserQuestion` **逐项**让用户选（不是按类目批量选），选项示例：`删除` / `替换为占位符` / `保留` / `跳过该项`
- **收到用户对每项的明确选择后**才能进入 Step 5
- 任何模糊回答（"随便"、"都行"、"看着办"）默认**全部跳过**，绝不替用户做主
- 如果用户回复"全删"或"全部按建议来"，仍然要列出清单做最后一次确认（防误操作）

### Step 5: 应用清理

按用户**逐项**确认结果执行：

- **删除文件/目录**：用 `rm -rf`（POSIX）或 `Remove-Item -Recurse -Force`（PowerShell）
- **替换文件内容**：用 Edit 工具，把匹配行替换为 `<REDACTED>` 或用户给的占位
- **重写 git 历史中的 Co-Authored-By / 旧密钥**：⚠️ **高危操作，必须二次确认**。推荐用 `git filter-repo`（不要用 `filter-branch`，自 Git 2.30 起已废弃）：

  ```bash
  # 安装 filter-repo（一次性）
  pip install git-filter-repo
  # 或 macOS: brew install git-filter-repo
  # Windows: pip install git-filter-repo（已预装 Python 即可）

  # 1. 先 dry-run：扫描出所有会被改的 commit（不改历史）
  git log --all --pretty=format:"%H %s" | while read sha _; do
    git show "$sha" | grep -lE "Co-Authored-By: Claude|api_key|secret" && echo "↑ $sha"
  done

  # 2. 展示给用户并二次确认
  #    确认后用 filter-repo 重写：
  git filter-repo --invert-paths --path-glob '*.env' --path .claude/  # 例：删 .env 和 .claude/ 的历史
  git filter-repo --message-callback 'open(sed "/^Co-Authored-By: Claude$/d")'  # 删 Co-Authored-By 行

  # 3. 远端 force push（最后一步，必须 --force-with-lease 防覆盖）
  git remote add origin https://github.com/<user>/<repo>.git
  git push --force-with-lease origin <branch>
  ```

  **Windows 兼容**：`filter-repo` 是 Python 包，跨平台一致；`filter-branch` 依赖的 `sed` 在 Windows Git Bash/MSYS 下行为不稳。  
  **默认建议不要重写历史**——只在 README/AGENTS.md 顶部加一行"本仓库使用 AI 辅助开发"作为折中。  
  **如果用户坚持不重写历史但要 push**：在 push 之前先把"历史中存在敏感内容"这个事实写到 issue 或 PR description 里，让协作者知情。

### Step 6: 生成 .gitignore 和 LICENSE（如果用户选了）

`.gitignore` 自动检测：扫 `package.json` / `requirements.txt` / `go.mod` / `Cargo.toml` / `pom.xml` / `*.csproj` 等决定项目类型，套对应模板。详细模板见 `references/gitignore-templates.md`。

`LICENSE` 模板见 `assets/license-<name>.txt`，直接拷贝到 `LICENSE` 文件。

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

### Step 7: 提交 + 推送

**commit message 格式**（Conventional Commits，**不带** Co-Authored-By）：

```
<type>(<scope>): <description>

<body 可选，简短说明改动>
```

type 取 `feat` / `fix` / `docs` / `refactor` / `chore` 等。新仓库首推用 `chore: initial commit`。

**关键**：本 skill 自己生成的所有 commit message **绝不**带 `Co-Authored-By: Claude` 或 `Generated with Claude Code`。

```bash
git add -A
git status                # 再次确认要提交的内容
git commit -m "..."
git push origin <branch>  # 或 git push -u origin main（首次）
```

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

**更新路径的 topics 模式**：更新路径问 topics 时多一档选择——「仅追加」/「替换全部」。替换全部时先用 `gh api repos/<owner>/<repo>/topics --jq '.names[]'` 取出现有 topics 列表，逐个 `gh repo edit <owner>/<repo> --remove-topic <现有topic>` 清掉，再 `--add-topic` 新的。

**失败处理**：
- Step 7 push 失败：跳过 7.5，进 Step 9 报告失败。
- `gh repo edit` 失败（网络/权限）：不卡流程，记下来在 Step 9 报告提示「仓库描述/topics 设置失败，可手动补」。README 已在仓库里，门面主体不丢。
- topics 推断不出任何候选：跳过 topics，只设描述，报告提一句「未自动设 topics」。

### Step 8: 判断是否需要打包 EXE 并询问 Release

代码推送完成后，判断项目是否适合发布 EXE。**不要只检测已有的 EXE，而是根据项目类型主动判断是否需要打包**。

**判断条件**（满足任一即认为需要打包）：

1. **Python GUI 项目**：`requirements.txt` 或 `main.py` 中包含以下任一依赖：
   - `customtkinter` / `tkinter` / `tk`
   - `PyQt5` / `PyQt6` / `PySide2` / `PySide6`
   - `wxPython` / `kivy` / `DearPyGui`
   - `pygame`（游戏/多媒体应用）
2. **有打包配置**：项目中存在 `*.spec` 文件（PyInstaller）、`setup.py`、`pyproject.toml` 中有 `[tool.pyinstaller]` 配置
3. **有打包脚本**：`Makefile`、`build.bat`、`build.sh` 等包含 `pyinstaller` 或 `nuitka` 命令
4. **README 提到打包**：README 中有"打包"、"EXE"、"可执行文件"、"发布"等关键词

**检测已有 EXE**：

代码推送完成后，检测是否有可发布的 EXE 文件：

```bash
# 检测常见打包产物目录
ls -lh dist/*.exe build/*.exe output/*.exe 2>/dev/null
```

**询问逻辑**：

- **如果检测到已有 EXE**：询问是否上传到 GitHub Release
- **如果判断需要打包但没有 EXE**：询问是否现在打包（调用 PyInstaller），然后再询问是否上传 Release
- **如果项目不适合打包**（如纯命令行工具、Web 服务、库）：跳过此步

用 `AskUserQuestion` 询问用户：

```
检测到这是 Python GUI 项目，适合发布 EXE 版本。
是否要打包并上传到 GitHub Release？
```

或（已有 EXE 时）：

```
检测到打包产物：dist/app.exe (39MB)
是否要上传到 GitHub Release？
```

选项：
1. **打包并创建新 Release** — 执行 PyInstaller 打包，询问版本号和 Release notes，然后 `gh release create`
2. **打包并更新最新 Release** — 执行 PyInstaller 打包，替换最新 Release 的 EXE 附件
3. **仅打包，不上传 Release** — 只执行 PyInstaller，EXE 保留在本地
4. **跳过** — 不打包，不更新 Release

如果用户选择创建/更新 Release：

```bash
# 创建新 Release 并上传 EXE
gh release create <tag> -R <owner>/<repo> --title "<title>" --notes "<notes>" "dist/app.exe#显示文件名.exe"

# 或更新现有 Release 的附件
gh release delete-asset <tag> <old-asset> -R <owner>/<repo> -y  # 先删旧的（如存在）
gh release upload <tag> "dist/app.exe#显示文件名.exe" -R <owner/<repo>
```

**版本号规则**：
- 如果用户没指定，从现有 Release 列表推断（如最新是 `v6.5.2`，建议 `v6.5.3`）
- Release notes 保持极简风格，除非用户要求详细说明

### Step 9: 报告

输出：
- 仓库 URL（如 `https://github.com/<user>/<name>`）
- 可见性（public/private）
- 提交的文件数
- 清理项摘要（删了 N 个文件、替换了 N 处）
- 门面装饰摘要：
  - README：新生成 / 已保留原版 / 已重写（原版备份于 README.bak.md）
  - 仓库描述：已设置 "<描述>" / 设置失败 / 已跳过
  - topics：python, automation, gui（共 3 个）/ 未设置（推断失败）/ 已跳过
- Release 更新情况（如有）

## 硬性规则

1. **绝不自动删除**任何文件——必须先 AskUserQuestion 确认。
2. **绝不自动 force push** 或重写历史——必须先 WARN + 二次确认。
3. **绝不**在 commit message 里带 `Co-Authored-By: Claude` / `Generated with ...`。
4. **绝不**推送 secrets（`.env` / `credentials.json` / `*.pem` / `id_rsa`）——发现就停下警告。
5. 扫到大文件（>10MB，非 LFS）停下警告，让用户决定。
6. 如果 `gh auth status` 失败，停下让用户跑 `gh auth login`。
7. 如果 README/CHANGELOG/CLAUDE.md 包含个人姓名、组织名，先标出再问。
8. **门面装饰只在新建仓库自动走全套；更新已有仓库必须先问，默认不动**——防把老仓库精心弄的 README/描述/topics 覆盖掉。
9. **重写 README、设置 topics 前至少一次 `AskUserQuestion` 确认**——不替用户决定 README 保留还是重写、不替用户定 topics。确认点合并成多字段一次问询，不逐子项追问。Step 6.6 不得改动用户在 Step 4 选了「保留」或给了自定义占位的行。

## 边界

本 skill **不**做：
- 推到非 GitHub（GitLab / Gitee / 自建）
- 处理 PR / Issue
- 跑测试 / lint / build
- 自动生成 commit history 改写（只提示 + 询问）
- 处理 LFS / submodule / monorepo 拆分
- 生成封面图 / social preview / badge / CONTRIBUTING 等配套文档
- 改 default branch / pages / wiki

本 skill **可以**做：
- 检测 EXE 打包产物并询问是否上传到 GitHub Release
- 生成/重写 README（含清理后刷新）
- 用 `gh repo edit` 设置仓库描述和 topics

## 失败模式

| 症状 | 处理 |
|---|---|
| `gh` 未安装 | 提示用户安装：`winget install GitHub.cli`（Win）/ `brew install gh`（Mac）/ `apt install gh`（Linux）|
| `gh auth status` 失败 | 提示用户跑 `gh auth login` |
| `git push` 被远端拒绝（非快进） | 跑 `git pull --rebase` 后再试，冲突停下来问 |
| 仓库名冲突 | 提示用户改名字 |
| 扫到大文件 | 停下问：加入 .gitignore / LFS / 强制推送 |
| 用户拒绝全部清理项 | 仍可推送，但要在最后警告"未清理的隐私项可能仍会上传" |

## 测试

scan.py 内置回归测试，改完正则后必跑：

```bash
# 跑内置回归测试（验证正则和文件扫描逻辑）
python scripts/scan.py --self-test

# 在目标项目上跑一次真实扫描（验证完整流程）
python scripts/scan.py /path/to/project
```

`--self-test` 会验证：
- 所有隐私模式正则（邮箱/手机/身份证/银行卡/API key/云密钥等）
- bank-card 正则是否正确拒绝 UUID、全重复数字等误报
- AI 痕迹内容检测（Co-Authored-By、Generated with Claude 等）
- 文件级集成测试（.env 危险文件、.claude/ AI 痕迹目录、正常文件不误报）

测试通过后才能提交改动。

normalize_topics.py 自带回归测试，改完归一化规则后必跑：

```bash
python scripts/normalize_topics.py --self-test
```

`--self-test` 验证：基本归一化（大小写/连字符/连续连字符/首尾连字符）、非 ASCII（中文/emoji）被丢弃、长度截断（50 字符）、dedup、总数上限（20）、纯数字/单字符 topic。

## 文件清单

- `SKILL.md` — 本文件
- `scripts/scan.py` — 扫描脚本（核心）
- `scripts/normalize_topics.py` — GitHub topics 归一化校验脚本（含 `--self-test`）
- `references/patterns.md` — 完整正则表
- `references/gitignore-templates.md` — 按项目类型的 .gitignore 模板
- `assets/license-*.txt` — 5 种 LICENSE 模板

## 备注

skill 装在用户级 `~/.claude/skills/Togithub/`，对所有项目生效。在某个具体项目里 `.claude/skills/Togithub/` 也可以放一份覆盖（项目级优先）。
