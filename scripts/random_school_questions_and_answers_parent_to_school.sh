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
How do I register my child for school in this district?
When is the first day of school this year?
How do I find out which school my child will attend based on our address?
How do I set up a parent-teacher conference with my child's teacher?
How can I check my student's grades online?
What is the process if my child is absent from school?
Who do I talk to if I think my child is being bullied?
How does the school handle reports of bullying on social media?
What time does the school day start and end for elementary students?
What time does the school day start and end for high school students?
How can I get a copy of the school calendar?
How do I enroll my child in the school lunch program?
How do I apply for free or reduced-price meals?
How do I add money to my student's lunch account?
What is the dress code for students at this school?
What are the rules about cell phone use during the school day?
How do I request bus transportation for my child?
Who do I contact about changes to our bus stop or route?
How are weather-related delays and cancellations communicated to families?
What immunizations are required for my child to attend school?
How can my student get extra help in math?
How can my student get extra help in reading?
What is the homework policy for elementary students?
How much homework should a middle school student expect each night?
How can I see what my child is learning in each subject this year?
Where can I find the curriculum or standards for my child's grade?
What should I do if I disagree with a grade my child received?
How can we request a class schedule change for our high school student?
What supports are available if my child is struggling in multiple classes?
How do you support students who are ahead and need more challenge?
What should we do if we move to a new address within the district?
How do I transfer my child from one school in the district to another?
How do I enroll a new student who is moving here from another state?
Who do I contact if I think my child may need special education services?
What is the process for starting an IEP evaluation?
What is the process for requesting a 504 plan?
How does the school support English language learners?
How does the school support students with anxiety or depression?
What mental health resources are available for students?
How can my student meet with the school counselor?
What is the procedure if my child needs to take medication at school?
How are food allergies handled in the classroom and cafeteria?
What are the rules about bringing birthday treats or outside food to school?
What are the eligibility requirements for students to play sports?
How does my student sign up for after-school clubs or activities?
How can my student join band, choir, or other fine arts programs?
What after-school programs are available for elementary students?
What options exist for summer school or credit recovery?
How does attendance affect my student's grades or ability to earn credit?
What happens if my child is tardy or late to class multiple times?
How do I reset my parent portal or student portal password?
What tools are available for parents to track attendance and grades?
How do I update my phone number and email for school notifications?
What should I do if my child loses a textbook or library book?
How can I see what my child has checked out from the school library?
How does the school handle vaping or substance use incidents on campus?
What safety measures are in place for visitors entering the building?
How are fire drills and lockdown drills conducted with students?
How do I report a safety concern or threat that I have heard about?
What should I do if my child says they feel unsafe at school?
How does the district address diversity, equity, and inclusion?
What support is available for students who are new to the district mid-year?
How do you help students transition from elementary to middle school?
How do you help students transition from middle school to high school?
How can my student get help preparing for the ACT or SAT?
What dual-credit or college-credit options are available to high school students?
How can my student get career or college counseling?
What are the graduation requirements for high school students?
How can my student get a copy of their transcript?
What is the policy on social media use for students and staff?
How do you distinguish between normal conflict and bullying in your policies?
How do you handle conflicts or behavior problems on the school bus?
What is the protocol if my child tests positive for a contagious illness?
How does the school communicate with families who speak another language at home?
How do we apply for transportation accommodations for a student with a disability?
What technology devices are issued to students, and in which grades?
What is the policy on students bringing their own laptops or tablets?
How do I report a problem with my student's school-issued device?
What expectations do you have for how often teachers communicate with parents?
How can I volunteer in my child's classroom or at school events?
What opportunities exist for student leadership or student government?
How can my student get involved in community service projects?
How can I share concerns or feedback directly with the principal?
How can I share concerns or feedback directly with the superintendent?
How can I share concerns or feedback directly with the school board?
How can I find the date, time, and location of the next school board meeting?
How can I watch school board meetings if I cannot attend in person?
Where can I find agendas or minutes from past school board meetings?
What is the process for submitting a public comment to the school board?
How are decisions about curriculum changes made at the district level?
How is the district using funds from recent bonds or levies?
What is the process for requesting a different teacher for my child?
How are substitute teachers supported so learning continues smoothly?
What is the policy on restroom and locker room use for students?
How does the school respond if a student is experiencing homelessness?
What can our family do at home to best support learning this year?
What supports are available for students who are behind in reading?
What supports are available for students who are behind in math?
How can we give general feedback on our overall experience with this school?
If I still have questions, what is the best way to contact the school?
EOF
