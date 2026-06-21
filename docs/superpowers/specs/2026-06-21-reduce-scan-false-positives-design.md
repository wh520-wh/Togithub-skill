# 降低 scan.py 误报 —— 设计文档

- 日期：2026-06-21
- 范围：`scripts/scan.py`（及配套 `references/patterns.md`、`SKILL.md` 描述）
- 目标：在不削弱真问题（danger/warn）检测能力的前提下，大幅降低 info 级 hint 与三类隐私模式的误报，消除"一行一条"导致的洪水式上报（文件扫描 **与** 历史扫描均生效）。

## 背景与根因

用户反馈用 Togithub 推项目时扫描出大量误报。经核查，主要元凶是 `org-name-hint`：

- `ORG_NAME_HINT` 对公司名使用了 `re.IGNORECASE`，导致 `metadata`/`metaphor`/`apple pie`/`und mit`（德语）这类普通文本被命中 `Meta`/`Apple`/`MIT`。
- `ORG_NAME_HINT_MIT` 用 `IGNORECASE` 匹配独立 `MIT`，把德语 `mit` 也命中。
- info 级 hint 在 `scan_line` 中**每命中一行生成一条 Finding**，在含大量 `metadata` 的代码库里直接炸出上千条。

此外，邮箱/本地路径/私有 IP 三类规则也缺少占位符白名单，会把示例值（`noreply@github.com`、`/home/user`、`192.168.0.1`）当真实隐私上报。

> 说明：经实测，原 `EXCLUDE_CONTEXT`（用于排除 `Google Maps SDK`/`Apple Music` 等产品名）存在 `\s+` 缺失 bug，但本设计改为"org-name-hint 仅在署名行触发"后，正文里的产品名根本不再被扫描，该 bug 对正文已无意义。本设计**不修复** `EXCLUDE_CONTEXT`，原因见第 1 节"EXCLUDE_CONTEXT 去留"。

## 不改动的内容

- 危险文件检测（`.env`/`.pem`/`id_rsa` 等）
- AI 内容痕迹检测（`Co-Authored-By`/`<system-reminder>` 等）
- 真实 secret/key 正则（aws/github/aliyun/stripe/jwt 等）及其 `danger` 严重度
- 严重度体系（info/warn/danger）与 `_DANGER_PRIVACY` 集合
- 历史扫描机制（`--scan-history`/`--history-only`）的取数方式
- 文件遍历、`SKIP_DIRS`、`SCANNABLE_EXTS`、`LARGE_FILE_BYTES` 等基础设施

所有 `warn`/`danger` 级真问题保持逐条可见、不被聚合、不被白名单吞掉。

## 设计

### 1. org-name-hint：收窄到署名行 + 修大小写

将 `ORG_NAME_HINT` 从"扫描每一行"改为"只扫描署名/归属行"。

**署名行定义**：新增独立正则 `ATTRIBUTION_LINE`，只取前缀、**不要求**后面跟姓名（这点与 `NAME_HINT_PATTERNS` 不同——后者要求前缀后跟姓名，会漏掉 `Author: Tencent` 这类纯组织署名行）：

```
ATTRIBUTION_LINE = re.compile(
    r"^[\s#/*\-]*(?:作者|Author|Maintainer|Owner|Created\s+by|By|by)\s*[:：]?"
)
```

`scan_line` 中先判断 `ATTRIBUTION_LINE.search(line)`，仅当命中时才运行 `ORG_NAME_HINT`，否则跳过 org-name 检测。

**具体改正**：

- 去掉 `ORG_NAME_HINT` 的 `re.IGNORECASE`，公司名按真实大小写匹配（`Meta` ≠ `metadata`，`Apple` ≠ `apple pie`）。
- `Meta`/`Apple`/`Amazon` 这三个与普通英文撞名的词，**保留匹配、但仅在署名行上触发**（撞词风险已由"署名行门控 + 大小写敏感"双重收敛，不再需要靠 email 间接覆盖）。代价：`Author: Zhang San, Apple Inc.` 这类无邮箱署名仍能报出雇主归属（这是期望行为，见下）。
- `ORG_NAME_HINT_MIT` 去掉 `IGNORECASE`（杀掉德语 `mit`），保留"不跟 License/许可证/协议/许可"过滤；**并补 `\s*` 变体**，使 `本项目采用MIT协议`（中文无空格写法）也不报。
- 学校名（武汉大学/清华大学/北京大学/复旦大学/上海交通大学/浙江大学/中山大学/华中科技大学）与区分度高的公司名（Tencent/Alibaba/Baidu/Bytedance/Huawei/NetEase/Meituan）按真实大小写 + 词边界匹配，**仅在署名行上**生效。

**EXCLUDE_CONTEXT 去留**：保留原样、不修 `\s+` bug。理由：署名行门控使正文产品名不再被扫；而在署名行上（如 `Author: Zhang San (Google Maps SDK team)`），产品名恰恰暴露了真实雇主，**应报不应排除**，所以 EXCLUDE_CONTEXT 在署名行上反而有害，修复它没有收益。原 EXCLUDE_CONTEXT 代码可保留（无害）或一并删除（简化），实施时择一，不影响行为。

预期效果：正文里的 `metadata`/`viewport`/`apple pie`/`und mit`/`Google Maps SDK` 彻底不报；真署名行 `Author: 张三 Tencent`、`Author: Zhang San, Apple Inc.` 仍能报。

### 2. info 级 hint 聚合上报（治洪水，文件 + 历史均生效）

将"同一 `path`、同一 info 级 hint 类型"的多条命中合并为一条 Finding：

- 聚合维度：`path` × `pattern`（pattern 为 `org-name-hint` 或 `real-name-hint`）。历史扫描的 path 形如 `commit:<sha>:<file>:<line>`，天然按行不同 → 历史聚合维度退化为按 `commit:<sha>:<file>` 聚合（见下）。
- 聚合后字段：`snippet` 与 `line` 取该组**第一条**命中的行内容与行号；新增 `count` 字段记录命中次数。
- `count` 写入 `Finding` dataclass，默认 `None`；非聚合 finding（large_file/dangerous_file 等）JSON 中为 `"count": null`，可接受。
- 只对 `severity == "info"` 聚合；`warn`/`danger` 级**逐条保留**，不聚合。

**实现位置（关键修订）**：抽出一个独立函数 `aggregate_info_findings(findings: list[Finding]) -> list[Finding]`，在 `main()` 中对**文件扫描结果**和**历史扫描结果**分别调用一次后再合并。历史扫描因为 path 含行号，聚合 key 取 `commit:<sha>:<file>` 前缀（即去掉末尾 `:line`），保证 `--history-only` 模式下洪水同样被治理。

### 3. 邮箱白名单

email 规则命中后做白名单过滤，命中白名单则**该 email 不报**（走 `continue` 继续试同行其他隐私模式，见第 7 节）。

- **保留 TLD 后缀**（不报）：地址的顶级域属于 `.example`/`.test`/`.invalid`/`.localhost` 之一。理由：这些是 RFC 6761/2606 保留的示例 TLD，`user@example.com` 的 `.com` 不在此列但 `example.com` 域名整体保留（见下）。
- **保留域名**（不报）：`example.com`/`example.org`/`example.net`/`test.com`。
- **保留整地址**（不报）：`noreply@github.com`、local 段为 `noreply` 且域为 `github.com` 或 `users.noreply.github.com`。
- **占位 local 段**（仅当域名在保留域名内时不报）：`user`/`foo`/`bar`/`your-email`/`your.email`/`email`/`test`/`example`/`admin`。

**明确声明**：`apple.com`/`meta.com`/`amazon.com` **不在**白名单。`zhangsan@apple.com` 这类真实邮箱仍按 `email` 规则的 `warn` 报出——只是归属信号以 `email`(warn) 形式呈现，而不再是 `org-name-hint`(info)。这是可接受的语义迁移：真实邮箱本就是 warn 级真问题，比 info 更该报。

过滤逻辑放在 `scan_line` 的 email 命中分支内；先解出 local 与 domain 再判白名单。

### 4. 本地路径：占位用户名不报

`local-path-win`/`local-path-unix` 命中后，提取捕获的用户名段（需给两个正则加捕获组，组 1 = 用户名段），若为占位符则不报（走 `continue`）：

- 占位符集合（大小写不敏感）：`user`/`username`/`user-name`/`alice`/`bob`/`foo`/`bar`/`yourname`/`your-name`/`name`/`project`/`app`/`home`/`example`/`default`/`guest`/`admin`/`test`。
- 是占位符 → 不报；不是 → 保留 `warn`。
- 跨平台说明：Windows 下正斜杠路径 `C:/Users/user/` 会被 `local-path-unix` 命中，捕获组仍能正确取出 `user`，行为一致。

### 5. 私有 IP：教科书默认值不报

`ipv4-private` 命中后，用 `m.group()` 取完整 IP 串（**无需新增捕获组**，现有正则 `m.group()` 已返回完整 IP），若在集合内则不报（走 `continue`）：

- 默认网关/通用值：`192.168.0.1`/`192.168.1.1`/`10.0.0.1`/`10.0.0.2`。
- 其余私有 IP（如 `192.168.1.100`）仍按 `warn` 报，因为可能是真实内网主机。
- 不收录 `0.0.0.0`/`255.255.255.255`：实测它们不匹配 `ipv4-private` 正则（只匹配 10/192.168/172.16-31），收录即死代码。

### 6. 自检与文档同步（硬性约束）

**自检方法学（关键修订）**：现有 `check_pattern` 测的是裸正则，无法覆盖白名单/署名行门控。新增一个 `check_scan_line(label, text, expect_patterns: set)` helper：调用 `scan_line(text, 1, "test")`，取返回 findings 的 `pattern` 集合，与期望集合比对。所有"白名单不报 / 门控不报"用例必须走这个 helper。

回归用例：
- **不应命中**（期望空集合）：
  - 正文词：`metadata`、`metaphor`、`apple pie`、`viewport`、`und mit Liebe`、`Google Maps SDK`、`Microsoft YaHei`、`本项目采用MIT协议`。
  - 白名单邮箱：`noreply@github.com`、`user@example.com`、`foo@test.com`、`admin@example.invalid`。
  - 占位路径：`/home/user/x`、`C:\Users\user\x`、`/home/alice/.ssh`。
  - 教科书 IP：`192.168.0.1`、`10.0.0.1`。
- **应命中**：
  - 署名行：`Author: 张三 Tencent`（real-name-hint + org-name-hint）、`Author: Zhang San, Apple Inc.`（org-name-hint）、`Maintainer: Alibaba`（org-name-hint，纯组织署名）。
  - 真实邮箱：`zhangsan@realcompany.cn`、`zhangsan@apple.com`（均 email, warn）。
  - 真实路径：`/home/zhangsan/x`、`C:\Users\zhangsan\x`。
  - 真实私有 IP：`192.168.1.100`。
  - 同行多隐私不漏报：`contact: noreply@github.com 或 13812345678` 应命中 `phone-cn`（验证白名单走 continue 而非 break）。
- 聚合行为：新增一个 `scan_file_content` 级用例——构造一个含 3 行 `Author: 张三 Tencent` 的文件，断言聚合后该文件 `org-name-hint` 只剩 1 条、`count == 3`。

文档同步：
- 更新 `references/patterns.md`：说明 org-name-hint 仅在署名行生效（列出 `ATTRIBUTION_LINE`）、邮箱/路径/IP 的白名单规则、info 级聚合行为（文件+历史）。
- 跑 `python scripts/scan.py .` 在本项目自检（本项目 SKILL.md/scan.py 自身含 `metadata`/`Microsoft` 等词，可反证规则收敛后不再洪水）。
- 检查 `SKILL.md` 中 Step 4（报告 + 确认）措辞是否与聚合后行为一致，必要时微调描述（不改变流程，只改文案）。

## 验收标准

1. `python scripts/scan.py --self-test` 全绿，含上述 `check_scan_line` 与聚合用例。
2. 在本项目自身目录跑 `python scripts/scan.py .`，`org-name-hint` 类命中数从"每文件多条"降为"每文件至多一条聚合项"或为 0。
3. `--history-only` 模式下，同一文件多行 info 命中同样被聚合（按 `commit:<sha>:<file>` 聚合）。
4. `noreply@github.com`、`/home/user`、`192.168.0.1`、`Google Maps SDK`、`metadata`、`本项目采用MIT协议` 不再出现在 findings 中。
5. 真实邮箱（含 `apple.com`）、真实路径、真实内网 IP、真实署名行（含纯组织署名）仍能被报出。
6. `contact: noreply@github.com 或 13812345678` 这类同行多隐私，白名单邮箱不报但手机号仍报。
7. `references/patterns.md` 与 `scan.py` 实现一致（无脱节）。

## 风险与缓解

- **白名单漏网某真实值**：占位符集合是有限枚举，存在把"碰巧叫 user 的真实用户"误判为占位的风险。缓解：占位符只覆盖最明显的教科书示例值；真实用户名（如 `zhangsan`）不在集合内，仍会报。注：`--exclude` 是按文件路径 glob 过滤，**无法**针对单条邮箱/路径解白名单，因此白名单外的真实误报需通过调集合本身解决，不能用 `--exclude` 兜底。
- **聚合掩盖真实问题**：只聚合 `info` 级，`warn`/`danger` 不受影响；聚合项仍带 `count` 与第一条 snippet/line，用户能感知规模。
- **署名行门控漏掉真实署名**：`ATTRIBUTION_LINE` 覆盖 `Author/Maintainer/Owner/Created by/作者/By` 前缀，能抓纯组织署名（`Author: Tencent`）；未覆盖的非典型署名格式（如 `# written by Foo`）不会触发 org-name-hint，但这类归属信号较弱，可接受。
- **Meta/Apple/Amazon 在署名行仍可能撞词**：如 `Author: apple pie recipe`（极少见）。可接受，因为署名行上下文已大幅降低撞词概率，且真实署名行 `Author: Zhang San, Apple Inc.` 必须能报，权衡下保留匹配。
