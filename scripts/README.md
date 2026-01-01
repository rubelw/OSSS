# OSSS Scripts — Utility & Automation Tools

The `scripts/` directory in this repository contains **useful automation scripts** used to support development, testing, setup, or maintenance workflows for the OSSS project. These may include shell scripts, helper utilities, maintenance tasks, and one-off tools that make everyday tasks easier for contributors and maintainers.

Scripts are commonly used to simplify or automate actions that would otherwise require a series of manual steps in the terminal or CI/CD workflows.

## Typical Contents

```
scripts/
├── *.sh                     # shell scripts for setup and maintenance
├── *.py                     # Python helpers and automation tools
├── *.bat                    # Windows batch scripts
├── cleanup.sh               # cleanup temporary data or build artifacts
├── reset_alembic.sh         # reset database migrations
├── other utility scripts
└── README.md                # this file
```

## How to Run Scripts

### Bash / Shell Scripts

Make sure scripts are executable:

```bash
chmod +x scripts/*.sh
```

Then run:

```bash
./scripts/your_script_name.sh
```

### Python Scripts

Run using Python:

```bash
python scripts/your_script.py
```

## Common Script Purposes

- environment setup
- database management
- testing and linting
- utilities and code generation
- cleanup and maintenance

## License

Scripts in this directory are part of the OSSS project and fall under the same OSS license.
