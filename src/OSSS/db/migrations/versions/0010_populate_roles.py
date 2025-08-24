from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date, datetime



# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB TypeDecorator; TSVectorType for PG tsvector
except Exception:
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):
            pass
    except Exception:
        class TSVectorType(sa.Text):
            pass

# --- Alembic identifiers ---
revision = "0010_populate_roles"
down_revision = "0009_populate_attendance_codes"
branch_labels = None
depends_on = None

# ---- Timestamp helpers ----
def _timestamps():
    return (
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def upgrade() -> None:
    conn = op.get_bind()

    roles = [
        # --- Governance & Executive ---
        {"name": "School Board Member/Trustee",
         "description": "Elected/appointed governance of the district or school; sets policy and oversees superintendent/head."},
        {"name": "Board Chair", "description": "Leads the governing board; sets agendas and presides over meetings."},
        {"name": "Board Vice Chair", "description": "Supports/acts in place of the chair as needed."},
        {"name": "Board Clerk", "description": "Records board actions; manages official records and notices."},
        {"name": "Superintendent",
         "description": "Chief executive of a public school district; accountable to the board."},
        {"name": "Head of School", "description": "Chief executive of an independent/private school."},
        {"name": "Deputy Superintendent", "description": "Second-in-command over district operations or academics."},
        {"name": "Associate Superintendent",
         "description": "Senior executive over major divisions (e.g., teaching & learning)."},
        {"name": "Assistant Superintendent",
         "description": "Executive leader over specific functions or clusters of schools."},
        {"name": "Chief of Staff",
         "description": "Coordinates executive priorities, cabinet operations, and cross-functional initiatives."},
        {"name": "Chief Academic Officer",
         "description": "Leads curriculum, instruction, assessment, and school improvement."},
        {"name": "Chief Schools Officer",
         "description": "Oversees school portfolio and principals; drives performance."},
        {"name": "Chief Operations Officer",
         "description": "Oversees non-instructional operations (facilities, transport, nutrition, safety)."},
        {"name": "Chief Financial Officer",
         "description": "Leads finance, budgeting, accounting, and fiscal reporting."},
        {"name": "Chief Information Officer",
         "description": "Leads technology strategy, systems, data, and cybersecurity."},
        {"name": "Chief Technology Officer",
         "description": "Oversees IT infrastructure, networks, endpoints, and platforms."},
        {"name": "Chief Human Resources Officer",
         "description": "Leads talent strategy, employee relations, payroll/benefits, and compliance."},
        {"name": "Chief Communications Officer",
         "description": "Directs communications, media relations, branding, and engagement."},
        {"name": "Chief Equity Officer", "description": "Leads equity, diversity, inclusion initiatives and policy."},
        {"name": "General Counsel", "description": "Provides legal guidance; manages risk, contracts, and compliance."},
        {"name": "Ombudsperson",
         "description": "Independent, confidential resource for resolving concerns and complaints."},

        # --- School Leadership ---
        {"name": "Principal",
         "description": "School-site leader responsible for instruction, operations, and culture."},
        {"name": "Assistant Principal",
         "description": "Supports principal in instruction, discipline, operations, and staff supervision."},
        {"name": "Associate Principal", "description": "Senior AP; often leads major school functions."},
        {"name": "Vice Principal", "description": "Alternative title for assistant/associate principal."},
        {"name": "Head of Upper School", "description": "Leads upper/secondary division in independent schools."},
        {"name": "Head of Middle School", "description": "Leads middle division."},
        {"name": "Head of Lower School", "description": "Leads lower/elementary division."},
        {"name": "Dean of Students", "description": "Leads student conduct, attendance, culture, and MTSS supports."},
        {"name": "Dean of Academics", "description": "Oversees curriculum, scheduling, grading, and academic quality."},
        {"name": "Grade-Level Dean", "description": "Oversees a grade’s academic and behavioral support systems."},
        {"name": "Director of Residential Life",
         "description": "Oversees dorms/residential programs (boarding schools)."},
        {"name": "Activities Director", "description": "Leads student activities, clubs, and co-curriculars."},
        {"name": "Athletics Director",
         "description": "Leads athletics programs, compliance, facilities, and scheduling."},
        {"name": "Assistant Athletics Director",
         "description": "Supports athletic director with operations and compliance."},

        # --- Teaching & Instructional Support ---
        {"name": "Classroom Teacher",
         "description": "Core instruction in content areas at elementary, middle, or high school."},
        {"name": "Elementary Teacher", "description": "Self-contained or team-taught elementary grades."},
        {"name": "Middle School Teacher", "description": "Departmentalized instruction for middle grades."},
        {"name": "High School Teacher", "description": "Subject-specific instruction at high school level."},
        {"name": "Art Teacher", "description": "Visual arts instruction and programming."},
        {"name": "Music Teacher", "description": "General music or performance ensembles."},
        {"name": "Band Director", "description": "Leads band program and performances."},
        {"name": "Choir Director", "description": "Leads choral program and performances."},
        {"name": "Theater Teacher", "description": "Drama instruction and productions."},
        {"name": "Physical Education Teacher", "description": "PE instruction; fitness, health, and wellness."},
        {"name": "Health Teacher", "description": "Health education curriculum."},
        {"name": "World Languages Teacher", "description": "Foreign/heritage language instruction."},
        {"name": "Computer Science Teacher", "description": "CS/coding/programming instruction."},
        {"name": "CTE Teacher", "description": "Career & Technical Education (pathways, labs, certifications)."},
        {"name": "Early Childhood Teacher", "description": "Pre-K and early learning instruction."},
        {"name": "Reading Interventionist", "description": "Targeted literacy interventions and progress monitoring."},
        {"name": "Math Interventionist", "description": "Targeted math interventions and progress monitoring."},
        {"name": "Instructional Coach", "description": "Job-embedded coaching on pedagogy and curriculum."},
        {"name": "Literacy Coach", "description": "Specialized coaching in reading and writing instruction."},
        {"name": "Math Coach", "description": "Specialized coaching in mathematics instruction."},
        {"name": "Mentor Teacher", "description": "Supports novice teachers with induction and practice."},
        {"name": "Media Specialist", "description": "Library/media program; information literacy; collections."},
        {"name": "Teacher-Librarian", "description": "Certified librarian providing instruction and curation."},
        {"name": "Gifted & Talented Teacher", "description": "GT/advanced learners instruction and enrichment."},
        {"name": "Gifted & Talented Coordinator",
         "description": "Oversees GT identification, services, and compliance."},
        {"name": "English Learner Teacher", "description": "EL/ESL/ML services and instruction."},
        {"name": "English Learner Coordinator", "description": "Oversees EL program, identification, and compliance."},
        {"name": "Title I Teacher", "description": "Interventions funded under Title I."},
        {"name": "Title I Coordinator", "description": "Oversees Title I compliance and services."},
        {"name": "Alternative Program Teacher", "description": "Instruction in alternative education settings."},
        {"name": "Virtual Program Teacher", "description": "Instruction in online/virtual programs."},
        {"name": "Substitute Teacher", "description": "Short-term classroom coverage."},
        {"name": "Long-Term Substitute", "description": "Extended coverage; curriculum and grading responsibilities."},
        {"name": "Teacher Resident", "description": "Residency preparation role co-teaching with a mentor."},
        {"name": "Student Teacher", "description": "Clinical practice under supervision."},
        {"name": "Instructional Fellow", "description": "Early-career instructional support role."},

        # --- Special Education & Related Services ---
        {"name": "Director of Special Education",
         "description": "Leads SPED/Exceptional Student Services and compliance (IDEA)."},
        {"name": "Special Education Teacher",
         "description": "Instruction and services for students with disabilities."},
        {"name": "SPED Case Manager", "description": "Coordinates IEPs, services, and progress reporting."},
        {"name": "School Psychologist", "description": "Evaluation, counseling, MTSS, and IEP support."},
        {"name": "Speech-Language Pathologist", "description": "Speech/language therapy and evaluations."},
        {"name": "Occupational Therapist", "description": "Fine-motor/sensory/ADL supports."},
        {"name": "Certified Occupational Therapy Assistant", "description": "Supports OT service delivery."},
        {"name": "Physical Therapist", "description": "Gross-motor/mobility therapy and evaluations."},
        {"name": "Physical Therapist Assistant", "description": "Supports PT services."},
        {"name": "Board Certified Behavior Analyst", "description": "Behavior analysis, plans, and consultation."},
        {"name": "Behavior Interventionist", "description": "Implements behavior plans and supports."},
        {"name": "Vision Specialist", "description": "Services for students with visual impairments."},
        {"name": "Orientation and Mobility Specialist",
         "description": "Travel/orientation training for visually impaired students."},
        {"name": "Deaf/Hard of Hearing Teacher", "description": "Instruction and support for D/HH students."},
        {"name": "504 Coordinator", "description": "Leads Section 504 identification and accommodation plans."},
        {"name": "SPED Compliance Coordinator", "description": "Monitors timelines, documentation, and audits."},
        {"name": "Paraprofessional", "description": "Classroom and individual student support."},
        {"name": "Instructional Aide", "description": "Assists with instruction and supervision."},
        {"name": "Teacher’s Aide", "description": "General classroom support role."},
        {"name": "Sign Language Interpreter", "description": "ASL/interpretation services for students and families."},
        {"name": "Transition Specialist", "description": "HS transition planning to postsecondary/workforce."},
        {"name": "Vocational Specialist", "description": "Career exploration and work-based learning supports."},

        # --- Student Services & Well-Being ---
        {"name": "School Counselor", "description": "Academic, social-emotional, and college/career counseling."},
        {"name": "Guidance Counselor", "description": "Legacy title for school counselor."},
        {"name": "School Social Worker", "description": "Family services, wraparound supports, attendance."},
        {"name": "Family Liaison", "description": "Connects families with resources and the school."},
        {"name": "School Nurse", "description": "Health services, care plans, medication, records."},
        {"name": "Health Aide", "description": "Supports nurse; first aid and documentation."},
        {"name": "Attendance Officer", "description": "Monitors attendance and interventions."},
        {"name": "Truancy Officer", "description": "Enforces compulsory attendance with due process."},
        {"name": "McKinney-Vento Liaison", "description": "Supports students experiencing homelessness."},
        {"name": "Foster Care Liaison", "description": "Coordinates supports for students in foster care."},
        {"name": "Behavior Support Coach", "description": "Coaches staff on behavior systems and PBIS."},
        {"name": "Restorative Practices Coordinator", "description": "Implements restorative approaches and circles."},
        {"name": "MTSS Coordinator", "description": "Coordinates MTSS tiers across academics/behavior."},
        {"name": "RTI Coordinator", "description": "Manages Response to Intervention processes."},
        {"name": "Director of Student Support Services",
         "description": "Oversees counseling, nursing, social work, and supports."},
        {"name": "Registrar", "description": "Manages student records, transcripts, and enrollments."},
        {"name": "Records Clerk", "description": "Supports records management and requests."},
        {"name": "Testing & Assessment Coordinator", "description": "Manages state/local tests and accommodations."},
        {"name": "College Counselor", "description": "Postsecondary advising (independent/HS)."},
        {"name": "Financial Aid Advisor", "description": "Supports tuition/aid processes (independent)."},

        # --- Curriculum, Instruction, Assessment & Accountability ---
        {"name": "Director of Curriculum and Instruction",
         "description": "Leads curriculum adoption, PD, and pedagogy."},
        {"name": "Director of Assessment, Research & Evaluation",
         "description": "Oversees testing, analytics, and program evaluation."},
        {"name": "Director of Accountability", "description": "Manages accountability metrics and reporting."},
        {"name": "Director of Data & Analytics", "description": "Leads analytics, dashboards, and data governance."},
        {"name": "Instructional Materials Coordinator", "description": "Textbooks/materials adoption and inventory."},
        {"name": "Textbook Coordinator", "description": "Procurement and distribution of textbooks."},
        {"name": "Professional Development Coordinator", "description": "Plans and manages staff learning programs."},
        {"name": "Teacher Induction Coordinator", "description": "New teacher support and certification pathways."},
        {"name": "Accreditation Coordinator", "description": "Manages accreditation cycles and evidence."},

        # --- Operations (HR/Finance/Procurement/Risk) ---
        {"name": "Human Resources Director", "description": "Leads HR strategy and operations."},
        {"name": "HR Manager", "description": "Manages HR processes and teams."},
        {"name": "HR Generalist", "description": "Broad HR support across functions."},
        {"name": "Recruiter", "description": "Leads talent sourcing and hiring pipelines."},
        {"name": "Payroll Manager", "description": "Oversees payroll operations and compliance."},
        {"name": "Payroll Specialist", "description": "Executes payroll processing and reporting."},
        {"name": "Benefits Manager", "description": "Administers benefits programs."},
        {"name": "Benefits Specialist", "description": "Benefits enrollment and support."},
        {"name": "Business Manager", "description": "School/district business office lead."},
        {"name": "Controller", "description": "Accounting controls, closing, and reporting."},
        {"name": "Accountant", "description": "General accounting and reconciliation."},
        {"name": "Accounts Payable Specialist", "description": "Processes vendor invoices and payments."},
        {"name": "Accounts Receivable Specialist", "description": "Manages receivables and collections."},
        {"name": "Purchasing Director", "description": "Leads procurement strategy and compliance."},
        {"name": "Buyer", "description": "Executes purchasing transactions and bids."},
        {"name": "Risk Manager", "description": "Enterprise risk and insurance programs."},
        {"name": "Insurance Coordinator", "description": "Manages insurance claims and coverage."},
        {"name": "Grants Manager", "description": "Oversees grants lifecycle and compliance."},
        {"name": "Grant Writer", "description": "Develops grant proposals and narratives."},
        {"name": "Federal Programs Director", "description": "Leads federal funds (Title I/II/III/IV) compliance."},
        {"name": "E-rate Coordinator", "description": "Manages E-rate applications and compliance."},
        {"name": "Compliance Officer", "description": "Oversees policy/regulatory compliance."},
        {"name": "Records/Retention Manager", "description": "Records schedules, storage, and disposition."},

        # --- Information Technology & Data ---
        {"name": "Director of Technology", "description": "Leads district technology vision and delivery."},
        {"name": "IT Director", "description": "Alternative title for Director of Technology."},
        {"name": "Network Administrator", "description": "LAN/WAN, wireless, and network services."},
        {"name": "Systems Administrator", "description": "Servers, identity, and core services."},
        {"name": "Cloud Administrator", "description": "Cloud platforms and identity management."},
        {"name": "Server Administrator", "description": "Physical/virtual servers and storage."},
        {"name": "Information Security Officer", "description": "Security policy, controls, and incident response."},
        {"name": "Database Administrator", "description": "DB performance, backups, and integrity."},
        {"name": "SIS Administrator", "description": "Student information system configuration and support."},
        {"name": "Data Engineer", "description": "Pipelines, integrations, and warehousing."},
        {"name": "Data Analyst", "description": "Dashboards, KPI tracking, and insights."},
        {"name": "ETL Developer", "description": "Extract/transform/load processes and tooling."},
        {"name": "Help Desk Manager", "description": "Leads support team and ticketing."},
        {"name": "Help Desk Technician", "description": "Frontline technical support to staff/students."},
        {"name": "Field Technician", "description": "On-site hardware and AV support."},
        {"name": "Instructional Technology Coach", "description": "Integrates technology with pedagogy."},
        {"name": "Instructional Technology Integrator", "description": "Supports teachers using digital tools."},
        {"name": "Web Administrator", "description": "Manages websites/portals and CMS."},
        {"name": "Webmaster", "description": "Alternative title for web administration."},
        {"name": "AV/Media Technician", "description": "Audio/visual systems and event support."},

        # --- Facilities, Maintenance & Custodial ---
        {"name": "Director of Facilities",
         "description": "Leads facilities strategy, maintenance, and capital projects."},
        {"name": "Facilities Manager", "description": "Oversees site maintenance and work orders."},
        {"name": "Plant Manager", "description": "Leads plant operations at large sites."},
        {"name": "Maintenance Technician", "description": "General maintenance and repairs."},
        {"name": "Electrician", "description": "Electrical systems and repairs."},
        {"name": "Plumber", "description": "Plumbing systems maintenance."},
        {"name": "HVAC Technician", "description": "Heating, ventilation, and air conditioning."},
        {"name": "Carpenter", "description": "Carpentry and finish work."},
        {"name": "Painter", "description": "Interior/exterior painting and finishes."},
        {"name": "Locksmith", "description": "Keying and access control hardware."},
        {"name": "Groundskeeper", "description": "Landscape and grounds maintenance."},
        {"name": "Irrigation Technician", "description": "Irrigation systems setup and repair."},
        {"name": "Custodial Supervisor", "description": "Leads custodial staff and schedules."},
        {"name": "Custodian", "description": "Cleaning, setup, and basic maintenance."},
        {"name": "Porter", "description": "Daytime cleaning and event turnover."},
        {"name": "Night Lead", "description": "Oversees night custodial shifts."},
        {"name": "Warehouse/Receiving", "description": "Shipping/receiving and storeroom management."},
        {"name": "Inventory Specialist", "description": "Tracks assets, consumables, and supplies."},
        {"name": "Energy Manager", "description": "Utility monitoring and conservation initiatives."},
        {"name": "Sustainability Manager", "description": "Sustainability programs and reporting."},

        # --- Transportation ---
        {"name": "Director of Transportation", "description": "Leads routing, fleet, and driver operations."},
        {"name": "Routing/Scheduling Coordinator", "description": "Creates routes, stops, and schedules."},
        {"name": "Dispatcher", "description": "Coordinates buses and communications."},
        {"name": "Bus Driver", "description": "Student transportation on regular and trip routes."},
        {"name": "Activity Driver", "description": "Drives for activities/athletics trips."},
        {"name": "Bus Aide/Monitor", "description": "Student supervision and safety on buses."},
        {"name": "Fleet Manager", "description": "Oversees maintenance shop and fleet lifecycle."},
        {"name": "Mechanic", "description": "Vehicle diagnostics and repair."},
        {"name": "Diesel Technician", "description": "Specialized diesel engine service."},
        {"name": "Shop Foreman", "description": "Leads mechanics and shop operations."},
        {"name": "Crossing Guard", "description": "Pedestrian safety near schools."},

        # --- Nutrition Services ---
        {"name": "Director of Nutrition Services", "description": "Leads USDA-compliant meal programs and kitchens."},
        {"name": "Food Service Director", "description": "Alternative title leading nutrition services."},
        {"name": "Cafeteria Manager", "description": "Site-level cafeteria operations and staffing."},
        {"name": "Kitchen Manager", "description": "Back-of-house operations and food safety."},
        {"name": "Cook", "description": "Food preparation and service."},
        {"name": "Prep Cook", "description": "Ingredients prep and batch cooking."},
        {"name": "Baker", "description": "Baked goods preparation."},
        {"name": "Cashier/Point-of-Sale Operator", "description": "Point-of-sale transactions and compliance."},
        {"name": "Dietitian", "description": "Menu planning and nutrition compliance."},
        {"name": "Nutritionist", "description": "Nutrition guidance and education."},

        # --- Safety, Security & Emergency Management ---
        {"name": "Director of Safety & Security",
         "description": "Leads security strategy, staffing, and incident response."},
        {"name": "Emergency Management Director", "description": "Plans drills, response, and recovery operations."},
        {"name": "School Resource Officer", "description": "Law enforcement officer assigned to schools."},
        {"name": "Campus Police Officer", "description": "District police/security officer."},
        {"name": "Security Guard", "description": "Access control and campus patrols."},
        {"name": "Campus Supervisor", "description": "Student supervision (lunch/recess/common areas)."},
        {"name": "Emergency Preparedness Coordinator", "description": "Coordinates safety plans and training."},

        # --- Front Office & School Support ---
        {"name": "School Secretary", "description": "Front office operations and parent/student support."},
        {"name": "Administrative Assistant", "description": "Administrative support to leaders/departments."},
        {"name": "Office Manager", "description": "Oversees office staff and procedures."},
        {"name": "Receptionist", "description": "Greets visitors, answers phones, and routes inquiries."},
        {"name": "Attendance Clerk", "description": "Attendance entry and parent communication."},
        {"name": "Student Services Clerk", "description": "Supports counseling, registration, and records."},
        {"name": "Data Clerk", "description": "Data entry, audits, and SIS support."},
        {"name": "SIS Clerk", "description": "Specialist data entry and reports in SIS."},
        {"name": "Health Office Clerk", "description": "Supports school nurse and health records."},

        # --- Athletics, Activities & Enrichment ---
        {"name": "Head Coach", "description": "Leads a sport program and coaching staff."},
        {"name": "Assistant Coach", "description": "Supports head coach with training and supervision."},
        {"name": "Athletic Trainer", "description": "Sports medicine, injury prevention, and rehab."},
        {"name": "Strength & Conditioning Coach", "description": "Athlete strength and conditioning programs."},
        {"name": "Club Sponsor", "description": "Staff sponsor for student clubs."},
        {"name": "Activity Sponsor", "description": "Leads co-curricular activities (e.g., yearbook)."},
        {"name": "Robotics Coach", "description": "Coaches robotics team and competitions."},
        {"name": "Debate Coach", "description": "Leads debate team and tournaments."},
        {"name": "Esports Coach", "description": "Coaches competitive gaming program."},
        {"name": "Yearbook Advisor", "description": "Advises yearbook production."},
        {"name": "Student Government Advisor", "description": "Advises student council/governance."},
        {"name": "Performing Arts Director", "description": "Oversees music, theater, and performances."},
        {"name": "Theater Director", "description": "Directs theatrical productions."},

        # --- Communications, Community & Advancement ---
        {"name": "Communications Director", "description": "Leads comms strategy and media relations."},
        {"name": "Public Relations Director", "description": "Manages public relations and press."},
        {"name": "Media Relations Manager", "description": "Press releases, interviews, and messaging."},
        {"name": "Family Engagement Coordinator", "description": "Strengthens family partnerships and outreach."},
        {"name": "Community Engagement Coordinator", "description": "Builds community partnerships and events."},
        {"name": "Translation Services Coordinator", "description": "Coordinates translation/interpretation services."},
        {"name": "Interpreter Services Coordinator", "description": "Manages interpreter scheduling and quality."},
        {"name": "Alumni Relations Director", "description": "Cultivates alumni networks (independent schools)."},
        {"name": "Advancement/Development Director", "description": "Leads fundraising and donor relations."},
        {"name": "Annual Giving Manager", "description": "Runs annual giving campaigns."},
        {"name": "Capital Campaign Manager", "description": "Leads capital fundraising initiatives."},
        {"name": "Major Gifts Officer", "description": "Manages high-capacity donor portfolios."},
        {"name": "Admissions Director", "description": "Leads admissions/enrollment (independent)."},
        {"name": "Enrollment Director", "description": "Oversees enrollment management and strategy."},
        {"name": "Financial Aid Director", "description": "Administers tuition assistance (independent)."},
        {"name": "Marketing Director", "description": "Leads marketing strategy and branding."},
        {"name": "Marketing Manager", "description": "Executes marketing campaigns and content."},
        {"name": "Graphic Designer", "description": "Designs print/digital collateral."},
        {"name": "Social Media Manager", "description": "Manages social platforms and engagement."},

        # --- Early Childhood & Extended Programs ---
        {"name": "Director of Early Childhood", "description": "Leads preschool/early learning programs."},
        {"name": "Preschool Teacher", "description": "Early childhood classroom instruction."},
        {"name": "Preschool Assistant", "description": "Assists preschool teachers and students."},
        {"name": "Before-School Program Director", "description": "Leads before-school care programs."},
        {"name": "After-School Program Director", "description": "Leads after-school care/enrichment."},
        {"name": "Extended Day Coordinator", "description": "Coordinates extended-day activities and staffing."},
        {"name": "Summer School Coordinator", "description": "Plans and manages summer learning."},
        {"name": "Enrichment Coordinator", "description": "Coordinates clubs, electives, and enrichment."},

        # --- Faith-Based/Religious (where applicable) ---
        {"name": "Chaplain", "description": "Provides spiritual care and services."},
        {"name": "Campus Minister", "description": "Leads campus ministry programs."},
        {"name": "Religion Teacher", "description": "Teaches religion curriculum."},
        {"name": "Theology Teacher", "description": "Teaches theology/biblical studies."},
        {"name": "Service Learning Coordinator", "description": "Coordinates service learning/community service."},

        # --- Miscellaneous / Program-Specific ---
        {"name": "Alternative Education Director", "description": "Leads alt-ed schools/programs."},
        {"name": "Virtual/Online Program Director", "description": "Leads online learning programs."},
        {"name": "CTE Director", "description": "Oversees career/technical education pathways."},
        {"name": "Pathways Coordinator", "description": "Coordinates career/college pathways and work-based learning."},
        {"name": "Apprenticeship Coordinator", "description": "Manages apprenticeships and employer partnerships."},
        {"name": "International Student Program Director",
         "description": "Leads international student recruitment/support."},
        {"name": "Homestay Coordinator", "description": "Coordinates host families and compliance."},
        {"name": "Testing Site Manager", "description": "Manages SAT/ACT/AP/IB test administrations."},
        {"name": "IB Coordinator", "description": "Coordinates International Baccalaureate programs."},
        {"name": "AP Coordinator", "description": "Coordinates Advanced Placement programs."},
        {"name": "Librarian", "description": "Library program lead; instruction and curation."},
        {"name": "Archivist", "description": "Maintains historical records and archives."},
        {"name": "Print Shop Manager", "description": "Oversees printing services and production."},
        {"name": "Mailroom Clerk", "description": "Handles mail distribution and shipping."},
        {"name": "Volunteer Coordinator", "description": "Recruits and manages school volunteers."},
    ]

    stmt = sa.text("""
        INSERT INTO roles (name, description)
        VALUES (:name, :description)
        ON CONFLICT (name) DO NOTHING
    """)
    conn.execute(stmt, roles)


def downgrade() -> None:
    conn = op.get_bind()

    names = [
        # Keep this list exactly in sync with upgrade()
        "School Board Member/Trustee", "Board Chair", "Board Vice Chair", "Board Clerk",
        "Superintendent", "Head of School", "Deputy Superintendent", "Associate Superintendent",
        "Assistant Superintendent", "Chief of Staff", "Chief Academic Officer", "Chief Schools Officer",
        "Chief Operations Officer", "Chief Financial Officer", "Chief Information Officer", "Chief Technology Officer",
        "Chief Human Resources Officer", "Chief Communications Officer", "Chief Equity Officer", "General Counsel",
        "Ombudsperson", "Principal", "Assistant Principal", "Associate Principal", "Vice Principal",
        "Head of Upper School",
        "Head of Middle School", "Head of Lower School", "Dean of Students", "Dean of Academics", "Grade-Level Dean",
        "Director of Residential Life", "Activities Director", "Athletics Director", "Assistant Athletics Director",
        "Classroom Teacher", "Elementary Teacher", "Middle School Teacher", "High School Teacher",
        "Art Teacher", "Music Teacher", "Band Director", "Choir Director", "Theater Teacher",
        "Physical Education Teacher", "Health Teacher", "World Languages Teacher", "Computer Science Teacher",
        "CTE Teacher",
        "Early Childhood Teacher", "Reading Interventionist", "Math Interventionist", "Instructional Coach",
        "Literacy Coach",
        "Math Coach", "Mentor Teacher", "Media Specialist", "Teacher-Librarian", "Gifted & Talented Teacher",
        "Gifted & Talented Coordinator", "English Learner Teacher", "English Learner Coordinator", "Title I Teacher",
        "Title I Coordinator", "Alternative Program Teacher", "Virtual Program Teacher", "Substitute Teacher",
        "Long-Term Substitute", "Teacher Resident", "Student Teacher", "Instructional Fellow",
        "Director of Special Education", "Special Education Teacher", "SPED Case Manager", "School Psychologist",
        "Speech-Language Pathologist", "Occupational Therapist", "Certified Occupational Therapy Assistant",
        "Physical Therapist", "Physical Therapist Assistant", "Board Certified Behavior Analyst",
        "Behavior Interventionist",
        "Vision Specialist", "Orientation and Mobility Specialist", "Deaf/Hard of Hearing Teacher", "504 Coordinator",
        "SPED Compliance Coordinator", "Paraprofessional", "Instructional Aide", "Teacher’s Aide",
        "Sign Language Interpreter",
        "Transition Specialist", "Vocational Specialist", "School Counselor", "Guidance Counselor",
        "School Social Worker",
        "Family Liaison", "School Nurse", "Health Aide", "Attendance Officer", "Truancy Officer",
        "McKinney-Vento Liaison",
        "Foster Care Liaison", "Behavior Support Coach", "Restorative Practices Coordinator", "MTSS Coordinator",
        "RTI Coordinator",
        "Director of Student Support Services", "Registrar", "Records Clerk", "Testing & Assessment Coordinator",
        "College Counselor", "Financial Aid Advisor", "Director of Curriculum and Instruction",
        "Director of Assessment, Research & Evaluation", "Director of Accountability", "Director of Data & Analytics",
        "Instructional Materials Coordinator", "Textbook Coordinator", "Professional Development Coordinator",
        "Teacher Induction Coordinator", "Accreditation Coordinator", "Human Resources Director", "HR Manager",
        "HR Generalist",
        "Recruiter", "Payroll Manager", "Payroll Specialist", "Benefits Manager", "Benefits Specialist",
        "Business Manager",
        "Controller", "Accountant", "Accounts Payable Specialist", "Accounts Receivable Specialist",
        "Purchasing Director",
        "Buyer", "Risk Manager", "Insurance Coordinator", "Grants Manager", "Grant Writer", "Federal Programs Director",
        "E-rate Coordinator", "Compliance Officer", "Records/Retention Manager", "Director of Technology",
        "IT Director",
        "Network Administrator", "Systems Administrator", "Cloud Administrator", "Server Administrator",
        "Information Security Officer", "Database Administrator", "SIS Administrator", "Data Engineer", "Data Analyst",
        "ETL Developer", "Help Desk Manager", "Help Desk Technician", "Field Technician",
        "Instructional Technology Coach", "Instructional Technology Integrator", "Web Administrator", "Webmaster",
        "AV/Media Technician",
        "Director of Facilities", "Facilities Manager", "Plant Manager", "Maintenance Technician", "Electrician",
        "Plumber",
        "HVAC Technician", "Carpenter", "Painter", "Locksmith", "Groundskeeper", "Irrigation Technician",
        "Custodial Supervisor",
        "Custodian", "Porter", "Night Lead", "Warehouse/Receiving", "Inventory Specialist", "Energy Manager",
        "Sustainability Manager",
        "Director of Transportation", "Routing/Scheduling Coordinator", "Dispatcher", "Bus Driver", "Activity Driver",
        "Bus Aide/Monitor", "Fleet Manager", "Mechanic", "Diesel Technician", "Shop Foreman", "Crossing Guard",
        "Director of Nutrition Services", "Food Service Director", "Cafeteria Manager", "Kitchen Manager", "Cook",
        "Prep Cook",
        "Baker", "Cashier/Point-of-Sale Operator", "Dietitian", "Nutritionist", "Director of Safety & Security",
        "Emergency Management Director", "School Resource Officer", "Campus Police Officer", "Security Guard",
        "Campus Supervisor",
        "Emergency Preparedness Coordinator", "School Secretary", "Administrative Assistant", "Office Manager",
        "Receptionist",
        "Attendance Clerk", "Student Services Clerk", "Data Clerk", "SIS Clerk", "Health Office Clerk", "Head Coach",
        "Assistant Coach", "Athletic Trainer", "Strength & Conditioning Coach", "Club Sponsor", "Activity Sponsor",
        "Robotics Coach", "Debate Coach", "Esports Coach", "Yearbook Advisor", "Student Government Advisor",
        "Performing Arts Director", "Theater Director", "Communications Director", "Public Relations Director",
        "Media Relations Manager", "Family Engagement Coordinator", "Community Engagement Coordinator",
        "Translation Services Coordinator", "Interpreter Services Coordinator", "Alumni Relations Director",
        "Advancement/Development Director", "Annual Giving Manager", "Capital Campaign Manager", "Major Gifts Officer",
        "Admissions Director", "Enrollment Director", "Financial Aid Director", "Marketing Director",
        "Marketing Manager",
        "Graphic Designer", "Social Media Manager", "Director of Early Childhood", "Preschool Teacher",
        "Preschool Assistant",
        "Before-School Program Director", "After-School Program Director", "Extended Day Coordinator",
        "Summer School Coordinator",
        "Enrichment Coordinator", "Chaplain", "Campus Minister", "Religion Teacher", "Theology Teacher",
        "Service Learning Coordinator",
        "Alternative Education Director", "Virtual/Online Program Director", "CTE Director", "Pathways Coordinator",
        "Apprenticeship Coordinator", "International Student Program Director", "Homestay Coordinator",
        "Testing Site Manager",
        "IB Coordinator", "AP Coordinator", "Librarian", "Archivist", "Print Shop Manager", "Mailroom Clerk",
        "Volunteer Coordinator"
    ]

    # Delete only the rows we added
    for n in names:
        conn.execute(sa.text("DELETE FROM roles WHERE name = :name"), {"name": n})