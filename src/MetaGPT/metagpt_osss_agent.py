"""
OSSS MetaGPT Agent — All logs written into chosen workspace
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from metagpt.team import Team
from metagpt.roles import ProductManager, Architect, ProjectManager, Engineer

import json
from textwrap import indent
import ast


def _pretty_log_role_output(logger, role_name: str, raw: dict) -> None:
    """
    Turn ugly nested dicts like:
      {'docs': {'2025...json': {'root_path': ..., 'filename': ..., 'content': '...json string...'}}}
    into something readable.
    """
    # Top-level file info
    if isinstance(raw, dict) and "root_path" in raw and "filename" in raw:
        logger.info(f"{role_name}: wrote {raw['root_path']}/{raw['filename']}")
        content = raw.get("content")
    elif isinstance(raw, dict) and "docs" in raw:
        for doc_name, meta in raw["docs"].items():
            root = meta.get("root_path", "")
            fname = meta.get("filename", doc_name)
            logger.info(f"{role_name}: wrote {root}/{fname}")
            content = meta.get("content")
            break  # just show the first doc for log brevity
    else:
        # Fallback: just log the raw structure
        logger.info(f"{role_name}: {raw}")
        return

    # Try to pretty-print JSON content (if it looks like JSON)
    if isinstance(content, str):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Not JSON, just log a short snippet
            snippet = content[:300].replace("\n", " ")
            logger.info(f"{role_name}: content snippet: {snippet}...")
            return

        # Pull out key bits people actually care about
        lines = []

        if "Project Name" in data:
            lines.append(f"Project: {data['Project Name']}")
        if "Original Requirements" in data:
            lines.append(f"Requirement: {data['Original Requirements']}")
        if "Product Goals" in data:
            goals = " • ".join(data["Product Goals"][:3])
            lines.append(f"Product goals: {goals}")
        if "User Stories" in data:
            first_two = " • ".join(data["User Stories"][:2])
            lines.append(f"User stories (sample): {first_two}")
        if "Implementation approach" in data:
            lines.append(f"Implementation: {data['Implementation approach']}")
        if "File list" in data:
            files = ", ".join(data["File list"][:4])
            lines.append(f"Key files: {files}")

        if not lines:
            pretty_json = json.dumps(data, indent=2)[:1000]
            indented_json = indent(pretty_json, "  ")
            logger.info(f"{role_name} content:\n{indented_json}")
            return

        indented_summary = indent("\n".join(lines), "  ")
        logger.info(f"{role_name} summary:\n{indented_summary}")


# ------------------------------------------------------------------
# Every call gets its own log placed inside <workspace>/run.log
# ------------------------------------------------------------------


def _build_workspace_logger(workspace: str) -> logging.Logger:
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    log_file = ws / "run.log"

    logger = logging.getLogger(f"metagpt_run_{ws.name}")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=5
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# --------------------------------------------------
# Main Run Function
# --------------------------------------------------


async def run_osss_metagpt_agent(
    requirement: str,
    investment: float = 2.0,
    workspace: str = "/workspace/MetaGPT_workspace/default_run",
    rag_index: str | None = None,
):
    logger = _build_workspace_logger(workspace)

    logger.info("=== 🚀 Starting OSSS MetaGPT run ===")
    logger.info(f"Human: {requirement}")
    logger.info(f"Investment: {investment}")
    logger.info(f"Workspace: {workspace}")
    logger.info(f"RAG Index: {rag_index}")

    # 1) Build the team
    team = Team()
    team.hire([ProductManager(), Architect(), ProjectManager(), Engineer()])

    # 2) Budget / investment
    team.invest(investment=investment)

    logger.info("Team instantiated; beginning run_project + run()")

    # 3) Give it the idea / requirement
    team.run_project(idea=requirement)

    # 4) Actually run the multi-agent loop
    result = await team.run(n_round=3)

    logger.info("=== ✅ Finished MetaGPT run ===")

    # If MetaGPT gave us a big string transcript, parse it into nicer logs
    if isinstance(result, str):
        logger.info("=== 📄 MetaGPT run transcript ===")
        for line in result.splitlines():
            line = line.strip()
            if not line:
                continue

            # Pass through the "Human: ..." line as-is
            if line.startswith("Human:"):
                logger.info(line)
                continue

            # Try to split "Alice(Product Manager): {...}" style lines
            if ":" in line:
                name, rest = line.split(":", 1)
                name = name.strip()
                payload = rest.strip()
                # Attempt to parse the dict-ish part with ast.literal_eval
                try:
                    data = ast.literal_eval(payload)
                except Exception:
                    # If we can't parse it, just log the line as-is
                    logger.info(f"{name}: {payload}")
                else:
                    _pretty_log_role_output(logger, name, data)
            else:
                logger.info(line)

        return result

    # Structured result: dict / list
    if isinstance(result, dict):
        _pretty_log_role_output(logger, "MetaGPT", result)
    elif isinstance(result, list):
        for idx, item in enumerate(result):
            if isinstance(item, dict):
                role_name = item.get("role") or item.get("name") or f"Step {idx + 1}"
                _pretty_log_role_output(logger, str(role_name), item)
            else:
                logger.info(f"Step {idx + 1}: {item!r}")
    else:
        # Fallback: just log it raw
        logger.info(f"Result (raw): {result!r}")

    return result


# ----------------------------------------------
# Two-agent conversation logging
# ----------------------------------------------


async def run_two_osss_agents_conversation(prompt: str):
    conv_dir = Path("/workspace/MetaGPT_workspace/conversations")
    conv_dir.mkdir(parents=True, exist_ok=True)

    log_file = conv_dir / "conversations.log"

    logger = logging.getLogger("metagpt_conversation")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=5)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)

    logger.info(f"🗣 Conversation start prompt={prompt}")

    # Your simple 2-agent conversation logic
    reply = f"Two-agent reply to: {prompt}"

    logger.info(f"🗣 Conversation result={reply}")

    return {"response": reply}
