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
How are you monitoring academic progress in each grade level this quarter?
What specific interventions are in place for students who are not on track in reading?
What specific interventions are in place for students who are not on track in math?
How are you ensuring our core instructional materials are being used with fidelity?
What trends are you seeing in classroom walkthrough data this month?
How are PLCs functioning in your building, and what are they currently focused on?
What support do your teachers say they need most right now to improve instruction?
How are you using formative assessment data to adjust instruction buildingwide?
Which student groups are currently underperforming, and what is your plan to address this?
How are you supporting new teachers in your building during their first year?
What is your plan for retaining our strongest teachers over the next three years?
How are you addressing concerns about teacher workload and burnout in your building?
What is your process for coaching teachers who are struggling instructionally?
How are you ensuring that evaluations are meaningful and growth-focused for staff?
What professional learning priorities have you set for your staff this semester?
How are you building a positive, collaborative culture among your staff?
What are the biggest behavior challenges you are seeing from students this year?
How are you using your building behavior data to adjust supports and expectations?
What does your Tier 1 behavior system look like in classrooms and common areas?
How is your MTSS or PBIS framework being implemented day to day?
What supports are in place for students with chronic behavior issues?
How are you communicating behavior expectations to students and families?
What trends are you seeing in attendance, and how are you responding to chronic absenteeism?
How are you supporting families of students who are frequently tardy or absent?
What is your plan to reduce out-of-school suspensions while maintaining safety?
How is your building implementing our district safety and crisis protocols?
When was the last time you reviewed emergency procedures with your staff?
How effective have your recent fire, lockdown, and evacuation drills been?
What concerns do staff have about safety, and how are you addressing them?
How are you managing visitor access and building entry during the school day?
What specific steps are you taking to prevent and respond to bullying incidents?
How are you supporting students’ social-emotional needs in your building?
What systems are in place for students to seek help when they are struggling emotionally?
How are counselors, social workers, and administrators collaborating in your building?
What partnerships with community mental health providers are you leveraging?
How are you ensuring that IEP and 504 accommodations are implemented with fidelity?
What supports are available for teachers who have multiple high-need students in one class?
How are English learners being supported in both language development and content learning?
What are you doing to ensure equitable access to advanced coursework in your building?
How are you monitoring equity in discipline, course placement, and opportunities across student groups?
What steps are you taking to build a more inclusive and culturally responsive school climate?
How are families being engaged in conversations about diversity, equity, and inclusion?
How are you communicating with families about student progress and school events?
What strategies are you using to increase participation in family conferences and events?
How are you incorporating family voice and feedback into your building decisions?
What outreach efforts are you making to families who are less connected to the school?
How well is your master schedule supporting student needs and teacher collaboration time?
What changes to your master schedule would most improve student outcomes?
How are you ensuring that students receive required minutes for core and intervention blocks?
What is your plan to cover classes when you face a shortage of substitute teachers?
How are you onboarding and supporting new paraprofessionals and support staff?
What staffing gaps do you anticipate next year, and what is your plan to address them?
How are you using your building budget to align with our strategic priorities?
What tradeoffs have you had to make in your building budget this year?
What additional resources would have the greatest impact if funding became available?
How are you tracking and managing the condition of your building and facilities?
What are your top facility needs or concerns in the next three years?
How well are shared spaces like cafeterias, gyms, and libraries being scheduled and used?
How is technology being integrated into instruction in your building?
What issues are you seeing with student devices or infrastructure that we need to address?
How are you ensuring staff are using our learning management systems consistently?
What data dashboards or reports are you finding most useful for decision-making?
How often are you reviewing key metrics with your leadership team, and which ones?
What leading indicators are you watching most closely for early signs of concern?
How are you developing your assistant principals and teacher leaders as future administrators?
What leadership responsibilities have you delegated, and how are you supporting those leaders?
What feedback have you received from staff about your communication and leadership this year?
What is one building-level practice you are most proud of right now?
What is one building-level practice you believe we need to change in the next year?
How are you welcoming and orienting new students who enroll mid-year?
What supports are in place for students transitioning between grade levels within your building?
How are you preparing students and families for transitions to the next school level?
What is your process for planning the start of the school year in your building?
What have you learned this year that will change how you open school next fall?
How are extracurricular and co-curricular programs supporting our academic and SEL goals?
What barriers are students facing in accessing clubs, athletics, or activities at your school?
How are you ensuring that communication about activities is reaching all families?
What systems are in place to monitor homework load and student stress in your building?
How are you addressing concerns about screen time and device use during the school day?
What is your plan for supporting students who are significantly behind in reading?
What is your plan for supporting students who are significantly behind in math?
How are you supporting students who are ready for more challenge or enrichment?
What are you doing to recognize and celebrate student success in your building?
How are student voice and leadership opportunities built into your school culture?
What are the biggest barriers preventing your building from reaching the next level of performance?
If you had to identify your building’s top three priorities for the next 12 months, what would they be?
What do you need from the district office to better support your building’s priorities?
What policies or procedures are getting in the way of effective work in your building?
How are you ensuring that your staff understand and implement new district initiatives?
What is your communication plan for sharing major changes with staff, students, and families?
How are you gathering feedback from staff on district-level decisions that affect them?
What recent success from your building should we be highlighting to the community?
What concerns are you hearing most frequently from families this semester?
How are you ensuring consistency between classrooms in grading practices and expectations?
What is your plan to reduce achievement gaps among student groups in your building?
How are you collaborating with other principals to share effective practices?
What role does your school improvement team play in guiding your building’s work?
How are you monitoring progress on your school improvement plan throughout the year?
What additional support or coaching would be most helpful to you as a principal right now?
Looking ahead three years, what is your vision for this school, and what will it take to get there?
EOF
