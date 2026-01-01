# Filebeat Data / Configuration for OSSS

The `es-shared/filebeat-data` directory contains shared **Filebeat configuration and data files** used within the OSSS project to collect, parse, and forward logs to an Elastic Stack setup.

**Filebeat** is part of the Elastic Stack and is typically used to harvest and forward logs from services to systems like:
- **Elasticsearch** (for storage & indexing)
- **Logstash** (for filtering & transformation)
- **Kibana** (for visualization & dashboards)

In OSSS, this directory provides a central place for Filebeat configurations that are shared across different services or environments.

## Purpose

This folder exists to hold:

- Filebeat configuration templates (inputs, modules, output targets)
- JSON or YAML definitions for pipelines
- Example log‑shipping patterns for OSSS services
- Shared fields or mappings used by Elastic ingestion

## Typical Contents

```
es-shared/filebeat-data/
├── filebeat.yml            # primary Filebeat config
├── modules.d/              # enabled Filebeat modules
├── pipelines/              # ingest pipelines for Elasticsearch
├── fields/                 # shared field definitions
├── templates/              # Elasticsearch index templates
└── README.md               # this file
```

## Usage

### Install Filebeat

Follow the official Elastic documentation to install Filebeat on your system:

```bash
# macOS
brew tap elastic/tap
brew install elastic/tap/filebeat
```

### Update config

Copy the shared config into the Filebeat install folder:

```bash
cp es-shared/filebeat-data/filebeat.yml /etc/filebeat/filebeat.yml
cp -r es-shared/filebeat-data/modules.d /etc/filebeat/modules.d
```

### Start Filebeat

Run Filebeat with:

```bash
filebeat setup
filebeat -e
```

## License

This directory and its contents are governed by the OSSS project’s main license.
