#!/usr/bin/env python3
"""Install the self-contained TriCouncil skill for Codex and/or WorkBuddy."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SOURCE = REPO_ROOT / "plugins" / "tricouncil-agent" / "skills" / "tricouncil"


def destination(host: str) -> Path:
    if host == "codex":
        root = Path(os.getenv("CODEX_HOME", Path.home() / ".codex"))
    elif host == "workbuddy":
        root = Path(os.getenv("WORKBUDDY_HOME", Path.home() / ".codebuddy"))
    else:
        raise ValueError(host)
    return root.expanduser() / "skills" / "tricouncil"


def install(host: str, force: bool) -> Path:
    target = destination(host)
    if target.exists():
        if not force:
            raise RuntimeError(f"{target} 已存在。使用 --force 更新；旧版本会先备份。")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = target.with_name(f"tricouncil.backup-{stamp}")
        target.replace(backup)
        print(f"已备份旧版本：{backup}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, target)
    runner = target / "scripts" / "tricouncil.py"
    if os.name != "nt":
        runner.chmod(0o755)
    print(f"已安装到 {host}：{target}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="安装 TriCouncil Skill")
    parser.add_argument("target", choices=["codex", "workbuddy", "all"])
    parser.add_argument("--force", action="store_true", help="备份并更新现有版本")
    parser.add_argument("--setup", action="store_true", help="安装后立即打开模型、API 和 Prompt 配置向导")
    args = parser.parse_args()
    hosts = ["codex", "workbuddy"] if args.target == "all" else [args.target]
    installed: list[Path] = []
    for host in hosts:
        installed.append(install(host, args.force))
    if args.setup:
        print("\n开始配置。直接回车即可保留推荐默认值。")
        completed = subprocess.run(
            [sys.executable, str(installed[0] / "scripts" / "tricouncil.py"), "setup"],
            check=False,
        )
        if completed.returncode:
            print("配置已保存但尚未完全就绪；稍后可运行 manage 继续。")
    print("请重启对应应用或新建任务，使 Skill 生效。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
