# src/OSSS/ai/agents/data_query/queryspec.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal, Tuple


@dataclass
class Projection:
    """
    A single projected column.

    - collection: which collection/table this comes from
    - field:      the actual field/column name
    - alias:      optional alias to expose to the UI / downstream consumers
    """
    collection: str   # "consents" or "persons"
    field: str        # "consent_type", "first_name", "last_name", etc.
    alias: Optional[str] = None  # e.g. "person_name"


@dataclass
class Join:
    """
    Declarative join between two collections.

    Example: consents.person_id -> persons.id

    - from_collection / from_field: the FK side
    - to_collection / to_field:     the PK/target side
    - alias:                        optional alias for the joined entity
    - select_fields:                fields to pull from the joined collection
    - computed_name_alias:          if set, downstream code can use select_fields
                                    (e.g. first_name + last_name) to build a single
                                    UI-friendly name column with this alias.
    """
    from_collection: str
    from_field: str
    to_collection: str
    to_field: str
    alias: Optional[str] = None
    # 👇 which fields to pull from the joined collection (e.g. first_name, last_name)
    select_fields: List[str] = field(default_factory=list)
    # 👇 optional alias for a computed human-name field (e.g. "person_name")
    computed_name_alias: Optional[str] = None


FilterOp = Literal[
    "eq",
    "neq",
    "lt",
    "lte",
    "gt",
    "gte",
    "contains",
    "startswith",
    "in",
]


@dataclass
class FilterCondition:
    """
    A simple filter you can later translate to query params or SQL.
    Example: last_name startswith 'R'
    """
    field: str            # "last_name"
    op: FilterOp          # "startswith"
    value: Any            # "R"


@dataclass
class QuerySpec:
    """
    Declarative description of a query over a base collection.

    Generated defaults:
      - projections: default columns to show
      - joins: FK-based joins (e.g. consents.person_id -> persons.id)
      - synonyms: NL → field paths (merged from schema.py)
      - search_fields: good candidates for UI search boxes
      - sort: ordered list of (field, direction) pairs
    """
    base_collection: str
    projections: List[Projection] = field(default_factory=list)
    joins: List[Join] = field(default_factory=list)
    filters: List[FilterCondition] = field(default_factory=list)
    synonyms: Dict[str, str] = field(default_factory=dict)
    search_fields: List[str] = field(default_factory=list)
    default_limit: int = 100
    # 👇 tiny UI-friendly subset of columns to show by default
    # These are the *aliases* you want visible in the UI when nothing else is specified.
    ui_default_projection_aliases: List[str] = field(default_factory=list)
    # 👇 ordered list of (field, direction) pairs, e.g. [("consent_type", "desc")]
    # direction should be "asc" or "desc"
    sort: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def needs_person_join(self) -> bool:
        # Convenience for your consents use-case (and any future person joins)
        return any(j.to_collection == "persons" for j in self.joins)

    def with_filter(self, field: str, op: FilterOp, value: Any) -> "QuerySpec":
        """
        Small helper to add a filter fluently.
        """
        self.filters.append(FilterCondition(field=field, op=op, value=value))
        return self

    def with_sort(self, field: str, direction: str = "asc") -> "QuerySpec":
        """
        Small helper to add a sort clause fluently.

        direction: "asc" or "desc" (case-insensitive)
        """
        norm_dir = direction.lower()
        if norm_dir not in ("asc", "desc"):
            raise ValueError(f"Invalid sort direction: {direction!r}")
        self.sort.append((field, norm_dir))
        return self


# ---------------------------------------------------------------------------
# DEFAULT QUERY SPECS
# ---------------------------------------------------------------------------

# These are looked up by collection name, e.g. DEFAULT_QUERY_SPECS["consents"]
DEFAULT_QUERY_SPECS: Dict[str, QuerySpec] = {
    # You can add more collections here over time.
    #
    # This entry wires up:
    #   consents.person_id → persons.id
    # and exposes a UI-friendly "person_name" column instead of person_id.
    "consents": QuerySpec(
        base_collection="consents",
        projections=[
            # NOTE: we intentionally expose "person_name" instead of "person_id"
            Projection(collection="persons", field="first_name", alias="person_first_name"),
            Projection(collection="persons", field="last_name", alias="person_last_name"),
            # downstream code can combine these into "person_name" if desired
            Projection(collection="consents", field="consent_type"),
            Projection(collection="consents", field="granted"),
            Projection(collection="consents", field="effective_date"),
            Projection(collection="consents", field="expires_on"),
            Projection(collection="consents", field="created_at"),
            Projection(collection="consents", field="updated_at"),
            Projection(collection="consents", field="id"),
        ],
        joins=[
            Join(
                from_collection="consents",
                from_field="person_id",
                to_collection="persons",
                to_field="id",
                alias="person",
                # pull enough fields to compute a nice human name
                select_fields=["first_name", "last_name"],
                # downstream code (in _execute_queryspec_http) can build "person_name"
                # from first_name + last_name and drop the raw person_id.
                computed_name_alias="person_name",
            )
        ],
        search_fields=[
            "consent_type",
            "person_name",  # virtual / computed field
        ],
        ui_default_projection_aliases=[
            # these are the primary columns to show in the compact UI table
            "person_name",
            "consent_type",
            "granted",
            "effective_date",
            "expires_on",
        ],
    ),
}
