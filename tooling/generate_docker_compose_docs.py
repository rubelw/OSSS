#!/usr/bin/env python
"""
Generate docs/backend/docker-compose.md from docker-compose.yml
for MkDocs + gen-files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Iterable

import yaml


def _format_list(title: str, values: Iterable[str]) -> list[str]:
    values = [str(v) for v in values]
    if not values:
        return []
    lines = [f"**{title}:**", ""]
    for v in values:
        lines.append(f"- `{v}`")
    lines.append("")
    return lines


def _format_env(env: Any) -> list[str]:
    if not env:
        return []

    pairs: list[tuple[str, str | None]] = []

    if isinstance(env, Mapping):
        for k, v in env.items():
            pairs.append((str(k), None if v is None else str(v)))
    else:
        for item in env:
            s = str(item)
            if "=" in s:
                k, v = s.split("=", 1)
                pairs.append((k, v))
            else:
                pairs.append((s, None))

    lines: list[str] = ["**Environment:**", ""]
    for k, v in pairs:
        if v is None:
            lines.append(f"- `{k}`")
        else:
            lines.append(f"- `{k}={v}`")
    lines.append("")
    return lines


def _format_service(name: str, cfg: Mapping[str, Any]) -> list[str]:
    lines: list[str] = [f"## `{name}`", ""]

    image = cfg.get("image")
    container_name = cfg.get("container_name")
    build = cfg.get("build")

    if image:
        lines.append(f"**Image:** `{image}`")
    if build:
        if isinstance(build, str):
            lines.append(f"**Build context:** `{build}`")
        elif isinstance(build, Mapping):
            ctx = build.get("context", ".")
            dockerfile = build.get("dockerfile")
            lines.append(f"**Build context:** `{ctx}`")
            if dockerfile:
                lines.append(f"**Dockerfile:** `{dockerfile}`")
    if container_name:
        lines.append(f"**Container name:** `{container_name}`")

    if any([image, build, container_name]):
        lines.append("")

    lines += _format_list("Ports", cfg.get("ports") or [])
    lines += _format_list("Volumes", cfg.get("volumes") or [])
    lines += _format_list("Depends on", cfg.get("depends_on") or [])
    lines += _format_list("Networks", cfg.get("networks") or [])

    lines += _format_env(cfg.get("environment"))

    command = cfg.get("command")
    if command:
        lines.append("**Command:**")
        lines.append("")
        if isinstance(command, str):
            lines.append(f"```bash\n{command}\n```")
        else:
            joined = " ".join(str(x) for x in command)
            lines.append(f"```bash\n{joined}\n```")
        lines.append("")

    labels = cfg.get("labels")
    if labels:
        lines.append("**Labels:**")
        lines.append("")
        if isinstance(labels, Mapping):
            for k, v in labels.items():
                lines.append(f"- `{k} = {v}`")
        else:
            for item in labels:
                lines.append(f"- `{item}`")
        lines.append("")

    return lines


def generate_docs(compose_path: Path, output_path: Path, title: str = "Docker Compose Services") -> None:
    with compose_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    services = data.get("services") or {}
    version = data.get("version")

    lines: list[str] = [f"# {title}", ""]

    if version:
        lines.append(f"_Compose file version: `{version}`_")
        lines.append("")

    if not services:
        lines.append("> No `services` section found in this compose file.")
    else:
        lines.append("This page documents the services defined in `docker-compose.yml`.")
        lines.append("")

        lines.append("## Services overview")
        lines.append("")
        lines.append("| Service | Image | Description |")
        lines.append("|---------|-------|-------------|")
        for name, cfg in services.items():
            image = cfg.get("image", "")
            desc = cfg.get("container_name", "") or ""
            lines.append(f"| `{name}` | `{image}` | {desc} |")
        lines.append("")

        for name, cfg in services.items():
            lines += _format_service(name, cfg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    compose_path = Path("docker-compose.yml")
    output_path = Path("docs/backend/docker-compose.md")

    if not compose_path.exists():
        # Silent no-op if compose file missing, keeps mkdocs happy
        return

    generate_docs(
        compose_path,
        output_path,
        title="Backend Docker Compose Services",
    )


if __name__ == "__main__":
    main()
