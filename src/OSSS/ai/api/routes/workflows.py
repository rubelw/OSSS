"""
Workflow discovery and management endpoints for the OSSS API.

This module exposes FastAPI routes that allow clients (UI, CLI, other services)
to discover and inspect available workflow definitions on disk.

Core capabilities:
- Scan configured directories for YAML workflow definitions
- Extract normalized metadata (name, category, version, complexity, tags, etc.)
- Provide search + filtering + pagination over discovered workflows
- Retrieve a single workflow’s metadata by workflow_id

Design notes:
- Workflows are *discovered from files*, not from a database.
- Discovery can be expensive (filesystem traversal + YAML parsing), so we cache.
- Cache is time-based (TTL). This favors simplicity over file-watching complexity.

Updates applied:
1) Ensure the *real* workflows directory is scanned (not just examples),
   so `OSSS/ai/workflows/data_views_demo.yaml` is discoverable.
2) Add a POST /workflows/refresh endpoint to force cache reload (dev-friendly).
3) Add a lightweight GET /workflows/raw endpoint to inspect the parsed YAML
   (helps debug why a file is/ isn't being interpreted the way you expect).
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import os          # Present but not currently used in this module (may be planned for env/config)
import time        # Used for cache TTL checks and fallback timestamps
import yaml        # YAML parsing for workflow definition files
from pathlib import Path  # Portable filesystem path handling
from collections import defaultdict  # Present but not currently used (could be used for grouping/categories)
from typing import Dict, List, Optional, Any

# ---------------------------------------------------------------------------
# FastAPI imports
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException, Query

# ---------------------------------------------------------------------------
# API models (Pydantic)
# ---------------------------------------------------------------------------

from OSSS.ai.api.models import WorkflowMetadata, WorkflowsResponse

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

from OSSS.ai.observability import get_logger

# Module-level logger used for tracing requests + debugging discovery
logger = get_logger(__name__)

# FastAPI router for this module’s endpoints
router = APIRouter()


# ===========================================================================
# WorkflowDiscoveryService
# ===========================================================================
class WorkflowDiscoveryService:
    """
    Service for discovering and managing available workflows.

    Responsibilities:
    - Know which directories to scan for workflow YAML files
    - Parse YAML safely (yaml.safe_load)
    - Extract metadata in a normalized form expected by the API models
    - Cache discovered workflows to avoid repeated filesystem scanning
    - Provide filtering (category/complexity) and text search (name/description/tags/etc.)
    """

    def __init__(self) -> None:
        # Cache of workflow_id -> WorkflowMetadata
        # This is an in-memory cache scoped to the process.
        self._workflow_cache: Dict[str, WorkflowMetadata] = {}

        # Optional: keep raw parsed YAML by workflow_id (debug endpoint)
        self._raw_yaml_cache: Dict[str, Dict[str, Any]] = {}

        # Timestamp (epoch seconds) when cache was last refreshed
        self._cache_timestamp = 0.0

        # Cache time-to-live (seconds). After this, a refresh is triggered.
        self._cache_ttl = 300.0  # 5 minutes

        # Directories (relative to current working directory) to scan for workflows.
        #
        # ✅ Updated: include the canonical workflows directory so your
        # `src/OSSS/ai/workflows/*.yaml` files are discovered.
        self._workflow_directories = [
            "src/OSSS/ai/workflows",           # ✅ main workflows directory
            "src/OSSS/ai/workflows/examples",  # existing examples
            "examples/charts",                 # existing
        ]

    # ----------------------------------------------------------------------
    # Cache management (public)
    # ----------------------------------------------------------------------
    def force_refresh(self) -> None:
        """Force a cache refresh immediately (used by POST /workflows/refresh)."""
        workflows = self._load_workflows()
        self._workflow_cache = {wf.workflow_id: wf for wf in workflows}
        self._cache_timestamp = time.time()
        logger.info("Workflow cache force-refreshed", extra={"count": len(workflows)})

    def get_raw_yaml_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Return the cached raw YAML dict for a workflow if available."""
        _ = self._get_cached_workflows()  # ensure cache populated
        return self._raw_yaml_cache.get(workflow_id)

    # ----------------------------------------------------------------------
    # Filesystem discovery helpers
    # ----------------------------------------------------------------------
    def _get_workflow_directories(self) -> List[Path]:
        from pathlib import Path

        def find_repo_root(start: Path) -> Path:
            cur = start.resolve()
            for _ in range(8):  # walk up a few levels
                if (cur / "pyproject.toml").exists() or (cur / "src" / "OSSS").exists():
                    return cur
                if cur.parent == cur:
                    break
                cur = cur.parent
            return start.resolve()

        cwd = Path.cwd()
        base_path = find_repo_root(cwd)

        logger.info(
            "Workflow discovery base_path resolved",
            extra={"base_path": str(base_path), "cwd": str(cwd), "configured_dirs": self._workflow_directories},
        )

        directories: List[Path] = []
        for dir_path in self._workflow_directories:
            full_path = (base_path / dir_path).resolve()
            if full_path.exists() and full_path.is_dir():
                directories.append(full_path)
            else:
                logger.warning(
                    "Workflow directory not found",
                    extra={"configured_path": dir_path, "resolved_path": str(full_path)},
                )

        logger.info("Workflow discovery directories finalized", extra={"directories": [str(p) for p in directories]})
        return directories

    # ----------------------------------------------------------------------
    # YAML metadata extraction
    # ----------------------------------------------------------------------
    def _extract_metadata_from_yaml(
        self,
        yaml_content: Dict[str, Any],
        file_path: Path,
    ) -> Optional[WorkflowMetadata]:
        """
        Convert a parsed YAML workflow definition into a WorkflowMetadata object.

        This function:
        - Extracts required fields with sensible defaults
        - Normalizes types (e.g., version to semver-ish string)
        - Normalizes complexity level to the allowed enum set
        - Derives tags from multiple potential locations
        """
        try:
            # --------------------------------------------------------------
            # Basic identity fields
            # --------------------------------------------------------------
            workflow_id = yaml_content.get("workflow_id", file_path.stem)
            name = yaml_content.get("name", workflow_id.replace("_", " ").title())
            description = yaml_content.get("description", f"Workflow: {name}")

            # --------------------------------------------------------------
            # Version normalization
            # --------------------------------------------------------------
            raw_version = yaml_content.get("version", "1.0.0")
            version = raw_version

            if isinstance(raw_version, (int, float)):
                version = f"{raw_version}.0.0"
            elif isinstance(raw_version, str):
                parts = raw_version.split(".")
                if len(parts) == 1:
                    version = f"{parts[0]}.0.0"
                elif len(parts) == 2:
                    version = f"{parts[0]}.{parts[1]}.0"
                else:
                    version = raw_version

            # --------------------------------------------------------------
            # Metadata block (optional)
            # --------------------------------------------------------------
            metadata = yaml_content.get("metadata", {})

            # Category/domain: allow either top-level 'category' or metadata.domain/category
            category = (
                yaml_content.get("category")
                or metadata.get("domain")
                or metadata.get("category")
                or "general"
            )

            # --------------------------------------------------------------
            # Tags
            # --------------------------------------------------------------
            tags = set()

            if "tags" in yaml_content:
                try:
                    tags.update(list(yaml_content["tags"]))
                except Exception:
                    pass

            if "tags" in metadata:
                try:
                    tags.update(list(metadata["tags"]))
                except Exception:
                    pass

            if category and category not in tags:
                tags.add(str(category))

            if not tags:
                tags = {"workflow", "general"}

            # --------------------------------------------------------------
            # Attribution
            # --------------------------------------------------------------
            created_by = yaml_content.get("created_by", metadata.get("created_by", "OSSS"))

            # --------------------------------------------------------------
            # Complexity normalization
            # --------------------------------------------------------------
            raw_complexity = metadata.get("complexity_level", "medium")
            complexity_mapping = {
                "beginner": "low",
                "simple": "low",
                "basic": "low",
                "intermediate": "medium",
                "advanced": "high",
                "complex": "high",
                "error_testing": "expert",
            }

            complexity_level = complexity_mapping.get(str(raw_complexity).lower(), str(raw_complexity).lower())
            if complexity_level not in ["low", "medium", "high", "expert"]:
                complexity_level = "medium"

            # --------------------------------------------------------------
            # Additional helpful metadata (optional)
            # --------------------------------------------------------------
            estimated_execution_time = metadata.get("estimated_execution_time", "30-45 seconds")
            use_cases = metadata.get("use_cases", [workflow_id.replace("_", " ")])

            nodes = yaml_content.get("nodes", [])
            node_count = len(nodes) if isinstance(nodes, list) else 0

            created_at = file_path.stat().st_ctime if file_path.exists() else time.time()

            return WorkflowMetadata(
                workflow_id=workflow_id,
                name=name,
                description=description,
                version=version,
                category=str(category).lower(),
                tags=list(tags),
                created_by=created_by,
                created_at=created_at,
                estimated_execution_time=estimated_execution_time,
                complexity_level=complexity_level,
                node_count=max(1, node_count),
                use_cases=(use_cases if isinstance(use_cases, list) else [str(use_cases)]),
            )

        except Exception as e:
            logger.warning(f"Failed to extract metadata from {file_path}: {e}")
            return None

    # ----------------------------------------------------------------------
    # Directory scanning
    # ----------------------------------------------------------------------
    def _discover_workflows_from_directory(self, directory: Path) -> List[WorkflowMetadata]:
        """
        Scan a directory recursively to find workflow definition YAML files.
        """
        workflows: List[WorkflowMetadata] = []

        try:
            yaml_patterns = ["*.yaml", "*.yml"]
            yaml_files: List[Path] = []
            for pattern in yaml_patterns:
                yaml_files.extend(directory.rglob(pattern))

            for yaml_file in yaml_files:
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        yaml_content = yaml.safe_load(f)

                    if yaml_content and isinstance(yaml_content, dict):
                        # Heuristic: consider it a workflow if it has key fields
                        if "workflow_id" in yaml_content or "nodes" in yaml_content:
                            metadata = self._extract_metadata_from_yaml(yaml_content, yaml_file)
                            if metadata:
                                workflows.append(metadata)
                                # ✅ cache raw yaml for debug endpoint
                                self._raw_yaml_cache[metadata.workflow_id] = yaml_content

                except Exception as e:
                    logger.debug(f"Skipped file {yaml_file}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error discovering workflows in {directory}: {e}")

        return workflows

    # ----------------------------------------------------------------------
    # Full load / deduplication
    # ----------------------------------------------------------------------
    def _load_workflows(self) -> List[WorkflowMetadata]:
        """
        Load all workflows from all configured directories.
        """
        all_workflows: List[WorkflowMetadata] = []
        directories = self._get_workflow_directories()

        logger.debug(f"Searching for workflows in {len(directories)} directories")

        # reset raw cache on full load so /workflows/raw doesn't return stale entries
        self._raw_yaml_cache = {}

        for directory in directories:
            workflows = self._discover_workflows_from_directory(directory)
            all_workflows.extend(workflows)
            logger.debug(f"Found {len(workflows)} workflows in {directory}")

        unique_workflows: Dict[str, WorkflowMetadata] = {}
        for workflow in all_workflows:
            if workflow.workflow_id not in unique_workflows:
                unique_workflows[workflow.workflow_id] = workflow
            else:
                existing = unique_workflows[workflow.workflow_id]
                if workflow.created_at > existing.created_at:
                    unique_workflows[workflow.workflow_id] = workflow

        workflows_list = list(unique_workflows.values())
        workflows_list.sort(key=lambda w: w.name.lower())

        logger.info(f"Loaded {len(workflows_list)} unique workflows")
        return workflows_list

    # ----------------------------------------------------------------------
    # Cache management
    # ----------------------------------------------------------------------
    def _should_refresh_cache(self) -> bool:
        return (time.time() - self._cache_timestamp) > self._cache_ttl

    def _get_cached_workflows(self) -> List[WorkflowMetadata]:
        if not self._workflow_cache or self._should_refresh_cache():
            workflows = self._load_workflows()
            self._workflow_cache = {wf.workflow_id: wf for wf in workflows}
            self._cache_timestamp = time.time()
            logger.debug(f"Refreshed workflow cache with {len(workflows)} workflows")

        return list(self._workflow_cache.values())

    # ----------------------------------------------------------------------
    # Filtering + search
    # ----------------------------------------------------------------------
    def _filter_workflows(
        self,
        workflows: List[WorkflowMetadata],
        search_query: Optional[str] = None,
        category_filter: Optional[str] = None,
        complexity_filter: Optional[str] = None,
    ) -> List[WorkflowMetadata]:
        filtered = workflows

        if category_filter:
            category_lower = category_filter.lower()
            filtered = [wf for wf in filtered if wf.category == category_lower]

        if complexity_filter:
            complexity_lower = complexity_filter.lower()
            filtered = [wf for wf in filtered if wf.complexity_level == complexity_lower]

        if search_query:
            search_lower = search_query.lower()
            search_filtered: List[WorkflowMetadata] = []

            for workflow in filtered:
                searchable_text = " ".join(
                    [
                        workflow.name.lower(),
                        workflow.description.lower(),
                        " ".join(workflow.tags),
                        " ".join(workflow.use_cases),
                        workflow.workflow_id.lower(),
                    ]
                )

                if search_lower in searchable_text:
                    search_filtered.append(workflow)

            filtered = search_filtered

        return filtered

    # ----------------------------------------------------------------------
    # Public service methods
    # ----------------------------------------------------------------------
    def get_workflows(
        self,
        search_query: Optional[str] = None,
        category_filter: Optional[str] = None,
        complexity_filter: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> WorkflowsResponse:
        all_workflows = self._get_cached_workflows()

        filtered_workflows = self._filter_workflows(
            all_workflows,
            search_query,
            category_filter,
            complexity_filter,
        )

        total_workflows = len(filtered_workflows)
        paginated_workflows = filtered_workflows[offset : offset + limit]
        has_more = (offset + len(paginated_workflows)) < total_workflows

        categories = sorted(list(set(wf.category for wf in all_workflows)))

        logger.info(
            f"Workflow discovery: found {total_workflows} workflows after filtering, "
            f"returning {len(paginated_workflows)} with pagination"
        )

        return WorkflowsResponse(
            workflows=paginated_workflows,
            categories=categories,
            total=total_workflows,
            limit=limit,
            offset=offset,
            has_more=has_more,
            search_query=search_query,
            category_filter=category_filter,
            complexity_filter=complexity_filter,
        )

    def get_workflow_by_id(self, workflow_id: str) -> Optional[WorkflowMetadata]:
        workflows = self._get_cached_workflows()
        for workflow in workflows:
            if workflow.workflow_id == workflow_id:
                return workflow
        return None


# ===========================================================================
# Global service instance
# ===========================================================================
workflow_service = WorkflowDiscoveryService()


# ===========================================================================
# POST /workflows/refresh  (✅ NEW)
# ===========================================================================
@router.post("/workflows/refresh")
async def refresh_workflows() -> Dict[str, Any]:
    """
    Force refresh the workflow discovery cache immediately (dev-friendly).
    """
    try:
        workflow_service.force_refresh()
        return {"status": "ok", "count": len(workflow_service._get_cached_workflows())}
    except Exception as e:
        logger.error(f"Workflow refresh failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to refresh workflows", "message": str(e), "type": type(e).__name__},
        )


# ===========================================================================
# GET /workflows/raw/{workflow_id}  (✅ NEW)
# ===========================================================================
@router.get("/workflows/raw/{workflow_id}")
async def get_workflow_raw_yaml(workflow_id: str) -> Dict[str, Any]:
    """
    Debug endpoint: return the raw parsed YAML for a workflow (as the server sees it).
    Useful when a YAML file is being discovered but not behaving as expected.
    """
    try:
        # validate workflow_id format (same policy as metadata endpoint)
        if not workflow_id or not workflow_id.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Invalid workflow ID format",
                    "message": "Workflow ID must contain only letters, numbers, hyphens, and underscores",
                    "workflow_id": workflow_id,
                },
            )

        raw = workflow_service.get_raw_yaml_by_id(workflow_id)
        if raw is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "Workflow not found", "message": f"No workflow found with ID: {workflow_id}", "workflow_id": workflow_id},
            )
        return {"workflow_id": workflow_id, "raw": raw}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Workflow raw retrieval failed for {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to retrieve workflow raw YAML", "message": str(e), "type": type(e).__name__, "workflow_id": workflow_id},
        )


# ===========================================================================
# GET /workflows
# ===========================================================================
@router.get("/workflows", response_model=WorkflowsResponse)
async def get_workflows(
    search: Optional[str] = Query(
        None,
        description="Search query to filter workflows by name, description, tags, or use cases",
        max_length=200,
        examples=["academic research", "legal analysis", "business"],
    ),
    category: Optional[str] = Query(
        None,
        description="Filter workflows by category",
        max_length=50,
        examples=["academic", "legal", "business", "general"],
    ),
    complexity: Optional[str] = Query(
        None,
        description="Filter workflows by complexity level",
        pattern=r"^(low|medium|high|expert)$",
        examples=["low", "medium", "high", "expert"],
    ),
    limit: int = Query(
        default=10, ge=1, le=100, description="Maximum number of workflows to return"
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of workflows to skip for pagination"
    ),
) -> WorkflowsResponse:
    """
    Discover and retrieve available workflows.
    """
    try:
        logger.info(
            f"Workflow discovery request: search='{search}', category='{category}', "
            f"complexity='{complexity}', limit={limit}, offset={offset}"
        )

        response = workflow_service.get_workflows(
            search_query=search,
            category_filter=category,
            complexity_filter=complexity,
            limit=limit,
            offset=offset,
        )

        logger.info(
            f"Workflow discovery completed: {len(response.workflows)} workflows returned, "
            f"total={response.total}, has_more={response.has_more}, "
            f"categories={len(response.categories)}"
        )

        return response

    except Exception as e:
        logger.error(f"Workflows endpoint failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to discover workflows",
                "message": str(e),
                "type": type(e).__name__,
            },
        )


# ===========================================================================
# GET /workflows/{workflow_id}
# ===========================================================================
@router.get("/workflows/{workflow_id}", response_model=WorkflowMetadata)
async def get_workflow_by_id(workflow_id: str) -> WorkflowMetadata:
    """
    Retrieve metadata for a single workflow.
    """
    try:
        logger.info(f"Retrieving workflow metadata for workflow_id: {workflow_id}")

        if not workflow_id or not workflow_id.replace("_", "").replace("-", "").isalnum():
            logger.warning(f"Invalid workflow_id format: {workflow_id}")
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Invalid workflow ID format",
                    "message": (
                        "Workflow ID must contain only letters, numbers, hyphens, "
                        f"and underscores: {workflow_id}"
                    ),
                    "workflow_id": workflow_id,
                },
            )

        workflow = workflow_service.get_workflow_by_id(workflow_id)

        if workflow is None:
            logger.warning(f"Workflow not found: {workflow_id}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Workflow not found",
                    "message": f"No workflow found with ID: {workflow_id}",
                    "workflow_id": workflow_id,
                },
            )

        logger.info(
            f"Workflow metadata retrieved for {workflow_id}: {workflow.name}, "
            f"category={workflow.category}, complexity={workflow.complexity_level}"
        )

        return workflow

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Workflow retrieval failed for {workflow_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to retrieve workflow",
                "message": str(e),
                "type": type(e).__name__,
                "workflow_id": workflow_id,
            },
        )
