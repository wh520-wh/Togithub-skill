# 降低 scan.py 误报 —— 设计文档

- 日期：2026-06-21
- 范围：`scripts/scan.py`（及配套 `references/patterns.md`、`SKILL.md` 描述）
- 目标：在不削弱真问题（danger/warn）检测能力的前提下，大幅降低 info 级 hint 与三类隐私模式的误报，消除"一行一条"导致的洪水式上报。

## 背景与根因

用户反馈用 Togithub 推项目时扫描出大量误报。经核查，主要元凶是 `org-name-hint`：

- `ORG_NAME_HINT` 对公司名使用了 `re.IGNORECASE`，导致 `metadata`/`metaphor`/`apple pie`/`und mit`（德语）这类普通文本被命中 `Meta`/`Apple`/`MIT`。
- `EXCLUDE_CONTEXT` 的后缀（如 `Maps`/`Cloud`/`Fonts`）因空格边界处理不当，本应排除的 `Google Maps SDK` 仍被命中。
- `ORG_NAME_HINT_MIT` 用 `IGNORECASE` 匹配独立 `MIT`，把德语 `mit` 也命中。
- info 级 hint 在 `scan_line` 中**每命中一行生成一条 Finding**，在含大量 `metadata` 的代码库里直接炸出上千条。

此外，邮箱/本地路径/私有 IP 三类规则也缺少占位符白名单，会把示例值（`noreply@github.com`、`/home/user`、`192.168.0.1`）当真实隐私上报。

## 不改动的内容

- 危险文件检测（`.env`/`.pem`/`id_rsa` 等）
- AI 内容痕迹检测（`Co-Authored-By`/`<system-reminder>` 等）
- 真实 secret/key 正则（aws/github/aliyun/stripe/jwt 等）及其 `danger` 严重度
- 严重度体系（info/warn/danger）与 `_DANGER_PRIVACY` 集合
- 历史扫描机制（`--scan-history`/`--history-only`）
- 文件遍历、`SKIP_DIRS`、`SCANNABLE_EXTS`、`LARGE_FILE_BYTES` 等基础设施

所有 `warn`/`danger` 级真问题保持逐条可见、不被聚合、不被白名单吞掉。

## 设计

### 1. org-name-hint：收窄到署名行 + 修大小写/撞名词

将 `ORG_NAME_HINT` 从"扫描每一行"改为"只扫描署名/归属行"。署名行定义沿用现有 `NAME_HINT_PATTERNS` 的前缀思路：行首（允许 `#`/`*`/`-`/空白）匹配 `Author|Maintainer|Owner|Created by|作者|By` 等。

实现：新增一个判断"是否署名行"的辅助正则 `ATTRIBUTION_LINE`，`scan_line` 中仅在署名行上运行 `ORG_NAME_HINT`，而非全文。

具体改正：

- 去掉 `ORG_NAME_HINT` 的 `re.IGNORECASE`，公司名按真实大小写匹配（`Meta` ≠ `metadata`，`Apple` ≠ `apple pie`）。
- `Meta`/`Apple`/`Amazon` 这三个与普通英文撞名的词，**不再作为裸词匹配**。改为仅在它们作为邮箱域名出现（`@meta.com`/`@apple.com`/`@amazon.com`）时，由 email 规则间接覆盖；org-name-hint 不再单独报它们。
- 修复 `EXCLUDE_CONTEXT` 的空格边界，使 `Maps`/`Cloud`/`Fonts`/`Translate` 等后缀真正吃掉前导空格，`Google Maps SDK` 等合法 SDK 名被正确排除。
- `ORG_NAME_HINT_MIT` 去掉 `IGNORECASE`（杀掉德语 `mit`），保留"不跟 License/许可证/协议/许可"过滤。
- 保留下来的学校名（武大/清华/北大/复旦/上交/浙大/中山/华科）与区分度高的公司名（Tencent/Alibaba/Baidu/Bytedance/Huawei/NetEase/Meituan）按真实大小写 + 词边界匹配，**仅在署名行上**生效。

预期效果：正文里的 `metadata`/`viewport`/`apple pie`/`und mit` 彻底不报；真署名行 `Author: 张三 Tencent` 仍能报。

### 2. info 级 hint 聚合上报（治洪水）

将"同一文件、同一 info 级 hint 类型"的多条命中合并为一条 Finding：

- 聚合维度：`path` × `pattern`（pattern 为 `org-name-hint` 或 `real-name-hint`）。
- 聚合后 `snippet` 取该文件该类型的**第一条**命中行。
- 新增字段 `count`（命中次数），写入 `Finding`；JSON 输出自然带上。
- 只对 `info` 级聚合；`warn`/`danger` 级**逐条保留**，不聚合。

实现位置：在 `main()` 的文件扫描循环里，对 `scan_file_content` 返回的 findings 做一次按 `(path, pattern)` 的聚合（仅当 `severity == "info"`）。

### 3. 邮箱白名单

新增 `SAFE_EMAIL_DOMAINS` 与 `SAFE_EMAIL_LOCALS` 集合，email 规则命中后做白名单过滤：

- 安全域名（不报）：`example.com`/`example.org`/`example.net`/`test.com`/`localhost`/`invalid`。
- 安全整地址前缀（local 部分为占位符则不报）：`noreply`/`user`/`foo`/`bar`/`your-email`/`your.email`/`email`/`test`/`example`/`admin`（仅当域名也在安全域内时）。
- 特例整地址：`noreply@github.com`、`*@users.noreply.github.com`。

不在白名单的真实邮箱仍按 `warn` 报。过滤逻辑放在 `scan_line` 的 email 命中分支内。

### 4. 本地路径：占位用户名不报

`local-path-win`/`local-path-unix` 命中后，提取捕获的用户名段，若为占位符则不报：

- 占位符集合：`user`/`username`/`user-name`/`alice`/`bob`/`foo`/`bar`/`yourname`/`your-name`/`name`/`project`/`app`/`home`/`example`（大小写不敏感）。
- 是占位符 → 不报；不是 → 保留 `warn`。

需要给两个 local-path 正则加捕获组以取出用户名段，再在 `scan_line` 中判断。

### 5. 私有 IP：教科书默认值不报

新增 `SAFE_PRIVATE_IPS` 集合，`ipv4-private` 命中后若匹配到的整串在集合内则不报：

- 默认网关/通用值：`192.168.0.1`/`192.168.1.1`/`10.0.0.1`/`10.0.0.2`/`0.0.0.0`/`255.255.255.255`。
- 其余私有 IP（如 `192.168.1.100`）仍按 `warn` 报，因为可能是真实内网主机。

注意：`ipv4-private` 正则需捕获完整 IP 串用于比对。

### 6. 自检与文档同步（硬性约束）

- 在 `_self_test` 中新增回归用例：
  - 不应命中：`metadata`/`metaphor`/`apple pie`/`und mit Liebe`/`viewport`/`Google Maps SDK`/`noreply@github.com`/`user@example.com`/`/home/user/x`/`C:\Users\user\`/`192.168.0.1`。
  - 应命中：`Author: 张三 Tencent`（署名行）/ 真实邮箱如 `zhangsan@realcompany.cn` / 真实路径如 `/home/zhangsan/x` / 真实私有 IP 如 `192.168.1.100`。
- 同步更新 `references/patterns.md`：说明 org-name-hint 仅在署名行生效、邮箱/路径/IP 的白名单规则、info 级聚合行为。
- 跑 `python scripts/scan.py .` 在本项目自检（本项目 SKILL.md/scan.py 自身含 `metadata`/`Microsoft` 等词，可反证规则收敛后不再洪水）。
- 检查 `SKILL.md` 中 Step 4（报告 + 确认）措辞是否与聚合后行为一致，必要时微调描述（不改变流程，只改文案）。

## 验收标准

1. `python scripts/scan.py --self-test` 全绿，含新增回归用例。
2. 在本项目自身目录跑 `python scripts/scan.py .`，`org-name-hint` 类命中数从"每文件多条"降为"每文件至多一条聚合项"或为 0（取决于本项目是否有署名行）。
3. `noreply@github.com`、`/home/user`、`192.168.0.1`、`Google Maps SDK`、`metadata` 不再出现在 findings 中。
4. 真实邮箱、真实路径、真实内网 IP、真实署名行仍能被报出。
5. `references/patterns.md` 与 `scan.py` 实现一致（无脱节）。

## 风险与缓解

- **白名单漏网某真实值**：占位符集合是有限枚举，存在把"碰巧叫 user 的真实用户"误判为占位的风险。缓解：占位符只覆盖最明显的教科书示例值；真实用户名（如 `zhangsan`）不在集合内，仍会报。用户若有特殊需求可用现有 `--exclude` 机制。
- **聚合掩盖真实问题**：只聚合 `info` 级，`warn`/`danger` 不受影响；聚合项仍带 `count` 与第一条 snippet，用户能感知规模。
- **署名行定义偏窄漏掉真实署名**：沿用现有 `NAME_HINT_PATTERNS` 的前缀集，与 real-name-hint 的判断口径一致，行为可预期。
