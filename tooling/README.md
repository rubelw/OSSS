# Tooling — OSSS Documentation & Automation Scripts

The `tooling/` directory contains scripts and utilities to automate OSSS documentation, code generation, and maintenance tasks. These tools support processes like generating OpenAPI docs, building Docker Compose docs, and other tasks that improve developer experience and keep documentation in sync with code.

## Purpose
The tooling scripts help with:
- Generating documentation (OpenAPI, Docker Compose)
- Automating repetitive tasks (exports, updates)
- Integrating with MkDocs builds using gen-files
- Ensuring docs remain in sync with code

## Typical Contents
```
tooling/
├── export_openapi.py
├── generate_docker_compose_docs.py
├── generate_all_docs.py
├── other tooling utilities
└── README.md
```

## MkDocs Integration
```
plugins:
  - gen-files:
      scripts:
        - tooling/export_openapi.py
        - tooling/generate_docker_compose_docs.py
        - tooling/generate_all_docs.py
```

## Manual Use
```
python tooling/export_openapi.py
python tooling/generate_docker_compose_docs.py
python tooling/generate_all_docs.py
```

## License
Follows OSSS project license.
