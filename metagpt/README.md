# MetaGPT Tool Schemas — Structured Interface Definitions

The `metagpt/tools/schemas` directory contains structured **schema definitions** used by the MetaGPT framework.  
These schemas define the **inputs, outputs, and contracts** for tools and agent interactions within OSSS's MetaGPT integration.

## Purpose

Schemas provide:

- Declarative API contracts for tools
- Safety and validation for agent‑driven tool calls
- Structured interfaces for LLM‑based reasoning and execution
- Shared documentation of expected parameters and result formats

## Typical Contents

```
metagpt/tools/schemas/
├── <tool_name>.schema.json        # JSON schema describing arguments & return types
├── <tool_group>.schema.py         # Python schema (pydantic / models)
└── __init__.py                    # package initializer
```

> Actual filenames depend on which tools have been implemented.

## Example Schema (conceptual)

```json
{
  "name": "fetch_student_records",
  "description": "Retrieve records for a given student ID",
  "type": "object",
  "properties": {
    "student_id": { "type": "string" },
    "limit": { "type": "integer" }
  },
  "required": ["student_id"]
}
```

Agents can then invoke the tool via a structured call:

```json
{
  "name": "fetch_student_records",
  "args": { "student_id": "S100112" }
}
```

## How Schemas Are Used

- Tool schemas are registered with MetaGPT's orchestrator
- LLM agents introspect schemas to determine required arguments
- Inputs are validated before being handed to tool implementations
- Results may be validated or transformed for consistency

This ensures:
- predictable execution
- safer integration with external systems
- fewer hallucinated tool calls
- traceable reasoning paths

## Implementation Notes

- JSON schemas should follow standard JSON Schema syntax
- Python schemas may use pydantic, TypedDict, attrs, or dataclasses
- Consistency in `name` and `properties` keys is essential
- Document non‑obvious fields directly in schema metadata

## Future Expansion

Consider adding:

- `schema_version` fields for evolution tracking
- automatic schema validation CI step
- schema‑driven tool documentation generation
- mkdocs integration to display tool APIs

## License

This directory is part of the OSSS + MetaGPT integration and falls under the OSSS project license.

