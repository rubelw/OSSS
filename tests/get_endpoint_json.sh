#!/usr/bin/env bash

curl http://localhost:8085/realms/OSSS/.well-known/openid-configuration | jq .
