# TriCouncil マルチモデル Agent

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

Codex と WorkBuddy で複数の AI モデルを連携させ、段階的な実行、独立レビュー、バグ修正、最終成果物の整理を行う、オープンソースかつサーバーレスの Skill / プラグインです。

## TriCouncil の特徴

- 1つのタスクで2つ、3つ、またはそれ以上のモデル API を利用できます。
- 各モデルにプロバイダー、エンドポイント、モデル名、役割、System Prompt を個別設定できます。
- ステージごとに実行モデルとレビューモデルを指定できます。
- モデルの追加、編集、削除、有効化、無効化をいつでも行えます。
- API Key を Git、Prompt、タスクログに保存しません。
- Web UI や常駐バックエンドは不要です。
- 同じ自己完結型 Skill を Codex と WorkBuddy にインストールできます。

## Clone 後のインストール

```bash
git clone git@github.com:xuduoyun781/tricouncil-multi-model-agent.git
cd tricouncil-multi-model-agent

# 推奨：インストール後すぐに安全な設定ウィザードを開く
./install.sh codex --setup
./install.sh workbuddy --setup

# 両方にインストールし、設定は一度だけ行う
./install.sh all --setup
```

Windows PowerShell：

```powershell
.\install.ps1 codex -Setup
.\install.ps1 workbuddy -Setup
.\install.ps1 all -Setup
```

更新時は `--force`、PowerShell では `-Force` を追加してください。既存バージョンは置換前にバックアップされます。

## モデル、API、Prompt の設定

設定ウィザードでは、モデルごとに次の項目を確認します。

1. モデルを有効にするか。
2. OpenAI 互換、Anthropic、Gemini のいずれを使用するか。
3. モデル名と API エンドポイント。
4. 非表示入力による API Key。
5. モデルの役割と専用 System Prompt。
6. 実行またはレビューを担当するステージ。
7. ステージ結果を統合するモデル。

Enter を押すと推奨デフォルトを維持できます。後からいつでも再設定できます。

```bash
# Codex
python3 ~/.codex/skills/tricouncil/scripts/tricouncil.py manage

# WorkBuddy / CodeBuddy
python3 ~/.codebuddy/skills/tricouncil/scripts/tricouncil.py manage
```

Codex または WorkBuddy に自然言語で依頼することもできます。

> TriCouncil に DeepSeek を追加し、コードレビューを担当させてください。

> Gemini を無効にして、メインモデルの Prompt を変更してください。

> TriCouncil の API と各ステージの役割を設定してください。

API Key をチャットに貼り付けないでください。Skill はキー入力を端末の非表示プロンプトへ誘導します。

## ワークフロー

```text
タスク
  ↓
計画：並列生成 → 独立レビュー → コーディネーターによる統合
  ↓
実行：並列作業 → 独立レビュー → 統合
  ↓
検証：検証モデルが結果を確認 → 他モデルが検証内容を再確認
  ↓
修正と納品：修正、テスト、パッケージ計画 → 最終クロスレビュー
```

指定されたモデルが無効の場合、TriCouncil は有効なモデルから代替を選択します。独立レビューを維持するため、少なくとも2つのモデルを有効にする必要があります。

## 対応 API

- OpenAI および OpenAI 互換 Chat Completions API
- Anthropic Messages API
- Google Gemini `generateContent`
- 有料 API を呼び出さないローカルデモプロバイダー

## セキュリティ

- API Key は `~/.config/tricouncil/secrets.json` にユーザー専用権限で保存されます。
- モデル設定と Prompt は `~/.config/tricouncil/config.json` に保存されます。
- Key はリポジトリ、タスク Prompt、実行ログに書き込まれません。
- 無効なモデルは呼び出されず、API コストも発生しません。
- `self-test` はローカルデモモデルのみを使用します。

## ローカル検証

```bash
python3 plugins/tricouncil-agent/skills/tricouncil/scripts/tricouncil.py self-test
```

## ライセンス

MIT
