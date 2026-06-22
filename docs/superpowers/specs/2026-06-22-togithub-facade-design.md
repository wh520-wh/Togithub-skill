# Togithub Skill 门面装饰优化设计

日期：2026-06-22
状态：待实现（v2，已按对抗式审查全面修订）

## 背景与动机

当前 `/Togithub` skill 的定位是「扫干净隐私 → 推上 GitHub → 完事」。推送完成后仓库内容光秃秃，缺乏一个正经开源项目应有的「门面」——README 排版简陋或缺失、仓库描述/topics 未设置。

本次优化把 skill 升级为「扫干净 → 装门面 → 推上去 → 设门面 → 完事」，让推送后的仓库具备基本门面。

## 范围

**做**：
- README 体面化（文件层，push 前落盘）
- 仓库描述 + topics 标签设置（仓库层，push 后用 `gh` 设置）

**不做**（明确排除）：
- 封面图 / social preview（本轮砍掉，不生成、不留占位）
- badge 小图标
- CONTRIBUTING / LICENSE 说明等配套文档
- 改 default branch、pages、wiki 等其他仓库设置

## 核心决策

| 决策项 | 选定方案 | 原因 |
|---|---|---|
| 门面触发时机 | 新建仓库自动走全套；更新已有仓库先问，默认不动 | 保护老仓库已精心弄好的 README/描述/topics |
| README 内容来源 | AI 起草 + 用户确认关键信息 | 比纯自动准、比纯模板省事 |
| 已有 README 处理 | 问用户「保留 / 重写」二选一；重写前未跟踪的先备份 | 不默认重写，防不可恢复丢失 |
| topics 来源 | AI 推断候选 + 用户勾选 | 防瞎填不准标签 |
| topics 归一化 | 新增 `scripts/normalize_topics.py` 脚本兜底 | 确定性规则不靠 agent 心算，防 gh 报错 |
| README 时序模型 | 两阶段：起草 → 扫描清理 → 刷新定稿 | 解决「README 被扫到」与「清理后不 stale」的拉扯 |
| 整体方案 | 方案 A：能自动的自动，不能自动的不强求 | 不踩未公开 GraphQL 接口的雷 |
| 封面图 | 不做 | 本轮明确排除 |

## 流程改造（线性两阶段模型）

v1 的「Step 6.5 编号靠后、落盘动作靠前」是反线性设计，agent 顺序执行会写错时序。v2 改为线性、显式两阶段：

- **Step 6.5 门面装饰·README 起草**：在 Step 6（.gitignore/LICENSE）之后、Step 7（commit/push）之前。生成 README 草稿落盘——**与 .gitignore/LICENSE 同批进扫描**，确保 README 自身被 Step 3 扫描覆盖（AI 不慎写进的邮箱/路径会被扫出）。
- **Step 6.6 门面装饰·README 刷新**：在 Step 5（应用清理）之后、Step 7（commit）之前。对清理后的 README 做一次定稿刷新——回填目录树（清理删了 `.claude/`、`task_plan.md` 等文件，目录树需重生成）、修复被扫描占位坏掉的示例行（见下文「README 清理可读性」）。
- **Step 7.5 门面装饰·仓库层**：在 Step 7（push）之后、Step 8（EXE/Release）之前。用 `gh repo edit` 设描述 + topics。

**说明**：现有 SKILL.md 的 Step 2a 铁律是「先落盘 .gitignore/LICENSE → 再 Step 3 扫描 → Step 4/5 确认清理 → Step 7 commit」。门面改动**不破坏这个铁律**，而是：
- README 草稿在 Step 6（.gitignore/LICENSE 落盘）这一步**同时**落盘，跟 .gitignore/LICENSE 一起进扫描。
- 清理完成后、commit 之前，多一步 Step 6.6 刷新 README。

新建路径执行顺序：`Step 2a 选配置 → Step 6 落盘 .gitignore/LICENSE + Step 6.5 落盘 README 草稿 → Step 3 扫描（含 README）→ Step 4/5 确认清理 → Step 6.6 刷新 README → Step 7 commit/push → Step 7.5 设仓库门面`。

更新路径执行顺序：`Step 2b → Step 6.5 问要不要重写 README（要重写则落盘草稿）→ Step 3 扫描 → Step 4/5 清理 → Step 6.6 刷新 README（若重写过）→ Step 7 commit/push → Step 7.5 问要不要更新描述/topics`。

> 编号 6.5/6.6/7.5 是新插步骤，现有 Step 1–9 编号不变；agent 按 Step 编号顺序读，每个新步骤的执行时机在该步骤正文里**显式写明**（「在 Step X 之后、Step Y 之前」），不靠散文澄清、不要求 agent 跳读。

Step 9 报告里多报一条「门面装饰摘要」。Step 8/9 编号不变。

## Step 6.5：门面装饰·README 起草

### 执行时机

在 Step 6（.gitignore/LICENSE 落盘）之后、Step 3 扫描之前。README 草稿与 .gitignore/LICENSE 同批落盘，进扫描。

### 触发条件

- 新建仓库路径（Step 2a）：自动执行。
- 更新已有仓库路径（Step 2b）：先问「要不要重写 README」，默认不动。

### 已有 README 检测

检测根目录及 `docs/` 下的 README 文件：`README.md` / `README.rst` / `README` / `README.markdown` / `README.txt` / `README.zh.md` / `README.cn.md`（大小写不敏感）。若多处存在，优先根目录。检测到则问用户「保留 / 重写」。

### 重写前的备份

重写 README 前，先判断 README 是否已被 git 跟踪：
- **已被跟踪**（`git ls-files` 能查到）：可直接重写，内容可从 git 历史恢复。
- **未被跟踪**（新仓库 state A，README 是用户手写的未提交文件）：先备份为 `README.bak.md`，再重写。报告里提示用户「原 README 已备份为 README.bak.md，确认无误后可删除」。

不默认重写。无 README 时直接走生成流程。

### 内容来源：AI 起草 + 用户确认关键信息

1. **AI 读代码起草**——读码范围**有界**，避免大项目读爆 context：
   - 必读：入口文件（`main.py`/`index.js`/`app.py`/`main.go` 等）、依赖清单（`requirements.txt`/`package.json`/`go.mod`/`Cargo.toml` 等）、顶层目录结构、现有 README/文档。
   - 按需：配置文件、CLI 参数定义。
2. **合并确认**（用一次 `AskUserQuestion` 多字段问询，不逐子项问）：
   - 项目一句话介绍（AI 给草稿，用户可改）
   - 核心功能亮点 2–4 条（AI 从代码推断，用户勾选/增删）
   - README 语言（AI 判定，用户确认，见下文「语言判定」）
3. 用户确认后，AI 生成 README 草稿落盘。

### README 结构模板

固定骨架：

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
<AI 扫目录生成的两级树——此节为占位，Step 6.6 清理后回填定稿>

## License
<见下文分支>
```

**License 章节分支**：
- 用户在 Step 2a 选了 LICENSE（MIT/Apache-2.0/...）：写「本项目采用 <LICENSE> 协议，详见 [LICENSE](LICENSE)」。
- 用户选了「不生成」：写「License: 待定」并留占位提示让用户填。

### 语言判定

- 有代码注释：按注释主体语言判定。
- 无注释/无法判定（纯数据、配置项目、空仓库）：默认中文（与 SKILL.md 一致），在确认问询里让用户可改。
- 中英混合：按注释主体语言；旗鼓相当时默认中文并让用户确认。

### 风格约束

- 不堆 badge，不放截图占位，不造图。
- 推断不准的章节留简短占位提示让用户填，不编造内容。

## Step 6.6：门面装饰·README 刷新

### 执行时机

在 Step 5（应用清理）之后、Step 7（commit）之前。仅当 Step 6.5 生成了/重写了 README 草稿时执行；若用户在 6.5 选了「保留原 README」则跳过。

### 刷新内容

1. **目录树回填**：清理可能删除了 `.claude/`、`task_plan.md`、`findings.md`、`progress.md` 等文件。重新扫描目录，把「## 目录结构」章节回填为清理后的真实两级树，不列已删文件。
2. **README 清理可读性复核**：Step 3 扫描可能命中 README 里的隐私行（AI 写用法示例时把真实路径/邮箱抄进去），Step 5 默认按 scan.py suggestion 替换为 `<REDACTED>` 类占位——这对代码合理，对 README 说明性示例会**坏掉可读性**（如 `python main.py --config <LOCAL-PATH-WIN>`）。
   - agent 对 README 里的每一处扫描命中，改写为**通用占位示例**而非 `<REDACTED>`：
     - 本地路径 → `/path/to/config.ini` 或 `./config.ini`
     - 邮箱 → `you@example.com`
     - 手机 → `13800000000`
     - API key → `your-api-key-here`
   - 刷新后 agent 通读一遍 README，确认示例行仍读得通。

### 新增脚本/依赖

Step 6.5/6.6 纯靠 agent 读代码 + 写文件，**不引入新脚本、不加新依赖**（topics 归一化脚本见 Step 7.5）。

## Step 7.5：门面装饰·仓库层（描述 + topics）

### 执行时机

在 Step 7（push）之后、Step 8（EXE/Release）之前。**Step 7 push 失败则跳过 7.5**，直接进 Step 9 报告失败——仓库不存在时 `gh repo edit` 必然失败，不白跑。

### 触发条件

- 新建仓库路径：push 成功后自动执行。
- 更新已有仓库路径：先问「要不要顺便更新仓库描述/topics」，说要才跑。

### 仓库描述（description）

**统一来源**（删掉 v1 的「对比」模糊逻辑）：
- 新建路径：复用 Step 6.5 里用户确认过的「项目一句话介绍」。Step 2a **不再单独问描述、`gh repo create` 不带 `--description`**，统一在 7.5 设置，避免描述被设两次。
- 更新路径：读现有 README 第一段作草稿，用 `AskUserQuestion` 让用户确认或改。

**设置**：
```bash
gh repo edit <owner>/<repo> --description "<描述>"
```
**shell 转义**：描述若含 `"`/`$`/反引号等 shell 元字符，用单引号包裹或经 gh 参数传递避免展开；agent 设置前校验内容。

### topics 话题标签

**来源**：AI 推断 + 用户勾选。

1. AI 读代码推断候选 topics：主语言（`python`/`typescript`/`go`…）、框架/依赖名（`customtkinter`/`fastapi`/`react`…）、项目类型词（`automation`/`cli`/`gui`/`web-scraper`…），凑 4–8 个候选。
2. 用 `AskUserQuestion` 把候选列出来让用户多选勾选，也可自己补。
3. 用户选完，经 `scripts/normalize_topics.py` 归一化校验后，用 `gh repo edit` 加上。

**归一化脚本** `scripts/normalize_topics.py`（新增）：
- 输入：topic 字符串列表（命令行参数或 stdin）。
- 规则：全小写；非 `[a-z0-9-]` 字符转连字符；压缩连续连字符；去首尾连字符；超 50 字符截断；去重；总数 ≤20（超出截断并警告）。
- 输出：归一化后的 topic 列表 + 任何被改动的告警。
- 不靠 agent 心算——`gh repo edit --add-topic` 对非法字符（`C++`、`_`、大写、空格）会直接报错，脚本兜底。

**更新路径的 topics 模式**：更新路径问 topics 时多一档选择——「仅追加」/「替换全部」。替换全部时先 `gh repo edit --remove-topic` 现有 topics 再 `--add-topic` 新的。

### 失败处理

- Step 7 push 失败：跳过 7.5，进 Step 9 报告失败。
- `gh repo edit` 失败（网络/权限）：不卡流程，记下来在 Step 9 报告提示「仓库描述/topics 设置失败，可手动补」。README 已在仓库里，门面主体不丢。
- topics 推断不出任何候选：跳过 topics，只设描述，报告提一句「未自动设 topics」。

## Step 9 报告补充

加一条「门面装饰摘要」：
```
门面装饰：
  - README：新生成 / 已保留原版 / 已重写（原版备份于 README.bak.md）
  - 仓库描述：已设置 "<描述>" / 设置失败 / 已跳过
  - topics：python, automation, gui（共 3 个）/ 未设置（推断失败）/ 已跳过
```

## 硬性规则补充

在现有「硬性规则」清单里加两条：

1. **门面装饰只在新建仓库自动走全套；更新已有仓库必须先问，默认不动**——防把老仓库精心弄的 README/描述/topics 覆盖掉。
2. **重写 README、设置 topics 前至少一次 `AskUserQuestion` 确认**——不替用户决定 README 保留还是重写、不替用户定 topics。确认点合并成多字段一次问询，不逐子项追问（照顾用户对反复确认的抵触）。

## 边界

在现有「边界」表补「门面」条目：

本 skill **可以**做：
- 生成/重写 README（含清理后刷新）
- 用 `gh repo edit` 设置仓库描述和 topics

本 skill **不**做：
- 生成封面图 / social preview
- 加 badge
- 加 CONTRIBUTING 等配套文档
- 改 default branch / pages / wiki

## 对现有文件的影响

| 文件 | 改动 |
|---|---|
| `SKILL.md` | 插 Step 6.5（README 起草）、6.6（README 刷新）、7.5（仓库层）三节，每节显式写明执行时机；Step 2a 去掉单独问描述、`gh repo create` 去 `--description`；Step 9 报告补门面摘要；硬性规则补两条；边界表补「门面」条目 |
| `scripts/scan.py` | 不动——门面流程依赖 scan.py 扫描 README，但 scan.py 逻辑本身不改 |
| `scripts/normalize_topics.py` | **新增**——topics 归一化校验脚本 |
| `references/patterns.md` | 不动 |
| `references/gitignore-templates.md` | 不动 |
| `assets/` | 不动 |
| `scripts/gen_cover.py` | 不创建——封面图这版不做 |

本次优化改 `SKILL.md` + 新增 `scripts/normalize_topics.py`，不碰 scan.py 逻辑、不碰正则、不加运行时依赖（normalize_topics.py 用标准库）。

## commit message 规范

- README 重写/新生成的 commit 用 `docs: add README` / `docs: rewrite README`。
- topics 归一化脚本用 `feat: add normalize_topics.py`。
- SKILL.md 流程改动用 `feat: add facade decoration to Togithub skill`。
- 均不带 `Co-Authored-By: Claude`（沿用现有硬性规则）。

## 验证方式（边界用例 checklist）

改完后人工程读 + 实跑，必测以下边界：

1. **新建路径，无 README**：6.5 生成草稿 → 3 扫描 → 6.6 刷新 → 7 push → 7.5 设描述+topics，全流程通。
2. **新建路径，README 草稿含 AI 抄进的真实路径/邮箱**：扫描命中 → 6.6 改写为通用占位示例（非 `<REDACTED>`），README 可读。
3. **新建路径，目录含 `.claude/`、`task_plan.md`**：清理删除后，6.6 目录树不列这些已删文件。
4. **更新路径，已有 README**：6.5 问保留/重写；选重写且 README 未跟踪 → 备份 `README.bak.md`。
5. **更新路径，topics 过时**：7.5 问「仅追加/替换全部」，替换全部能清旧加新。
6. **空仓库/纯数据项目**：语言判定走兜底（默认中文 + 让用户确认）。
7. **用户选「不生成 LICENSE」**：README License 章节写「待定」占位。
8. **Step 7 push 失败**：7.5 跳过，Step 9 报告失败。
9. **topics 含非法字符（如 `C++`）**：normalize_topics.py 归一化为 `c` 并告警，gh 不报错。
10. **`gh repo edit` 失败（断网）**：流程不卡，报告提示「设置失败可手动补」。
