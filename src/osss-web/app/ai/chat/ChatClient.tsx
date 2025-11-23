"use client";

import React, {
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";

// Reference the image from the public folder
const uploadIcon = "/add.png"; // Path from public directory

const API_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE ?? "/api/osss";

interface UiMessage {
  id: number;
  who: "user" | "bot";
  content: string;
  isHtml?: boolean;
}

interface RetrievedChunk {
  source?: string;           // 👈 add this
  score?: number;
  filename?: string;
  chunk_index?: number;
  text_preview?: string;
  image_paths?: string[] | null;
  page_index?: number | null;
  page_chunk_index?: number | null;
  pdf_index_path?: string | null; // 👈 add this

}


// Strip PII / link-like content from TEXT that goes back into chatHistory
function sanitizeForGuard(src: string): string {
  let t = src;

  // Collapse whitespace
  t = t.replace(/\s+/g, " ").trim();

  // Emails
  t = t.replace(/\S+@\S+\b/g, "[redacted email]");

  // URLs (so they don't end up in chatHistory)
  t = t.replace(/https?:\/\/\S+/gi, "[redacted url]");

  // Markdown-style links [text](url) -> keep just the text
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");

  // Phone-like patterns (rough)
  t = t.replace(/\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g, "[redacted phone]");

  return t;
}

/**
 * Very small Markdown → HTML helper:
 * - code blocks
 * - inline code
 * - links
 * - bold
 * - bullet lists starting with `* ` or `- `
 *   (even if they originally appeared inline, like `: * item1 * item2`)
 */
function mdToHtml(src: string): string {
  // Escape HTML
  let s = src
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // --- Normalize inline bullets into real lines --------------------
  s = s.replace(/([^\n])\s+\*(\s+)/g, "$1\n*$2");

  // Code blocks
  s = s.replace(/```([\s\S]*?)```/g, (_m, code) => {
    return `<pre><code>${code.replace(/&/g, "&amp;")}</code></pre>`;
  });

  // Inline code
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Markdown links
  s = s.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer">$1</a>'
  );

  // Bold
  s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // --- Bullet list handling ----------------------------------------
  const lines = s.split(/\n/);
  let inList = false;
  const out: string[] = [];

  for (const line of lines) {
    const bulletMatch = line.match(/^\s*([*-])\s+(.+)/);

    if (bulletMatch) {
      const itemText = bulletMatch[2];
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${itemText}</li>`);
    } else {
      if (inList) {
        out.push("</ul>");
        inList = false;
      }
      if (line.trim().length > 0) {
        out.push(`${line}<br/>`);
      } else {
        out.push("<br/>");
      }
    }
  }

  if (inList) {
    out.push("</ul>");
  }

  return out.join("");
}

/**
 * Build an HTML "Sources" block appended to the bot reply,
 * with direct links to /rag-pdfs/main/<filename>.
 */
function buildSourcesHtmlFromChunks(chunks: RetrievedChunk[]): string {
  if (!chunks || chunks.length === 0) return "";

  const items: string[] = [];

  for (const c of chunks) {
    // 👇 centralize how we compute the source path
    const sourcePath: string | undefined =
      (c as any).pdf_index_path || // best: mirrored path under vector_indexes/.../pdfs
      (c as any).source ||         // next best: source path from indexer
      c.filename ||                // fallback: bare filename
      undefined;

    if (!sourcePath) continue;

    // Encode each path segment so `/` stays as `/`
    const safeSegments = sourcePath.split("/").map((seg) => encodeURIComponent(seg));
    const href = `/rag-pdfs/main/${safeSegments.join("/")}`;

    // Shown text: just the last part
    const displayName =
      sourcePath.split("/").pop() ||
      c.filename ||
      "Unknown file";

    const metaParts: string[] = [];
    if (typeof c.page_index === "number") {
      metaParts.push(`page ${c.page_index + 1}`);
    }
    if (typeof c.score === "number") {
      metaParts.push(`score ${c.score.toFixed(3)}`);
    }
    const meta =
      metaParts.length > 0 ? ` – ${metaParts.join(" – ")}` : "";

    items.push(
      `<li><a href="${href}" target="_blank" rel="noreferrer">${displayName}</a>${meta}</li>`
    );
  }

  if (!items.length) return "";

  return `
    <div class="rag-sources" style="margin-top:12px;">
      <div style="font-weight:bold;margin-bottom:4px;">Sources</div>
      <ul style="padding-left:16px;margin:0;">
        ${items.join("\n")}
      </ul>
    </div>
  `;
}


/**
 * Map the raw intent label to a more descriptive explanation.
 * This is aligned with server-side intents.
 */
/**
 * Map the raw intent label to a more descriptive explanation.
 * This is aligned with server-side intents.
 */
function describeIntent(intent: string): string {
  switch (intent) {
    case "superintendent":
      return "district leadership / superintendent communications";
    case "superintendent_goals":
      return "superintendent goals and accountability";
    case "principal":
      return "building-level leadership / principal perspective";
    case "teacher":
      return "classroom-level / teacher perspective";
    case "student":
      return "student reflection / student help";
    case "parent":
      return "family or guardian perspective";
    case "angry_student":
      return "frustrated or resistant student perspective";
    case "school_board":
      return "board governance / policy and oversight";
    case "accountability_partner":
      return "goal-setting and follow-through coaching";
    case "staff_directory":
      return "staff directory / people lookup";
    case "student_counts":
      return "student enrollment / counts and numbers";
    case "transfers":
      return "open enrollment and transfer questions";
    case "enrollment":
      return "new student registration / enrollment support";
    case "school_calendar":
      return "school-year calendar, key dates and schedules";
    case "schedule_meeting":
      return "new parent teacher conference";
    case "bullying_concern":
      return "bullying concern";
    case "student_portal":
      return "student portal";
    case "student_dress_code":
      return "student dress code";
    case "school_hours":
      return "school hours";
    case "food_allergy_policy":
      return "food allergy policy";
    case "visitor_safety":
      return "visitor safety";
    case "student_transition_support":
      return "student transition support";
    case "volunteering":
      return "volunteering";
    case "board_feedback":
      return "board feedback";
    case "board_meeting_access":
      return "board meeting access";
    case "board_records":
      return "board records";
    case "grade_appeal":
      return "grade appeal";
    case "dei_initiatives":
      return "DEI initiatives";
    case "multilingual_communication":
      return "multilingual communication";
    case "bond_levy_spending":
      return "bond levy spending";
    case "family_learning_support":
      return "family learning support";
    case "school_feedback":
      return "school feedback";
    case "school_contact":
      return "school contact";
    case "transportation_contact":
      return "transportation contact";
    case "homework_expectations":
      return "homework expectations";
    case "emergency_drills":
      return "emergency drills";
    case "graduation_requirements":
      return "graduation requirements";
    case "operational_risks":
      return "operational risks";
    case "curriculum_governance":
      return "curriculum governance";
    case "program_equity":
      return "program equity";
    case "curriculum_timeline":
      return "curriculum timeline";
    case "essa_accountability":
      return "ESSA accountability";
    case "new_teacher_support":
      return "new teacher support";
    case "professional_learning_priorities":
      return "professional learning priorities";
    case "staff_culture_development":
      return "staff culture development";
    case "student_support_team":
      return "student support team";
    case "resource_prioritization":
      return "resource prioritization";
    case "instructional_technology_integration":
      return "instructional technology integration";
    case "building_practice_improvement":
      return "building practice improvement";
    case "academic_progress_monitoring":
      return "academic progress monitoring";
    case "data_dashboard_usage":
      return "data dashboard usage";
    case "leadership_reflection":
      return "leadership reflection";
    case "communication_strategy":
      return "communication strategy";
    case "family_concerns":
      return "family concerns";
    case "district_leadership":
      return "district leadership";
    case "instructional_practice":
      return "instructional practice";
    case "contact_information":
      return "contact information";
    case "staff_recruit":
        return "staff recruitment";
    case "student_behavior_interventions":
        return "student behavior interventions";
    case "school_fundraising":
        return "school fundraising";
    case "parent_involvement":
        return "parent involvement";
    case "school_infrastructure":
        return "school infrastructure";
    case "special_education":
        return "special education";
    case "student_assessment":
        return "student assessment";
    case "after_school_programs":
        return "after school programs";
    case "diversity_inclusion_policy":
        return "diversity and inclusion policy";
    case "health_services":
        return "health services";
    case "school_security":
        return "school security";
    case "parent_communication":
        return "parent communication";
    case "student_discipline":
        return "student discipline";
    case "college_preparation":
        return "college preparation";
    case "social_emotional_learning":
        return "social emotional learning";
    case "technology_access":
        return "technology access";
    case "school_improvement_plan":
        return "school improvement plan";
    case "student_feedback":
        return "student feedback";
    case "community_partnerships":
        return "community partnerships";
    case "alumni_relations":
        return "alumni relations";
    case "miscarriage_policy":
        return "miscarriage policy";
    case "early_childhood_education":
        return "early childhood education";
    case "student_mentorship":
        return "student mentorship";
    case "cultural_events":
        return "cultural events";
    case "school_lunch_program":
        return "school lunch program";
    case "homeroom_structure":
        return "homeroom structure";
    case "student_enrichment":
        return "student enrichment";
    case "student_inclusion":
        return "student inclusion";
    case "school_illness_policy":
        return "school illness policy";
    case "volunteer_opportunities":
        return "volunteer opportunities";
    case "collaborative_teaching":
        return "collaborative teaching";
    case "student_retention":
        return "student retention";
    case "school_evacuation_plans":
        return "school evacuation plans";
    case "intervention_strategies":
        return "intervention strategies";
    case "school_awards":
        return "school awards";
    case "dropout_prevention":
        return "dropout prevention";
    case "teacher_evaluation":
        return "teacher evaluation";
    case "special_events":
        return "special events";
    case "curriculum_integration":
        return "curriculum integration";
    case "field_trips":
        return "field trips";
    case "student_attendance":
        return "student attendance";
    case "school_spirit":
        return "school spirit";
    case "classroom_management":
        return "classroom management";
    case "student_health_records":
        return "student health records";
    case "parent_involvement_events":
        return "parent involvement events";
    case "teacher_training":
        return "teacher training";
    case "school_uniform_policy":
        return "school uniform policy";
    case "school_cultural_committees":
        return "school cultural committees";
    case "school_business_partnerships":
        return "school business partnerships";
    case "school_community_outreach":
        return "school community outreach";
    case "equal_access_to_opportunities":
        return "equal access to opportunities";
    case "counselor_support":
        return "counselor support";
    case "diversity_equity_policy":
        return "diversity equity policy";
    case "student_recognition_programs":
        return "student recognition programs";
    case "teacher_mentoring":
        return "teacher mentoring";
    case "peer_tutoring":
        return "peer tutoring";
    case "school_closures":
        return "school closures";
    case "district_budget":
        return "district budget";
    case "parent_surveys":
        return "parent surveys";
    case "student_portfolios":
        return "student portfolios";
    case "activity_fee_policy":
        return "activity fee policy";
    case "school_photography":
        return "school photography";
    case "student_policies":
        return "student policies";
    case "student_graduation_plan":
        return "student graduation plan";
    case "math_support_program":
        return "math support program";
    case "reading_support_program":
        return "reading support program";
    case "school_budget_oversight":
        return "school budget oversight";
    case "student_travel_policy":
        return "student travel policy";
    case "extrahelp_tutoring":
        return "extrahelp tutoring";
    case "enrichment_programs":
        return "enrichment programs";
    case "school_compliance":
        return "school compliance";
    case "parent_teacher_association":
        return "parent teacher association";
    case "student_career_services":
        return "student career services";
    case "student_scholarship_opportunities":
        return "student scholarship opportunities";
    case "student_support_services":
        return "student support services";
    case "school_conflict_resolution":
        return "school conflict resolution";
    case "dropout_intervention":
        return "dropout intervention";
    case "student_assignment_tracking":
        return "student assignment tracking";
    case "support_for_special_populations":
        return "support for special populations";
    case "student_voice":
        return "student voice";
    case "grading_policy":
        return "grading policy";
    case "facility_repairs":
        return "facility repairs";
    case "afterschool_clubs":
        return "afterschool clubs";
    case "peer_relationships":
        return "peer relationships";
    case "early_intervention":
        return "early intervention";
    case "school_mascot":
        return "school mascot";
    case "student_leadership":
        return "student leadership";
    case "parental_rights":
        return "parental rights";
    case "alumni_engagement":
        return "alumni engagement";
    case "bullying_training":
        return "bullying training";
    case "school_funding":
        return "school funding";
    case "school_disaster_preparedness":
        return "school disaster preparedness";
    case "student_health_screenings":
        return "student health screenings";
    case "accessibility_in_education":
        return "accessibility in education";
    case "inclusion_policy":
        return "inclusion policy";
    case "school_community_events":
        return "school community events";
    case "internal_communication":
        return "internal communication";
    case "extracurricular_funding":
        return "extracurricular funding";
    case "student_orientation":
        return "student orientation";
    case "school_culture_initiatives":
        return "school culture initiatives";
    case "student_retention_strategies":
        return "student retention strategies";
    case "family_school_partnerships":
        return "family school partnerships";
    case "campus_cleanliness":
        return "campus cleanliness";
    case "professional_development_evaluation":
        return "professional development evaluation";
    case "student_behavior_monitoring":
        return "student behavior monitoring";
    case "diversity_and_inclusion_training":
        return "diversity and inclusion training";
    case "school_broadcasts":
        return "school broadcasts";
    case "food_nutrition_programs":
        return "food nutrition programs";
    case "school_climate_surveys":
        return "school climate surveys";
    case "athletic_funding":
        return "athletic funding";
    case "teacher_feedback_mechanisms":
        return "teacher feedback mechanisms";
    case "gifted_education":
        return "gifted education";
    case "campus_recreation":
        return "campus recreation";
    case "peer_mediation":
        return "peer mediation";
    case "alumni_network":
        return "alumni network";
    case "student_financial_aid":
        return "student financial aid";
    case "parental_involvement_training":
        return "parental involvement training";
    case "school_partnerships":
        return "school partnerships";
    case "school_building_maintenance":
        return "school building maintenance";
    case "school_engagement_measurements":
        return "school engagement measurements";
    case "community_outreach_programs":
        return "community outreach programs";
    case "student_transportation_support":
        return "student transportation support";
    case "recruitment_and_retention_for_support_staff":
        return "recruitment and retention for support staff";
    case "school_leadership_development":
        return "school leadership development";
    case "school_business_partnerships":
        return "school business partnerships";
    case "student_medical_accommodations":
        return "student medical accommodations";
    case "parent_teacher_conferences":
        return "parent teacher conferences";
    case "extra_credit_opportunities":
        return "extra credit opportunities";
    case "teacher_assistant_support":
        return "teacher assistant support";
    case "financial_aid_training":
        return "financial aid training";
    case "student_mobility":
        return "student mobility";
    case "student_promotions":
        return "student promotions";
    case "student_arts_programs":
        return "student arts programs";
    case "alumni_engagement_events":
        return "alumni engagement events";
    case "student_community_service":
        return "student community service";
    case "school_closure_protocols":
        return "school closure protocols";
    case "school_psychological_support":
        return "school psychological support";
    case "parent_support_groups":
        return "parent support groups";
    case "conflict_of_interest_policies":
        return "conflict of interest policies";
    case "interschool_collaboration":
        return "interschool collaboration";
    case "school_event_scheduling":
        return "school event scheduling";
    case "teacher_contract_negotiations":
        return "teacher contract negotiations";
    case "summer_learning_programs":
        return "summer learning programs";
    case "student_mobility_and_transition":
        return "student mobility and transition";
    case "staff_wellness":
        return "staff wellness";
    case "technology_support_for_teachers":
        return "technology support for teachers";
    case "community_feedback_on_school_policy":
        return "community feedback on school policy";
    case "peer_support_networks":
        return "peer support networks";
    case "school_enrollment_forecasting":
        return "school enrollment forecasting";
    case "student_activity_registration":
        return "student activity registration";
    case "school_computer_lab_access":
        return "school computer lab access";
    case "school_website_access":
        return "school website access";
    case "online_courses":
        return "online courses";
    case "student_report_cards":
        return "student report cards";
    case "teacher_facilitator":
        return "teacher facilitator";
    case "student_mental_health_support":
        return "student mental health support";
    case "teacher_collaboration":
        return "teacher collaboration";
    case "school_policies_oversight":
        return "school policies oversight";
    case "school_closure_notifications":
        return "school closure notifications";
    case "parent_school_communication":
        return "parent school communication";
    case "student_tutoring_services":
        return "student tutoring services";
    case "international_student_support":
        return "international student support";
    case "math_intervention_program":
        return "math intervention program";
    case "reading_intervention_program":
        return "reading intervention program";
    case "extra_credit_opportunities":
        return "extra credit opportunities";
    case "student_retention_strategies":
        return "student retention strategies";
    case "staff_training_opportunities":
        return "staff training opportunities";
    case "school_inspection_reports":
        return "school inspection reports";
    case "student_homework_help":
        return "student homework help";
    case "student_field_trip_permission":
        return "student field trip permission";
    case "student_participation_fees":
        return "student participation fees";
    case "school_disaster_recovery":
        return "school disaster recovery";
    case "student_behavior_rewards":
        return "student behavior rewards";
    case "school_bullying_policy":
        return "school bullying policy";
    case "parent_feedback_surveys":
        return "parent feedback surveys";
    case "student_mental_health_evaluation":
        return "student mental health evaluation";
    case "college_readiness_programs":
        return "college readiness programs";
    case "student_extracurricular_registration":
        return "student extracurricular registration";
    case "student_school_id":
        return "student school ID";
    case "school_uniform_policy":
        return "school uniform policy";
    case "transportation_routes":
        return "transportation routes";
    case "student_reporting_system":
        return "student reporting system";
    case "academic_intervention_teams":
        return "academic intervention teams";
    case "school_reading_programs":
        return "school reading programs";
    case "parent_portal_setup":
        return "parent portal setup";
    case "student_behavior_contracts":
        return "student behavior contracts";
    case "student_counseling_services":
        return "student counseling services";
    case "student_financial_aid_opportunities":
        return "student financial aid opportunities";
    case "school_community_partnerships":
        return "school community partnerships";
    case "school_bus_route_planning":
        return "school bus route planning";
    case "campus_security_updates":
        return "campus security updates";
    case "parent_participation_in_school_events":
        return "parent participation in school events";
    case "student_drop_out_prevention":
        return "student drop-out prevention";
    case "school_performance_reports":
        return "school performance reports";
    case "special_education_programs":
        return "special education programs";
    case "school_nurse_services":
        return "school nurse services";
    case "student_career_exploration":
        return "student career exploration";
    case "school_partnership_with_local_businesses":
        return "school partnership with local businesses";
    case "school_school_mascot":
        return "school mascot";
    case "parent_communication_platform":
        return "parent communication platform";
    case "after_school_study_sessions":
        return "after school study sessions";
    case "student_financial_assistance_requests":
        return "student financial assistance requests";
    case "specialized_school_services":
        return "specialized school services";
    case "student_aid_requests":
        return "student aid requests";
    case "school_gardening_programs":
        return "school gardening programs";
    case "school_sports_teams":
        return "school sports teams";
    case "school_property_insurance":
        return "school property insurance";
    case "school_budget_allocations":
        return "school budget allocations";
    case "student_computer_accessibility":
        return "student computer accessibility";
    case "parent_teacher_conferences":
        return "parent teacher conferences";
    case "student_discipline_policy":
        return "student discipline policy";
    case "school_graduation_ceremonies":
        return "school graduation ceremonies";
    case "after_school_extra_credit_opportunities":
        return "after school extra credit opportunities";
    case "student_transportation_services":
        return "student transportation services";
    case "diversity_and_inclusion_training":
        return "diversity and inclusion training";
    case "after_school_homework_club":
        return "after school homework club";
    case "student_feedback_forms":
        return "student feedback forms";
    case "school_compliance_with_regulations":
        return "school compliance with regulations";
    case "student_parking_policy":
        return "student parking policy";
    case "school_security_training":
        return "school security training";
    case "student_assessment_results":
        return "student assessment results";
    case "parental_consent_for_medical_treatment":
        return "parental consent for medical treatment";
    case "after_school_club_meetings":
        return "after school club meetings";
    case "student_graduation_credentials":
        return "student graduation credentials";
    case "school_nutrition_program":
        return "school nutrition program";
    case "school_evacuations_plan":
        return "school evacuations plan";
    case "school_transportation_policies":
        return "school transportation policies";
    case "student_virtual_learning_support":
        return "student virtual learning support";
    case "afterschool_tutoring_programs":
        return "afterschool tutoring programs";
    case "student_admission_fees":
        return "student admission fees";
    case "school_peer_mentoring":
        return "school peer mentoring";
    case "student_workstudy_opportunities":
        return "student work-study opportunities";
    case "parent_feedback_for_school_policies":
        return "parent feedback for school policies";
    case "parent_teacher_association_meetings":
        return "parent teacher association meetings";
    case "student_volunteer_opportunities":
        return "student volunteer opportunities";
    case "school_athletic_events":
        return "school athletic events";
    case "school_talent_shows":
        return "school talent shows";
    case "school_debate_teams":
        return "school debate teams";
    case "school_uniforms":
        return "school uniforms";
    // Adding additional cases here:
    case "general":
    default:
      return "general information / mixed audience";
  }
}


export default function ChatClient() {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const [chatHistory, setChatHistory] = useState<
    { role: "user" | "assistant" | "system"; content: string }[]
  >([]);

  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]); // Store File objects
  const [uploadedFilesNames, setUploadedFilesNames] = useState<string[]>([]); // Store file names

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [retrievedChunks, setRetrievedChunks] = useState<RetrievedChunk[]>([]);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const fileArray = Array.from(files);
      setUploadedFiles((prevFiles) => [...prevFiles, ...fileArray]);
      const fileNames = fileArray.map((file) => file.name);
      setUploadedFilesNames((prevNames) => [...prevNames, ...fileNames]);
    }
  };

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    }
  }, [messages]);

  const appendMessage = useCallback(
    (who: "user" | "bot", content: string, isHtml = false) => {
      setMessages((prev) => {
        const lastId = prev.length ? prev[prev.length - 1].id : 0;
        return [...prev, { id: lastId + 1, who, content, isHtml }];
      });
    },
    []
  );

  const handleReset = () => {
    setMessages([]);
    setChatHistory([]);
    setRetrievedChunks([]);
    setInput("");
    setUploadedFiles([]); // Reset uploaded files
    setUploadedFilesNames([]); // Reset file names
  };

  const handleSend = useCallback(async () => {
    if (sending) return;
    const text = input.trim();
    if (!text && uploadedFiles.length === 0) return; // Ensure that there's something to send

    setSending(true);
    appendMessage("user", text, false);
    setInput("");

    // ---- 1) Update chat history for conversation memory -------------
    const historySnapshot = [
      ...chatHistory,
      { role: "user" as const, content: text },
    ];

    const hasSystem = historySnapshot.some((m) => m.role === "system");
    const baseSys = hasSystem
      ? []
      : [
          {
            role: "system" as const,
            content:
              "You are a helpful assistant for Dallas Center-Grimes Community School District (DCG) in Iowa. " +
              "When the user mentions 'DCG' or 'Dallas Center Grimes', they mean the school district, NOT the Dallas Cowboys. " +
              "Prefer information drawn from the provided DCG documents. " +
              "Respond in clear Markdown with at least 2 sentences. " +
              "Avoid including personal emails, phone numbers, or long URLs in your answer; refer to documents by title and page.",
          },
        ];

    const messagesForHistory = [...baseSys, ...historySnapshot];
    setChatHistory(messagesForHistory);

    // ---- 2) Build messages payload for RAG using FULL conversation ---
    const messagesForRag = messagesForHistory;

    try {
      const url = `${API_BASE}/ai/chat/rag`;
      const body = {
        model: "llama3.2-vision",
        messages: messagesForRag,
        temperature: 0.2,
        stream: false,
        index: "main",
        max_tokens: 8000,

      };


      // 2) Create FormData and put raw JSON string under "payload"
      const form = new FormData();
      form.append("payload", JSON.stringify(body));

      // If you support upload:
      // if (uploadedFiles && uploadedFiles.length > 0) {
      //   Array.from(uploadedFiles).forEach((file) => {
      //     form.append("files", file);          // 👈 must match `files: list[UploadFile]`
      //   });
      // }

      const resp = await fetch(url, {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
        body: form,
      });

      const raw = await resp.text();
      console.log("RAG raw response:", resp.status, raw);


      let payload: any = null;
      try {
        payload = JSON.parse(raw);
      } catch {
        appendMessage(
          "bot",
          raw || "(Non-JSON response from /ai/chat/rag)",
          false
        );
        setSending(false);
        return;
      }

      // ---- 3) retrieved_chunks -> store for UI ONLY ------------------
      const maybeChunks = payload?.retrieved_chunks;
      let chunksForThisReply: RetrievedChunk[] = [];

      if (Array.isArray(maybeChunks)) {
        chunksForThisReply = maybeChunks;
        setRetrievedChunks(chunksForThisReply);
      } else {
        setRetrievedChunks([]);
      }

      console.log("SAFE raw payload:", payload);
      console.log("retrieved_chunks (if any):", payload?.retrieved_chunks);

      const core = payload?.answer ?? payload;

      if (!resp.ok) {
        const msg =
          core?.detail?.reason ||
          core?.detail ||
          raw ||
          `HTTP ${resp.status}`;
        appendMessage("bot", String(msg), false);
        setSending(false);
        return;
      }

      // ---- 4) Text reply --------------------------------------------
      let reply: string =
        core?.message?.content ??
        core?.choices?.[0]?.message?.content ??
        core?.choices?.[0]?.text ??
        (typeof core === "string" ? core : raw);

      if (!reply?.trim()) {
        reply = "(Empty reply from /ai/chat/rag)";
      }

      // Keep two versions:
      // - replyForDisplay: full markdown with newlines
      // - replyForHistory: sanitized for future prompts
      let replyForDisplay = reply;
      const replyForHistory = sanitizeForGuard(reply);


      // ---- 5) Attach classifier intent from server response ----------
      // We assume rag_router returns these fields; fall back gracefully.
      const classifierIntent: string =
        payload?.intent ??
        payload?.intent_label ??
        payload?.meta?.intent ??
        "general";

      const intentConfidence: number | null =
        typeof payload?.intent_confidence === "number"
          ? payload.intent_confidence
          : typeof payload?.confidence === "number"
          ? payload.confidence
          : typeof payload?.meta?.intent_confidence === "number"
          ? payload.meta.intent_confidence
          : null;

      const intentDescription = describeIntent(classifierIntent);

      // 3A: Get INTENT returned directly from the server
      const returnedIntent: string | null =
        typeof payload?.intent === "string" ? payload.intent : null;

      // Work on the display version (preserve newlines)
      replyForDisplay = (replyForDisplay ?? "").trimEnd();

      // Append router intent *only* (no classifier detail line)
      if (returnedIntent) {
        replyForDisplay += `\n\n---\n**Intent:** ${returnedIntent}`;
      }



      // Convert to HTML (with bullet list support)
      const outHtml = mdToHtml(String(replyForDisplay));

      // Append "Sources" block with PDF links
      const sourcesHtml = buildSourcesHtmlFromChunks(chunksForThisReply);
      const finalHtml = outHtml + sourcesHtml;

      appendMessage("bot", finalHtml, true);

      // Store sanitized reply (without extra markdown cruft) in history
      setChatHistory((prev) => [
        ...prev,
        { role: "assistant", content: String(replyForHistory) },
      ]);

    } catch (err: any) {
      appendMessage("bot", `Network error: ${String(err)}`, false);
    }

    setSending(false);
  }, [appendMessage, chatHistory, input, sending]);

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (
    e
  ) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <div className="mentor-container" style={{ display: "flex", flexDirection: "column", height: "100vh", maxHeight: "100vh" }}>
      {/* Header with New Chat Button */}
      <div className="mentor-header" style={{ display: "flex", justifyContent: "space-between" }}>
        <div>General Chat — Use responsibly</div>
        <button
          type="button"
          className="mentor-quick-button"
          onClick={handleReset}
          style={{
            backgroundColor: "#4CAF50",
            color: "white",
            border: "none",
            padding: "10px",
            cursor: "pointer",
            fontSize: "16px",
          }}
        >
          New Chat
        </button>
      </div>

      {/* Uploaded files display */}
      <div className="uploaded-files">
        {uploadedFilesNames.length > 0 && (
          <div>
            <strong>Uploaded Files:</strong>
            <ul>
              {uploadedFilesNames.map((file, index) => (
                <li key={index}>{file}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="mentor-messages" style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
        {messages.length === 0 && <div className="mentor-empty-hint">Say hello to begin.</div>}
        {messages.map((m) => (
          <div key={m.id} className={`mentor-msg ${m.who === "user" ? "user" : "bot"}`}>
            <div className={`mentor-bubble ${m.who === "user" ? "user" : "bot"}`}>
              {m.isHtml ? <div dangerouslySetInnerHTML={{ __html: m.content }} /> : m.content}
            </div>
          </div>
        ))}
      </div>

      {/* Composer */}
      <div className="mentor-composer">
        <div className="textarea-container" style={{ position: "relative", width: "100%" }}>
          {/* Invisible file input */}
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            onChange={handleFileUpload}
            multiple // Allow multiple file uploads
          />
          {/* Button to trigger file selection */}
          <button
            type="button"
            className="file-upload-btn"
            style={{
              position: "absolute",
              left: "10px",
              top: "50%",
              transform: "translateY(-50%)",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              marginRight: "10px", // Add space between the button and the textarea
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <img
              src={uploadIcon}
              alt="Upload"
              style={{
                width: "20px",   // Adjust size of the image if necessary
                height: "20px",
              }}
            />
          </button>

          <textarea
            className="mentor-input"
            placeholder="Type your message… (Ctrl/Cmd+Enter to send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            style={{
              paddingLeft: "50px",   // Create space for the button
              width: "100%",         // Make the textarea span the entire width
              boxSizing: "border-box", // Ensure padding doesn't affect the width
            }}
          />
        </div>

        <button
          type="button"
          className="mentor-send primary"
          onClick={handleSend}
          disabled={sending}
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </div>

      <div className="mentor-footer">Local model proxy — for experimentation and allowed use only.</div>
    </div>
  );
}