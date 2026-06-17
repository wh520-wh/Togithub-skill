# Togithub

> 推 GitHub 前自动清隐私和 AI 痕迹，再也不怕忘删 .env。

一个 Claude Code Skill：把本地项目推上 GitHub 之前，自动扫描并清理个人隐私信息、AI 协作痕迹、危险文件。逐项向你确认，绝不擅自删除。

## 你什么时候需要它？

**场景 1**：你用 Claude Code 写完一个项目，想推上 GitHub，但不确定代码里有没有泄露邮箱、手机号、API key。

**场景 2**：你的 git 历史里有 `Co-Authored-By: Claude`，不想让别人知道你用 AI 辅助开发。

**场景 3**：你有 `.env` 文件、本地路径 `D:\Users\你的名字\`，推之前想确认一遍。

## 它会交付什么？

安装后，用 `/Togithub` 或说"推送到 GitHub"触发。它会：

1. 扫描你的项目文件和 git 历史
2. 列出所有发现的问题（隐私/AI 痕迹/危险文件）
3. 逐项让你确认处理方式（删除/替换/跳过）
4. 提交并推送到 GitHub

扫描结果示例：

```json
{
  "summary": {
    "total": 12,
    "by_category": {
      "dangerous_file": 1,
      "ai_trace_content": 3,
      "privacy_pattern": 8
    },
    "by_severity": {
      "danger": 2,
      "warn": 7,
      "info": 3
    }
  },
  "findings": [
    {
      "category": "dangerous_file",
      "severity": "danger",
      "path": ".env",
      "suggestion": "绝不推送：加入 .gitignore 或改用环境变量"
    },
    {
      "category": "privacy_pattern",
      "severity": "danger",
      "path": "config.py",
      "line": 3,
      "pattern": "api-key",
      "snippet": "api_key = 'abcdefghijklmnopqrst'",
      "suggestion": "替换为占位符（如 `<API-KEY>`）或删除"
    }
  ]
}
```

## 快速开始

```bash
# 克隆到 Claude Code skills 目录
git clone https://github.com/wh520-wh/Togithub.git ~/.claude/skills/Togithub
```

然后在任何项目里说"推送到 GitHub"或 `/Togithub` 即可。

## 触发方式

以下任意一句话都能触发：

- 推送到 GitHub
- 推上 github
- publish to github
- 上传到 GitHub
- 发布到 GitHub
- 推到远程
- /Togithub

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

| 特性 | Togithub | 手动检查 | pre-commit hooks |
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
