# Togithub-skill

> 推 GitHub 前的安全检查站——扫描、清理、确认、推送，一条命令搞定。

[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://claude.ai/code)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**你用 AI 写完代码，想推上 GitHub，但不确定有没有泄露邮箱、API key、`Co-Authored-By: Claude`。**

Togithub-skill 帮你：扫描项目文件和 git 历史 → 列出所有问题 → 逐项让你确认 → 提交推送。

## 快速开始

```bash
git clone https://github.com/wh520-wh/Togithub-skill.git ~/.claude/skills/Togithub-skill
```

然后在任何项目里说"推送到 GitHub"或 `/Togithub-skill` 即可。

## 扫描结果示例

```json
{
  "summary": { "total": 12, "danger": 2, "warn": 7, "info": 3 },
  "findings": [
    { "path": ".env", "severity": "danger", "suggestion": "绝不推送" },
    { "path": "config.py:3", "severity": "danger", "pattern": "api-key", "snippet": "api_key = 'abcdefghijklmnopqrst'" },
    { "path": "README.md:42", "severity": "warn", "pattern": "Co-Authored-By: Claude" }
  ]
}
```

## 触发方式

以下任意一句话都能触发：

- `/Togithub-skill`
- 推送到 GitHub / 推上 github / publish to github
- 上传到 GitHub / 发布到 GitHub / 推到远程

## 它扫描什么？

| 类别 | 检测内容 | 严重度 |
|---|---|---|
| **危险文件** | `.env`、`*.pem`、`id_rsa*`、`credentials.json` | 🔴 danger |
| **API 密钥** | AWS、阿里云、腾讯云、华为云、Stripe、Slack、Anthropic、OpenAI、npm、PyPI、Discord webhook | 🔴 danger |
| **个人信息** | 邮箱、手机号（国内）、身份证号、银行卡号 | 🟡 warn |
| **本地路径** | `D:\Users\...`、`/home/...`、`~/.ssh/...` | 🟡 warn |
| **AI 痕迹文件** | `.claude/`、`task_plan.md`、`.cursorrules`、`AGENTS.md` | 🟡 warn |
| **AI 痕迹内容** | `Co-Authored-By: Claude`、`Generated with Claude Code`、`<system-reminder>` | 🟡 warn |
| **组织名/学校名** | 清华、北大、Microsoft、Google 等（仅提示） | ℹ️ info |

完整正则表见 [`references/patterns.md`](references/patterns.md)。

## 它和同类有什么不同？

| 特性 | Togithub-skill | 手动检查 | pre-commit hooks |
|---|---|---|---|
| 扫描 git 历史 | ✅ | ❌ | ❌ |
| 逐项确认 | ✅ | ✅ | ❌（自动拒绝） |
| 覆盖国内隐私模式 | ✅（手机号、身份证、国内云密钥） | ❌ | ❌ |
| 清理 AI 痕迹 | ✅ | 容易漏 | ❌ |
| 一键推送 | ✅ | ❌ | ❌ |

## 安全边界

**不会做的事**：
- 不会自动删除任何文件——每项都向你确认
- 不会自动 force push 或重写历史——必须二次确认
- 不会推送 secrets——发现就停下警告
- 不会在 commit message 里带 `Co-Authored-By: Claude`

**会停下来问你的时刻**：
- 扫到大文件（>10MB）
- 扫到 `.env` 或私钥文件
- 需要重写 git 历史时
- 用户模糊回答（"随便"、"都行"）时默认跳过

## 文件结构

| 文件 | 作用 |
|---|---|
| `SKILL.md` | Skill 指令手册（9 步流程 + 硬性规则） |
| `scripts/scan.py` | 扫描脚本（支持文件扫描 + git 历史扫描） |
| `references/patterns.md` | 完整正则表（30+ 模式） |
| `references/gitignore-templates.md` | 按项目类型的 .gitignore 模板 |
| `assets/license-*.txt` | 5 种 LICENSE 模板 |

## 验证与测试

```bash
# 跑内置回归测试（27 项，验证正则和文件扫描逻辑）
python scripts/scan.py --self-test

# 在目标项目上跑一次真实扫描
python scripts/scan.py /path/to/your/project

# 跑 git 历史扫描
python scripts/scan.py /path/to/your/project --scan-history
```

## 前置条件

- Python 3.9+
- gh CLI（`winget install GitHub.cli`）
- gh 已登录（`gh auth login`）

## License

[MIT](LICENSE)
