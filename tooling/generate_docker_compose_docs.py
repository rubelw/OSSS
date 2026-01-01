#!/usr/bin/env python
"""
Generate docs/backend/docker-compose.md from docker-compose.yml
for MkDocs + gen-files, and per-service docs under docs/backend/docker/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Iterable

import sys

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    # Fail loudly so MkDocs logs show what's wrong
    print("[docker-compose-docs] ERROR: PyYAML is not installed. Run `pip install pyyaml`.", file=sys.stderr)
    raise


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


def _service_body_lines(name: str, cfg: Mapping[str, Any]) -> list[str]:
    """
    Core description for a single service (without the H1).
    Reused by both overview page sections and per-service pages.
    """
    lines: list[str] = []

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


def _write_service_page(name: str, cfg: Mapping[str, Any], service_path: Path) -> None:
    """
    Write a standalone page for a single service at service_path.
    Supports optional extra documentation in docs/backend/docker_docs/<service>.md.
    """
    service_lines: list[str] = [f"# `{name}` service", ""]
    service_lines.append(
        "This page documents the configuration for the "
        f"`{name}` service from `docker-compose.yml`.\n"
    )
    service_lines += _service_body_lines(name, cfg)

    # --- Include extra documentation if available ---
    extra_doc_path = Path("docs/backend/docker_docs") / f"{name}.md"
    if extra_doc_path.exists():
        service_lines.append("## Additional Documentation\n")
        service_lines.append("")
        with extra_doc_path.open("r", encoding="utf-8") as extra:
            service_lines.append(extra.read())
        service_lines.append("")

    service_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.write_text("\n".join(service_lines), encoding="utf-8")
    print(f"[docker-compose-docs] Wrote service doc: {service_path}", file=sys.stderr)


def generate_docs(compose_path: Path, overview_path: Path, title: str = "Docker Compose Services") -> None:
    print(f"[docker-compose-docs] Reading compose file from: {compose_path}", file=sys.stderr)

    with compose_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    services = data.get("services") or {}
    version = data.get("version")

    # Directory where per-service docs will live, e.g. docs/backend/docker/
    services_dir = overview_path.parent / "docker"

    lines: list[str] = [f"# {title}", ""]

    if version:
        lines.append(f"_Compose file version: `{version}`_")
        lines.append("")

    if not services:
        lines.append("> No `services` section found in this compose file.")
    else:
        lines.append("This page documents the services defined in `docker-compose.yml`.")
        lines.append("")
        lines.append(
            "Each service also has its own page under `backend/docker/` "
            "with more detailed configuration."
        )
        lines.append("")

        # Overview table with links to per-service docs
        lines.append("## Services overview")
        lines.append("")
        lines.append("| Service | Image | Description |")
        lines.append("|---------|-------|-------------|")

        for name, cfg in services.items():
            image = cfg.get("image", "")
            desc = cfg.get("container_name", "") or ""
            # Link to per-service page, relative to this overview page
            link = f"docker/{name}.md"
            lines.append(f"| [`{name}`]({link}) | `{image}` | {desc} |")

        lines.append("")

        # Inline sections on the overview page (optional)
        lines.append("## Service details")
        lines.append("")
        for name, cfg in services.items():
            lines.append(f"### `{name}`")
            lines.append("")
            lines += _service_body_lines(name, cfg)
            lines.append("")

            # Also write a standalone page for this service
            service_path = services_dir / f"{name}.md"
            _write_service_page(name, cfg, service_path)

    overview_path.parent.mkdir(parents=True, exist_ok=True)
    overview_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[docker-compose-docs] Wrote overview docs to: {overview_path}", file=sys.stderr)


def main() -> None:
    # Resolve project root from this file, so it works regardless of CWD
    project_root = Path(__file__).resolve().parents[1]
    compose_path = project_root / "docker-compose.yml"
    overview_path = project_root / "docs" / "backend" / "docker-compose.md"

    if not compose_path.exists():
        print(f"[docker-compose-docs] docker-compose.yml not found at: {compose_path}", file=sys.stderr)
        return

    generate_docs(
        compose_path,
        overview_path,
        title="Backend Docker Compose Services",
    )


if __name__ == "__main__":
    main()
