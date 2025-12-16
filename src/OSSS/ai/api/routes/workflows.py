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

        # Timestamp (epoch seconds) when cache was last refreshed
        self._cache_timestamp = 0.0

        # Cache time-to-live (seconds). After this, a refresh is triggered.
        self._cache_ttl = 300.0  # 5 minutes

        # Directories (relative to current working directory) to scan for workflows.
        # These paths are intentionally simple and can be expanded later (config/env).
        self._workflow_directories = [
            "src/osss/workflows/examples",
            "examples/charts",
        ]

    # ----------------------------------------------------------------------
    # Filesystem discovery helpers
    # ----------------------------------------------------------------------
    def _get_workflow_directories(self) -> List[Path]:
        """
        Resolve workflow directory paths to concrete filesystem Paths.

        Returns:
            A list of Path objects that exist and are directories.

        Notes:
            - Uses the current working directory as the base, which means
              behavior depends on how/where the service is started.
            - If you need deterministic behavior across environments,
              consider using an env var or app config to define base_path.
        """
        directories: List[Path] = []

        # Use current working directory as base for relative scan locations
        base_path = Path.cwd()

        for dir_path in self._workflow_directories:
            full_path = base_path / dir_path

            # Only include valid directories (ignore missing paths)
            if full_path.exists() and full_path.is_dir():
                directories.append(full_path)

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

        Args:
            yaml_content: Parsed YAML as a dictionary.
            file_path: Path to the workflow file (used for defaults + timestamps).

        Returns:
            WorkflowMetadata if extraction succeeds, otherwise None.
        """
        try:
            # --------------------------------------------------------------
            # Basic identity fields
            # --------------------------------------------------------------

            # workflow_id can be explicitly set, otherwise use the file stem
            workflow_id = yaml_content.get("workflow_id", file_path.stem)

            # Human-friendly name; derive from workflow_id when absent
            name = yaml_content.get("name", workflow_id.replace("_", " ").title())

            # Description; fallback to a generic description
            description = yaml_content.get("description", f"Workflow: {name}")

            # --------------------------------------------------------------
            # Version normalization
            # --------------------------------------------------------------
            # We try to normalize to a semantic-version-ish string:
            # - numeric -> "<n>.0.0"
            # - "1"     -> "1.0.0"
            # - "1.2"   -> "1.2.0"
            # - "1.2.3" -> keep as-is
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

            # Category/domain: prefer metadata.domain, then metadata.category, else "general"
            category = metadata.get("domain", metadata.get("category", "general"))

            # --------------------------------------------------------------
            # Tags: merged from multiple sources
            # --------------------------------------------------------------
            tags = set()

            # Allow tags at the top-level YAML
            if "tags" in yaml_content:
                tags.update(yaml_content["tags"])

            # Allow tags within the metadata block
            if "tags" in metadata:
                tags.update(metadata["tags"])

            # Always include category as a tag for discoverability
            if category not in tags:
                tags.add(category)

            # Fallback tags if somehow still empty
            if not tags:
                tags = {"workflow", "general"}

            # --------------------------------------------------------------
            # Attribution
            # --------------------------------------------------------------
            # created_by may be specified at the top level or within metadata
            created_by = yaml_content.get(
                "created_by", metadata.get("created_by", "OSSS")
            )

            # --------------------------------------------------------------
            # Complexity normalization
            # --------------------------------------------------------------
            # Convert loose labels into canonical set:
            # low | medium | high | expert
            raw_complexity = metadata.get("complexity_level", "medium")
            complexity_mapping = {
                "beginner": "low",
                "simple": "low",
                "basic": "low",
                "intermediate": "medium",
                "advanced": "high",
                "complex": "high",
                "error_testing": "expert",  # special case
            }

            complexity_level = complexity_mapping.get(
                raw_complexity.lower(), raw_complexity.lower()
            )

            # Guardrail: ensure we only emit supported values
            if complexity_level not in ["low", "medium", "high", "expert"]:
                complexity_level = "medium"

            # --------------------------------------------------------------
            # Additional helpful metadata (optional)
            # --------------------------------------------------------------
            estimated_execution_time = metadata.get(
                "estimated_execution_time", "30-45 seconds"
            )

            # Use cases: allow list or single value; normalize to list[str]
            use_cases = metadata.get("use_cases", [workflow_id.replace("_", " ")])

            # Node count: workflows are typically graphs; "nodes" is expected
            nodes = yaml_content.get("nodes", [])
            node_count = len(nodes)

            # created_at: prefer filesystem create time; fallback to current time
            created_at = file_path.stat().st_ctime if file_path.exists() else time.time()

            # --------------------------------------------------------------
            # Return a fully populated WorkflowMetadata model
            # --------------------------------------------------------------
            return WorkflowMetadata(
                workflow_id=workflow_id,
                name=name,
                description=description,
                version=version,
                category=category.lower(),
                tags=list(tags),
                created_by=created_by,
                created_at=created_at,
                estimated_execution_time=estimated_execution_time,
                complexity_level=complexity_level,
                node_count=max(1, node_count),  # ensure non-zero (UI friendliness)
                use_cases=(use_cases if isinstance(use_cases, list) else [str(use_cases)]),
            )

        except Exception as e:
            # Any failure to parse a workflow file should not kill discovery.
            # We log and return None so the caller can skip this workflow.
            logger.warning(f"Failed to extract metadata from {file_path}: {e}")
            return None

    # ----------------------------------------------------------------------
    # Directory scanning
    # ----------------------------------------------------------------------
    def _discover_workflows_from_directory(self, directory: Path) -> List[WorkflowMetadata]:
        """
        Scan a directory recursively to find workflow definition YAML files.

        Args:
            directory: Root directory to scan.

        Returns:
            A list of WorkflowMetadata objects discovered in that directory.

        Notes:
            - Uses rglob("*.yaml"/"*.yml") to discover files recursively.
            - Each file is parsed with yaml.safe_load for safety.
            - We do a simple "looks like workflow" check:
              workflow_id exists OR nodes exists.
        """
        workflows: List[WorkflowMetadata] = []

        try:
            # Find YAML files via glob patterns
            yaml_patterns = ["*.yaml", "*.yml"]
            yaml_files: List[Path] = []

            for pattern in yaml_patterns:
                yaml_files.extend(directory.rglob(pattern))

            # Parse each YAML file and attempt metadata extraction
            for yaml_file in yaml_files:
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        yaml_content = yaml.safe_load(f)

                    # We only handle dict-like YAML at this point
                    if yaml_content and isinstance(yaml_content, dict):
                        # Heuristic: consider it a workflow if it has key fields
                        if "workflow_id" in yaml_content or "nodes" in yaml_content:
                            metadata = self._extract_metadata_from_yaml(
                                yaml_content, yaml_file
                            )
                            if metadata:
                                workflows.append(metadata)

                except Exception as e:
                    # Bad YAML, permission issues, encoding errors, etc.
                    # Not fatal; skip this file and continue scanning.
                    logger.debug(f"Skipped file {yaml_file}: {e}")
                    continue

        except Exception as e:
            # A directory-level failure (permissions, FS errors, etc.)
            logger.error(f"Error discovering workflows in {directory}: {e}")

        return workflows

    # ----------------------------------------------------------------------
    # Full load / deduplication
    # ----------------------------------------------------------------------
    def _load_workflows(self) -> List[WorkflowMetadata]:
        """
        Load all workflows from all configured directories.

        Steps:
        1) Resolve directories
        2) Discover workflows in each directory
        3) Deduplicate by workflow_id (keeping newest)
        4) Sort by name for stable output ordering

        Returns:
            A list of unique, sorted WorkflowMetadata objects.
        """
        all_workflows: List[WorkflowMetadata] = []
        directories = self._get_workflow_directories()

        logger.debug(f"Searching for workflows in {len(directories)} directories")

        for directory in directories:
            workflows = self._discover_workflows_from_directory(directory)
            all_workflows.extend(workflows)
            logger.debug(f"Found {len(workflows)} workflows in {directory}")

        # Deduplicate by workflow_id
        unique_workflows: Dict[str, WorkflowMetadata] = {}

        for workflow in all_workflows:
            if workflow.workflow_id not in unique_workflows:
                unique_workflows[workflow.workflow_id] = workflow
            else:
                # If duplicates exist, keep whichever file appears "newer"
                existing = unique_workflows[workflow.workflow_id]
                if workflow.created_at > existing.created_at:
                    unique_workflows[workflow.workflow_id] = workflow

        workflows_list = list(unique_workflows.values())

        # Stable ordering for UI + tests
        workflows_list.sort(key=lambda w: w.name.lower())

        logger.info(f"Loaded {len(workflows_list)} unique workflows")
        return workflows_list

    # ----------------------------------------------------------------------
    # Cache management
    # ----------------------------------------------------------------------
    def _should_refresh_cache(self) -> bool:
        """
        Determine whether our in-memory cache is stale.

        Returns:
            True if cache age exceeds TTL.
        """
        return (time.time() - self._cache_timestamp) > self._cache_ttl

    def _get_cached_workflows(self) -> List[WorkflowMetadata]:
        """
        Return workflows from cache, refreshing if needed.

        Refresh happens when:
        - Cache is empty (first run)
        - Cache TTL has expired

        Returns:
            List of WorkflowMetadata currently cached.
        """
        if not self._workflow_cache or self._should_refresh_cache():
            workflows = self._load_workflows()

            # Cache as workflow_id -> WorkflowMetadata for fast lookup
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
        """
        Filter workflows by category, complexity, and full-text-ish search.

        Args:
            workflows: Workflows to filter (usually cached list)
            search_query: Optional substring search across name/desc/tags/use_cases/id
            category_filter: Optional exact match on category
            complexity_filter: Optional exact match on complexity_level

        Returns:
            Filtered list of WorkflowMetadata.
        """
        filtered = workflows

        # Category filter is an exact match (normalized to lowercase)
        if category_filter:
            category_lower = category_filter.lower()
            filtered = [wf for wf in filtered if wf.category == category_lower]

        # Complexity filter is an exact match (normalized to lowercase)
        if complexity_filter:
            complexity_lower = complexity_filter.lower()
            filtered = [wf for wf in filtered if wf.complexity_level == complexity_lower]

        # Search query uses substring matching across multiple fields
        if search_query:
            search_lower = search_query.lower()
            search_filtered: List[WorkflowMetadata] = []

            for workflow in filtered:
                # Construct a single string of searchable fields.
                # This is a simple approach (not tokenized / ranked).
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
        """
        Return workflows with filtering + pagination.

        Args:
            search_query: Optional search term
            category_filter: Optional category
            complexity_filter: Optional complexity (low|medium|high|expert)
            limit: Page size
            offset: Page offset

        Returns:
            WorkflowsResponse including:
            - workflows (current page)
            - categories (all categories across all workflows)
            - pagination metadata
        """
        # Load (cached) workflows
        all_workflows = self._get_cached_workflows()

        # Apply user-provided filters/search
        filtered_workflows = self._filter_workflows(
            all_workflows,
            search_query,
            category_filter,
            complexity_filter,
        )

        # Pagination calculations
        total_workflows = len(filtered_workflows)
        paginated_workflows = filtered_workflows[offset : offset + limit]
        has_more = (offset + len(paginated_workflows)) < total_workflows

        # Provide a list of all categories for UI filter dropdowns, etc.
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
        """
        Lookup a workflow by workflow_id.

        This is used by the /workflows/{workflow_id} endpoint.

        Args:
            workflow_id: ID to look for (exact match)

        Returns:
            WorkflowMetadata if found, else None.
        """
        workflows = self._get_cached_workflows()
        for workflow in workflows:
            if workflow.workflow_id == workflow_id:
                return workflow
        return None


# ===========================================================================
# Global service instance
# ===========================================================================
# This is a singleton-like instance reused across requests in the process.
workflow_service = WorkflowDiscoveryService()


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

    Endpoint behavior:
    - Scans configured directories for YAML workflow definitions
      (via cached WorkflowDiscoveryService)
    - Extracts normalized metadata per workflow
    - Applies optional search + filtering
    - Returns a paginated list plus category list for UI filtering

    Raises:
        HTTPException(500) on unexpected discovery errors.
    """
    try:
        logger.info(
            f"Workflow discovery request: search='{search}', category='{category}', "
            f"complexity='{complexity}', limit={limit}, offset={offset}"
        )

        # Delegate discovery/search/filtering/pagination to the service layer
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
        # Catch-all: we intentionally avoid leaking raw exceptions to the client.
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

    This endpoint:
    - Validates workflow_id format (simple alnum + '_' + '-')
    - Looks up workflow metadata in the cached discovery service
    - Returns 404 if not found

    Raises:
        HTTPException(422) if workflow_id is invalid
        HTTPException(404) if workflow_id not found
        HTTPException(500) on unexpected errors
    """
    try:
        logger.info(f"Retrieving workflow metadata for workflow_id: {workflow_id}")

        # Validate workflow_id format early to avoid weird path-like IDs or injection-y strings.
        # This is intentionally conservative:
        # - underscores and hyphens are allowed
        # - everything else must be alphanumeric
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

        # Lookup workflow metadata from service
        workflow = workflow_service.get_workflow_by_id(workflow_id)

        # Not found -> 404
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
        # Important: let FastAPI return the intended status codes for known failure modes.
        raise

    except Exception as e:
        # Catch-all for unexpected server errors
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
