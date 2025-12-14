# src/OSSS/ai/intents/heuristics/__init__.py
from .apply import HeuristicRule, apply_heuristics
from .staff_info_rules import RULES as STAFF_INFO_RULES
from .student_info_rules import RULES as STUDENT_INFO_RULES
from .enrollment_rules import RULES as ENROLLMENT_RULES
from .incident_rules import RULES as INCIDENT_RULES
from .buildings_rules import RULES as BUILDINGS_RULES
from .assets_rules import RULES as ASSETS_RULES
from .goals_rules import RULES as GOALS_RULES

# ---------------------------------------------------------------------------
# Auto-generated / table-backed rules
# (MUST be imported before ALL_RULES)
# ---------------------------------------------------------------------------

from .academic_terms_rules import RULES as ACADEMIC_TERMS_RULES
from .accommodations_rules import RULES as ACCOMMODATIONS_RULES
from .activities_rules import RULES as ACTIVITIES_RULES
from .addresses_rules import RULES as ADDRESSES_RULES
from .agenda_item_approvals_rules import RULES as AGENDA_ITEM_APPROVALS_RULES
from .agenda_item_files_rules import RULES as AGENDA_ITEM_FILES_RULES
from .agenda_items_rules import RULES as AGENDA_ITEMS_RULES
from .agenda_workflow_steps_rules import RULES as AGENDA_WORKFLOW_STEPS_RULES
from .agenda_workflows_rules import RULES as AGENDA_WORKFLOWS_RULES
from .alignments_rules import RULES as ALIGNMENTS_RULES
from .ap_vendors_rules import RULES as AP_VENDORS_RULES
from .asset_parts_rules import RULES as ASSET_PARTS_RULES
from .assignment_categories_rules import RULES as ASSIGNMENT_CATEGORIES_RULES
from .assignments_rules import RULES as ASSIGNMENTS_RULES
from .attendance_codes_rules import RULES as ATTENDANCE_CODES_RULES
from .attendance_daily_summary_rules import RULES as ATTENDANCE_DAILY_SUMMARY_RULES
from .attendance_events_rules import RULES as ATTENDANCE_EVENTS_RULES
from .attendances_rules import RULES as ATTENDANCES_RULES
from .audit_logs_rules import RULES as AUDIT_LOGS_RULES
from .behavior_codes_rules import RULES as BEHAVIOR_CODES_RULES
from .behavior_interventions_rules import RULES as BEHAVIOR_INTERVENTIONS_RULES
from .bell_schedules_rules import RULES as BELL_SCHEDULES_RULES
from .bus_routes_rules import RULES as BUS_ROUTES_RULES
from .bus_stop_times_rules import RULES as BUS_STOP_TIMES_RULES
from .bus_stops_rules import RULES as BUS_STOPS_RULES
from .calendar_days_rules import RULES as CALENDAR_DAYS_RULES
from .calendars_rules import RULES as CALENDARS_RULES
from .channels_rules import RULES as CHANNELS_RULES
from .class_ranks_rules import RULES as CLASS_RANKS_RULES
from .comm_search_index_rules import RULES as COMM_SEARCH_INDEX_RULES
from .committees_rules import RULES as COMMITTEES_RULES
from .compliance_records_rules import RULES as COMPLIANCE_RECORDS_RULES
from .consents_rules import RULES as CONSENTS_RULES
from .consequence_types_rules import RULES as CONSEQUENCE_TYPES_RULES
from .consequences_rules import RULES as CONSEQUENCES_RULES
from .contacts_rules import RULES as CONTACTS_RULES
from .course_prerequisites_rules import RULES as COURSE_PREREQUISITES_RULES
from .course_sections_rules import RULES as COURSE_SECTIONS_RULES
from .courses_rules import RULES as COURSES_RULES
from .curricula_rules import RULES as CURRICULA_RULES
from .curriculum_units_rules import RULES as CURRICULUM_UNITS_RULES
from .curriculum_versions_rules import RULES as CURRICULUM_VERSIONS_RULES
from .data_quality_issues_rules import RULES as DATA_QUALITY_ISSUES_RULES
from .data_sharing_agreements_rules import RULES as DATA_SHARING_AGREEMENTS_RULES
from .deduction_codes_rules import RULES as DEDUCTION_CODES_RULES
from .deliveries_rules import RULES as DELIVERIES_RULES
from .department_position_index_rules import RULES as DEPARTMENT_POSITION_INDEX_RULES
from .departments_rules import RULES as DEPARTMENTS_RULES
from .document_activity_rules import RULES as DOCUMENT_ACTIVITY_RULES
from .document_links_rules import RULES as DOCUMENT_LINKS_RULES
from .document_notifications_rules import RULES as DOCUMENT_NOTIFICATIONS_RULES
from .document_permissions_rules import RULES as DOCUMENT_PERMISSIONS_RULES
from .document_search_index_rules import RULES as DOCUMENT_SEARCH_INDEX_RULES
from .document_versions_rules import RULES as DOCUMENT_VERSIONS_RULES
from .documents_rules import RULES as DOCUMENTS_RULES
from .earnings_codes_rules import RULES as EARNING_CODES_RULES
from .education_associations_rules import RULES as EDUCATION_ASSOCIATIONS_RULES
from .ell_plans_rules import RULES as ELL_PLANS_RULES
from .embeds_rules import RULES as EMBEDS_RULES
from .emergency_contacts_rules import RULES as EMERGENCY_CONTACTS_RULES
from .employee_deductions_rules import RULES as EMPLOYEE_DEDUCTIONS_RULES
from .employee_earnings_rules import RULES as EMPLOYEE_EARNINGS_RULES
from .entity_tags_rules import RULES as ENTITY_TAGS_RULES
from .evaluation_assignments_rules import RULES as EVALUATION_ASSIGNMENTS_RULES
from .evaluation_cycles_rules import RULES as EVALUATION_CYCLES_RULES
from .evaluation_files_rules import RULES as EVALUATION_FILES_RULES
from .evaluation_questions_rules import RULES as EVALUATION_QUESTIONS_RULES
from .evaluation_reports_rules import RULES as EVALUATION_REPORTS_RULES
from .evaluation_responses_rules import RULES as EVALUATION_RESPONSES_RULES
from .evaluation_sections_rules import RULES as EVALUATION_SECTIONS_RULES
from .evaluation_signoffs_rules import RULES as EVALUATION_SIGNOFFS_RULES
from .evaluation_templates_rules import RULES as EVALUATION_TEMPLATES_RULES
from .events_rules import RULES as EVENTS_RULES
from .export_runs_rules import RULES as EXPORT_RUNS_RULES
from .external_ids_rules import RULES as EXTERNAL_IDS_RULES
from .facilities_rules import RULES as FACILITIES_RULES
from .family_portal_access_rules import RULES as FAMILY_PORTAL_ACCESS_RULES
from .fan_app_settings_rules import RULES as FAN_APP_SETTINGS_RULES
from .fan_pages_rules import RULES as FAN_PAGES_RULES
from .feature_flags_rules import RULES as FEATURE_FLAGS_RULES
from .fees_rules import RULES as FEES_RULES
from .files_rules import RULES as FILES_RULES
from .final_grades_rules import RULES as FINAL_GRADES_RULES
from .fiscal_periods_rules import RULES as FISCAL_PERIODS_RULES
from .fiscal_years_rules import RULES as FISCAL_YEARS_RULES
from .floors_rules import RULES as FLOORS_RULES
from .folders_rules import RULES as FOLDERS_RULES
from .frameworks_rules import RULES as FRAMEWORKS_RULES
from .gl_account_balances_rules import RULES as GL_ACCOUNT_BALANCES_RULES
from .gl_account_segments_rules import RULES as GL_ACCOUNT_SEGMENTS_RULES
from .gl_accounts_rules import RULES as GL_ACCOUNTS_RULES
from .gl_segment_values_rules import RULES as GL_SEGMENT_VALUES_RULES
from .gl_segments_rules import RULES as GL_SEGMENTS_RULES
from .governing_bodies_rules import RULES as GOVERNING_BODIES_RULES
from .gpa_calculations_rules import RULES as GPA_CALCULATIONS_RULES
from .grade_levels_rules import RULES as GRADE_LEVELS_RULES
from .grade_scale_bands_rules import RULES as GRADE_SCALE_BANDS_RULES
from .grade_scales_rules import RULES as GRADE_SCALES_RULES
from .gradebook_entries_rules import RULES as GRADEBOOK_ENTRIES_RULES
from .grading_periods_rules import RULES as GRADING_PERIODS_RULES
from .guardians_rules import RULES as GUARDIANS_RULES
from .health_profiles_rules import RULES as HEALTH_PROFILES_RULES
from .hr_employees_rules import RULES as HR_EMPLOYEES_RULES
from .hr_position_assignments_rules import RULES as HR_POSITION_ASSIGNMENTS_RULES
from .hr_positions_rules import RULES as HR_POSITIONS_RULES
from .iep_plans_rules import RULES as IEP_PLANS_RULES
from .immunization_records_rules import RULES as IMMUNIZATION_RECORDS_RULES
from .immunizations_rules import RULES as IMMUNIZATIONS_RULES
from .incident_participants_rules import RULES as INCIDENT_PARTICIPANTS_RULES
from .incidents_rules import RULES as INCIDENTS_RULES
from .initiatives_rules import RULES as INITIATIVES_RULES
from .invoices_rules import RULES as INVOICES_RULES
from .journal_batches_rules import RULES as JOURNAL_BATCHES_RULES
from .journal_entries_rules import RULES as JOURNAL_ENTRIES_RULES
from .journal_entry_lines_rules import RULES as JOURNAL_ENTRY_LINES_RULES
from .kpi_datapoints_rules import RULES as KPI_DATAPOINTS_RULES
from .kpis_rules import RULES as KPIS_RULES
from .leases_rules import RULES as LEASES_RULES
from .library_checkouts_rules import RULES as LIBRARY_CHECKOUTS_RULES
from .library_fines_rules import RULES as LIBRARY_FINES_RULES
from .library_holds_rules import RULES as LIBRARY_HOLDS_RULES
from .library_items_rules import RULES as LIBRARY_ITEMS_RULES
from .live_scorings_rules import RULES as LIVE_SCORINGS_RULES
from .maintenance_requests_rules import RULES as MAINTENANCE_REQUESTS_RULES
from .materials_rules import RULES as MATERIALS_RULES
from .meal_accounts_rules import RULES as MEAL_ACCOUNTS_RULES
from .meal_eligibility_statuses_rules import RULES as MEAL_ELIGIBILITY_STATUSES_RULES
from .meal_transactions_rules import RULES as MEAL_TRANSACTIONS_RULES
from .medication_administrations_rules import RULES as MEDICATION_ADMINISTRATIONS_RULES
from .medications_rules import RULES as MEDICATIONS_RULES
from .meeting_documents_rules import RULES as MEETING_DOCUMENTS_RULES
from .meeting_files_rules import RULES as MEETING_FILES_RULES
from .meeting_permissions_rules import RULES as MEETING_PERMISSIONS_RULES
from .meeting_publications_rules import RULES as MEETING_PUBLICATIONS_RULES
from .meeting_search_index_rules import RULES as MEETING_SEARCH_INDEX_RULES
from .meetings_rules import RULES as MEETINGS_RULES
from .memberships_rules import RULES as MEMBERSHIPS_RULES
from .message_recipients_rules import RULES as MESSAGE_RECIPIENTS_RULES
from .messages_rules import RULES as MESSAGES_RULES
from .meters_rules import RULES as METERS_RULES
from .minutes_rules import RULES as MINUTES_RULES
from .motions_rules import RULES as MOTIONS_RULES
from .move_orders_rules import RULES as MOVE_ORDERS_RULES
from .notifications_rules import RULES as NOTIFICATIONS_RULES
from .nurse_visits_rules import RULES as NURSE_VISITS_RULES
from .objectives_rules import RULES as OBJECTIVES_RULES
from .order_line_items_rules import RULES as ORDER_LINE_ITEMS_RULES
from .orders_rules import RULES as ORDERS_RULES
from .organizations_rules import RULES as ORGANIZATIONS_RULES
from .pages_rules import RULES as PAGES_RULES
from .part_locations_rules import RULES as PART_LOCATIONS_RULES
from .parts_rules import RULES as PARTS_RULES
from .pay_periods_rules import RULES as PAY_PERIODS_RULES
from .paychecks_rules import RULES as PAYCHECKS_RULES
from .payments_rules import RULES as PAYMENTS_RULES
from .payroll_runs_rules import RULES as PAYROLL_RUNS_RULES
from .periods_rules import RULES as PERIODS_RULES
from .permissions_rules import RULES as PERMISSIONS_RULES
from .person_addresses_rules import RULES as PERSON_ADDRESSES_RULES
from .person_contacts_rules import RULES as PERSON_CONTACTS_RULES
from .personal_notes_rules import RULES as PERSONAL_NOTES_RULES
from .persons_rules import RULES as PERSONS_RULES
from .plan_alignments_rules import RULES as PLAN_ALIGNMENTS_RULES
from .plan_assignments_rules import RULES as PLAN_ASSIGNMENTS_RULES
from .plan_filters_rules import RULES as PLAN_FILTERS_RULES
from .plan_search_index_rules import RULES as PLAN_SEARCH_INDEX_RULES
from .plans_rules import RULES as PLANS_RULES
from .pm_plans_rules import RULES as PM_PLANS_RULES
from .pm_work_generators_rules import RULES as PM_WORK_GENERATORS_RULES
from .policies_rules import RULES as POLICIES_RULES
from .policy_approvals_rules import RULES as POLICY_APPROVALS_RULES
from .policy_comments_rules import RULES as POLICY_COMMENTS_RULES
from .policy_files_rules import RULES as POLICY_FILES_RULES
from .policy_legal_refs_rules import RULES as POLICY_LEGAL_REFS_RULES
from .policy_publications_rules import RULES as POLICY_PUBLICATIONS_RULES
from .policy_search_index_rules import RULES as POLICY_SEARCH_INDEX_RULES
from .policy_versions_rules import RULES as POLICY_VERSIONS_RULES
from .policy_workflow_steps_rules import RULES as POLICY_WORKFLOW_STEPS_RULES
from .policy_workflows_rules import RULES as POLICY_WORKFLOWS_RULES
from .post_attachments_rules import RULES as POST_ATTACHMENTS_RULES
from .posts_rules import RULES as POSTS_RULES
from .project_tasks_rules import RULES as PROJECT_TASKS_RULES
from .projects_rules import RULES as PROJECTS_RULES
from .proposal_documents_rules import RULES as PROPOSAL_DOCUMENTS_RULES
from .proposal_reviews_rules import RULES as PROPOSAL_REVIEWS_RULES
from .proposals_rules import RULES as PROPOSALS_RULES
from .publications_rules import RULES as PUBLICATIONS_RULES
from .report_cards_rules import RULES as REPORT_CARDS_RULES
from .requirements_rules import RULES as REQUIREMENTS_RULES
from .resolutions_rules import RULES as RESOLUTIONS_RULES
from .retention_rules_rules import RULES as RETENTION_RULES_RULES
from .review_requests_rules import RULES as REVIEW_REQUESTS_RULES
from .review_rounds_rules import RULES as REVIEW_ROUNDS_RULES
from .reviews_rules import RULES as REVIEWS_RULES
from .role_permissions_rules import RULES as ROLE_PERMISSIONS_RULES
from .roles_rules import RULES as ROLES_RULES
from .rooms_rules import RULES as ROOMS_RULES
from .round_decisions_rules import RULES as ROUND_DECISIONS_RULES
from .scan_requests_rules import RULES as SCAN_REQUESTS_RULES
from .scan_results_rules import RULES as SCAN_RESULTS_RULES
from .schools_rules import RULES as SCHOOLS_RULES
from .scorecard_kpis_rules import RULES as SCORECARD_KPIS_RULES
from .scorecards_rules import RULES as SCORECARDS_RULES
from .section504_plans_rules import RULES as SECTION504_PLANS_RULES
from .section_meetings_rules import RULES as SECTION_MEETINGS_RULES
from .section_room_assignments_rules import RULES as SECTION_ROOM_ASSIGNMENTS_RULES
from .sis_import_jobs_rules import RULES as SIS_IMPORT_JOBS_RULES
from .space_reservations_rules import RULES as SPACE_RESERVATIONS_RULES
from .spaces_rules import RULES as SPACES_RULES
from .special_education_cases_rules import RULES as SPECIAL_EDUCATION_CASES_RULES
from .staff_rules import RULES as STAFF_RULES
from .standardized_tests_rules import RULES as STANDARDIZED_TESTS_RULES
from .standards_rules import RULES as STANDARDS_RULES
from .state_reporting_snapshots_rules import RULES as STATE_REPORTING_SNAPSHOTS_RULES
from .states_rules import RULES as STATES_RULES
from .student_guardians_rules import RULES as STUDENT_GUARDIANS_RULES
from .student_program_enrollments_rules import RULES as STUDENT_PROGRAM_ENROLLMENTS_RULES
from .student_school_enrollments_rules import RULES as STUDENT_SCHOOL_ENROLLMENTS_RULES
from .student_section_enrollments_rules import RULES as STUDENT_SECTION_ENROLLMENTS_RULES
from .student_transportation_assignments_rules import RULES as STUDENT_TRANSPORTATION_ASSIGNMENTS_RULES
from .students_rules import RULES as STUDENTS_RULES
from .subjects_rules import RULES as SUBJECTS_RULES
from .subscriptions_rules import RULES as SUBSCRIPTIONS_RULES
from .tags_rules import RULES as TAGS_RULES
from .teacher_section_assignments_rules import RULES as TEACHER_SECTION_ASSIGNMENTS_RULES
from .test_administrations_rules import RULES as TEST_ADMINISTRATIONS_RULES
from .test_results_rules import RULES as TEST_RESULTS_RULES
from .ticket_scans_rules import RULES as TICKET_SCANS_RULES
from .ticket_types_rules import RULES as TICKET_TYPES_RULES
from .tickets_rules import RULES as TICKETS_RULES
from .transcript_lines_rules import RULES as TRANSCRIPT_LINES_RULES
from .user_accounts_rules import RULES as USER_ACCOUNTS_RULES
from .users_rules import RULES as USERS_RULES
from .vendors_rules import RULES as VENDORS_RULES
from .votes_rules import RULES as VOTES_RULES
from .waivers_rules import RULES as WAIVERS_RULES
from .warranties_rules import RULES as WARRANTIES_RULES
from .webhooks_rules import RULES as WEBHOOKS_RULES
from .work_order_parts_rules import RULES as WORK_ORDER_PARTS_RULES
from .work_order_tasks_rules import RULES as WORK_ORDER_TASKS_RULES
from .work_order_time_logs_rules import RULES as WORK_ORDER_TIME_LOGS_RULES
from .work_orders_rules import RULES as WORK_ORDERS_RULES

ALL_RULES = [
    *STAFF_INFO_RULES,
    *STUDENT_INFO_RULES,
    *ENROLLMENT_RULES,
    *INCIDENT_RULES,
    *BUILDINGS_RULES,
    *ASSETS_RULES,
    *GOALS_RULES,
    *ACADEMIC_TERMS_RULES,
    *ACCOMMODATIONS_RULES,
    *ACTIVITIES_RULES,
    *ADDRESSES_RULES,
    *AGENDA_ITEM_APPROVALS_RULES,
    *AGENDA_ITEM_FILES_RULES,
    *AGENDA_ITEMS_RULES,
    *AGENDA_WORKFLOW_STEPS_RULES,
    *AGENDA_WORKFLOWS_RULES,
    *ALIGNMENTS_RULES,
    *AP_VENDORS_RULES,
    *ASSET_PARTS_RULES,
    *ASSIGNMENT_CATEGORIES_RULES,
    *ASSIGNMENTS_RULES,
    *ATTENDANCE_CODES_RULES,
    *ATTENDANCE_DAILY_SUMMARY_RULES,
    *ATTENDANCE_EVENTS_RULES,
    *ATTENDANCES_RULES,
    *AUDIT_LOGS_RULES,
    *BEHAVIOR_CODES_RULES,
    *BEHAVIOR_INTERVENTIONS_RULES,
    *BELL_SCHEDULES_RULES,
    *BUS_ROUTES_RULES,
    *BUS_STOP_TIMES_RULES,
    *BUS_STOPS_RULES,
    *CALENDAR_DAYS_RULES,
    *CALENDARS_RULES,
    *CHANNELS_RULES,
    *CLASS_RANKS_RULES,
    *COMM_SEARCH_INDEX_RULES,
    *COMMITTEES_RULES,
    *COMPLIANCE_RECORDS_RULES,
    *CONSENTS_RULES,
    *CONSEQUENCE_TYPES_RULES,
    *CONSEQUENCES_RULES,
    *CONTACTS_RULES,
    *COURSE_PREREQUISITES_RULES,
    *COURSE_SECTIONS_RULES,
    *COURSES_RULES,
    *CURRICULA_RULES,
    *CURRICULUM_UNITS_RULES,
    *CURRICULUM_VERSIONS_RULES,
    *DATA_QUALITY_ISSUES_RULES,
    *DATA_SHARING_AGREEMENTS_RULES,
    *DEDUCTION_CODES_RULES,
    *DELIVERIES_RULES,
    *DEPARTMENT_POSITION_INDEX_RULES,
    *DEPARTMENTS_RULES,
    *DOCUMENT_ACTIVITY_RULES,
    *DOCUMENT_LINKS_RULES,
    *DOCUMENT_NOTIFICATIONS_RULES,
    *DOCUMENT_PERMISSIONS_RULES,
    *DOCUMENT_SEARCH_INDEX_RULES,
    *DOCUMENT_VERSIONS_RULES,
    *DOCUMENTS_RULES,
    *EARNING_CODES_RULES,
    *EDUCATION_ASSOCIATIONS_RULES,
    *ELL_PLANS_RULES,
    *EMBEDS_RULES,
    *EMERGENCY_CONTACTS_RULES,
    *EMPLOYEE_DEDUCTIONS_RULES,
    *EMPLOYEE_EARNINGS_RULES,
    *ENTITY_TAGS_RULES,
    *EVALUATION_ASSIGNMENTS_RULES,
    *EVALUATION_CYCLES_RULES,
    *EVALUATION_FILES_RULES,
    *EVALUATION_QUESTIONS_RULES,
    *EVALUATION_REPORTS_RULES,
    *EVALUATION_RESPONSES_RULES,
    *EVALUATION_SECTIONS_RULES,
    *EVALUATION_SIGNOFFS_RULES,
    *EVALUATION_TEMPLATES_RULES,
    *EXPORT_RUNS_RULES,
    *EXTERNAL_IDS_RULES,
    *FACILITIES_RULES,
    *FAMILY_PORTAL_ACCESS_RULES,
    *FAN_APP_SETTINGS_RULES,
    *FAN_PAGES_RULES,
    *FEATURE_FLAGS_RULES,
    *FEES_RULES,
    *FINAL_GRADES_RULES,
    *FISCAL_PERIODS_RULES,
    *FISCAL_YEARS_RULES,
    *FLOORS_RULES,
    *FOLDERS_RULES,
    *FRAMEWORKS_RULES,
    *GL_ACCOUNT_BALANCES_RULES,
    *GL_ACCOUNT_SEGMENTS_RULES,
    *GL_ACCOUNTS_RULES,
    *GL_SEGMENT_VALUES_RULES,
    *GL_SEGMENTS_RULES,
    *GOVERNING_BODIES_RULES,
    *GPA_CALCULATIONS_RULES,
    *GRADE_LEVELS_RULES,
    *GRADE_SCALE_BANDS_RULES,
    *GRADE_SCALES_RULES,
    *GRADEBOOK_ENTRIES_RULES,
    *GRADING_PERIODS_RULES,
    *GUARDIANS_RULES,
    *HEALTH_PROFILES_RULES,
    *HR_EMPLOYEES_RULES,
    *HR_POSITION_ASSIGNMENTS_RULES,
    *HR_POSITIONS_RULES,
    *IEP_PLANS_RULES,
    *IMMUNIZATION_RECORDS_RULES,
    *IMMUNIZATIONS_RULES,
    *INCIDENT_PARTICIPANTS_RULES,
    *INCIDENTS_RULES,
    *INITIATIVES_RULES,
    *INVOICES_RULES,
    *JOURNAL_BATCHES_RULES,
    *JOURNAL_ENTRIES_RULES,
    *JOURNAL_ENTRY_LINES_RULES,
    *KPI_DATAPOINTS_RULES,
    *KPIS_RULES,
    *LEASES_RULES,
    *LIBRARY_CHECKOUTS_RULES,
    *LIBRARY_FINES_RULES,
    *LIBRARY_HOLDS_RULES,
    *LIBRARY_ITEMS_RULES,
    *LIVE_SCORINGS_RULES,
    *MAINTENANCE_REQUESTS_RULES,
    *MATERIALS_RULES,
    *MEAL_ACCOUNTS_RULES,
    *MEAL_ELIGIBILITY_STATUSES_RULES,
    *MEAL_TRANSACTIONS_RULES,
    *MEDICATION_ADMINISTRATIONS_RULES,
    *MEDICATIONS_RULES,
    *MEETING_DOCUMENTS_RULES,
    *MEETING_FILES_RULES,
    *MEETING_PERMISSIONS_RULES,
    *MEETING_PUBLICATIONS_RULES,
    *MEETING_SEARCH_INDEX_RULES,
    *MEETINGS_RULES,
    *MEMBERSHIPS_RULES,
    *MESSAGE_RECIPIENTS_RULES,
    *MESSAGES_RULES,
    *METERS_RULES,
    *MINUTES_RULES,
    *MOTIONS_RULES,
    *MOVE_ORDERS_RULES,
    *NURSE_VISITS_RULES,
    *OBJECTIVES_RULES,
    *ORDER_LINE_ITEMS_RULES,
    *ORGANIZATIONS_RULES,
    *PART_LOCATIONS_RULES,
    *PAY_PERIODS_RULES,
    *PAYCHECKS_RULES,
    *PAYMENTS_RULES,
    *PAYROLL_RUNS_RULES,
    *PERSON_ADDRESSES_RULES,
    *PERSON_CONTACTS_RULES,
    *PERSONAL_NOTES_RULES,
    *PERSONS_RULES,
    *PLAN_ALIGNMENTS_RULES,
    *PLAN_ASSIGNMENTS_RULES,
    *PLAN_FILTERS_RULES,
    *PLAN_SEARCH_INDEX_RULES,
    *PM_PLANS_RULES,
    *PM_WORK_GENERATORS_RULES,
    *POLICIES_RULES,
    *POLICY_APPROVALS_RULES,
    *POLICY_COMMENTS_RULES,
    *POLICY_FILES_RULES,
    *POLICY_LEGAL_REFS_RULES,
    *POLICY_PUBLICATIONS_RULES,
    *POLICY_SEARCH_INDEX_RULES,
    *POLICY_VERSIONS_RULES,
    *POLICY_WORKFLOW_STEPS_RULES,
    *POLICY_WORKFLOWS_RULES,
    *POST_ATTACHMENTS_RULES,
    *POSTS_RULES,
    *PROJECT_TASKS_RULES,
    *PROJECTS_RULES,
    *PROPOSAL_DOCUMENTS_RULES,
    *PROPOSAL_REVIEWS_RULES,
    *PROPOSALS_RULES,
    *REPORT_CARDS_RULES,
    *REQUIREMENTS_RULES,
    *RESOLUTIONS_RULES,
    *RETENTION_RULES_RULES,
    *REVIEW_REQUESTS_RULES,
    *REVIEW_ROUNDS_RULES,
    *ROLE_PERMISSIONS_RULES,
    *ROLES_RULES,
    *ROOMS_RULES,
    *ROUND_DECISIONS_RULES,
    *SCAN_REQUESTS_RULES,
    *SCAN_RESULTS_RULES,
    *SCHOOLS_RULES,
    *SCORECARD_KPIS_RULES,
    *SCORECARDS_RULES,
    *SECTION504_PLANS_RULES,
    *SECTION_MEETINGS_RULES,
    *SECTION_ROOM_ASSIGNMENTS_RULES,
    *SIS_IMPORT_JOBS_RULES,
    *SPACE_RESERVATIONS_RULES,
    *SPACES_RULES,
    *SPECIAL_EDUCATION_CASES_RULES,
    *STAFF_RULES,
    *STANDARDIZED_TESTS_RULES,
    *STANDARDS_RULES,
    *STATE_REPORTING_SNAPSHOTS_RULES,
    *STATES_RULES,
    *STUDENT_GUARDIANS_RULES,
    *STUDENT_PROGRAM_ENROLLMENTS_RULES,
    *STUDENT_SCHOOL_ENROLLMENTS_RULES,
    *STUDENT_SECTION_ENROLLMENTS_RULES,
    *STUDENT_TRANSPORTATION_ASSIGNMENTS_RULES,
    *STUDENTS_RULES,
    *SUBJECTS_RULES,
    *SUBSCRIPTIONS_RULES,
    *TEACHER_SECTION_ASSIGNMENTS_RULES,
    *TEST_ADMINISTRATIONS_RULES,
    *TEST_RESULTS_RULES,
    *TICKET_SCANS_RULES,
    *TICKET_TYPES_RULES,
    *TICKETS_RULES,
    *TRANSCRIPT_LINES_RULES,
    *USER_ACCOUNTS_RULES,
    *USERS_RULES,
    *VOTES_RULES,
    *WAIVERS_RULES,
    *WARRANTIES_RULES,
    *WEBHOOKS_RULES,
    *WORK_ORDER_PARTS_RULES,
    *WORK_ORDER_TASKS_RULES,
    *WORK_ORDER_TIME_LOGS_RULES,
    *WORK_ORDERS_RULES,
]

__all__ = [
    "HeuristicRule",
    "apply_heuristics",
    "ALL_RULES",
]
