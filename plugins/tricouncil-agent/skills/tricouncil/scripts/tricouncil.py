#!/usr/bin/env python3
"""TriCouncil: a dependency-free, no-server multi-model task runner."""

from __future__ import annotations

import argparse
import concurrent.futures
import getpass
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / ".config" / "tricouncil"
DEFAULT_CONFIG = CONFIG_DIR / "config.json"
SECRETS_FILE = CONFIG_DIR / "secrets.json"
PROVIDERS = {"openai_compatible", "anthropic", "gemini", "demo"}


def configure_console() -> None:
    """Keep multilingual output usable on Windows and in CI terminals."""
    if os.name != "nt":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"未找到 {path}；请先运行 init 或 setup") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON 无效：{path}:{exc.lineno}:{exc.colno}") from exc


def write_json(path: Path, data: Any, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp = Path(handle.name)
    if private:
        temp.chmod(0o600)
    temp.replace(path)


def secrets() -> dict[str, str]:
    if not SECRETS_FILE.exists():
        return {}
    return {str(k): str(v) for k, v in read_json(SECRETS_FILE).items()}


def key_for(agent: dict[str, Any]) -> str:
    name = agent.get("api_key_name", "")
    return os.getenv(name, "") or secrets().get(name, "")


def agents_by_id(config: dict[str, Any], enabled_only: bool = False) -> dict[str, dict[str, Any]]:
    items = config.get("agents", [])
    if enabled_only:
        items = [item for item in items if item.get("enabled", True)]
    return {item["id"]: item for item in items}


def validate(config: dict[str, Any], require_keys: bool = True) -> list[str]:
    errors: list[str] = []
    all_agents = config.get("agents", [])
    if not isinstance(all_agents, list) or len(all_agents) < 2:
        return ["至少要配置两个 agents"]
    ids = [agent.get("id") for agent in all_agents]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        errors.append("agent id 必须非空且不能重复")
    enabled = [agent for agent in all_agents if agent.get("enabled", True)]
    if len(enabled) < 2:
        errors.append("至少要启用两个模型")
    for agent in all_agents:
        identity = agent.get("id", "未知模型")
        if agent.get("provider") not in PROVIDERS:
            errors.append(f"{identity}: provider 不受支持")
        for field in ("label", "model", "role", "system_prompt"):
            if not agent.get(field):
                errors.append(f"{identity}: 缺少 {field}")
        if agent.get("enabled", True) and agent.get("provider") != "demo":
            if not agent.get("base_url"):
                errors.append(f"{identity}: 缺少 base_url")
            if not agent.get("api_key_name"):
                errors.append(f"{identity}: 缺少 api_key_name")
            elif require_keys and not key_for(agent):
                errors.append(f"{identity}: 未配置 {agent['api_key_name']}")
    known = set(ids)
    stages = config.get("stages", [])
    if not stages:
        errors.append("至少要配置一个 stage")
    for stage in stages:
        if not all(stage.get(x) for x in ("id", "name", "instruction")):
            errors.append("stage 必须包含 id、name 和 instruction")
        unknown = (set(stage.get("workers", [])) | set(stage.get("reviewers", []))) - known
        if unknown:
            errors.append(f"{stage.get('id', 'stage')}: 未知 agents {sorted(unknown)}")
    return errors


def api_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}（服务响应正文已隐藏）") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络连接失败：{exc.reason}") from exc


def call(agent: dict[str, Any], system: str, prompt: str, config: dict[str, Any]) -> str:
    provider = agent["provider"]
    if provider == "demo":
        time.sleep(0.05)
        if "独立审查" in prompt:
            return f"{agent['label']}：建议补充失败路径、证据、验收标准和回滚说明。"
        if "阶段协调者" in prompt:
            return "阶段共识：保留可执行结果，并补齐验证证据、异常处理和交付清单。"
        return f"{agent['label']}（{agent['role']}）：已完成本阶段，列出结果、风险和下一步。"

    base = agent["base_url"].rstrip("/")
    model = agent["model"]
    api_key = key_for(agent)
    timeout = float(config.get("timeout_seconds", 120))
    max_tokens = int(config.get("max_output_tokens", 3000))
    if provider == "openai_compatible":
        data = api_json(
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {api_key}"},
            {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "max_tokens": max_tokens},
            timeout,
        )
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            return "\n".join(item.get("text", "") for item in content if isinstance(item, dict))
        return str(content)
    if provider == "anthropic":
        data = api_json(
            f"{base}/v1/messages",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            {"model": model, "system": system, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens},
            timeout,
        )
        return "\n".join(item.get("text", "") for item in data["content"] if item.get("type") == "text")
    if provider == "gemini":
        safe_model = urllib.parse.quote(model, safe="-_.")
        safe_key = urllib.parse.quote(api_key, safe="")
        data = api_json(
            f"{base}/models/{safe_model}:generateContent?key={safe_key}",
            {},
            {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": max_tokens}},
            timeout,
        )
        return "\n".join(item.get("text", "") for item in data["candidates"][0]["content"]["parts"])
    raise RuntimeError(f"不支持 provider {provider}")


def safe_call(agent: dict[str, Any], system: str, prompt: str, config: dict[str, Any]) -> dict[str, Any]:
    attempts = int(config.get("retries", 2)) + 1
    for attempt in range(attempts):
        try:
            content = call(agent, system, prompt, config).strip()
            if not content:
                raise RuntimeError("空响应")
            return {"agent_id": agent["id"], "label": agent["label"], "content": content, "error": None}
        except Exception as exc:
            if attempt == attempts - 1:
                return {"agent_id": agent["id"], "label": agent["label"], "content": "", "error": f"{type(exc).__name__}: {exc}"}
            time.sleep(min(2**attempt, 4))
    raise AssertionError("unreachable")


def parallel(ids: list[str], agents: dict[str, dict[str, Any]], prompts: Callable, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not ids:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ids)) as pool:
        jobs = []
        for agent_id in ids:
            system, prompt = prompts(agents[agent_id])
            jobs.append(pool.submit(safe_call, agents[agent_id], system, prompt, config))
        return [job.result() for job in jobs]


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[-limit:] + "\n[较早内容已截断]"


def execute(config: dict[str, Any], task: str, output: Path) -> dict[str, Any]:
    problems = validate(config, require_keys=True)
    if problems:
        raise RuntimeError("配置检查失败：\n- " + "\n- ".join(problems))
    enabled = agents_by_id(config, enabled_only=True)
    enabled_ids = list(enabled)
    coordinator = enabled.get(config.get("coordinator")) or enabled[enabled_ids[0]]
    limit = int(config.get("max_context_chars", 50000))
    previous = "这是第一个阶段，暂无前序结论。"
    record: dict[str, Any] = {"task": task, "status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "stages": []}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "run.json", record)
    try:
        total = len(config["stages"])
        for index, stage in enumerate(config["stages"], 1):
            worker_ids = [item for item in stage.get("workers", []) if item in enabled]
            if not worker_ids:
                worker_ids = [coordinator["id"]]
            reviewer_ids = [item for item in stage.get("reviewers", []) if item in enabled and item not in worker_ids]
            if not reviewer_ids:
                reviewer_ids = [item for item in enabled_ids if item not in worker_ids]
            print(f"[{index}/{total}] {stage['name']}：{', '.join(worker_ids)} 执行", flush=True)

            def work_prompt(agent):
                return (
                    f"你是多模型团队成员。固定角色：{agent['role']}\n{agent['system_prompt']}",
                    f"总任务：\n{task}\n\n当前阶段：{stage['name']}\n要求：{stage['instruction']}\n\n前序共识：\n{clip(previous, limit)}\n\n请独立完成并输出可交付结果。",
                )

            outputs = parallel(worker_ids, enabled, work_prompt, config)
            good = [item for item in outputs if not item["error"]]
            if not good:
                raise RuntimeError(f"阶段“{stage['name']}”没有成功结果")
            candidates = "\n\n".join(f"### {item['label']}\n{item['content']}" for item in good)
            print(f"[{index}/{total}] {stage['name']}：{', '.join(reviewer_ids) or '无'} 审查", flush=True)

            def review_prompt(agent):
                return (
                    f"你是独立审查者。固定角色：{agent['role']}\n{agent['system_prompt']}",
                    f"总任务：\n{task}\n\n对当前阶段“{stage['name']}”的结果进行独立审查：\n{clip(candidates, limit)}\n\n检查错误、遗漏、假设、风险和可执行性，给出必须修改项和理由。",
                )

            reviews = parallel(reviewer_ids, enabled, review_prompt, config)
            review_text = "\n\n".join(f"### {item['label']}\n{item['content']}" for item in reviews if not item["error"]) or "没有可用审查。"
            merged = safe_call(
                coordinator,
                f"固定角色：{coordinator['role']}\n{coordinator['system_prompt']}",
                f"总任务：\n{task}\n\n你是阶段协调者。阶段：{stage['name']}\n候选：\n{clip(candidates, limit)}\n\n审查：\n{clip(review_text, limit)}\n\n解决冲突，吸收有效修正，输出一个可交给下一阶段的结论并保留未解决风险。",
                config,
            )
            if merged["error"]:
                raise RuntimeError(f"协调模型失败：{merged['error']}")
            previous = merged["content"]
            record["stages"].append({"id": stage["id"], "name": stage["name"], "workers": worker_ids, "reviewers": reviewer_ids, "outputs": outputs, "reviews": reviews, "synthesis": previous})
            write_json(output / "run.json", record)
        record.update({"status": "completed", "final_output": previous, "finished_at": datetime.now(timezone.utc).isoformat()})
        (output / "final.md").write_text(previous + "\n", encoding="utf-8")
        write_json(output / "run.json", record)
        return record
    except Exception as exc:
        record.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}", "finished_at": datetime.now(timezone.utc).isoformat()})
        write_json(output / "run.json", record)
        raise


def init_config(path: Path, force: bool = False) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "assets" / "config.example.json", path)


def ask(label: str, current: str = "") -> str:
    suffix = f" [{current}]" if current else ""
    value = input(f"{label}{suffix}：").strip()
    return value or current


def ask_multiline(label: str, current: str = "") -> str:
    print(f"{label}（单独输入 . 结束；直接输入 . 保留原内容）：")
    lines: list[str] = []
    while True:
        line = input()
        if line == ".":
            break
        lines.append(line)
    value = "\n".join(lines).strip()
    return value or current


def require_agent_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise RuntimeError("agent id 只能包含字母、数字、下划线和连字符")
    return value


def choose_stage_roles(config: dict[str, Any], agent_id: str) -> None:
    print("设置该模型在各阶段的职责：w=执行，r=审查，b=两者，s=跳过。")
    for stage in config["stages"]:
        workers = stage.setdefault("workers", [])
        reviewers = stage.setdefault("reviewers", [])
        current = "b" if agent_id in workers and agent_id in reviewers else "w" if agent_id in workers else "r" if agent_id in reviewers else "s"
        role = input(f"{stage['name']} [当前 {current}]：").strip().lower() or current
        if role not in {"w", "r", "b", "s"}:
            print("输入无效，保留当前设置。")
            continue
        if agent_id in workers:
            workers.remove(agent_id)
        if agent_id in reviewers:
            reviewers.remove(agent_id)
        if role in {"w", "b"}:
            workers.append(agent_id)
        if role in {"r", "b"}:
            reviewers.append(agent_id)


def cmd_init(args) -> int:
    path = Path(args.config).expanduser()
    existed = path.exists()
    init_config(path, args.force)
    print(f"{'配置已存在' if existed and not args.force else '已创建配置'}：{path}")
    return 0


def save_key(name: str, value: str) -> None:
    data = secrets()
    data[name] = value
    write_json(SECRETS_FILE, data, private=True)


def cmd_setup(args) -> int:
    path = Path(args.config).expanduser()
    init_config(path)
    config = read_json(path)
    print("TriCouncil 设置。直接回车保留当前值；API Key 输入不会显示。")
    for agent in config["agents"]:
        answer = input(f"\n启用 {agent['label']} [{agent['id']}]？[Y/n] ").strip().lower()
        agent["enabled"] = answer not in {"n", "no", "0"}
        if not agent["enabled"]:
            continue
        provider = input(f"接口类型 [{agent['provider']}]：").strip()
        if provider:
            if provider not in PROVIDERS:
                raise RuntimeError(f"不支持的接口类型：{provider}")
            agent["provider"] = provider
        model = input(f"模型名称 [{agent['model']}]：").strip()
        if model:
            agent["model"] = model
        base = input(f"API 地址 [{agent['base_url']}]：").strip()
        if base:
            agent["base_url"] = base
        key_name = agent.get("api_key_name", "")
        current = bool(key_for(agent))
        change = input(f"{key_name} 当前{'已配置' if current else '未配置'}，现在输入/更换？[y/N] ").strip().lower()
        if change in {"y", "yes", "1"}:
            value = getpass.getpass(f"输入 {key_name}：").strip()
            if value:
                save_key(key_name, value)
        if input("修改角色或固定 Prompt？[y/N] ").strip().lower() in {"y", "yes", "1"}:
            agent["role"] = ask("角色", agent["role"])
            agent["system_prompt"] = ask_multiline("输入固定 Prompt", agent["system_prompt"])
        if input("修改该模型参与的阶段？[y/N] ").strip().lower() in {"y", "yes", "1"}:
            choose_stage_roles(config, agent["id"])
    if sum(bool(item.get("enabled", True)) for item in config["agents"]) < 2:
        raise RuntimeError("至少必须启用两个模型；设置未保存")
    coordinator = ask("阶段结果协调模型 ID", config.get("coordinator", ""))
    if coordinator not in agents_by_id(config):
        raise RuntimeError(f"未知协调模型：{coordinator}")
    config["coordinator"] = coordinator
    write_json(path, config)
    print(f"设置已保存：{path}")
    return cmd_doctor(args)


def cmd_add_model(args) -> int:
    path = Path(args.config).expanduser()
    config = read_json(path)
    existing = agents_by_id(config)
    agent_id = require_agent_id(ask("新模型 ID（如 researcher）"))
    if agent_id in existing:
        raise RuntimeError(f"agent 已存在：{agent_id}")
    provider = ask("接口类型 openai_compatible / anthropic / gemini", "openai_compatible")
    if provider not in PROVIDERS - {"demo"}:
        raise RuntimeError("接口类型无效")
    default_urls = {"openai_compatible": "https://api.openai.com/v1", "anthropic": "https://api.anthropic.com", "gemini": "https://generativelanguage.googleapis.com/v1beta"}
    agent = {
        "id": agent_id,
        "label": ask("显示名称", agent_id),
        "enabled": True,
        "provider": provider,
        "base_url": ask("API 地址", default_urls[provider]),
        "model": ask("模型名称"),
        "api_key_name": ask("密钥名称", f"{agent_id.upper().replace('-', '_')}_API_KEY"),
        "role": ask("角色", "协作模型"),
        "system_prompt": ask_multiline("输入该模型的固定 Prompt"),
    }
    if not agent["model"] or not agent["system_prompt"]:
        raise RuntimeError("模型名称和 Prompt 不能为空")
    config["agents"].append(agent)
    choose_stage_roles(config, agent_id)
    write_json(path, config)
    print(f"已新增 {agent['label']}。使用 configure-key {agent['api_key_name']} 录入密钥。")
    return 0


def find_agent(config: dict[str, Any], agent_id: str) -> dict[str, Any]:
    target = next((item for item in config["agents"] if item["id"] == agent_id), None)
    if not target:
        raise RuntimeError(f"未知 agent：{agent_id}")
    return target


def cmd_edit_model(args) -> int:
    path = Path(args.config).expanduser()
    config = read_json(path)
    agent = find_agent(config, args.agent_id)
    print("直接回车保留当前值。")
    agent["label"] = ask("显示名称", agent["label"])
    provider = ask("接口类型", agent["provider"])
    if provider not in PROVIDERS:
        raise RuntimeError("接口类型无效")
    agent["provider"] = provider
    agent["base_url"] = ask("API 地址", agent.get("base_url", ""))
    agent["model"] = ask("模型名称", agent["model"])
    agent["api_key_name"] = ask("密钥名称", agent.get("api_key_name", ""))
    agent["role"] = ask("角色", agent["role"])
    if input("修改固定 Prompt？[y/N] ").strip().lower() in {"y", "yes", "1"}:
        agent["system_prompt"] = ask_multiline("输入新 Prompt", agent["system_prompt"])
    if input("修改参与阶段？[y/N] ").strip().lower() in {"y", "yes", "1"}:
        choose_stage_roles(config, agent["id"])
    write_json(path, config)
    print(f"已更新 {agent['label']}。")
    return 0


def cmd_remove_model(args) -> int:
    path = Path(args.config).expanduser()
    config = read_json(path)
    agent = find_agent(config, args.agent_id)
    if len(config["agents"]) <= 2:
        raise RuntimeError("至少保留两个模型，无法删除")
    config["agents"] = [item for item in config["agents"] if item["id"] != args.agent_id]
    for stage in config["stages"]:
        stage["workers"] = [item for item in stage.get("workers", []) if item != args.agent_id]
        stage["reviewers"] = [item for item in stage.get("reviewers", []) if item != args.agent_id]
    if config.get("coordinator") == args.agent_id:
        config["coordinator"] = config["agents"][0]["id"]
    write_json(path, config)
    print(f"已删除 {agent['label']}；保存的 API Key 不会自动删除，可用 remove-key 清除。")
    return 0


def cmd_set_prompt(args) -> int:
    path = Path(args.config).expanduser()
    config = read_json(path)
    agent = find_agent(config, args.agent_id)
    if args.file:
        prompt = Path(args.file).expanduser().read_text(encoding="utf-8").strip()
    else:
        prompt = ask_multiline(f"输入 {agent['label']} 的新 Prompt", agent["system_prompt"])
    if not prompt:
        raise RuntimeError("Prompt 不能为空")
    agent["system_prompt"] = prompt
    write_json(path, config)
    print(f"已更新 {agent['label']} 的 Prompt。")
    return 0


def cmd_set_model(args) -> int:
    path = Path(args.config).expanduser()
    config = read_json(path)
    agent = find_agent(config, args.agent_id)
    for field in ("model", "provider", "base_url", "api_key_name"):
        value = getattr(args, field, None)
        if value:
            agent[field] = value
    if agent["provider"] not in PROVIDERS:
        raise RuntimeError("接口类型无效")
    write_json(path, config)
    print(f"已更新 {agent['label']}：{agent['provider']} / {agent['model']}")
    return 0


def cmd_manage(args) -> int:
    actions = {
        "1": ("查看状态", lambda: cmd_status(args)),
        "2": ("新增模型", lambda: cmd_add_model(args)),
        "3": ("编辑模型、Prompt 与阶段", lambda: cmd_edit_model(argparse.Namespace(**vars(args), agent_id=ask("Agent ID")))),
        "4": ("启用模型", lambda: cmd_toggle(argparse.Namespace(**vars(args), agent_id=ask("Agent ID")), True)),
        "5": ("关闭模型", lambda: cmd_toggle(argparse.Namespace(**vars(args), agent_id=ask("Agent ID")), False)),
        "6": ("录入或更换 API Key", lambda: cmd_configure_key(argparse.Namespace(**vars(args), name=ask("密钥名称")))),
        "7": ("删除 API Key", lambda: cmd_remove_key(argparse.Namespace(**vars(args), name=ask("密钥名称")))),
        "8": ("删除模型", lambda: cmd_remove_model(argparse.Namespace(**vars(args), agent_id=ask("Agent ID")))),
    }
    while True:
        print("\nTriCouncil 模型管理")
        for number, (label, _) in actions.items():
            print(f"{number}. {label}")
        print("0. 完成")
        choice = input("请选择：").strip()
        if choice == "0":
            return 0
        action = actions.get(choice)
        if not action:
            print("无效选择。")
            continue
        try:
            action[1]()
        except Exception as exc:
            print(f"操作失败：{exc}")


def cmd_configure_key(args) -> int:
    value = getpass.getpass(f"输入 {args.name}（不会显示）：").strip()
    if not value:
        raise RuntimeError("没有输入密钥")
    save_key(args.name, value)
    print(f"已安全保存 {args.name}（文件权限仅当前用户可读）。")
    return 0


def cmd_remove_key(args) -> int:
    data = secrets()
    existed = data.pop(args.name, None) is not None
    write_json(SECRETS_FILE, data, private=True)
    print(f"{'已删除' if existed else '未找到'} {args.name}")
    return 0


def cmd_toggle(args, state: bool) -> int:
    path = Path(args.config).expanduser()
    config = read_json(path)
    target = find_agent(config, args.agent_id)
    target["enabled"] = state
    if sum(bool(item.get("enabled", True)) for item in config["agents"]) < 2:
        raise RuntimeError("至少需要两个启用模型，无法关闭")
    write_json(path, config)
    print(f"{target['label']} 已{'启用' if state else '关闭'}。")
    return 0


def cmd_status(args) -> int:
    path = Path(args.config).expanduser()
    config = read_json(path)
    print(f"配置：{path}")
    for agent in config["agents"]:
        state = "启用" if agent.get("enabled", True) else "关闭"
        key_state = "无需密钥" if agent["provider"] == "demo" else ("密钥已配置" if key_for(agent) else "缺少密钥")
        print(f"- {agent['id']}: {state}｜{agent['label']}｜{agent['model']}｜{key_state}")
    return 0


def cmd_doctor(args) -> int:
    config = read_json(Path(args.config).expanduser())
    problems = validate(config, require_keys=True)
    if problems:
        print("配置尚未就绪：")
        for item in problems:
            print(f"- {item}")
        return 1
    enabled = [item for item in config["agents"] if item.get("enabled", True)]
    print(f"配置有效：{len(enabled)} 个模型已启用，{len(config['stages'])} 个阶段。")
    return 0


def cmd_run(args) -> int:
    config = read_json(Path(args.config).expanduser())
    task = Path(args.task_file).read_text(encoding="utf-8").strip() if args.task_file else args.task.strip()
    if len(task) < 3:
        raise RuntimeError("任务内容太短")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path(args.output).expanduser().resolve() if args.output else Path.cwd() / ".tricouncil-runs" / stamp
    execute(config, task, output)
    print(f"任务完成：{output}\n最终结果：{output / 'final.md'}")
    return 0


def cmd_self_test(args) -> int:
    config = read_json(ROOT / "assets" / "config.demo.json")
    with tempfile.TemporaryDirectory(prefix="tricouncil-test-") as directory:
        output = Path(directory) / "result"
        result = execute(config, "验证插件的执行、审查、合并和结果保存。", output)
        assert result["status"] == "completed" and (output / "final.md").exists()
        assert all(stage["reviews"] for stage in result["stages"])
    print("自检通过：执行、并发、审查、合并和结果保存均正常。")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="TriCouncil 多模型协作插件")
    result.add_argument("--config", default=os.getenv("TRICOUNCIL_CONFIG", str(DEFAULT_CONFIG)))
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init"); init.add_argument("--force", action="store_true"); init.set_defaults(handler=cmd_init)
    setup = commands.add_parser("setup"); setup.set_defaults(handler=cmd_setup)
    manage = commands.add_parser("manage"); manage.set_defaults(handler=cmd_manage)
    status = commands.add_parser("status"); status.set_defaults(handler=cmd_status)
    doctor = commands.add_parser("doctor"); doctor.set_defaults(handler=cmd_doctor)
    for name, handler in (("configure-key", cmd_configure_key), ("remove-key", cmd_remove_key)):
        command = commands.add_parser(name); command.add_argument("name"); command.set_defaults(handler=handler)
    enable = commands.add_parser("enable"); enable.add_argument("agent_id"); enable.set_defaults(handler=lambda args: cmd_toggle(args, True))
    disable = commands.add_parser("disable"); disable.add_argument("agent_id"); disable.set_defaults(handler=lambda args: cmd_toggle(args, False))
    add_model = commands.add_parser("add-model"); add_model.set_defaults(handler=cmd_add_model)
    edit_model = commands.add_parser("edit-model"); edit_model.add_argument("agent_id"); edit_model.set_defaults(handler=cmd_edit_model)
    remove_model = commands.add_parser("remove-model"); remove_model.add_argument("agent_id"); remove_model.set_defaults(handler=cmd_remove_model)
    set_prompt = commands.add_parser("set-prompt"); set_prompt.add_argument("agent_id"); set_prompt.add_argument("--file"); set_prompt.set_defaults(handler=cmd_set_prompt)
    set_model = commands.add_parser("set-model"); set_model.add_argument("agent_id"); set_model.add_argument("--model"); set_model.add_argument("--provider"); set_model.add_argument("--base-url"); set_model.add_argument("--api-key-name"); set_model.set_defaults(handler=cmd_set_model)
    run = commands.add_parser("run")
    tasks = run.add_mutually_exclusive_group(required=True); tasks.add_argument("--task"); tasks.add_argument("--task-file")
    run.add_argument("--output"); run.set_defaults(handler=cmd_run)
    test = commands.add_parser("self-test"); test.set_defaults(handler=cmd_self_test)
    return result


def main() -> int:
    configure_console()
    args = parser().parse_args()
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print("已停止。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"执行失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
