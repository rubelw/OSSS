# OSSS/ai/workflows/template_loader.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterable

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class WorkflowTemplate:
    workflow_id: str
    name: str
    version: str
    graph: Optional[str]
    agents: List[str]
    raw: Dict[str, Any]


class WorkflowTemplateLoader:
    """
    Loads workflow templates from YAML files.

    Default search paths (repo-relative):
      - OSSS/ai/workflows (this module's directory)
      - ./examples (repo root "examples" directory)

    Notes:
      - Supports *.yaml and *.yml
      - Dedupes by workflow_id (newer file mtime wins)
    """

    def __init__(
        self,
        templates_dir: Optional[str] = None,
        extra_dirs: Optional[List[str]] = None,
    ) -> None:
        # Primary directory: explicit override OR this module folder
        self._dir = Path(templates_dir) if templates_dir else Path(__file__).parent

        # Extra directories (repo-relative by default)
        self._extra_dirs = [Path(p) for p in (extra_dirs or [])]

        # Cache: workflow_id -> WorkflowTemplate
        self._cache: Dict[str, WorkflowTemplate] = {}

    def _require_yaml(self) -> None:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load workflow templates. Install pyyaml.")

    def _find_repo_root(self, start: Path) -> Path:
        cur = start.resolve()
        for _ in range(10):
            if (cur / "pyproject.toml").exists() or (cur / "src" / "OSSS").exists():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
        return start.resolve()

    def _resolved_search_dirs(self) -> List[Path]:
        """
        Build the final list of directories to scan.
        - Always includes self._dir (absolute/relative ok)
        - Always includes repo_root/examples (if exists)
        - Includes any extra_dirs passed in
        """
        dirs: List[Path] = []

        # main directory
        dirs.append(self._dir.resolve())

        # repo_root/examples
        repo_root = self._find_repo_root(Path.cwd())
        examples_dir = (repo_root / "examples").resolve()
        if examples_dir.exists() and examples_dir.is_dir():
            dirs.append(examples_dir)

        # user-provided extra dirs
        for p in self._extra_dirs:
            rp = (repo_root / p).resolve() if not p.is_absolute() else p.resolve()
            if rp.exists() and rp.is_dir():
                dirs.append(rp)

        # de-dup preserve order
        seen = set()
        out: List[Path] = []
        for d in dirs:
            if d in seen:
                continue
            seen.add(d)
            out.append(d)

        logger.debug(
            "Workflow template search dirs resolved",
            extra={"dirs": [str(d) for d in out]},
        )
        return out

    def _iter_yaml_files(self, directory: Path) -> Iterable[Path]:
        # recursive search under each directory
        yield from directory.rglob("*.yaml")
        yield from directory.rglob("*.yml")

    def _load_one(self, p: Path) -> Optional[WorkflowTemplate]:
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                return None

            wf_id = (data.get("workflow_id") or "").strip()
            if not wf_id:
                logger.warning("Workflow template missing workflow_id", extra={"path": str(p)})
                return None

            # graph is optional; allow either top-level "graph" OR flow.entry_point-only configs
            graph = (data.get("graph") or "").strip() or None

            # if they described nodes, infer agent list from node_id or node_type
            agents: List[str] = []
            nodes = data.get("nodes") or []
            if isinstance(nodes, list):
                for n in nodes:
                    if not isinstance(n, dict):
                        continue
                    # prefer explicit agent_type, else node_type, else node_id
                    agent = (n.get("config") or {}).get("agent_type") or n.get("node_type") or n.get("node_id")
                    if isinstance(agent, str) and agent.strip():
                        agents.append(agent.strip())

            return WorkflowTemplate(
                workflow_id=wf_id,
                name=str(data.get("name") or wf_id),
                version=str(data.get("version") or "1.0.0"),
                graph=graph,
                agents=agents,
                raw=data,
            )
        except Exception as e:
            logger.warning("Failed to load workflow template", extra={"path": str(p), "error": str(e)})
            return None

    def refresh(self) -> None:
        """Reload all templates from disk (scans OSSS/ai/workflows + ./examples by default)."""
        self._require_yaml()

        candidates: Dict[str, Dict[str, Any]] = {}
        # candidates[workflow_id] = {"tpl": WorkflowTemplate, "mtime": float, "path": str}

        scanned_files = 0
        loaded = 0

        for d in self._resolved_search_dirs():
            if not d.exists() or not d.is_dir():
                continue

            for p in sorted(self._iter_yaml_files(d)):
                scanned_files += 1
                tpl = self._load_one(p)
                if not tpl:
                    continue

                loaded += 1
                mtime = p.stat().st_mtime if p.exists() else 0.0

                existing = candidates.get(tpl.workflow_id)
                if existing is None or mtime > float(existing.get("mtime") or 0.0):
                    candidates[tpl.workflow_id] = {"tpl": tpl, "mtime": mtime, "path": str(p)}

        self._cache = {wf_id: v["tpl"] for wf_id, v in candidates.items()}

        logger.info(
            "Workflow templates loaded",
            extra={
                "count": len(self._cache),
                "scanned_files": scanned_files,
                "loaded_templates": loaded,
                "dirs": [str(d) for d in self._resolved_search_dirs()],
            },
        )

    def get(self, workflow_id: str) -> Optional[WorkflowTemplate]:
        if not self._cache:
            self.refresh()
        return self._cache.get((workflow_id or "").strip())

    def list(self) -> List[WorkflowTemplate]:
        if not self._cache:
            self.refresh()
        return list(self._cache.values())

    # Optional helper if you want the mapping directly (preflight supports this if present)
    def get_templates(self) -> Dict[str, WorkflowTemplate]:
        if not self._cache:
            self.refresh()
        return dict(self._cache)
