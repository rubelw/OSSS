# OSSS Database Schema Reference

TABLE: academic_terms
DESCRIPTION: Stores academic terms records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- type : text 
- start_date : date (NOT NULL) 
- end_date : date (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: accommodations
DESCRIPTION: Stores accommodations records for the application. References related entities via: iep plan. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- iep_plan_id : CHAR(36) 
- applies_to : text 
- description : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: activities
DESCRIPTION: Stores activities records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : varchar(128) (NOT NULL) 
- description : text 
- is_active : boolean (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: addresses
DESCRIPTION: Stores addresses records for the application. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- line1 : text (NOT NULL) 
- line2 : text 
- city : text (NOT NULL) 
- state : text 
- postal_code : text 
- country : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: agenda_item_approvals
DESCRIPTION: Stores agenda item approvals records for the application. References related entities via: approver, item, step. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- item_id : CHAR(36) (NOT NULL) 
- step_id : CHAR(36) (NOT NULL) 
- approver_id : CHAR(36) 
- decision : varchar(16) 
- decided_at : timestamp 
- comment : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: agenda_item_files
DESCRIPTION: Stores agenda item files records for the application. References related entities via: agenda item, file. 4 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- agenda_item_id : CHAR(36) (NOT NULL) 
- file_id : CHAR(36) (NOT NULL) 
- caption : varchar(255) 

TABLE: agenda_items
DESCRIPTION: Stores agenda items records for the application. Key attributes include title. References related entities via: linked objective, linked policy, meeting, parent. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 4 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (NOT NULL) 
- parent_id : CHAR(36) 
- position : int (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- description : text 
- linked_policy_id : CHAR(36) 
- linked_objective_id : CHAR(36) 
- time_allocated : int 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: agenda_workflow_steps
DESCRIPTION: Stores agenda workflow steps records for the application. References related entities via: approver, workflow. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- workflow_id : CHAR(36) (NOT NULL) 
- step_no : int (NOT NULL) 
- approver_type : varchar(20) (NOT NULL) 
- approver_id : CHAR(36) 
- rule : varchar(255) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: agenda_workflows
DESCRIPTION: Stores agenda workflows records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- active : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: alignments
DESCRIPTION: Stores alignments records for the application. References related entities via: curriculum version, requirement. Includes standard audit timestamps (created_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- curriculum_version_id : CHAR(36) (NOT NULL) 
- requirement_id : CHAR(36) (NOT NULL) 
- alignment_level : varchar(32) (NOT NULL) 
- evidence_url : varchar(512) 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: announcements
DESCRIPTION: No description provided.
KEY COLUMNS:
- user_id : CHAR(36) (NOT NULL) 
- course_id : CHAR(36) (NOT NULL) 
- text : text 
- state : varchar(9) (NOT NULL) 
- scheduled_time : timestamp 
- creation_time : timestamp 
- update_time : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: ap_vendors
DESCRIPTION: Stores ap vendors records for the application. Key attributes include name. References related entities via: tax. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- vendor_no : varchar(64) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- tax_id : varchar(64) 
- remit_to : JSON 
- contact : JSON 
- attributes : JSON 
- active : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: approvals
DESCRIPTION: Stores approvals records for the application. References related entities via: association, proposal. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- association_id : CHAR(36) (NOT NULL) 
- approved_at : timestamp (NOT NULL) 
- expires_at : timestamp 
- status : varchar(7) (NOT NULL) 
- proposal_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: asset_parts
DESCRIPTION: Stores asset parts records for the application. References related entities via: asset, part. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- asset_id : CHAR(36) (NOT NULL) 
- part_id : CHAR(36) (NOT NULL) 
- qty : numeric(12,2) (NOT NULL) 

TABLE: assets
DESCRIPTION: Stores assets records for the application. Key attributes include serial_no. References related entities via: building, parent asset, space. Includes standard audit timestamps (created_at, updated_at). 16 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- building_id : CHAR(36) 
- space_id : CHAR(36) 
- parent_asset_id : CHAR(36) 
- tag : varchar(128) (NOT NULL, UNIQUE) 
- serial_no : varchar(128) 
- manufacturer : varchar(255) 
- model : varchar(255) 
- category : varchar(64) 
- status : varchar(32) 
- install_date : date 
- warranty_expires_at : date 
- expected_life_months : int 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: assignment_categories
DESCRIPTION: Stores assignment categories records for the application. Key attributes include name. References related entities via: section. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- section_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- weight : numeric(5,2) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: assignments
DESCRIPTION: Stores assignments records for the application. Key attributes include name. References related entities via: category, section. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- section_id : CHAR(36) (NOT NULL) 
- category_id : CHAR(36) 
- name : text (NOT NULL) 
- due_date : date 
- points_possible : numeric(8,2) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: attendance
DESCRIPTION: Stores attendance records for the application. References related entities via: meeting, user. 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- meeting_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) (NOT NULL) 
- status : varchar(16) 
- arrived_at : timestamp 
- left_at : timestamp 

TABLE: attendance_codes
DESCRIPTION: Stores attendance codes records for the application. Key attributes include code. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined.
KEY COLUMNS:
- code : text (PK, NOT NULL) 
- description : text 
- is_present : text (NOT NULL) 
- is_excused : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: attendance_daily_summary
DESCRIPTION: Stores attendance daily summary records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- date : date (NOT NULL) 
- present_minutes : int (NOT NULL) 
- absent_minutes : int (NOT NULL) 
- tardy_minutes : int (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: attendance_events
DESCRIPTION: Stores attendance events records for the application. Key attributes include code. References related entities via: section meeting, student. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- section_meeting_id : CHAR(36) 
- date : date (NOT NULL) 
- code : text (NOT NULL) 
- minutes : int 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: audit_logs
DESCRIPTION: Stores audit logs records for the application. References related entities via: actor, entity. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- actor_id : CHAR(36) 
- action : text (NOT NULL) 
- entity_type : text (NOT NULL) 
- entity_id : CHAR(36) (NOT NULL) 
- metadata : JSON 
- occurred_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: behavior_codes
DESCRIPTION: Stores behavior codes records for the application. Key attributes include code. Includes standard audit timestamps (created_at, updated_at). 4 column(s) defined.
KEY COLUMNS:
- code : text (PK, NOT NULL) 
- description : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: behavior_interventions
DESCRIPTION: Stores behavior interventions records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- intervention : text (NOT NULL) 
- start_date : date (NOT NULL) 
- end_date : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: bell_schedules
DESCRIPTION: Stores bell schedules records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: buildings
DESCRIPTION: Stores buildings records for the application. Key attributes include name, code. References related entities via: facility. Includes standard audit timestamps (created_at, updated_at). 12 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- facility_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- code : varchar(64) (UNIQUE) 
- year_built : int 
- floors_count : int 
- gross_sqft : numeric(12,2) 
- use_type : varchar(64) 
- address : json 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: bus_routes
DESCRIPTION: Stores bus routes records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- name : text (NOT NULL) 
- school_id : CHAR(36) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: bus_stop_times
DESCRIPTION: Stores bus stop times records for the application. References related entities via: route, stop. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- route_id : CHAR(36) (NOT NULL) 
- stop_id : CHAR(36) (NOT NULL) 
- arrival_time : TIME (NOT NULL) 
- departure_time : TIME 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: bus_stops
DESCRIPTION: Stores bus stops records for the application. Key attributes include name. References related entities via: route. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- route_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- latitude : numeric(10,7) 
- longitude : numeric(10,7) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: calendar_days
DESCRIPTION: Stores calendar days records for the application. References related entities via: calendar. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- calendar_id : CHAR(36) (NOT NULL) 
- date : date (NOT NULL) 
- day_type : text (NOT NULL) 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: calendars
DESCRIPTION: Stores calendars records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: camp_registrations
DESCRIPTION: Stores camp registrations records for the application. Key attributes include participant_name. References related entities via: camp, school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- participant_name : varchar(255) (NOT NULL) 
- camp_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: camps
DESCRIPTION: Stores camps records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: channels
DESCRIPTION: Stores channels records for the application. Key attributes include name. References related entities via: org. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- org_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- audience : varchar(16) (NOT NULL) 
- description : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: class_ranks
DESCRIPTION: Stores class ranks records for the application. References related entities via: school, student, term. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- term_id : CHAR(36) (NOT NULL) 
- student_id : CHAR(36) (NOT NULL) 
- rank : int (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: comm_search_index
DESCRIPTION: Stores comm search index records for the application. References related entities via: entity. 4 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- entity_type : varchar(32) (NOT NULL) 
- entity_id : CHAR(36) (NOT NULL) 
- ts : TEXT 

TABLE: committees
DESCRIPTION: Stores cic committees records for the application. Key attributes include name. References related entities via: organization, school. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- organization_id : CHAR(36) 
- school_id : CHAR(36) 
- name : text (NOT NULL) 
- description : text 
- status : text (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: compliance_records
DESCRIPTION: Stores compliance records records for the application. References related entities via: asset, building. Includes standard audit timestamps (created_at, updated_at). 12 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- building_id : CHAR(36) 
- asset_id : CHAR(36) 
- record_type : varchar(64) (NOT NULL) 
- authority : varchar(255) 
- identifier : varchar(128) 
- issued_at : date 
- expires_at : date 
- documents : json 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: concession_items
DESCRIPTION: No description provided.
KEY COLUMNS:
- name : varchar(255) 
- price_cents : int (NOT NULL) 
- inventory_quantity : int (NOT NULL) 
- stand_id : CHAR(36) (NOT NULL) 
- active : boolean (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: concession_sale_items
DESCRIPTION: No description provided.
KEY COLUMNS:
- sale_id : CHAR(36) (NOT NULL) 
- item_id : CHAR(36) (NOT NULL) 
- quantity : int (NOT NULL) 
- line_total_cents : int (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: concession_sales
DESCRIPTION: No description provided.
KEY COLUMNS:
- stand_id : CHAR(36) (NOT NULL) 
- event_id : CHAR(36) 
- buyer_name : text 
- buyer_email : text 
- buyer_phone : text 
- buyer_address_line1 : text 
- buyer_address_line2 : text 
- buyer_city : text 
- buyer_state : text 
- buyer_postal_code : text 
- school_id : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: concession_stands
DESCRIPTION: No description provided.
KEY COLUMNS:
- name : text (NOT NULL, UNIQUE) 
- location : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: consents
DESCRIPTION: Stores consents records for the application. References related entities via: person. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
Synonyms: consent, parent consent, permissions, approval
KEY COLUMNS:
- person_id : CHAR(36) (NOT NULL) 
- consent_type : text (NOT NULL) 
- granted : boolean (NOT NULL) 
- effective_date : date (NOT NULL) 
- expires_on : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: consequence_types
DESCRIPTION: Stores consequence types records for the application. Key attributes include code. Includes standard audit timestamps (created_at, updated_at). 4 column(s) defined.
KEY COLUMNS:
- code : text (PK, NOT NULL) 
- description : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: consequences
DESCRIPTION: Stores consequences records for the application. References related entities via: incident, participant. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- incident_id : CHAR(36) (NOT NULL) 
- participant_id : CHAR(36) (NOT NULL) 
- consequence_code : text (NOT NULL) 
- start_date : date 
- end_date : date 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: consolidated_out
DESCRIPTION: Aggregated, student-facing result after consolidating multiple tutor outputs. References related entities via: sessions, tutor_turns. Includes standard audit timestamps (created_at). 6 column(s) defined. Primary key is `id`. No foreign key fields detected (links stored via references).
KEY COLUMNS:
- consolidated_answer : text (NOT NULL) 
- confidence : numeric (NOT NULL) 
- scores : JSON (NOT NULL) 
- selected_tutors : JSON (NOT NULL) 
- rationale : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: contacts
DESCRIPTION: Stores contacts records for the application. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- type : text (NOT NULL) 
- value : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: course_prerequisites
DESCRIPTION: Stores course prerequisites records for the application. References related entities via: course, prereq course. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- course_id : CHAR(36) (NOT NULL) 
- prereq_course_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: course_sections
DESCRIPTION: Stores course sections records for the application. References related entities via: course, school, term. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- course_id : CHAR(36) (NOT NULL) 
- term_id : CHAR(36) (NOT NULL) 
- section_number : text (NOT NULL) 
- capacity : int 
- school_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: course_students
DESCRIPTION: No description provided.
KEY COLUMNS:
- course_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: course_teachers
DESCRIPTION: No description provided.
KEY COLUMNS:
- course_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: courses
DESCRIPTION: Stores course records and Google Classroom fields. Key attributes include name, code/section. References related entities via: school, subject, user. Includes standard audit timestamps (created_at, updated_at). 19 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- subject_id : CHAR(36) 
- name : text (NOT NULL) 
- code : text 
- credit_hours : numeric(4,2) 
- user_id : CHAR(36) (NOT NULL) 
- section : varchar(255) 
- description : text 
- room : varchar(64) 
- owner_id : varchar(64) 
- course_state : varchar(11) (NOT NULL) 
- enrollment_code : varchar(64) 
- alternate_link : varchar(512) 
- calendar_id : varchar(255) 
- creation_time : timestamp 
- update_time : timestamp 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: coursework
DESCRIPTION: No description provided.
KEY COLUMNS:
- user_id : CHAR(36) (NOT NULL) 
- course_id : CHAR(36) (NOT NULL) 
- topic_id : CHAR(36) 
- title : varchar(255) (NOT NULL) 
- description : text 
- work_type : varchar(24) (NOT NULL) 
- state : varchar(9) (NOT NULL) 
- due_date : date 
- due_time : TIME 
- max_points : numeric 
- creation_time : timestamp 
- update_time : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: curricula
DESCRIPTION: Stores curricula records for the application. Key attributes include title, name. References related entities via: organization, proposal. Includes standard audit timestamps (created_at, published_at). 13 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- organization_id : CHAR(36) (NOT NULL) 
- proposal_id : CHAR(36) 
- title : varchar(255) (NOT NULL) 
- subject : varchar(128) 
- grade_range : varchar(64) 
- description : text 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- status : varchar(7) (NOT NULL) 
- published_at : timestamp 
- metadata : json 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: curriculum_units
DESCRIPTION: Stores curriculum units records for the application. Key attributes include title. References related entities via: curriculum. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- curriculum_id : CHAR(36) (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- order_index : int (NOT NULL) 
- summary : text 
- metadata : json 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: curriculum_versions
DESCRIPTION: Stores curriculum versions records for the application. References related entities via: curriculum. Includes standard audit timestamps (created_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- curriculum_id : CHAR(36) (NOT NULL) 
- version : varchar(64) (NOT NULL) 
- status : varchar(32) (NOT NULL) 
- submitted_at : timestamp 
- decided_at : timestamp 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: data_quality_issues
DESCRIPTION: Stores data quality issues records for the application. References related entities via: entity. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- entity_type : text (NOT NULL) 
- entity_id : CHAR(36) (NOT NULL) 
- rule : text (NOT NULL) 
- severity : text (NOT NULL) 
- details : text 
- detected_at : timestamp (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: data_sharing_agreements
DESCRIPTION: Stores data sharing agreements records for the application. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- vendor : text (NOT NULL) 
- scope : text 
- start_date : date 
- end_date : date 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: deduction_codes
DESCRIPTION: Stores deduction codes records for the application. Key attributes include code, name. References related entities via: vendor. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- code : varchar(32) (NOT NULL, UNIQUE) 
- name : varchar(128) (NOT NULL) 
- pretax : boolean (NOT NULL) 
- vendor_id : CHAR(36) 
- attributes : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: deliveries
DESCRIPTION: Stores deliveries records for the application. References related entities via: post, user. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- post_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) (NOT NULL) 
- delivered_at : timestamp 
- medium : varchar(16) 
- status : varchar(16) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: department_position_index
DESCRIPTION: Stores department position index records for the application. References related entities via: department, position. Includes standard audit timestamps (created_at). 4 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- department_id : CHAR(36) (NOT NULL) 
- position_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 

TABLE: departments
DESCRIPTION: Stores departments records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: document_activity
DESCRIPTION: Stores document activity records for the application. References related entities via: actor, document. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- document_id : CHAR(36) (NOT NULL) 
- actor_id : CHAR(36) 
- action : varchar(32) (NOT NULL) 
- at : timestamp (NOT NULL) 
- meta : JSON 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: document_links
DESCRIPTION: Stores document links records for the application. References related entities via: document, entity. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- document_id : CHAR(36) (NOT NULL) 
- entity_type : varchar(50) (NOT NULL) 
- entity_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: document_notifications
DESCRIPTION: Stores document notifications records for the application. References related entities via: document, user. 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- document_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) (NOT NULL) 
- subscribed : boolean (NOT NULL) 
- last_sent_at : timestamp 

TABLE: document_permissions
DESCRIPTION: Stores document permissions records for the application. References related entities via: principal, resource. 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- resource_type : varchar(20) (NOT NULL) 
- resource_id : CHAR(36) (NOT NULL) 
- principal_type : varchar(20) (NOT NULL) 
- principal_id : CHAR(36) (NOT NULL) 
- permission : varchar(20) (NOT NULL) 

TABLE: document_search_index
DESCRIPTION: Stores document search index records for the application. References related entities via: document. 2 column(s) defined. 1 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- document_id : CHAR(36) (PK, NOT NULL) 
- ts : TEXT 

TABLE: document_versions
DESCRIPTION: Stores document versions records for the application. References related entities via: document, file. Includes standard audit timestamps (created_at, published_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- document_id : CHAR(36) (NOT NULL) 
- version_no : int (NOT NULL) 
- file_id : CHAR(36) (NOT NULL) 
- checksum : varchar(128) 
- created_by : CHAR(36) 
- created_at : timestamp (NOT NULL) 
- published_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: documents
DESCRIPTION: Stores documents records for the application. Key attributes include title. References related entities via: current version, folder. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- folder_id : CHAR(36) 
- title : varchar(255) (NOT NULL) 
- current_version_id : CHAR(36) 
- is_public : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: donations
DESCRIPTION: Stores donations records for the application. Key attributes include donor_name and amount. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- donor_name : varchar(255) (NOT NULL) 
- amount_cents : int (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- campaign_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: earning_codes
DESCRIPTION: Stores earning codes records for the application. Key attributes include code, name. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- code : varchar(32) (NOT NULL, UNIQUE) 
- name : varchar(128) (NOT NULL) 
- taxable : boolean (NOT NULL) 
- attributes : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: education_associations
DESCRIPTION: Stores education associations records for the application. Key attributes include name. Includes standard audit timestamps (created_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : varchar(255) (NOT NULL, UNIQUE) 
- contact : json 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: ell_plans
DESCRIPTION: Stores ell plans records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- level : text 
- effective_start : date (NOT NULL) 
- effective_end : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: embeds
DESCRIPTION: Stores embeds records for the application. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- provider : varchar(64) (NOT NULL) 
- url : varchar(1024) (NOT NULL) 
- meta : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: emergency_contacts
DESCRIPTION: Stores emergency contacts records for the application. References related entities via: person. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- person_id : CHAR(36) (NOT NULL) 
- contact_name : text (NOT NULL) 
- relationship : text 
- phone : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: employee_deductions
DESCRIPTION: Stores employee deductions records for the application. References related entities via: deduction code, employee, run. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- run_id : CHAR(36) (NOT NULL) 
- employee_id : CHAR(36) (NOT NULL) 
- deduction_code_id : CHAR(36) (NOT NULL) 
- amount : numeric(12,2) (NOT NULL) 
- attributes : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: employee_earnings
DESCRIPTION: Stores employee earnings records for the application. References related entities via: earning code, employee, run. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- run_id : CHAR(36) (NOT NULL) 
- employee_id : CHAR(36) (NOT NULL) 
- earning_code_id : CHAR(36) (NOT NULL) 
- hours : numeric(10,2) 
- rate : numeric(12,4) 
- amount : numeric(12,2) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: entity_tags
DESCRIPTION: Stores entity tags records for the application. References related entities via: entity, tag. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : uuid (PK, NOT NULL) 
- entity_type : varchar(64) (NOT NULL) 
- entity_id : uuid (NOT NULL) 
- tag_id : uuid (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_assignments
DESCRIPTION: Stores evaluation assignments records for the application. References related entities via: cycle, evaluator user, subject user, template. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 4 foreign key field(s) detected.
KEY COLUMNS:
- cycle_id : CHAR(36) (NOT NULL) 
- subject_user_id : CHAR(36) (NOT NULL) 
- evaluator_user_id : CHAR(36) (NOT NULL) 
- template_id : CHAR(36) (NOT NULL) 
- status : varchar(32) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_cycles
DESCRIPTION: Stores evaluation cycles records for the application. Key attributes include name. References related entities via: org. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- org_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- start_at : timestamp 
- end_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_files
DESCRIPTION: Stores evaluation files records for the application. References related entities via: assignment, file. 3 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- assignment_id : CHAR(36) (NOT NULL) 
- file_id : CHAR(36) (NOT NULL) 

TABLE: evaluation_questions
DESCRIPTION: Stores evaluation questions records for the application. References related entities via: section. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- section_id : CHAR(36) (NOT NULL) 
- text : text (NOT NULL) 
- type : varchar(16) (NOT NULL) 
- scale_min : int 
- scale_max : int 
- weight : numeric 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_reports
DESCRIPTION: Stores evaluation reports records for the application. References related entities via: cycle, file. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- cycle_id : CHAR(36) (NOT NULL) 
- scope : JSON 
- generated_at : timestamp (NOT NULL) 
- file_id : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_responses
DESCRIPTION: Stores evaluation responses records for the application. References related entities via: assignment, question. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- assignment_id : CHAR(36) (NOT NULL) 
- question_id : CHAR(36) (NOT NULL) 
- value_num : numeric 
- value_text : text 
- comment : text 
- answered_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_sections
DESCRIPTION: Stores evaluation sections records for the application. Key attributes include title. References related entities via: template. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- template_id : CHAR(36) (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- order_no : int (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_signoffs
DESCRIPTION: Stores evaluation signoffs records for the application. References related entities via: assignment, signer. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- note : text 
- assignment_id : CHAR(36) (NOT NULL) 
- signer_id : CHAR(36) (NOT NULL) 
- signed_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: evaluation_templates
DESCRIPTION: Stores evaluation templates records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- for_role : varchar(80) 
- version : int (NOT NULL) 
- is_active : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: events
DESCRIPTION: Stores events records for the application. Key attributes include title. References related entities via: activity, school. Includes standard audit timestamps (created_at, updated_at). 12 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- activity_id : CHAR(36) 
- title : varchar(255) (NOT NULL) 
- summary : text 
- starts_at : timestamp (NOT NULL) 
- ends_at : timestamp 
- venue : varchar(255) 
- status : varchar(16) (NOT NULL) 
- attributes : JSON 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: export_runs
DESCRIPTION: Stores export runs records for the application. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- export_name : text (NOT NULL) 
- ran_at : timestamp (NOT NULL) 
- status : text (NOT NULL) 
- file_uri : text 
- error : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: external_ids
DESCRIPTION: Stores external ids records for the application. References related entities via: entity, external. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- entity_type : text (NOT NULL) 
- entity_id : CHAR(36) (NOT NULL) 
- system : text (NOT NULL) 
- external_id : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: facilities
DESCRIPTION: Stores facilities records for the application. Key attributes include name, code. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- code : varchar(64) (UNIQUE) 
- address : json 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: family_portal_access
DESCRIPTION: Stores family portal access records for the application. References related entities via: guardian, student. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- guardian_id : CHAR(36) (NOT NULL) 
- student_id : CHAR(36) (NOT NULL) 
- permissions : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: fan_app_settings
DESCRIPTION: Stores fan app settings records for the application. Key attributes include key and value. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- key : varchar(255) (NOT NULL) 
- value : varchar(255) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- settings : json (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: fan_pages
DESCRIPTION: Stores fan pages records for the application. Key attributes include title and content. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- title : varchar(255) (NOT NULL) 
- content : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: feature_flags
DESCRIPTION: Stores feature flags records for the application. References related entities via: org. 4 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- org_id : CHAR(36) (NOT NULL) 
- key : varchar(64) (NOT NULL) 
- enabled : text (NOT NULL) 

TABLE: fees
DESCRIPTION: Stores fees records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- amount : numeric(10,2) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: files
DESCRIPTION: Stores files records for the application. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- storage_key : varchar(512) (NOT NULL) 
- filename : varchar(255) (NOT NULL) 
- size : int 
- mime_type : varchar(127) 
- created_by : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: final_grades
DESCRIPTION: Stores final grades records for the application. References related entities via: grading period, section, student. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- section_id : CHAR(36) (NOT NULL) 
- grading_period_id : CHAR(36) (NOT NULL) 
- numeric_grade : numeric(6,3) 
- letter_grade : text 
- credits_earned : numeric(5,2) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: fiscal_periods
DESCRIPTION: Stores fiscal periods records for the application. References related entities via: fiscal year. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- year_number : int (NOT NULL) 
- period_no : int (NOT NULL) 
- start_date : date (NOT NULL) 
- end_date : date (NOT NULL) 
- is_closed : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: fiscal_years
DESCRIPTION: Stores fiscal years records for the application. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- year : int (NOT NULL, UNIQUE) 
- start_date : date (NOT NULL) 
- end_date : date (NOT NULL) 
- is_closed : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: floors
DESCRIPTION: Stores floors records for the application. Key attributes include name. References related entities via: building. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- building_id : CHAR(36) (NOT NULL) 
- level_code : varchar(32) (NOT NULL) 
- name : varchar(128) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: folders
DESCRIPTION: Stores folders records for the application. Key attributes include name. References related entities via: org, parent. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- org_id : CHAR(36) (NOT NULL) 
- parent_id : CHAR(36) 
- name : varchar(255) (NOT NULL) 
- is_public : boolean (NOT NULL) 
- sort_order : int 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: frameworks
DESCRIPTION: Stores frameworks records for the application. Key attributes include code, name. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- code : varchar(64) (NOT NULL, UNIQUE) 
- name : varchar(255) (NOT NULL) 
- edition : varchar(64) 
- effective_from : date 
- effective_to : date 
- metadata : json 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: fundraising_campaigns
DESCRIPTION: Stores fundraising campaigns records for the application. Key attributes include title and goal amount. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- title : varchar(255) (NOT NULL) 
- goal_cents : int (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: game_official_contracts
DESCRIPTION: Stores game official contracts records for the application. Key attributes include fee_cents. References related entities via: game, official. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- game_id : CHAR(36) (NOT NULL) 
- official_id : CHAR(36) (NOT NULL) 
- fee_cents : int (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: game_programs
DESCRIPTION: Stores game program records for the application. Key attributes include title and content. References related entities via: game. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- game_id : CHAR(36) (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- content : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: game_reports
DESCRIPTION: Stores game report records for the application. Key attributes include report_type and content. References related entities via: game. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- game_id : CHAR(36) (NOT NULL) 
- report_type : varchar(100) (NOT NULL) 
- content : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: games
DESCRIPTION: Stores games records for the application. Key attributes include opponent and score. References related entities via: season, team. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- team_id : CHAR(36) (NOT NULL) 
- opponent : varchar(255) (NOT NULL) 
- score : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- season_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: gl_account_balances
DESCRIPTION: Stores gl account balances records for the application. References related entities via: account, fiscal period. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- account_id : CHAR(36) (NOT NULL) 
- fiscal_period_id : CHAR(36) (NOT NULL) 
- begin_balance : numeric(16,2) (NOT NULL) 
- debit_total : numeric(16,2) (NOT NULL) 
- credit_total : numeric(16,2) (NOT NULL) 
- end_balance : numeric(16,2) (NOT NULL) 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: gl_account_segments
DESCRIPTION: Stores gl account segments records for the application. References related entities via: account, segment, value. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- segment_id : CHAR(36) (NOT NULL) 
- value_id : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: gl_accounts
DESCRIPTION: Stores gl accounts records for the application. Key attributes include code, name. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- code : varchar(128) (NOT NULL, UNIQUE) 
- name : varchar(255) (NOT NULL) 
- acct_type : varchar(32) (NOT NULL) 
- active : boolean (NOT NULL) 
- attributes : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: gl_segment_values
DESCRIPTION: Stores gl segment values records for the application. Key attributes include code, name. References related entities via: segment. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- code : varchar(32) (NOT NULL) 
- name : varchar(128) (NOT NULL) 
- active : boolean (NOT NULL) 
- segment_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: gl_segments
DESCRIPTION: Stores gl segments records for the application. Key attributes include code, name. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- code : varchar(32) (NOT NULL, UNIQUE) 
- name : varchar(128) (NOT NULL) 
- seq : int (NOT NULL) 
- length : int 
- required : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: goals
DESCRIPTION: Stores goals records for the application. Key attributes include name. References related entities via: plan. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- plan_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- description : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: governing_bodies
DESCRIPTION: Stores governing bodies records for the application. Key attributes include name. References related entities via: org. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- org_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- type : varchar(50) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: gpa_calculations
DESCRIPTION: Stores gpa calculations records for the application. References related entities via: student, term. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- term_id : CHAR(36) (NOT NULL) 
- gpa : numeric(4,3) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: grade_levels
DESCRIPTION: Stores grade levels records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : varchar(12) (NOT NULL) 
- ordinal : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: grade_scale_bands
DESCRIPTION: Stores grade scale bands records for the application. References related entities via: grade scale. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- grade_scale_id : CHAR(36) (NOT NULL) 
- label : text (NOT NULL) 
- min_value : numeric(6,3) (NOT NULL) 
- max_value : numeric(6,3) (NOT NULL) 
- gpa_points : numeric(4,2) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: grade_scales
DESCRIPTION: Stores grade scales records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- type : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: gradebook_entries
DESCRIPTION: Stores gradebook entries records for the application. References related entities via: assignment, student. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- assignment_id : CHAR(36) (NOT NULL) 
- student_id : CHAR(36) (NOT NULL) 
- score : numeric(8,3) 
- submitted_at : timestamp 
- late : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: grading_periods
DESCRIPTION: Stores grading periods records for the application. Key attributes include name. References related entities via: term. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- term_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- start_date : date (NOT NULL) 
- end_date : date (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: guardian_invitations
DESCRIPTION: No description provided.
KEY COLUMNS:
- user_id : CHAR(36) (NOT NULL) 
- student_user_id : CHAR(36) (NOT NULL) 
- invited_email : varchar(255) (NOT NULL) 
- state : varchar(37) (NOT NULL) 
- create_time : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: guardians
DESCRIPTION: Stores guardian linkages between students and their guardians. Includes standard audit timestamps (created_at, updated_at). Composite index on (student_user_id, guardian_email).
KEY COLUMNS:
- student_user_id : CHAR(36) (NOT NULL) 
- guardian_user_id : CHAR(36) 
- guardian_email : varchar(255) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: health_profiles
DESCRIPTION: Stores health profiles records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- allergies : text 
- conditions : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: hr_employees
DESCRIPTION: Stores hr employees records for the application. References related entities via: department segment, person, primary school. Includes standard audit timestamps (created_at, updated_at). 12 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- person_id : CHAR(36) 
- employee_no : varchar(32) (NOT NULL, UNIQUE) 
- primary_school_id : CHAR(36) 
- department_segment_id : CHAR(36) 
- employment_type : varchar(16) 
- status : varchar(16) (NOT NULL) 
- hire_date : date 
- termination_date : date 
- attributes : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: hr_position_assignments
DESCRIPTION: Stores hr position assignments records for the application. References related entities via: employee, position. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- employee_id : CHAR(36) (NOT NULL) 
- position_id : CHAR(36) (NOT NULL) 
- start_date : date (NOT NULL) 
- end_date : date 
- percent : numeric(5,2) 
- funding_split : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: hr_positions
DESCRIPTION: Stores hr positions records for the application. Key attributes include title. References related entities via: department segment. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- title : varchar(255) (NOT NULL) 
- department_segment_id : CHAR(36) 
- grade : varchar(32) 
- fte : numeric(5,2) 
- attributes : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: iep_plans
DESCRIPTION: Stores iep plans records for the application. References related entities via: special ed case. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- special_ed_case_id : CHAR(36) (NOT NULL) 
- effective_start : date (NOT NULL) 
- effective_end : date 
- summary : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: immunization_records
DESCRIPTION: Stores immunization records records for the application. References related entities via: immunization, student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- immunization_id : CHAR(36) (NOT NULL) 
- date_administered : date (NOT NULL) 
- dose_number : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: immunizations
DESCRIPTION: Stores immunizations records for the application. Key attributes include name, code. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : text (NOT NULL) 
- code : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: incident_participants
DESCRIPTION: Stores incident participants records for the application. References related entities via: incident, person. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- incident_id : CHAR(36) (NOT NULL) 
- person_id : CHAR(36) (NOT NULL) 
- role : text (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: incidents
DESCRIPTION: Stores incidents records for the application. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) 
- occurred_at : timestamp (NOT NULL) 
- behavior_code : text (NOT NULL) 
- description : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: initiatives
DESCRIPTION: Stores initiatives records for the application. Key attributes include name. References related entities via: objective, owner. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- objective_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- description : text 
- owner_id : CHAR(36) 
- due_date : date 
- status : varchar(32) 
- priority : varchar(16) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: invoices
DESCRIPTION: Stores invoices records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- issued_on : date (NOT NULL) 
- due_on : date 
- status : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: journal_batches
DESCRIPTION: Stores journal batches records for the application. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- batch_no : varchar(64) (NOT NULL, UNIQUE) 
- description : varchar(255) 
- source : varchar(64) 
- status : varchar(16) (NOT NULL) 
- posted_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: journal_entries
DESCRIPTION: Stores journal entries records for the application. References related entities via: batch, fiscal period. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- fiscal_period_id : CHAR(36) (NOT NULL) 
- je_no : varchar(64) (NOT NULL) 
- journal_date : date (NOT NULL) 
- description : varchar(255) 
- status : varchar(16) (NOT NULL) 
- total_debits : numeric(14,2) (NOT NULL) 
- total_credits : numeric(14,2) (NOT NULL) 
- batch_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: journal_entry_lines
DESCRIPTION: Stores journal entry lines records for the application. References related entities via: account, entry. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- entry_id : CHAR(36) (NOT NULL) 
- account_id : CHAR(36) (NOT NULL) 
- line_no : int (NOT NULL) 
- description : varchar(255) 
- debit : numeric(14,2) (NOT NULL) 
- credit : numeric(14,2) (NOT NULL) 
- segment_overrides : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: kpi_datapoints
DESCRIPTION: Stores kpi datapoints records for the application. References related entities via: kpi. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- note : text 
- kpi_id : CHAR(36) (NOT NULL) 
- as_of : date (NOT NULL) 
- value : numeric (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: kpis
DESCRIPTION: Stores kpis records for the application. Key attributes include name. References related entities via: goal, objective. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- goal_id : CHAR(36) 
- objective_id : CHAR(36) 
- name : varchar(255) (NOT NULL) 
- unit : varchar(32) 
- target : numeric 
- baseline : numeric 
- direction : varchar(8) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: leases
DESCRIPTION: Stores leases records for the application. References related entities via: building. Includes standard audit timestamps (created_at, updated_at). 13 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- building_id : CHAR(36) 
- landlord : varchar(255) 
- tenant : varchar(255) 
- start_date : date 
- end_date : date 
- base_rent : numeric(14,2) 
- rent_schedule : json 
- options : json 
- documents : json 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: library_checkouts
DESCRIPTION: Stores library checkouts records for the application. References related entities via: item, person. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- item_id : CHAR(36) (NOT NULL) 
- person_id : CHAR(36) (NOT NULL) 
- checked_out_on : date (NOT NULL) 
- due_on : date (NOT NULL) 
- returned_on : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: library_fines
DESCRIPTION: Stores library fines records for the application. References related entities via: person. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- person_id : CHAR(36) (NOT NULL) 
- amount : numeric(10,2) (NOT NULL) 
- reason : text 
- assessed_on : date (NOT NULL) 
- paid_on : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: library_holds
DESCRIPTION: Stores library holds records for the application. References related entities via: item, person. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- item_id : CHAR(36) (NOT NULL) 
- person_id : CHAR(36) (NOT NULL) 
- placed_on : date (NOT NULL) 
- expires_on : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: library_items
DESCRIPTION: Stores library items records for the application. Key attributes include title. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- title : text (NOT NULL) 
- author : text 
- isbn : text 
- barcode : text (UNIQUE) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: live_scoring
DESCRIPTION: Stores live scoring records for the application. Key attributes include score and status. References related entities via: game. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- game_id : CHAR(36) (NOT NULL) 
- score : int (NOT NULL) 
- status : varchar(50) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: maintenance_requests
DESCRIPTION: Stores maintenance requests records for the application. References related entities via: asset, building, converted work order, school, space, submitted by user. Includes standard audit timestamps (created_at, updated_at). 14 column(s) defined. Primary key is `id`. 6 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) 
- building_id : CHAR(36) 
- space_id : CHAR(36) 
- asset_id : CHAR(36) 
- submitted_by_user_id : CHAR(36) 
- status : varchar(32) (NOT NULL) 
- priority : varchar(16) 
- summary : varchar(255) (NOT NULL) 
- description : text 
- converted_work_order_id : CHAR(36) 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: manual_stats
DESCRIPTION: Stores manual stats records for the application. Key attributes include type and value. References related entities via: game. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- stat_type : varchar(100) (NOT NULL) 
- value : int (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- game_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: materials
DESCRIPTION: No description provided.
KEY COLUMNS:
- type : varchar(10) (NOT NULL) 
- title : varchar(255) 
- url : varchar(1024) 
- drive_file_id : varchar(128) 
- payload : json 
- announcement_id : CHAR(36) 
- coursework_id : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: meal_accounts
DESCRIPTION: Stores meal accounts records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- balance : numeric(10,2) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: meal_eligibility_statuses
DESCRIPTION: Stores meal eligibility statuses records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- status : text (NOT NULL) 
- effective_start : date (NOT NULL) 
- effective_end : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: meal_transactions
DESCRIPTION: Stores meal transactions records for the application. References related entities via: account. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- account_id : CHAR(36) (NOT NULL) 
- transacted_at : timestamp (NOT NULL) 
- amount : numeric(10,2) (NOT NULL) 
- description : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: medication_administrations
DESCRIPTION: Stores medication administrations records for the application. References related entities via: medication, student. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- medication_id : CHAR(36) (NOT NULL) 
- administered_at : timestamp (NOT NULL) 
- dose : text 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: medications
DESCRIPTION: Stores medications records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : text (NOT NULL) 
- instructions : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: meeting_documents
DESCRIPTION: Stores meeting documents records for the application. References related entities via: document, meeting. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (NOT NULL) 
- document_id : CHAR(36) 
- file_uri : text 
- label : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: meeting_files
DESCRIPTION: Stores meeting files records for the application. References related entities via: file, meeting. 4 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- meeting_id : CHAR(36) (NOT NULL) 
- file_id : CHAR(36) (NOT NULL) 
- caption : varchar(255) 

TABLE: meeting_permissions
DESCRIPTION: Stores meeting permissions records for the application. References related entities via: meeting, user. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) (NOT NULL) 
- can_view : boolean (NOT NULL) 
- can_edit : text (NOT NULL) 
- can_manage : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: meeting_publications
DESCRIPTION: Stores meeting publications records for the application. References related entities via: meeting. Includes standard audit timestamps (published_at). 4 column(s) defined. 1 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (PK, NOT NULL) 
- published_at : timestamp (NOT NULL) 
- public_url : varchar(1024) 
- archive_url : varchar(1024) 

TABLE: meeting_search_index
DESCRIPTION: Stores meeting search index records for the application. References related entities via: meeting. 2 column(s) defined. 1 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (PK, NOT NULL) 
- ts : TEXT 

TABLE: meetings
DESCRIPTION: Stores meetings records for the application. Key attributes include title. References related entities via: governing body, org. Includes standard audit timestamps (created_at, updated_at). 12 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- org_id : CHAR(36) (NOT NULL) 
- governing_body_id : CHAR(36) 
- committee_id : CHAR(36) (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- scheduled_at : timestamp (NOT NULL) 
- starts_at : timestamp (NOT NULL) 
- ends_at : timestamp 
- location : varchar(255) 
- status : varchar(32) 
- is_public : boolean (NOT NULL) 
- stream_url : varchar(1024) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: memberships
DESCRIPTION: Stores cic memberships records for the application. References related entities via: committee, person. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- committee_id : CHAR(36) (NOT NULL) 
- person_id : CHAR(36) (NOT NULL) 
- role : text 
- start_date : date 
- end_date : date 
- voting_member : boolean (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: message_recipients
DESCRIPTION: Stores message recipients records for the application. References related entities via: message, person. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- message_id : CHAR(36) (NOT NULL) 
- person_id : CHAR(36) (NOT NULL) 
- delivery_status : text 
- delivered_at : timestamp 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: messages
DESCRIPTION: Stores messages records for the application. References related entities via: sender. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- sender_id : CHAR(36) 
- channel : text (NOT NULL) 
- subject : text 
- body : text 
- sent_at : timestamp 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: meters
DESCRIPTION: Stores meters records for the application. Key attributes include name. References related entities via: asset, building. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- asset_id : CHAR(36) 
- building_id : CHAR(36) 
- name : varchar(255) (NOT NULL) 
- meter_type : varchar(64) 
- uom : varchar(32) 
- last_read_value : numeric(18,6) 
- last_read_at : timestamp 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: minutes
DESCRIPTION: Stores minutes records for the application. References related entities via: author, meeting. Includes standard audit timestamps (published_at, created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (NOT NULL) 
- author_id : CHAR(36) 
- content : text 
- published_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: motions
DESCRIPTION: Stores motions records for the application. References related entities via: agenda item, moved by, seconded by. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- agenda_item_id : CHAR(36) (NOT NULL) 
- text : text (NOT NULL) 
- moved_by_id : CHAR(36) 
- seconded_by_id : CHAR(36) 
- passed : boolean 
- tally_for : int 
- tally_against : int 
- tally_abstain : int 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: move_orders
DESCRIPTION: Stores move orders records for the application. References related entities via: from space, person, project, to space. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 4 foreign key field(s) detected.
KEY COLUMNS:
- project_id : CHAR(36) 
- person_id : CHAR(36) 
- from_space_id : CHAR(36) 
- to_space_id : CHAR(36) 
- move_date : date 
- status : varchar(32) 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: notifications
DESCRIPTION: Stores notifications records for the application. References related entities via: user. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- user_id : CHAR(36) (NOT NULL) 
- type : varchar(50) (NOT NULL) 
- payload : JSON 
- read_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: nurse_visits
DESCRIPTION: Stores nurse visits records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- visited_at : timestamp (NOT NULL) 
- reason : text 
- disposition : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: objectives
DESCRIPTION: Stores objectives records for the application. Key attributes include name. References related entities via: goal. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- goal_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- description : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: officials
DESCRIPTION: Stores officials records for the application. Key attributes include name and certification. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 0 foreign key field(s) detected.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- certification : varchar(255) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: order_line_items
DESCRIPTION: Stores order line items records for the application. References related entities via: order, ticket type. Includes standard audit timestamps (created_at, updated_at). 6+ column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- order_id : CHAR(36) (NOT NULL) 
- ticket_type_id : CHAR(36) (NOT NULL) 
- quantity : int (NOT NULL) 
- unit_price_cents : int (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: orders
DESCRIPTION: Stores orders records for the application. References related entities via: event, purchaser user. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- event_id : CHAR(36) (NOT NULL) 
- purchaser_user_id : CHAR(36) 
- buyer_name : varchar(255) 
- buyer_email : varchar(255) 
- total_cents : int (NOT NULL) 
- currency : varchar(8) (NOT NULL) 
- status : varchar(8) (NOT NULL) 
- external_ref : varchar(255) 
- attributes : JSON 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: organizations
DESCRIPTION: Stores organizations records for the application. Key attributes include name, code. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : varchar(255) (NOT NULL, UNIQUE) 
- code : text (UNIQUE) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: pages
DESCRIPTION: Stores pages records for the application. Key attributes include slug, title. References related entities via: channel. Includes standard audit timestamps (published_at, created_at, updated_at). 9 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- slug : varchar(255) (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- body : text 
- status : varchar(16) (NOT NULL) 
- published_at : timestamp 
- channel_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: part_locations
DESCRIPTION: Stores part locations records for the application. References related entities via: building, part, space. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- part_id : CHAR(36) (NOT NULL) 
- building_id : CHAR(36) 
- space_id : CHAR(36) 
- location_code : varchar(128) 
- qty_on_hand : numeric(12,2) (NOT NULL) 
- min_qty : numeric(12,2) 
- max_qty : numeric(12,2) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: parts
DESCRIPTION: Stores parts records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- sku : varchar(128) (UNIQUE) 
- name : varchar(255) (NOT NULL) 
- description : text 
- unit_cost : numeric(12,2) 
- uom : varchar(32) 
- attributes : JSON 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: passes
DESCRIPTION: No description provided.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : varchar(128) 
- description : text 
- price_cents : int 
- valid_from : date 
- valid_to : date 
- max_uses : int 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: pay_periods
DESCRIPTION: Stores pay periods records for the application. Key attributes include code. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- code : varchar(32) (NOT NULL, UNIQUE) 
- start_date : date (NOT NULL) 
- end_date : date (NOT NULL) 
- pay_date : date (NOT NULL) 
- status : varchar(16) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: paychecks
DESCRIPTION: Stores paychecks records for the application. References related entities via: employee, run. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- run_id : CHAR(36) (NOT NULL) 
- employee_id : CHAR(36) (NOT NULL) 
- check_no : varchar(32) 
- gross_pay : numeric(12,2) (NOT NULL) 
- net_pay : numeric(12,2) (NOT NULL) 
- taxes : JSON 
- attributes : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: payments
DESCRIPTION: Stores payments records for the application. References related entities via: invoice. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- invoice_id : CHAR(36) (NOT NULL) 
- paid_on : date (NOT NULL) 
- amount : numeric(10,2) (NOT NULL) 
- method : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: payroll_runs
DESCRIPTION: Stores payroll runs records for the application. References related entities via: created by user, pay period, posted entry. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- pay_period_id : CHAR(36) (NOT NULL) 
- run_no : int (NOT NULL) 
- status : varchar(16) (NOT NULL) 
- created_by_user_id : CHAR(36) 
- posted_entry_id : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: periods
DESCRIPTION: Stores periods records for the application. Key attributes include name. References related entities via: bell schedule. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- bell_schedule_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- start_time : TIME (NOT NULL) 
- end_time : TIME (NOT NULL) 
- sequence : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: permissions
DESCRIPTION: Stores permissions records for the application. Key attributes include code. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- code : text (NOT NULL, UNIQUE) 
- description : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: person_addresses
DESCRIPTION: Stores person addresses records for the application. References related entities via: address, person. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- person_id : CHAR(36) (NOT NULL) 
- address_id : CHAR(36) (NOT NULL) 
- is_primary : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: person_contacts
DESCRIPTION: Stores person contacts records for the application. References related entities via: contact, person. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- person_id : CHAR(36) (NOT NULL) 
- contact_id : CHAR(36) (NOT NULL) 
- label : text 
- is_primary : text (NOT NULL) 
- is_emergency : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: personal_notes
DESCRIPTION: Stores personal notes records for the application. References related entities via: entity, user. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- user_id : CHAR(36) (NOT NULL) 
- entity_type : varchar(50) (NOT NULL) 
- entity_id : CHAR(36) (NOT NULL) 
- text : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: persons
DESCRIPTION: Stores persons records for the application. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- first_name : text (NOT NULL) 
- last_name : text (NOT NULL) 
- middle_name : text 
- dob : date 
- email : text 
- phone : text 
- gender : varchar(6) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: plan_alignments
DESCRIPTION: Stores plan alignments records for the application. References related entities via: agenda item, objective, policy. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- note : text 
- agenda_item_id : CHAR(36) 
- policy_id : CHAR(36) 
- objective_id : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: plan_assignments
DESCRIPTION: Stores plan assignments records for the application. References related entities via: assignee, entity. 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- entity_type : varchar(50) (NOT NULL) 
- entity_id : CHAR(36) (NOT NULL) 
- assignee_type : varchar(20) (NOT NULL) 
- assignee_id : CHAR(36) (NOT NULL) 

TABLE: plan_filters
DESCRIPTION: Stores plan filters records for the application. Key attributes include name. References related entities via: plan. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- plan_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- criteria : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: plan_search_index
DESCRIPTION: Stores plan search index records for the application. References related entities via: plan. 2 column(s) defined. 1 foreign key field(s) detected.
KEY COLUMNS:
- plan_id : CHAR(36) (PK, NOT NULL) 
- ts : TEXT 

TABLE: plans
DESCRIPTION: Stores plans records for the application. Key attributes include name. References related entities via: org. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- org_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- cycle_start : date 
- cycle_end : date 
- status : varchar(32) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: pm_plans
DESCRIPTION: Stores pm plans records for the application. Key attributes include name. References related entities via: asset, building. Includes standard audit timestamps (created_at, updated_at). 12 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- asset_id : CHAR(36) 
- building_id : CHAR(36) 
- name : varchar(255) (NOT NULL) 
- frequency : varchar(64) 
- next_due_at : timestamp 
- last_completed_at : timestamp 
- active : boolean (NOT NULL) 
- procedure : json 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: pm_work_generators
DESCRIPTION: Stores pm work generators records for the application. References related entities via: pm plan. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- pm_plan_id : CHAR(36) (NOT NULL) 
- last_generated_at : timestamp 
- lookahead_days : int 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: policies
DESCRIPTION: Stores policies records for the application. Key attributes include code, title. References related entities via: org. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- org_id : CHAR(36) (NOT NULL) 
- code : varchar(64) 
- title : varchar(255) (NOT NULL) 
- status : varchar(32) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: policy_approvals
DESCRIPTION: Stores policy approvals records for the application. References related entities via: approver, policy version, step. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- policy_version_id : CHAR(36) (NOT NULL) 
- step_id : CHAR(36) (NOT NULL) 
- approver_id : CHAR(36) 
- decision : varchar(16) 
- decided_at : timestamp 
- comment : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: policy_comments
DESCRIPTION: Stores policy comments records for the application. References related entities via: policy version, user. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- policy_version_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) 
- text : text (NOT NULL) 
- visibility : varchar(16) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: policy_files
DESCRIPTION: Stores policy files records for the application. References related entities via: file, policy version. Includes standard audit timestamps (created_at). 4 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- policy_version_id : CHAR(36) (NOT NULL) 
- file_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 

TABLE: policy_legal_refs
DESCRIPTION: Stores policy legal refs records for the application. References related entities via: policy version. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- policy_version_id : CHAR(36) (NOT NULL) 
- citation : varchar(255) (NOT NULL) 
- url : varchar(1024) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: policy_publications
DESCRIPTION: Stores policy publications records for the application. References related entities via: policy version. Includes standard audit timestamps (published_at). 4 column(s) defined. 1 foreign key field(s) detected.
KEY COLUMNS:
- policy_version_id : CHAR(36) (PK, NOT NULL) 
- published_at : timestamp (NOT NULL) 
- public_url : varchar(1024) 
- is_current : boolean (NOT NULL) 

TABLE: policy_search_index
DESCRIPTION: Stores policy search index records for the application. References related entities via: policy. 2 column(s) defined. 1 foreign key field(s) detected.
KEY COLUMNS:
- policy_id : CHAR(36) (PK, NOT NULL) 
- ts : TEXT 

TABLE: policy_versions
DESCRIPTION: Stores policy versions records for the application. References related entities via: policy, supersedes version. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- policy_id : CHAR(36) (NOT NULL) 
- version_no : int (NOT NULL) 
- content : text 
- effective_date : date 
- supersedes_version_id : CHAR(36) 
- created_by : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: policy_workflow_steps
DESCRIPTION: Stores policy workflow steps records for the application. References related entities via: approver, workflow. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- workflow_id : CHAR(36) (NOT NULL) 
- step_no : int (NOT NULL) 
- approver_type : varchar(20) (NOT NULL) 
- approver_id : CHAR(36) 
- rule : varchar(255) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: policy_workflows
DESCRIPTION: Stores policy workflows records for the application. Key attributes include name. References related entities via: policy. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- policy_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- active : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: post_attachments
DESCRIPTION: Stores post attachments records for the application. References related entities via: file, post. 3 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- post_id : CHAR(36) (NOT NULL) 
- file_id : CHAR(36) (NOT NULL) 

TABLE: posts
DESCRIPTION: Stores posts records for the application. Key attributes include title. References related entities via: author, channel. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- channel_id : CHAR(36) (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- body : text 
- status : varchar(16) (NOT NULL) 
- publish_at : timestamp 
- author_id : CHAR(36) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: project_tasks
DESCRIPTION: Stores project tasks records for the application. Key attributes include name. References related entities via: assignee user, project. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- project_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- status : varchar(32) 
- start_date : date 
- end_date : date 
- percent_complete : numeric(5,2) 
- assignee_user_id : CHAR(36) 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: projects
DESCRIPTION: Stores projects records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 12 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) 
- name : varchar(255) (NOT NULL) 
- project_type : varchar(32) 
- status : varchar(32) 
- start_date : date 
- end_date : date 
- budget : numeric(14,2) 
- description : text 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: proposal_documents
DESCRIPTION: Stores cic proposal documents records for the application. References related entities via: document, proposal. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- proposal_id : CHAR(36) (NOT NULL) 
- document_id : CHAR(36) 
- file_uri : text 
- label : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: proposal_reviews
DESCRIPTION: Stores proposal reviews records for the application. References related entities via: proposal, reviewer. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- proposal_id : CHAR(36) (NOT NULL) 
- review_round_id : CHAR(36) (NOT NULL) 
- reviewer_id : CHAR(36) 
- decision : text 
- decided_at : timestamp 
- comment : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: proposal_standard_map
DESCRIPTION: No description provided.
KEY COLUMNS:
- proposal_id : CHAR(36) (PK, NOT NULL) 
- standard_id : CHAR(36) (PK, NOT NULL) 

TABLE: proposals
DESCRIPTION: No description provided.
KEY COLUMNS:
- organization_id : CHAR(36) 
- association_id : CHAR(36) 
- committee_id : CHAR(36) (NOT NULL) 
- submitted_by_id : CHAR(36) 
- school_id : CHAR(36) 
- subject_id : CHAR(36) 
- course_id : CHAR(36) 
- title : varchar(255) (NOT NULL) 
- summary : text 
- rationale : text 
- status : varchar(9) (NOT NULL) 
- submitted_at : timestamp 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: publications
DESCRIPTION: Stores cic publications records for the application. References related entities via: meeting. Includes standard audit timestamps (published_at, created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (NOT NULL) 
- published_at : timestamp (NOT NULL) 
- public_url : text 
- is_final : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: report_cards
DESCRIPTION: Stores report cards records for the application. References related entities via: student, term. Includes standard audit timestamps (published_at, created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- term_id : CHAR(36) (NOT NULL) 
- published_at : timestamp 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: requirements
DESCRIPTION: Stores requirements records for the application. Key attributes include title. Includes standard audit timestamps (created_at). 9 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- state_code : varchar(2) (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- category : varchar(128) 
- description : text 
- effective_date : date 
- reference_url : varchar(512) 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: resolutions
DESCRIPTION: Stores cic resolutions records for the application. Key attributes include title. References related entities via: meeting. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- meeting_id : CHAR(36) (NOT NULL) 
- title : text (NOT NULL) 
- summary : text 
- effective_date : date 
- status : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: retention_rules
DESCRIPTION: Stores retention rules records for the application. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- entity_type : varchar(50) (NOT NULL) 
- policy : JSON (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: review_requests
DESCRIPTION: Stores review requests records for the application. References related entities via: association, curriculum version. Includes standard audit timestamps (created_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- curriculum_version_id : CHAR(36) (NOT NULL) 
- association_id : CHAR(36) (NOT NULL) 
- status : varchar(32) (NOT NULL) 
- submitted_at : timestamp 
- decided_at : timestamp 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: review_rounds
DESCRIPTION: Stores review rounds records for the application. References related entities via: proposal. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- round_no : int (NOT NULL) 
- opened_at : timestamp 
- closed_at : timestamp 
- status : varchar(8) 
- proposal_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: reviewers
DESCRIPTION: Stores reviewers records for the application. Key attributes include name. References related entities via: association. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- email : varchar(255) (NOT NULL) 
- active : boolean (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: reviews
DESCRIPTION: Stores reviews records for the application. References related entities via: review round, reviewer. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- review_round_id : CHAR(36) (NOT NULL) 
- reviewer_id : CHAR(36) (NOT NULL) 
- status : varchar(9) (NOT NULL) 
- submitted_at : timestamp 
- content : json 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: role_permissions
DESCRIPTION: Stores role permissions records for the application. References related entities via: permission, role. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- role_id : CHAR(36) (NOT NULL) 
- permission_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: roles
DESCRIPTION: Stores roles records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : text (NOT NULL, UNIQUE) 
- description : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: rooms
DESCRIPTION: Stores rooms records for the application. Key attributes include name. References related entities via: school. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) (NOT NULL) 
- name : text (NOT NULL) 
- capacity : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: round_decisions
DESCRIPTION: Stores round decisions records for the application. References related entities via: review round. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- review_round_id : CHAR(36) (NOT NULL, UNIQUE) 
- decision : varchar(24) (NOT NULL) 
- decided_at : timestamp 
- notes : text 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: scan_requests
DESCRIPTION: Stores scan requests records for the application. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- qr_code : varchar(128) (NOT NULL) 
- location : varchar(255) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: scan_results
DESCRIPTION: Stores scan results records for the application. References related entities via: ticket. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- ok : boolean (NOT NULL) 
- ticket_id : CHAR(36) 
- status : varchar(32) 
- message : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: schools
DESCRIPTION: Stores schools records for the application. Key attributes include name. References related entities via: nces school, organization. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- organization_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- school_code : text (UNIQUE) 
- nces_school_id : text 
- building_code : text 
- type : text 
- timezone : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: score_entries
DESCRIPTION: Stores score entry records for the application. Key attributes include points and period. References related entities via: game, team. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- team_id : CHAR(36) (NOT NULL) 
- points : int (NOT NULL) 
- period : varchar(50) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- game_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: scorecard_kpis
DESCRIPTION: Stores scorecard kpis records for the application. References related entities via: kpi, scorecard. 4 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- scorecard_id : CHAR(36) (NOT NULL) 
- kpi_id : CHAR(36) (NOT NULL) 
- display_order : int 

TABLE: scorecards
DESCRIPTION: Stores scorecards records for the application. Key attributes include name. References related entities via: plan. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- plan_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: seasons
DESCRIPTION: Stores season records for the application. Key attributes include name and year. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 0 foreign key field(s) detected.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- year : varchar(50) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: section504_plans
DESCRIPTION: Stores section504 plans records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- effective_start : date (NOT NULL) 
- effective_end : date 
- summary : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: section_meetings
DESCRIPTION: Stores section meetings records for the application. References related entities via: period, room, section. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- section_id : CHAR(36) (NOT NULL) 
- day_of_week : int (NOT NULL) 
- period_id : CHAR(36) 
- room_id : CHAR(36) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: section_room_assignments
DESCRIPTION: Stores section room assignments records for the application. References related entities via: room, section. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- section_id : CHAR(36) (NOT NULL) 
- room_id : CHAR(36) (NOT NULL) 
- start_date : date 
- end_date : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: sessions
DESCRIPTION: Represents a tutoring session context between a student and one or more AI tutors. References related entities via: students. Includes standard audit timestamps (created_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- subject : text (NOT NULL) 
- objective_code : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: sis_import_jobs
DESCRIPTION: Stores sis import jobs records for the application. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- source : text (NOT NULL) 
- status : text (NOT NULL) 
- started_at : timestamp (NOT NULL) 
- finished_at : timestamp 
- counts : JSON 
- error_log : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: space_reservations
DESCRIPTION: Stores space reservations records for the application. References related entities via: booked by user, space. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- space_id : CHAR(36) (NOT NULL) 
- booked_by_user_id : CHAR(36) 
- start_at : timestamp (NOT NULL) 
- end_at : timestamp (NOT NULL) 
- purpose : varchar(255) 
- status : varchar(32) (NOT NULL) 
- setup : json 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: spaces
DESCRIPTION: Stores spaces records for the application. Key attributes include code, name. References related entities via: building, floor. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- floor_id : CHAR(36) 
- code : varchar(64) (NOT NULL) 
- name : varchar(255) 
- space_type : varchar(64) 
- area_sqft : numeric(12,2) 
- capacity : int 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- building_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: special_education_cases
DESCRIPTION: Stores special education cases records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- eligibility : text 
- case_opened : date 
- case_closed : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: sports
DESCRIPTION: Stores sport records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 0 foreign key field(s) detected.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: staff
DESCRIPTION: Stores staff records for the application. Key attributes include title. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- employee_number : text (UNIQUE) 
- title : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: standardized_tests
DESCRIPTION: Stores standardized tests records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : text (NOT NULL) 
- subject : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: standards
DESCRIPTION: Stores standards records for the application. Key attributes include code. References related entities via: framework, parent. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- framework_id : CHAR(36) (NOT NULL) 
- code : varchar(128) (NOT NULL) 
- description : text (NOT NULL) 
- parent_id : CHAR(36) 
- grade_band : varchar(64) 
- effective_from : date 
- effective_to : date 
- attributes : json 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: stat_imports
DESCRIPTION: Stores stat import records for the application. Key attributes include source and status. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 0 foreign key field(s) detected.
KEY COLUMNS:
- source : varchar(255) (NOT NULL) 
- status : varchar(100) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: state_reporting_snapshots
DESCRIPTION: Stores state reporting snapshots records for the application. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- as_of_date : date (NOT NULL) 
- scope : text 
- payload : JSON 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: states
DESCRIPTION: Stores states records for the application. Key attributes include code, name. 2 column(s) defined.
KEY COLUMNS:
- code : varchar(2) (PK, NOT NULL) 
- name : varchar(64) (NOT NULL) 

TABLE: store_order_items
DESCRIPTION: Stores store order item records for the application. Key attributes include quantity and price. References related entities via: store_order, store_product. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- order_id : CHAR(36) (NOT NULL) 
- product_id : CHAR(36) (NOT NULL) 
- quantity : int (NOT NULL) 
- price_cents : int (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: store_orders
DESCRIPTION: Stores store order records for the application. Key attributes include user and total price. References related entities via: user. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- customer_id : CHAR(36) 
- status : varchar(32) (NOT NULL) 
- notes : text 
- metadata : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: store_products
DESCRIPTION: Stores store product records for the application. Key attributes include name and price. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 0 foreign key field(s) detected.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- sku : varchar(128) (UNIQUE) 
- price_cents : int (NOT NULL) 
- inventory_qty : int (NOT NULL) 
- metadata : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: student_guardians
DESCRIPTION: Stores student guardians records for the application. References related entities via: guardian, student. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- student_id : CHAR(36) (NOT NULL) 
- guardian_id : CHAR(36) (NOT NULL) 
- custody : text 
- is_primary : text (NOT NULL) 
- contact_order : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: student_program_enrollments
DESCRIPTION: Stores student program enrollments records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- program_name : text (NOT NULL) 
- start_date : date (NOT NULL) 
- end_date : date 
- status : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: student_school_enrollments
DESCRIPTION: Stores student school enrollments records for the application. References related entities via: school, student. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- entry_date : date (NOT NULL) 
- exit_date : date 
- status : varchar(11) (NOT NULL) 
- exit_reason : text 
- grade_level_id : CHAR(36) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: student_section_enrollments
DESCRIPTION: Stores student section enrollments records for the application. References related entities via: section, student. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- section_id : CHAR(36) (NOT NULL) 
- added_on : date (NOT NULL) 
- dropped_on : date 
- seat_time_minutes : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: student_submissions
DESCRIPTION: No description provided.
KEY COLUMNS:
- student_user_id : CHAR(36) (NOT NULL) 
- coursework_id : CHAR(36) (NOT NULL) 
- state : varchar(20) (NOT NULL) 
- late : boolean (NOT NULL) 
- assigned_grade : numeric 
- draft_grade : numeric 
- alternate_link : varchar(512) 
- update_time : timestamp 
- user_profile_id : CHAR(36) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: student_transportation_assignments
DESCRIPTION: Stores student transportation assignments records for the application. References related entities via: route, stop, student. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- route_id : CHAR(36) 
- stop_id : CHAR(36) 
- direction : text 
- effective_start : date (NOT NULL) 
- effective_end : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: students
DESCRIPTION: Stores students records for the application. References related entities via: person. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
Synonyms: student, learner, pupil
KEY COLUMNS:
- person_id : CHAR(36) (NOT NULL, UNIQUE) 
- student_number : text (UNIQUE) 
- graduation_year : int 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: subjects
DESCRIPTION: Stores subjects records for the application. Key attributes include name, code. References related entities via: department. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- department_id : CHAR(36) 
- name : text (NOT NULL) 
- code : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: subscriptions
DESCRIPTION: Stores subscriptions records for the application. References related entities via: channel, principal. Includes standard audit timestamps (created_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- id : CHAR(36) (PK, NOT NULL) 
- channel_id : CHAR(36) (NOT NULL) 
- principal_type : varchar(20) (NOT NULL) 
- principal_id : CHAR(36) (NOT NULL) 
- created_at : timestamp (NOT NULL) 

TABLE: tags
DESCRIPTION: Stores tags records for the application. Includes standard audit timestamps (created_at, updated_at). 4 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- label : varchar(80) (NOT NULL, UNIQUE) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: teacher_section_assignments
DESCRIPTION: Stores teacher section assignments records for the application. References related entities via: section, staff. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- staff_id : CHAR(36) (NOT NULL) 
- section_id : CHAR(36) (NOT NULL) 
- role : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: team_messages
DESCRIPTION: Stores team message records for the application. Key attributes include content. References related entities via: team. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- content : text (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- team_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: teams
DESCRIPTION: Stores team records for the application. Key attributes include name and mascot. References related entities via: sport, season. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- sport_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- mascot : varchar(255) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- season_id : CHAR(36) (NOT NULL) 
- school_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: test_administrations
DESCRIPTION: Stores test administrations records for the application. References related entities via: school, test. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- test_id : CHAR(36) (NOT NULL) 
- administration_date : date (NOT NULL) 
- school_id : CHAR(36) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: test_results
DESCRIPTION: Stores test results records for the application. References related entities via: administration, student. Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- administration_id : CHAR(36) (NOT NULL) 
- student_id : CHAR(36) (NOT NULL) 
- scale_score : numeric(8,2) 
- percentile : numeric(5,2) 
- performance_level : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: ticket_scans
DESCRIPTION: Stores ticket scans records for the application. References related entities via: scanned by user, ticket. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- ticket_id : CHAR(36) (NOT NULL) 
- scanned_by_user_id : CHAR(36) 
- scanned_at : timestamp (NOT NULL) 
- result : varchar(16) (NOT NULL) 
- location : varchar(255) 
- meta : JSON 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: ticket_types
DESCRIPTION: Stores ticket types records for the application. Key attributes include name. References related entities via: event. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- name : varchar(128) (NOT NULL) 
- price_cents : int (NOT NULL) 
- quantity_total : int (NOT NULL) 
- quantity_sold : int (NOT NULL) 
- sales_starts_at : timestamp 
- sales_ends_at : timestamp 
- attributes : JSON 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- event_id : CHAR(36) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: tickets
DESCRIPTION: No description provided.
KEY COLUMNS:
- order_id : CHAR(36) (NOT NULL) 
- ticket_type_id : CHAR(36) (NOT NULL) 
- event_id : CHAR(36) 
- qr_code : varchar(128) 
- status : varchar(8) (NOT NULL) 
- issued_at : timestamp 
- redeemed_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: topics
DESCRIPTION: No description provided.
KEY COLUMNS:
- user_id : CHAR(36) (NOT NULL) 
- course_id : CHAR(36) (NOT NULL) 
- name : varchar(255) (NOT NULL) 
- update_time : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: transcript_lines
DESCRIPTION: Stores transcript lines records for the application. References related entities via: course, student, term. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- course_id : CHAR(36) 
- term_id : CHAR(36) 
- credits_attempted : numeric(5,2) 
- credits_earned : numeric(5,2) 
- final_letter : text 
- final_numeric : numeric(6,3) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: trips
DESCRIPTION: Stores trip records for the application. Key attributes include destination and purpose. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`. 0 foreign key field(s) detected.
KEY COLUMNS:
- destination : varchar(255) (NOT NULL) 
- purpose : varchar(255) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: turn_in
DESCRIPTION: Input payload for an orchestration turn involving multiple tutors. References related entities via: sessions, tutor_spec. Includes standard audit timestamps (created_at). 5 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- session_id : CHAR(36) (NOT NULL) 
- prompt : text (NOT NULL) 
- objective_code : text (NOT NULL) 
- tutors : JSON (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: tutor_out
DESCRIPTION: Normalized output from a single tutor/agent for a given turn. References related entities via: turn_in. Includes standard audit timestamps (created_at). 6 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- tutor_id : text (NOT NULL) 
- response : text (NOT NULL) 
- evidence : JSON (NOT NULL) 
- score : numeric (NOT NULL) 
- confidence : numeric (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: tutor_spec
DESCRIPTION: No description provided.
KEY COLUMNS:
- tutor_id : CHAR(36) (NOT NULL, UNIQUE) 
- spec_json : json 
- description : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: tutors
DESCRIPTION: Stores AI tutor and human tutor records for the application. Key attributes include name, email, specialization. References related entities via: tutor_spec. Includes standard audit timestamps (created_at, updated_at). Primary key is `id`.
KEY COLUMNS:
- name : varchar(255) (NOT NULL) 
- email : varchar(255) (UNIQUE) 
- specialization : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: unit_standard_map
DESCRIPTION: Joins curriculum_units to standards (M:N).
KEY COLUMNS:
- unit_id : CHAR(36) (PK, NOT NULL) 
- standard_id : CHAR(36) (PK, NOT NULL) 

TABLE: user_accounts
DESCRIPTION: Stores user accounts records for the application. References related entities via: person. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- person_id : CHAR(36) (NOT NULL) 
- username : text (NOT NULL, UNIQUE) 
- password_hash : text 
- is_active : boolean (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: user_profiles
DESCRIPTION: No description provided.
KEY COLUMNS:
- user_id : CHAR(36) (NOT NULL) 
- primary_email : varchar(255) 
- full_name : varchar(255) 
- photo_url : varchar(512) 
- is_teacher : boolean (NOT NULL) 
- is_student : boolean (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: users
DESCRIPTION: Stores users records for the application. Includes standard audit timestamps (created_at, updated_at). Primary key is `id`.
KEY COLUMNS:
- username : text (NOT NULL, UNIQUE) 
- email : text (NOT NULL, UNIQUE) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: vendors
DESCRIPTION: Stores vendors records for the application. Key attributes include name. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- name : varchar(255) (NOT NULL, UNIQUE) 
- contact : json 
- active : boolean (NOT NULL) 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: votes
DESCRIPTION: Stores votes records for the application. References related entities via: motion, voter. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- motion_id : CHAR(36) (NOT NULL) 
- voter_id : CHAR(36) (NOT NULL) 
- value : varchar(16) (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: waivers
DESCRIPTION: Stores waivers records for the application. References related entities via: student. Includes standard audit timestamps (created_at, updated_at). 7 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- student_id : CHAR(36) (NOT NULL) 
- reason : text 
- amount : numeric(10,2) 
- granted_on : date 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: warranties
DESCRIPTION: Stores warranties records for the application. References related entities via: asset, vendor. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- asset_id : CHAR(36) (NOT NULL) 
- vendor_id : CHAR(36) 
- policy_no : varchar(128) 
- start_date : date 
- end_date : date 
- terms : text 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: webhooks
DESCRIPTION: Stores webhooks records for the application. Includes standard audit timestamps (created_at, updated_at). 6 column(s) defined. Primary key is `id`.
KEY COLUMNS:
- target_url : varchar(1024) (NOT NULL) 
- secret : varchar(255) 
- events : JSON 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: work_assignments
DESCRIPTION: No description provided.
KEY COLUMNS:
- event_id : CHAR(36) (NOT NULL) 
- worker_id : CHAR(36) (NOT NULL) 
- stipend_cents : int 
- status : varchar(9) (NOT NULL) 
- assigned_at : timestamp 
- checked_in_at : timestamp 
- completed_at : timestamp 
- id : CHAR(36) (PK, NOT NULL) 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 

TABLE: work_order_parts
DESCRIPTION: Stores work order parts records for the application. References related entities via: part, work order. Includes standard audit timestamps (created_at, updated_at). 9 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- work_order_id : CHAR(36) (NOT NULL) 
- part_id : CHAR(36) 
- qty : numeric(12,2) (NOT NULL) 
- unit_cost : numeric(12,2) 
- extended_cost : numeric(12,2) 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: work_order_tasks
DESCRIPTION: Stores work order tasks records for the application. Key attributes include title. References related entities via: work order. Includes standard audit timestamps (created_at, updated_at). 10 column(s) defined. Primary key is `id`. 1 foreign key field(s) detected.
KEY COLUMNS:
- work_order_id : CHAR(36) (NOT NULL) 
- seq : int (NOT NULL) 
- title : varchar(255) (NOT NULL) 
- is_mandatory : text (NOT NULL) 
- status : varchar(32) 
- completed_at : timestamp 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: work_order_time_logs
DESCRIPTION: Stores work order time logs records for the application. References related entities via: user, work order. Includes standard audit timestamps (created_at, updated_at). 11 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected.
KEY COLUMNS:
- work_order_id : CHAR(36) (NOT NULL) 
- user_id : CHAR(36) 
- started_at : timestamp 
- ended_at : timestamp 
- hours : numeric(10,2) 
- hourly_rate : numeric(12,2) 
- cost : numeric(12,2) 
- notes : text 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: work_orders
DESCRIPTION: Stores work orders records for the application. References related entities via: asset, assigned to user, building, request, school, space. Includes standard audit timestamps (created_at, updated_at). 22 column(s) defined. Primary key is `id`. 6 foreign key field(s) detected.
KEY COLUMNS:
- school_id : CHAR(36) 
- building_id : CHAR(36) 
- space_id : CHAR(36) 
- asset_id : CHAR(36) 
- request_id : CHAR(36) (UNIQUE) 
- status : varchar(32) (NOT NULL) 
- priority : varchar(16) 
- category : varchar(64) 
- summary : varchar(255) (NOT NULL) 
- description : text 
- requested_due_at : timestamp 
- scheduled_start_at : timestamp 
- scheduled_end_at : timestamp 
- completed_at : timestamp 
- assigned_to_user_id : CHAR(36) 
- materials_cost : numeric(12,2) 
- labor_cost : numeric(12,2) 
- other_cost : numeric(12,2) 
- attributes : json 
- created_at : timestamp (NOT NULL) 
- updated_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 

TABLE: workers
DESCRIPTION: No description provided.
KEY COLUMNS:
- first_name : varchar(80) (NOT NULL) 
- last_name : varchar(80) (NOT NULL) 
- created_at : timestamp (NOT NULL) 
- id : CHAR(36) (PK, NOT NULL) 
- updated_at : timestamp (NOT NULL) 
