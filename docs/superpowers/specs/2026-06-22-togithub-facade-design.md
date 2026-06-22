# Togithub Skill 门面装饰优化设计

日期：2026-06-22
状态：待实现

## 背景与动机

当前 `/Togithub` skill 的定位是「扫干净隐私 → 推上 GitHub → 完事」。推送完成后仓库内容光秃秃，仅有一堆代码，缺乏一个正经开源项目应有的「门面」——README 排版简陋或缺失、仓库描述/topics 未设置。点开仓库第一眼不像用心做的项目，像临时裸推的代码堆。

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
| 门面触发时机 | 新建仓库自动走全套；更新已有仓库先问，默认不动 | 保护老仓库已精心弄好的 README/描述/topics，不自作主张覆盖 |
| README 内容来源 | AI 起草 + 用户确认关键信息 | 比纯自动准、比纯模板省事 |
| 已有 README 处理 | 问用户「保留 / 重写」二选一 | 不默认重写，不备份覆盖，避免丢原有内容 |
| topics 来源 | AI 推断候选 + 用户勾选 | 防瞎填不准标签 |
| 整体方案 | 方案 A：能自动的自动，不能自动的不强求 | 不踩未公开 GraphQL 接口的雷 |
| 封面图 | 不做 | 本轮明确排除 |

## 流程改造

在现有 Step 1–9 之间插入两步，不重排原有步骤：

- **Step 6.5 门面装饰·文件层**：生成 README，落盘到仓库，跟 .gitignore/LICENSE 一起进首批待扫描/待提交文件。

  **时序澄清**：现有 SKILL.md 的 Step 2a 铁律是「先落盘 .gitignore/LICENSE → 再走 Step 3 扫描 → 再 commit」。README 必须落盘在**扫描之前**，与 .gitignore/LICENSE 同批——这样 Step 3 扫描能覆盖到刚生成的 README，把 AI 不慎写进 README 的邮箱/本地路径等隐私扫出来一并清理；若 README 落盘在扫描之后，则其自身成为扫描盲区。

  因此实际执行顺序为：生成 .gitignore + LICENSE + README（Step 6.5 文件层）→ Step 3 扫描（含 README）→ Step 4/5 确认清理 → Step 7 commit/push。Step 6.5 的「编号位置」靠后（在 Step 6 之后），但其「落盘动作」插在 Step 3 扫描之前。spec 描述的 Step 编号顺序是给 agent 看的阅读顺序，落盘时序以本段澄清为准。
- **Step 7.5 门面装饰·仓库层**：插在 Step 7（push）之后、Step 8（EXE/Release）之前。用 `gh repo edit` 设描述 + topics。

**关键顺序**（沿用现有铁律）：门面文件先落盘 → 再扫描 → 再 commit → 再 push → 再设仓库门面。绝不先 push 再补门面，否则首推就是光秃秃的。

Step 8/9（Release/报告）顺延为 Step 8/9 不变，Step 9 报告里多报一条「门面装饰摘要」。

## Step 6.5：门面装饰·文件层（README）

### 触发条件

- 新建仓库路径（Step 2a）：自动执行。
- 更新已有仓库路径（Step 2b）：先问「要不要动 README」，默认不动。

### 已有 README 处理

若项目已存在 README（README.md / README.rst / README 等），用 `AskUserQuestion` 问用户：
- 保留原 README
- 让 AI 重写一份

不默认重写，不备份覆盖。无 README 时直接走生成流程。

### 内容来源：AI 起草 + 用户确认关键信息

1. AI 读代码（入口文件、配置、依赖清单、现有文档/注释）起草 README。
2. 用 `AskUserQuestion` 抽关键信息让用户确认/填：
   - 项目一句话介绍（AI 给草稿，用户可改）
   - 核心功能亮点 2–4 条（AI 从代码推断，用户勾选/增删）
   - 目标用户/场景（可选，AI 草稿）
3. 用户确认后，AI 生成最终 README。

### README 结构模板

固定骨架，填确认后的内容：

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
<AI 扫目录生成的两级树>

## License
<与 Step 6 选的 LICENSE 一致>
```

### 风格约束

- 中文项目用中文 README，英文项目用英文（按现有文件语言判定）。
- 不堆 badge。
- 不放截图占位，不造图。
- 推断不准的章节留简短占位提示让用户填，不编造内容。

### 新增脚本/依赖

无。这步纯靠 agent 读代码 + 写文件，不引入新脚本、不加新依赖。

## Step 7.5：门面装饰·仓库层（描述 + topics）

### 触发条件

- 新建仓库路径：push 成功后自动执行。
- 更新已有仓库路径：先问「要不要顺便更新仓库描述/topics」，说要才跑。

### 仓库描述（description）

**来源**：复用 Step 6.5 里用户确认过的「项目一句话介绍」，不重复问。若 Step 2a 新建时用户填过描述，对比：Step 6.5 的那句更准就用那句，否则沿用 Step 2a 填的。

**设置**：
```bash
gh repo edit <owner>/<repo> --description "<描述>"
```

### topics 话题标签

**来源**：AI 推断 + 用户勾选。

1. AI 读代码推断候选 topics：主语言（`python`/`typescript`/`go`…）、框架/依赖名（`customtkinter`/`fastapi`/`react`…）、项目类型词（`automation`/`cli`/`gui`/`web-scraper`…），凑 4–8 个候选。
2. 用 `AskUserQuestion` 把候选列出来让用户多选勾选，也可自己补。
3. 用户选完，AI 用 `gh repo edit` 一次性加上：
```bash
gh repo edit <owner>/<repo> --add-topic <topic1> --add-topic <topic2> ...
```

**归一化约束**：GitHub topics 每个限 50 字符、全小写、只能字母数字和连字符，总数上限 20。AI 推断时直接按这规则归一化（大写转小写、空格转连字符、超长截断），不让脏数据捅到 `gh` 报错。

### 失败处理

- `gh repo edit` 失败（网络/权限）：不卡住整个流程，记下来在 Step 9 报告里提示「仓库描述/topics 设置失败，可手动补」。README 已在仓库里，门面主体不丢。
- topics 推断不出任何候选（项目太怪）：跳过 topics，只设描述，报告里提一句「未自动设 topics」。

## Step 9 报告补充

在现有报告输出里加一条「门面装饰摘要」，形如：

```
门面装饰：
  - README：新生成 / 已保留原版 / 已重写
  - 仓库描述：已设置 "<描述>"
  - topics：python, automation, gui（共 3 个）/ 未设置（推断失败）/ 已跳过
```

让人一眼看清这次到底装了什么、没装什么。

## 硬性规则补充

在现有「硬性规则」清单里加两条：

1. **门面装饰只在新建仓库自动走全套；更新已有仓库必须先问，默认不动**——防把老仓库精心弄的 README/描述/topics 覆盖掉。
2. **README 重写、topics 设置每一步都走 `AskUserQuestion` 确认**——不替用户决定 README 保留还是重写、不替用户定 topics，跟现有"绝不自动删除/force push"一脉相承。

## 边界

在现有「边界」表里补「门面」相关条目：

本 skill **可以**做：
- 生成/重写 README
- 用 `gh repo edit` 设置仓库描述和 topics

本 skill **不**做：
- 生成封面图 / social preview
- 加 badge
- 加 CONTRIBUTING 等配套文档
- 改 default branch / pages / wiki

## 对现有文件的影响

| 文件 | 改动 |
|---|---|
| `SKILL.md` | Step 1–9 之间插 6.5、7.5 两节；Step 9 报告补门面摘要；硬性规则补两条；边界表补「门面」条目 |
| `scripts/scan.py` | 不动——门面是 agent 层逻辑，不靠扫描器 |
| `references/patterns.md` | 不动——没加新正则 |
| `references/gitignore-templates.md` | 不动 |
| `assets/` | 不动 |
| `scripts/gen_cover.py` | 不创建——封面图这版不做 |

本次优化**只改 SKILL.md 一个文件**，不碰脚本、不碰正则、不加依赖。

## 验证方式

- 改完 SKILL.md 后人工走读：确认 6.5、7.5 两节插对位置、与现有 Step 衔接无断裂。
- 在一个测试项目上实跑 `/Togithub`，确认：新建仓库时 README 生成、描述/topics 设置都按设计走；已有 README 时会问保留/重写。
- 更新已有仓库路径，确认会先问再动门面。
- `gh repo edit` 故意失败（断网/坏 token），确认流程不卡、报告里有提示。
