# Changelog

## [Unreleased] - 鲁班工坊打磨

### Added
- `scripts/scan.py` 新增 `--self-test` 模式，内置 27 项回归测试（模式单元测试 + 文件扫描集成测试）
- `SKILL.md` 新增 Python 3.9+ 版本要求说明
- `SKILL.md` 新增"测试"章节，说明如何跑回归测试
- `CLAUDE.md` 新增，供 Claude Code 代理理解项目结构

### Fixed
- `scripts/scan.py` bank-card 正则误报：UUID 截断、SHA1 哈希等十六进制串不再被误判为银行卡号
- `scripts/scan.py` bank-card 正则误报：全重复数字（如 `1111111111111111`）不再被误判
- `scripts/scan.py` `.claude/` 目录检测：修复目录内文件（如 `.claude/memory.md`）不被识别为 AI 痕迹的问题

### Changed
- `scripts/scan.py` `match_ai_trace_file` 逻辑：现在同时检查完整路径和首级目录名
- `references/patterns.md` bank-card 描述更新，注明已排除十六进制和全重复数字
