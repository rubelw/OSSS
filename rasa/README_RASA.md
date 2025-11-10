# Rasa Mentor (OSSS add-on)

This directory contains a minimal **Rasa 3.x** project wired for a quick start as a standalone chatbot service.

## Quick Start

```bash
# from the OSSS repo root
docker compose -f docker-compose.yml -f docker-compose.rasa.yml up -d
```

This will:
- mount `./rasa` into the container
- **train** a minimal model
- start the Rasa server on **http://localhost:5005**

## Test it

**Talk to the bot** via REST webhook:

```bash
curl -s http://localhost:5005/webhooks/rest/webhook   -H 'Content-Type: application/json'   -d '{"sender":"test-user","message":"hello"}' | jq .
```

You should see a response like:
```json
[{"recipient_id":"test-user","text":"Hey there! I'm your OSSS Mentor. How can I help today?"}]
```

## Project Layout

```
rasa/
├── config.yml         # NLU pipeline + policies
├── credentials.yml    # enables REST channel
├── domain.yml         # intents + responses
├── data/
│   ├── nlu.yml        # training utterances
│   ├── stories.yml    # sample dialogues
│   └── rules.yml      # simple rule-based responses
└── README_RASA.md
```

## Makefile helpers (optional)

Add these targets to your root `Makefile` if useful:

```Makefile
rasa-up:
	 docker compose -f docker-compose.yml -f docker-compose.rasa.yml up -d

rasa-down:
	 docker compose -f docker-compose.yml -f docker-compose.rasa.yml down

rasa-logs:
	 docker logs -f rasa-mentor

rasa-train:
	 docker compose -f docker-compose.yml -f docker-compose.rasa.yml run --rm rasa-mentor rasa train
```

## Notes

- This starter uses **REST** only. If you later add custom actions, include an `actions` service (image `rasa/rasa-sdk:3.6.2x`) and an `endpoints.yml` that points to it.
- CORS is set to `*`. Adjust if you are hosting a web client on another origin.
- Model files will be generated inside the container at `/app/models` (persisted because `/app` is mounted to `./rasa`).

