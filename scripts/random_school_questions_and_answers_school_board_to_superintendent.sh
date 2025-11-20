#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8081}"

# Require jq for JSON parsing/encoding
if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required but not installed." >&2
  exit 1
fi

i=0
while IFS= read -r question; do
  if [ -z "$question" ]; then
    continue
  fi

  i=$((i + 1))

  json_question=$(printf '%s' "$question" | jq -Rs .)

  resp=$(
    curl -sS -X 'POST' \
      "$API_BASE/ai/chat/rag" \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -d '{
  "model": "llama3.2-vision",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": '"$json_question"'
    }
  ],
  "max_tokens": 2048,
  "temperature": 0.1,
  "debug": false,
  "index": "main"
}' \
  ) || { echo "Request $i failed." >&2; continue; }

  intent=$(
    printf '%s\n' "$resp" \
      | jq -r '(.intent // "general")' 2>/dev/null \
      || echo "general"
  )

  if [ "$intent" = "general" ]; then
    echo
    echo "=============================="
    echo "QUESTION $i:"
    echo "$question"
    echo "=============================="
    echo "$resp"
    echo
    echo "---- END RESPONSE FOR QUESTION $i ----"
    echo
  fi

done << 'EOF'
What benchmarks should the board use to evaluate district academic progress this year?
What staffing shortages are we projecting for next year, and what is the mitigation plan?
How are the new literacy interventions performing based on early assessment data?
What is the superintendent’s recommendation for managing increasing enrollment in certain buildings?
What are the district’s three biggest operational risks right now?
Can you provide an update on progress toward the strategic plan goals adopted last year?
Where are we currently over budget, and what adjustments do you recommend?
What legislative changes this session could impact our funding or operations?
What is the long-range facilities recommendation for the next 5–10 years?
How are we measuring the impact of our professional development programs?
What data is informing your recommendation on future boundary adjustments?
How is the district responding to increases in behavioral incidents?
What is the plan to improve teacher retention and recruitment competitiveness?
How do current class sizes compare to board-approved targets?
What steps are being taken to improve communication consistency across buildings?
How confident are we in meeting our ESSA accountability targets?
What new grants or funding opportunities should the district pursue?
How are principals being supported in instructional leadership development?
What is the timeline for rolling out new curriculum materials next year?
How do we ensure equity across buildings in course offerings and student supports?
Can you summarize feedback from your most recent superintendent advisory councils?
What is your recommendation for improving community engagement around major decisions?
How is transportation capacity changing with current fleet conditions?
What safety improvements are most urgently needed based on recent audits?
How are we evaluating the effectiveness of our mental health partnerships?
What technology upgrades are required in the next two years to stay current?
How do we ensure consistent discipline practices across schools?
What new or emerging challenges should the board be preparing for now?
EOF
