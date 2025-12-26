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

  # JSON-escape the question safely
  # This produces something like:  "How do I set up ... teacher?"
  json_question=$(printf '%s' "$question" | jq -Rs .)

  # Call the API and capture the response
  resp=$(
    curl -sS -X 'POST' \
      "$API_BASE/ai/chat/rag" \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -d '{
  "model": "llama3.1",
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

  # Extract intent; default to "general" if anything goes wrong
  intent=$(
    printf '%s\n' "$resp" \
      | jq -r '(.intent // "general")' 2>/dev/null \
      || echo "general"
  )

  # Only output if the classifier intent is "general"
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
What is our current projected ending general fund balance for this fiscal year?
How does our projected fund balance compare to the board-approved target percentage?
Which three expenditure categories are driving the largest year-over-year increases?
Where are we currently over budget, and what is your plan to address those variances?
Where are we currently under budget, and are those savings sustainable or one-time?
How closely are actual revenues tracking to the assumptions in our adopted budget?
How sensitive is our budget to changes in enrollment of plus or minus 50 students?
Can you walk me through the major assumptions behind our five-year financial forecast?
What are the key financial risks you see in the next 12–24 months?
What mitigation strategies do you recommend for those financial risks?
How are we monitoring the impact of inflation on our operating costs?
What is our current cash-on-hand position in days, and how has that trended over time?
Do you anticipate any cash flow shortfalls that would require short-term borrowing?
How diversified are our revenue sources, and where are we most vulnerable?
What changes, if any, do you expect in state aid or local revenue next year?
How are we tracking expenditures tied to restricted funds versus unrestricted funds?
Are there any restricted funds that we are not fully utilizing that could support priorities?
How are we ensuring that grant funds are spent down on schedule and within guidelines?
Which grants are set to expire soon, and what is our plan for programs they currently support?
Can you provide a summary of how ESSER or other one-time funds have been allocated so far?
Which ongoing costs are currently being covered by one-time funds, and what is our exit plan?
How are you communicating to principals which funds are ongoing versus temporary?
What criteria are you using to recommend reductions if our revenues come in below projections?
If we were required to reduce the budget by five percent, what options would you place on the table first?
How are we aligning our budget to the district’s strategic plan priorities?
Can you show me where our spending clearly reflects our top three strategic priorities?
Where do you see misalignment between what we say is a priority and how we are actually spending?
How are we tracking expenditures for key initiatives so we can evaluate return on investment?
What financial data do you provide principals monthly, and how are they using it?
Are there building leaders who may need additional support to interpret and manage their budgets?
How are we monitoring overtime and extra-duty pay across departments?
Do you see any patterns of inefficiency or waste in our current spending?
What opportunities do you see for cost savings that would not harm core instructional programs?
How often do you review vendor contracts for pricing competitiveness and performance?
Are there any contracts you recommend we rebid or renegotiate this year?
What controls are in place to prevent unauthorized or inappropriate purchasing?
Have our most recent audits identified any material weaknesses or significant deficiencies?
What progress have we made on addressing prior audit findings or recommendations?
How confident are you in the accuracy and timeliness of our financial reporting systems?
What internal controls do you consider our strongest, and which need the most improvement?
How are we managing the financial aspects of student activity accounts?
Do you have any concerns about controls or oversight in activity or booster accounts?
How are we accounting for and monitoring donations, gifts, and fundraising revenue?
What is our current debt load, and how does it compare to statutory or board limits?
What is the timetable for our next potential bond issue or refinancing opportunity?
How are we ensuring that bond proceeds are spent in accordance with voter-approved purposes?
Can you provide an update on major capital projects from a budget and cash flow standpoint?
Are any capital projects currently over budget or facing cost escalation risks?
What is our long-term plan for funding major maintenance and facility renewal needs?
How are we tracking the total cost of ownership for new facilities or additions?
What trends are you seeing in health insurance and other benefit costs?
How are we modeling the financial impact of salary settlements during negotiations?
What is the projected impact of upcoming labor agreements on our long-range forecast?
Do we have any positions that are consistently hard to fill because of compensation issues?
How are we funding substitutes, and are those costs trending up or down?
What is our per-pupil spending compared to similar districts, and where do we differ most?
How does our spending on instruction, support services, and administration compare to benchmarks?
What metrics do you suggest we use to monitor financial health at the board level?
Which dashboards or standard reports should we be reviewing monthly as a cabinet?
How easy is it for non-financial leaders to understand the reports you provide?
What training or support could we offer principals to improve their financial literacy?
How are you staying current with changes in school finance law and regulations?
Are there any upcoming legislative changes that could significantly impact our budget?
What compliance deadlines are on the horizon that we need to be prepared for?
Are there any areas where you worry we may be at risk of non-compliance?
How are we managing procurement to ensure both compliance and efficiency?
Do we have clear thresholds and processes for quotes, bids, and RFPs?
How are student transportation costs trending, and what is driving those changes?
What is the financial status of our food service program, and is it self-sustaining?
Are there opportunities to improve efficiency in transportation or food service without reducing quality?
How are we tracking the cost of technology devices, licenses, and support contracts?
Do you have concerns about the sustainability of our current technology replacement cycle?
How are we budgeting for cybersecurity tools, insurance, and incident response?
What contingency plans do we have in place for unexpected large expenses, such as major equipment failure?
How are we planning financially for enrollment growth or the possibility of enrollment decline?
Are there particular schools or programs where enrollment trends may drive future staffing changes?
What is our process for evaluating the financial impact of starting a new program or closing an existing one?
How do you evaluate whether a grant-funded program is financially sustainable once the grant ends?
What criteria do you use to recommend whether to continue, expand, or sunset a program?
How well are our chart of accounts and coding structures supporting program-level reporting?
Are principals and department heads coding expenditures consistently and accurately?
What investments in the finance office itself would improve accuracy, efficiency, or transparency?
Do you feel the finance team has adequate staffing and tools to meet current expectations?
What processes in the business office are most paper-heavy or manual that we could streamline?
How are we handling vendor onboarding, and do we have adequate checks in that process?
Are there any concerns about segregation of duties within our financial processes?
If you had additional capacity in the finance office, what work would you prioritize first?
What do you need from me and from the board to communicate our financial story more clearly to the community?
How can we better help staff, families, and community members understand our budget constraints and tradeoffs?
What aspects of our current budget process work well, and what would you change for next year?
How early do you need strategic direction from me to build a realistic budget proposal?
What is one financial risk that keeps you up at night that I should better understand?
What is one financial opportunity you see that we have not yet taken advantage of?
If you could change one state or local rule to improve school finance operations, what would it be?
What questions do you wish board members would ask more often about our finances?
Is there anything about our financial position that you think I am underestimating or overlooking?
If an unexpected $1 million became available tomorrow, how would you recommend we allocate it?
If we suddenly had to cut $1 million tomorrow, what would you recommend we protect at all costs?
How are we incorporating feedback from external auditors or consultants into our financial practices?
What regular financial communication to staff and the public would most improve trust and transparency?
EOF
