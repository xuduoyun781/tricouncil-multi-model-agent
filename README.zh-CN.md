# TriCouncil 多模型协作 Agent

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

一个开源、无服务器的 Skill/插件，让 Codex 和 WorkBuddy 调用多个 AI 模型，完成分阶段执行、独立审查、Bug 修复和最终交付。

## 为什么使用 TriCouncil？

- 一个任务可同时使用 2、3 个或更多模型 API。
- 每个模型拥有独立的供应商、接口地址、模型名、角色和系统 Prompt。
- 每个阶段可以分别指定执行模型与审查模型。
- 随时新增、编辑、删除、启用或关闭模型。
- API Key 不进入 Git、Prompt 或任务日志。
- 不需要网页界面或常驻后端。
- 同一份自包含 Skill 可安装到 Codex 和 WorkBuddy。

## Clone 后安装

```bash
git clone git@github.com:xuduoyun781/tricouncil-multi-model-agent.git
cd tricouncil-multi-model-agent

# 推荐：安装后立即进入安全配置向导
./install.sh codex --setup
./install.sh workbuddy --setup

# 同时安装到两个平台，只配置一次
./install.sh all --setup
```

Windows PowerShell：

```powershell
.\install.ps1 codex -Setup
.\install.ps1 workbuddy -Setup
.\install.ps1 all -Setup
```

更新已有安装时添加 `--force`，PowerShell 使用 `-Force`。安装器会先备份旧版本。

## 配置模型、API 和 Prompt

向导会为每个模型询问：

1. 是否启用。
2. 接口类型：OpenAI 兼容、Anthropic 或 Gemini。
3. 模型名称和 API 地址。
4. 通过终端隐藏输入 API Key。
5. 模型角色和专属系统 Prompt。
6. 模型在哪些阶段执行或审查。
7. 哪个启用模型负责合并阶段结果。

直接回车即可保留推荐默认值。之后可随时重新配置：

```bash
# Codex
python3 ~/.codex/skills/tricouncil/scripts/tricouncil.py manage

# WorkBuddy / CodeBuddy
python3 ~/.codebuddy/skills/tricouncil/scripts/tricouncil.py manage
```

也可以直接对 Codex 或 WorkBuddy 说：

> 给 TriCouncil 新增一个 DeepSeek 模型，负责代码审查。

> 关闭 Gemini，并修改主模型的 Prompt。

> 配置 TriCouncil 的 API 和各阶段角色。

不要把 API Key 粘贴到聊天里。Skill 会将密钥输入转移到终端隐藏提示。

## 工作流程

```text
任务
  ↓
规划：模型并行产出 → 独立审查 → 协调模型合并
  ↓
执行：模型并行工作 → 独立审查 → 协调模型合并
  ↓
验证：验证模型检查结果 → 其他模型复核验证结论
  ↓
修复与交付：修复、测试、打包方案 → 最终交叉检查
```

如果某阶段指定的模型被关闭，TriCouncil 会从仍启用的模型中选择替代者。系统至少保留两个启用模型，以保证存在独立审查。

## 支持的 API

- OpenAI 及兼容 Chat Completions 的接口
- Anthropic Messages API
- Google Gemini `generateContent`
- 不调用付费 API 的本地演示模型

## 安全

- 密钥保存在 `~/.config/tricouncil/secrets.json`，权限仅当前用户可读。
- 模型设置与 Prompt 保存在 `~/.config/tricouncil/config.json`。
- 密钥不会写入仓库、任务 Prompt 或运行日志。
- 关闭的模型不会被调用，也不会产生模型费用。
- `self-test` 使用本地演示模型，不调用付费 API。

## 本地验证

```bash
python3 plugins/tricouncil-agent/skills/tricouncil/scripts/tricouncil.py self-test
```

## 许可证

MIT
