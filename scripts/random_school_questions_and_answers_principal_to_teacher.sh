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
How are you using formative assessments to check for understanding during lessons?
Can you walk me through how you plan your lessons for this unit?
How do you decide when to reteach a concept versus move on?
What strategies are you using to differentiate for students at different readiness levels?
How are you supporting students who are reading significantly below grade level?
How are you challenging students who quickly master the material?
How do you make learning goals clear to students at the start of a lesson?
What routines do you have in place to start class smoothly and on time?
How are you reinforcing classroom expectations throughout the day?
What strategies are you finding most effective for redirecting off-task behavior?
How do you ensure that all students have a chance to participate in discussions?
How are you incorporating student voice and choice into your lessons?
How are you communicating learning progress to students on a regular basis?
What tools or systems are you using to track student mastery of standards?
How are you using our curriculum resources alongside your own materials?
What adjustments have you made to the curriculum to better fit your students?
How do you decide which homework tasks are most valuable for learning?
How do you support students who consistently do not complete homework?
How are you aligning your grading practices with our standards-based approach?
How are you providing students with opportunities to revise or reassess work?
What does small-group instruction look like in your classroom?
How do you use data from assessments to form small groups?
How often do you meet with each small group during a typical week?
How are you supporting English learners during whole-group instruction?
What visual or language supports are you using to scaffold complex tasks?
How are you implementing accommodations and modifications from IEPs and 504 plans?
How do you collaborate with special education staff who work with your students?
How are you integrating social-emotional learning into your daily routines?
What strategies are you using to build relationships with students who are hard to reach?
How do you respond when you notice a student seems withdrawn or upset?
How are you reinforcing our school-wide behavior expectations in your classroom?
What is your process for contacting families when academic or behavior concerns arise?
How do you communicate positive news and celebrations to families?
What tools are you using to keep families informed about assignments and deadlines?
How are you supporting students who have frequent absences or tardies?
What patterns are you noticing in your attendance data this quarter?
How are you using technology to enhance, rather than replace, good instruction?
What tech tools are you finding most useful for student engagement right now?
How are you ensuring that all students are using devices appropriately during class?
How do you support students who struggle with managing digital distractions?
How are you preparing students for upcoming state or district assessments?
What test-taking or self-regulation strategies are you teaching students?
How do you help students reflect on their performance after major assessments?
What structures do you have for students to set and review academic goals?
How are you collaborating with your grade-level or content team on planning?
What have you contributed recently to your PLC that has helped the team?
What is one successful instructional strategy you could share with colleagues?
How are you incorporating feedback from your last observation into your practice?
What professional learning goal are you currently working on this semester?
What support or resources would help you reach that professional goal?
What do you see as one of your greatest strengths as a teacher right now?
What is one area of your practice you most want to improve this year?
How are you integrating writing into your content area on a regular basis?
How do you check that students are actually thinking during independent work time?
What strategies are you using to support productive group work among students?
How are you ensuring that group roles are clear and equitable?
How do you close a lesson so that students consolidate the day’s learning?
What evidence do you look for to know that a lesson was successful?
How are you supporting students with executive functioning challenges?
What systems do you have to help students stay organized with materials and deadlines?
How do you handle late work in a way that maintains both high expectations and support?
What norms have you established around respectful discussion and disagreement?
How are you incorporating multiple perspectives and diverse voices in your content?
What adjustments have you made based on student feedback this year?
How are you using exit tickets or quick checks to inform your next lesson?
What do you typically do when a large portion of the class misses the same question?
How are you ensuring that students know what high-quality work looks like?
What examples or rubrics do you share with students before major tasks?
How are you supporting students who are new to our school or district?
What routines help new students quickly feel included in your class?
How are you collaborating with our counselor or social worker about student needs?
What patterns are you noticing in student behavior that concern you right now?
How are you helping students build persistence when work feels challenging?
What do you do when students say, “I can’t do this” or “This is too hard”?
How are you reinforcing a growth mindset through your feedback and language?
What strategies are you using to minimize lost instructional time during transitions?
How are you planning for students who finish tasks much earlier than others?
What does student engagement look and sound like to you in your classroom?
When engagement is low, what steps do you take to adjust in the moment?
How are you using choice boards, menus, or projects to personalize learning?
What opportunities do students have to reflect on their own learning habits?
How do you gather informal feedback from students about your teaching or the course?
What routines do you have in place for students to get make-up work after absences?
How are you preparing students for the next grade level or course in your subject?
What communication do you have with teachers in the grade above or below you?
How are you supporting students during longer-term projects or research tasks?
What checkpoints do you build into multi-day assignments to keep students on track?
How do you manage classroom materials and space to support active learning?
What adjustments have you made to your seating arrangement this year and why?
How are you incorporating movement or brain breaks into longer class periods?
What procedures do you have for students to get help without disrupting the class?
How do you ensure that your questions during instruction target higher-order thinking?
What opportunities do students have to create, present, or teach others in your class?
How are you integrating cross-curricular connections into your lessons?
What strategies are you using to support students who are learning English at home but another language at school?
How are you documenting parent contacts and follow-up actions?
What aspects of our school-wide initiatives have been most helpful in your classroom?
What aspects of our school-wide initiatives feel unclear or hard to implement?
If you could change one thing about our schedule or routines to help instruction, what would it be?
How can I best support you in meeting the needs of your students this quarter?
EOF
