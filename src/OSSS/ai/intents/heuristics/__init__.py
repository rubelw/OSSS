# src/OSSS/ai/intents/heuristics/__init__.py
from .apply import HeuristicRule, apply_heuristics
from .show_staffs_rules import RULES as SHOW_STAFFS_RULES
from .show_students_rules import RULES as SHOW_STUDENTS_RULES
from .show_enrollment_rules import RULES as SHOW_ENROLLMENT_RULES
from .show_incident_rules import RULES as SHOW_INCIDENT_RULES
from .show_buildings_rules import RULES as SHOW_BUILDINGS_RULES
from .show_assets_rules import RULES as SHOW_ASSETS_RULES
from .show_goals_rules import RULES as SHOW_GOALS_RULES

# ---------------------------------------------------------------------------
# Auto-generated / table-backed rules
# (MUST be imported before ALL_RULES)
# ---------------------------------------------------------------------------

from .show_academic_terms_rules import RULES as SHOW_ACADEMIC_TERMS_RULES
from .show_accommodations_rules import RULES as SHOW_ACCOMMODATIONS_RULES
from .show_activities_rules import RULES as SHOW_ACTIVITIES_RULES
from .show_addresses_rules import RULES as SHOW_ADDRESSES_RULES
from .show_agenda_item_approvals_rules import RULES as SHOW_AGENDA_ITEM_APPROVALS_RULES
from .show_agenda_item_files_rules import RULES as SHOW_AGENDA_ITEM_FILES_RULES
from .show_agenda_items_rules import RULES as SHOW_AGENDA_ITEMS_RULES
from .show_agenda_workflow_steps_rules import RULES as SHOW_AGENDA_WORKFLOW_STEPS_RULES
from .show_agenda_workflows_rules import RULES as SHOW_AGENDA_WORKFLOWS_RULES
from .show_alignments_rules import RULES as SHOW_ALIGNMENTS_RULES
from .show_ap_vendors_rules import RULES as SHOW_AP_VENDORS_RULES
from .show_asset_parts_rules import RULES as SHOW_ASSET_PARTS_RULES
from .show_assignment_categories_rules import RULES as SHOW_ASSIGNMENT_CATEGORIES_RULES
from .show_assignments_rules import RULES as SHOW_ASSIGNMENTS_RULES
from .show_attendance_codes_rules import RULES as SHOW_ATTENDANCE_CODES_RULES
from .show_attendance_daily_summary_rules import RULES as SHOW_ATTENDANCE_DAILY_SUMMARY_RULES
from .show_attendance_events_rules import RULES as SHOW_ATTENDANCE_EVENTS_RULES
from .show_attendances_rules import RULES as SHOW_ATTENDANCES_RULES
from .show_audit_logs_rules import RULES as SHOW_AUDIT_LOGS_RULES
from .show_behavior_codes_rules import RULES as SHOW_BEHAVIOR_CODES_RULES
from .show_behavior_interventions_rules import RULES as SHOW_BEHAVIOR_INTERVENTIONS_RULES
from .show_bell_schedules_rules import RULES as SHOW_BELL_SCHEDULES_RULES
from .show_bus_routes_rules import RULES as SHOW_BUS_ROUTES_RULES
from .show_bus_stop_times_rules import RULES as SHOW_BUS_STOP_TIMES_RULES
from .show_bus_stops_rules import RULES as SHOW_BUS_STOPS_RULES
from .show_calendar_days_rules import RULES as SHOW_CALENDAR_DAYS_RULES
from .show_calendars_rules import RULES as SHOW_CALENDARS_RULES
from .show_channels_rules import RULES as SHOW_CHANNELS_RULES
from .show_class_ranks_rules import RULES as SHOW_CLASS_RANKS_RULES
from .show_comm_search_index_rules import RULES as SHOW_COMM_SEARCH_INDEX_RULES
from .show_committees_rules import RULES as SHOW_COMMITTEES_RULES
from .show_compliance_records_rules import RULES as SHOW_COMPLIANCE_RECORDS_RULES
from .show_consents_rules import RULES as SHOW_CONSENTS_RULES
from .show_consequence_types_rules import RULES as SHOW_CONSEQUENCE_TYPES_RULES
from .show_consequences_rules import RULES as SHOW_CONSEQUENCES_RULES
from .show_contacts_rules import RULES as SHOW_CONTACTS_RULES
from .show_course_prerequisites_rules import RULES as SHOW_COURSE_PREREQUISITES_RULES
from .show_course_sections_rules import RULES as SHOW_COURSE_SECTIONS_RULES
from .show_courses_rules import RULES as SHOW_COURSES_RULES
from .show_curricula_rules import RULES as SHOW_CURRICULA_RULES
from .show_curriculum_units_rules import RULES as SHOW_CURRICULUM_UNITS_RULES
from .show_curriculum_versions_rules import RULES as SHOW_CURRICULUM_VERSIONS_RULES
from .show_data_quality_issues_rules import RULES as SHOW_DATA_QUALITY_ISSUES_RULES
from .show_data_sharing_agreements_rules import RULES as SHOW_DATA_SHARING_AGREEMENTS_RULES
from .show_deduction_codes_rules import RULES as SHOW_DEDUCTION_CODES_RULES
from .show_deliveries_rules import RULES as SHOW_DELIVERIES_RULES
from .show_department_position_index_rules import RULES as SHOW_DEPARTMENT_POSITION_INDEX_RULES
from .show_departments_rules import RULES as SHOW_DEPARTMENTS_RULES
from .show_document_activity_rules import RULES as SHOW_DOCUMENT_ACTIVITY_RULES
from .show_document_links_rules import RULES as SHOW_DOCUMENT_LINKS_RULES
from .show_document_notifications_rules import RULES as SHOW_DOCUMENT_NOTIFICATIONS_RULES
from .show_document_permissions_rules import RULES as SHOW_DOCUMENT_PERMISSIONS_RULES
from .show_document_search_index_rules import RULES as SHOW_DOCUMENT_SEARCH_INDEX_RULES
from .show_document_versions_rules import RULES as SHOW_DOCUMENT_VERSIONS_RULES
from .show_documents_rules import RULES as SHOW_DOCUMENTS_RULES
from .show_earnings_codes_rules import RULES as SHOW_EARNING_CODES_RULES
from .show_education_associations_rules import RULES as SHOW_EDUCATION_ASSOCIATIONS_RULES
from .show_ell_plans_rules import RULES as SHOW_ELL_PLANS_RULES
from .show_embeds_rules import RULES as SHOW_EMBEDS_RULES
from .show_emergency_contacts_rules import RULES as SHOW_EMERGENCY_CONTACTS_RULES
from .show_employee_deductions_rules import RULES as SHOW_EMPLOYEE_DEDUCTIONS_RULES
from .show_employee_earnings_rules import RULES as SHOW_EMPLOYEE_EARNINGS_RULES
from .show_entity_tags_rules import RULES as SHOW_ENTITY_TAGS_RULES
from .show_evaluation_assignments_rules import RULES as SHOW_EVALUATION_ASSIGNMENTS_RULES
from .show_evaluation_cycles_rules import RULES as SHOW_EVALUATION_CYCLES_RULES
from .show_evaluation_files_rules import RULES as SHOW_EVALUATION_FILES_RULES
from .show_evaluation_questions_rules import RULES as SHOW_EVALUATION_QUESTIONS_RULES
from .show_evaluation_reports_rules import RULES as SHOW_EVALUATION_REPORTS_RULES
from .show_evaluation_responses_rules import RULES as SHOW_EVALUATION_RESPONSES_RULES
from .show_evaluation_sections_rules import RULES as SHOW_EVALUATION_SECTIONS_RULES
from .show_evaluation_signoffs_rules import RULES as SHOW_EVALUATION_SIGNOFFS_RULES
from .show_evaluation_templates_rules import RULES as SHOW_EVALUATION_TEMPLATES_RULES
from .show_events_rules import RULES as SHOW_EVENTS_RULES
from .show_export_runs_rules import RULES as SHOW_EXPORT_RUNS_RULES
from .show_external_ids_rules import RULES as SHOW_EXTERNAL_IDS_RULES
from .show_facilities_rules import RULES as SHOW_FACILITIES_RULES
from .show_family_portal_access_rules import RULES as SHOW_FAMILY_PORTAL_ACCESS_RULES
from .show_fan_app_settings_rules import RULES as SHOW_FAN_APP_SETTINGS_RULES
from .show_fan_pages_rules import RULES as SHOW_FAN_PAGES_RULES
from .show_feature_flags_rules import RULES as SHOW_FEATURE_FLAGS_RULES
from .show_fees_rules import RULES as SHOW_FEES_RULES
from .show_files_rules import RULES as SHOW_FILES_RULES
from .show_final_grades_rules import RULES as SHOW_FINAL_GRADES_RULES
from .show_fiscal_periods_rules import RULES as SHOW_FISCAL_PERIODS_RULES
from .show_fiscal_years_rules import RULES as SHOW_FISCAL_YEARS_RULES
from .show_floors_rules import RULES as SHOW_FLOORS_RULES
from .show_folders_rules import RULES as SHOW_FOLDERS_RULES
from .show_frameworks_rules import RULES as SHOW_FRAMEWORKS_RULES
from .show_gl_account_balances_rules import RULES as SHOW_GL_ACCOUNT_BALANCES_RULES
from .show_gl_account_segments_rules import RULES as SHOW_GL_ACCOUNT_SEGMENTS_RULES
from .show_gl_accounts_rules import RULES as SHOW_GL_ACCOUNTS_RULES
from .show_gl_segment_values_rules import RULES as SHOW_GL_SEGMENT_VALUES_RULES
from .show_gl_segments_rules import RULES as SHOW_GL_SEGMENTS_RULES
from .show_governing_bodies_rules import RULES as SHOW_GOVERNING_BODIES_RULES
from .show_gpa_calculations_rules import RULES as SHOW_GPA_CALCULATIONS_RULES
from .show_grade_levels_rules import RULES as SHOW_GRADE_LEVELS_RULES
from .show_grade_scale_bands_rules import RULES as SHOW_GRADE_SCALE_BANDS_RULES
from .show_grade_scales_rules import RULES as SHOW_GRADE_SCALES_RULES
from .show_gradebook_entries_rules import RULES as SHOW_GRADEBOOK_ENTRIES_RULES
from .show_grading_periods_rules import RULES as SHOW_GRADING_PERIODS_RULES
from .show_guardians_rules import RULES as SHOW_GUARDIANS_RULES
from .show_health_profiles_rules import RULES as SHOW_HEALTH_PROFILES_RULES
from .show_hr_employees_rules import RULES as SHOW_HR_EMPLOYEES_RULES
from .show_hr_position_assignments_rules import RULES as SHOW_HR_POSITION_ASSIGNMENTS_RULES
from .show_hr_positions_rules import RULES as SHOW_HR_POSITIONS_RULES
from .show_iep_plans_rules import RULES as SHOW_IEP_PLANS_RULES
from .show_immunization_records_rules import RULES as SHOW_IMMUNIZATION_RECORDS_RULES
from .show_immunizations_rules import RULES as SHOW_IMMUNIZATIONS_RULES
from .show_incident_participants_rules import RULES as SHOW_INCIDENT_PARTICIPANTS_RULES
from .show_incidents_rules import RULES as SHOW_INCIDENTS_RULES
from .show_initiatives_rules import RULES as SHOW_INITIATIVES_RULES
from .show_invoices_rules import RULES as SHOW_INVOICES_RULES
from .show_journal_batches_rules import RULES as SHOW_JOURNAL_BATCHES_RULES
from .show_journal_entries_rules import RULES as SHOW_JOURNAL_ENTRIES_RULES
from .show_journal_entry_lines_rules import RULES as SHOW_JOURNAL_ENTRY_LINES_RULES
from .show_kpi_datapoints_rules import RULES as SHOW_KPI_DATAPOINTS_RULES
from .show_kpis_rules import RULES as SHOW_KPIS_RULES
from .show_leases_rules import RULES as SHOW_LEASES_RULES
from .show_library_checkouts_rules import RULES as SHOW_LIBRARY_CHECKOUTS_RULES
from .show_library_fines_rules import RULES as SHOW_LIBRARY_FINES_RULES
from .show_library_holds_rules import RULES as SHOW_LIBRARY_HOLDS_RULES
from .show_library_items_rules import RULES as SHOW_LIBRARY_ITEMS_RULES
from .show_live_scorings_rules import RULES as SHOW_LIVE_SCORINGS_RULES
from .show_maintenance_requests_rules import RULES as SHOW_MAINTENANCE_REQUESTS_RULES
from .show_materials_rules import RULES as SHOW_MATERIALS_RULES
from .show_meal_accounts_rules import RULES as SHOW_MEAL_ACCOUNTS_RULES
from .show_meal_eligibility_statuses_rules import RULES as SHOW_MEAL_ELIGIBILITY_STATUSES_RULES
from .show_meal_transactions_rules import RULES as SHOW_MEAL_TRANSACTIONS_RULES
from .show_medication_administrations_rules import RULES as SHOW_MEDICATION_ADMINISTRATIONS_RULES
from .show_medications_rules import RULES as SHOW_MEDICATIONS_RULES
from .show_meeting_documents_rules import RULES as SHOW_MEETING_DOCUMENTS_RULES
from .show_meeting_files_rules import RULES as SHOW_MEETING_FILES_RULES
from .show_meeting_permissions_rules import RULES as SHOW_MEETING_PERMISSIONS_RULES
from .show_meeting_publications_rules import RULES as SHOW_MEETING_PUBLICATIONS_RULES
from .show_meeting_search_index_rules import RULES as SHOW_MEETING_SEARCH_INDEX_RULES
from .show_meetings_rules import RULES as SHOW_MEETINGS_RULES
from .show_memberships_rules import RULES as SHOW_MEMBERSHIPS_RULES
from .show_message_recipients_rules import RULES as SHOW_MESSAGE_RECIPIENTS_RULES
from .show_messages_rules import RULES as SHOW_MESSAGES_RULES
from .show_meters_rules import RULES as SHOW_METERS_RULES
from .show_minutes_rules import RULES as SHOW_MINUTES_RULES
from .show_motions_rules import RULES as SHOW_MOTIONS_RULES
from .show_move_orders_rules import RULES as SHOW_MOVE_ORDERS_RULES
from .show_notifications_rules import RULES as SHOW_NOTIFICATIONS_RULES
from .show_nurse_visits_rules import RULES as SHOW_NURSE_VISITS_RULES
from .show_objectives_rules import RULES as SHOW_OBJECTIVES_RULES
from .show_order_line_items_rules import RULES as SHOW_ORDER_LINE_ITEMS_RULES
from .show_orders_rules import RULES as SHOW_ORDERS_RULES
from .show_organizations_rules import RULES as SHOW_ORGANIZATIONS_RULES
from .show_pages_rules import RULES as SHOW_PAGES_RULES
from .show_part_locations_rules import RULES as SHOW_PART_LOCATIONS_RULES
from .show_parts_rules import RULES as SHOW_PARTS_RULES
from .show_pay_periods_rules import RULES as SHOW_PAY_PERIODS_RULES
from .show_paychecks_rules import RULES as SHOW_PAYCHECKS_RULES
from .show_payments_rules import RULES as SHOW_PAYMENTS_RULES
from .show_payroll_runs_rules import RULES as SHOW_PAYROLL_RUNS_RULES
from .show_periods_rules import RULES as SHOW_PERIODS_RULES
from .show_permissions_rules import RULES as SHOW_PERMISSIONS_RULES
from .show_person_addresses_rules import RULES as SHOW_PERSON_ADDRESSES_RULES
from .show_person_contacts_rules import RULES as SHOW_PERSON_CONTACTS_RULES
from .show_personal_notes_rules import RULES as SHOW_PERSONAL_NOTES_RULES
from .show_persons_rules import RULES as SHOW_PERSONS_RULES
from .show_plan_alignments_rules import RULES as SHOW_PLAN_ALIGNMENTS_RULES
from .show_plan_assignments_rules import RULES as SHOW_PLAN_ASSIGNMENTS_RULES
from .show_plan_filters_rules import RULES as SHOW_PLAN_FILTERS_RULES
from .show_plan_search_index_rules import RULES as SHOW_PLAN_SEARCH_INDEX_RULES
from .show_plans_rules import RULES as SHOW_PLANS_RULES
from .show_pm_plans_rules import RULES as SHOW_PM_PLANS_RULES
from .show_pm_work_generators_rules import RULES as SHOW_PM_WORK_GENERATORS_RULES
from .show_policies_rules import RULES as SHOW_POLICIES_RULES
from .show_policy_approvals_rules import RULES as SHOW_POLICY_APPROVALS_RULES
from .show_policy_comments_rules import RULES as SHOW_POLICY_COMMENTS_RULES
from .show_policy_files_rules import RULES as SHOW_POLICY_FILES_RULES
from .show_policy_legal_refs_rules import RULES as SHOW_POLICY_LEGAL_REFS_RULES
from .show_policy_publications_rules import RULES as SHOW_POLICY_PUBLICATIONS_RULES
from .show_policy_search_index_rules import RULES as SHOW_POLICY_SEARCH_INDEX_RULES
from .show_policy_versions_rules import RULES as SHOW_POLICY_VERSIONS_RULES
from .show_policy_workflow_steps_rules import RULES as SHOW_POLICY_WORKFLOW_STEPS_RULES
from .show_policy_workflows_rules import RULES as SHOW_POLICY_WORKFLOWS_RULES
from .show_post_attachments_rules import RULES as SHOW_POST_ATTACHMENTS_RULES
from .show_posts_rules import RULES as SHOW_POSTS_RULES
from .show_project_tasks_rules import RULES as SHOW_PROJECT_TASKS_RULES
from .show_projects_rules import RULES as SHOW_PROJECTS_RULES
from .show_proposal_documents_rules import RULES as SHOW_PROPOSAL_DOCUMENTS_RULES
from .show_proposal_reviews_rules import RULES as SHOW_PROPOSAL_REVIEWS_RULES
from .show_proposals_rules import RULES as SHOW_PROPOSALS_RULES
from .show_publications_rules import RULES as SHOW_PUBLICATIONS_RULES
from .show_report_cards_rules import RULES as SHOW_REPORT_CARDS_RULES
from .show_requirements_rules import RULES as SHOW_REQUIREMENTS_RULES
from .show_resolutions_rules import RULES as SHOW_RESOLUTIONS_RULES
from .show_retention_rules_rules import RULES as SHOW_RETENTION_RULES_RULES
from .show_review_requests_rules import RULES as SHOW_REVIEW_REQUESTS_RULES
from .show_review_rounds_rules import RULES as SHOW_REVIEW_ROUNDS_RULES
from .show_reviews_rules import RULES as SHOW_REVIEWS_RULES
from .show_role_permissions_rules import RULES as SHOW_ROLE_PERMISSIONS_RULES
from .show_roles_rules import RULES as SHOW_ROLES_RULES
from .show_rooms_rules import RULES as SHOW_ROOMS_RULES
from .show_round_decisions_rules import RULES as SHOW_ROUND_DECISIONS_RULES
from .show_scan_requests_rules import RULES as SHOW_SCAN_REQUESTS_RULES
from .show_scan_results_rules import RULES as SHOW_SCAN_RESULTS_RULES
from .show_schools_rules import RULES as SHOW_SCHOOLS_RULES
from .show_scorecard_kpis_rules import RULES as SHOW_SCORECARD_KPIS_RULES
from .show_scorecards_rules import RULES as SHOW_SCORECARDS_RULES
from .show_section504_plans_rules import RULES as SHOW_SECTION504_PLANS_RULES
from .show_section_meetings_rules import RULES as SHOW_SECTION_MEETINGS_RULES
from .show_section_room_assignments_rules import RULES as SHOW_SECTION_ROOM_ASSIGNMENTS_RULES
from .show_sis_import_jobs_rules import RULES as SHOW_SIS_IMPORT_JOBS_RULES
from .show_space_reservations_rules import RULES as SHOW_SPACE_RESERVATIONS_RULES
from .show_spaces_rules import RULES as SHOW_SPACES_RULES
from .show_special_education_cases_rules import RULES as SHOW_SPECIAL_EDUCATION_CASES_RULES
from .show_standardized_tests_rules import RULES as SHOW_STANDARDIZED_TESTS_RULES
from .show_standards_rules import RULES as SHOW_STANDARDS_RULES
from .show_state_reporting_snapshots_rules import RULES as SHOW_STATE_REPORTING_SNAPSHOTS_RULES
from .show_states_rules import RULES as SHOW_STATES_RULES
from .show_student_guardians_rules import RULES as SHOW_STUDENT_GUARDIANS_RULES
from .show_student_program_enrollments_rules import RULES as SHOW_STUDENT_PROGRAM_ENROLLMENTS_RULES
from .show_student_school_enrollments_rules import RULES as SHOW_STUDENT_SCHOOL_ENROLLMENTS_RULES
from .show_student_section_enrollments_rules import RULES as SHOW_STUDENT_SECTION_ENROLLMENTS_RULES
from .show_student_transportation_assignments_rules import RULES as SHOW_STUDENT_TRANSPORTATION_ASSIGNMENTS_RULES
from .show_subjects_rules import RULES as SHOW_SUBJECTS_RULES
from .show_subscriptions_rules import RULES as SHOW_SUBSCRIPTIONS_RULES
from .show_tags_rules import RULES as SHOW_TAGS_RULES
from .show_teacher_section_assignments_rules import RULES as SHOW_TEACHER_SECTION_ASSIGNMENTS_RULES
from .show_test_administrations_rules import RULES as SHOW_TEST_ADMINISTRATIONS_RULES
from .show_test_results_rules import RULES as SHOW_TEST_RESULTS_RULES
from .show_ticket_scans_rules import RULES as SHOW_TICKET_SCANS_RULES
from .show_ticket_types_rules import RULES as SHOW_TICKET_TYPES_RULES
from .show_tickets_rules import RULES as SHOW_TICKETS_RULES
from .show_transcript_lines_rules import RULES as SHOW_TRANSCRIPT_LINES_RULES
from .show_user_accounts_rules import RULES as SHOW_USER_ACCOUNTS_RULES
from .show_users_rules import RULES as SHOW_USERS_RULES
from .show_vendors_rules import RULES as SHOW_VENDORS_RULES
from .show_votes_rules import RULES as SHOW_VOTES_RULES
from .show_waivers_rules import RULES as SHOW_WAIVERS_RULES
from .show_warranties_rules import RULES as SHOW_WARRANTIES_RULES
from .show_webhooks_rules import RULES as SHOW_WEBHOOKS_RULES
from .show_work_order_parts_rules import RULES as SHOW_WORK_ORDER_PARTS_RULES
from .show_work_order_tasks_rules import RULES as SHOW_WORK_ORDER_TASKS_RULES
from .show_work_order_time_logs_rules import RULES as SHOW_WORK_ORDER_TIME_LOGS_RULES
from .show_work_orders_rules import RULES as SHOW_WORK_ORDERS_RULES

ALL_RULES = [
    *SHOW_STAFFS_RULES,
    *SHOW_STUDENTS_RULES,
    *SHOW_ENROLLMENT_RULES,
    *SHOW_INCIDENT_RULES,
    *SHOW_BUILDINGS_RULES,
    *SHOW_ASSETS_RULES,
    *SHOW_GOALS_RULES,
    *SHOW_ACADEMIC_TERMS_RULES,
    *SHOW_ACCOMMODATIONS_RULES,
    *SHOW_ACTIVITIES_RULES,
    *SHOW_ADDRESSES_RULES,
    *SHOW_AGENDA_ITEM_APPROVALS_RULES,
    *SHOW_AGENDA_ITEM_FILES_RULES,
    *SHOW_AGENDA_ITEMS_RULES,
    *SHOW_AGENDA_WORKFLOW_STEPS_RULES,
    *SHOW_AGENDA_WORKFLOWS_RULES,
    *SHOW_ALIGNMENTS_RULES,
    *SHOW_AP_VENDORS_RULES,
    *SHOW_ASSET_PARTS_RULES,
    *SHOW_ASSIGNMENT_CATEGORIES_RULES,
    *SHOW_ASSIGNMENTS_RULES,
    *SHOW_ATTENDANCE_CODES_RULES,
    *SHOW_ATTENDANCE_DAILY_SUMMARY_RULES,
    *SHOW_ATTENDANCE_EVENTS_RULES,
    *SHOW_ATTENDANCES_RULES,
    *SHOW_AUDIT_LOGS_RULES,
    *SHOW_BEHAVIOR_CODES_RULES,
    *SHOW_BEHAVIOR_INTERVENTIONS_RULES,
    *SHOW_BELL_SCHEDULES_RULES,
    *SHOW_BUS_ROUTES_RULES,
    *SHOW_BUS_STOP_TIMES_RULES,
    *SHOW_BUS_STOPS_RULES,
    *SHOW_CALENDAR_DAYS_RULES,
    *SHOW_CALENDARS_RULES,
    *SHOW_CHANNELS_RULES,
    *SHOW_CLASS_RANKS_RULES,
    *SHOW_COMM_SEARCH_INDEX_RULES,
    *SHOW_COMMITTEES_RULES,
    *SHOW_COMPLIANCE_RECORDS_RULES,
    *SHOW_CONSENTS_RULES,
    *SHOW_CONSEQUENCE_TYPES_RULES,
    *SHOW_CONSEQUENCES_RULES,
    *SHOW_CONTACTS_RULES,
    *SHOW_COURSE_PREREQUISITES_RULES,
    *SHOW_COURSE_SECTIONS_RULES,
    *SHOW_COURSES_RULES,
    *SHOW_CURRICULA_RULES,
    *SHOW_CURRICULUM_UNITS_RULES,
    *SHOW_CURRICULUM_VERSIONS_RULES,
    *SHOW_DATA_QUALITY_ISSUES_RULES,
    *SHOW_DATA_SHARING_AGREEMENTS_RULES,
    *SHOW_DEDUCTION_CODES_RULES,
    *SHOW_DELIVERIES_RULES,
    *SHOW_DEPARTMENT_POSITION_INDEX_RULES,
    *SHOW_DEPARTMENTS_RULES,
    *SHOW_DOCUMENT_ACTIVITY_RULES,
    *SHOW_DOCUMENT_LINKS_RULES,
    *SHOW_DOCUMENT_NOTIFICATIONS_RULES,
    *SHOW_DOCUMENT_PERMISSIONS_RULES,
    *SHOW_DOCUMENT_SEARCH_INDEX_RULES,
    *SHOW_DOCUMENT_VERSIONS_RULES,
    *SHOW_DOCUMENTS_RULES,
    *SHOW_EARNING_CODES_RULES,
    *SHOW_EDUCATION_ASSOCIATIONS_RULES,
    *SHOW_ELL_PLANS_RULES,
    *SHOW_EMBEDS_RULES,
    *SHOW_EMERGENCY_CONTACTS_RULES,
    *SHOW_EMPLOYEE_DEDUCTIONS_RULES,
    *SHOW_EMPLOYEE_EARNINGS_RULES,
    *SHOW_ENTITY_TAGS_RULES,
    *SHOW_EVALUATION_ASSIGNMENTS_RULES,
    *SHOW_EVALUATION_CYCLES_RULES,
    *SHOW_EVALUATION_FILES_RULES,
    *SHOW_EVALUATION_QUESTIONS_RULES,
    *SHOW_EVALUATION_REPORTS_RULES,
    *SHOW_EVALUATION_RESPONSES_RULES,
    *SHOW_EVALUATION_SECTIONS_RULES,
    *SHOW_EVALUATION_SIGNOFFS_RULES,
    *SHOW_EVALUATION_TEMPLATES_RULES,
    *SHOW_EXPORT_RUNS_RULES,
    *SHOW_EXTERNAL_IDS_RULES,
    *SHOW_FACILITIES_RULES,
    *SHOW_FAMILY_PORTAL_ACCESS_RULES,
    *SHOW_FAN_APP_SETTINGS_RULES,
    *SHOW_FAN_PAGES_RULES,
    *SHOW_FEATURE_FLAGS_RULES,
    *SHOW_FEES_RULES,
    *SHOW_FINAL_GRADES_RULES,
    *SHOW_FISCAL_PERIODS_RULES,
    *SHOW_FISCAL_YEARS_RULES,
    *SHOW_FLOORS_RULES,
    *SHOW_FOLDERS_RULES,
    *SHOW_FRAMEWORKS_RULES,
    *SHOW_GL_ACCOUNT_BALANCES_RULES,
    *SHOW_GL_ACCOUNT_SEGMENTS_RULES,
    *SHOW_GL_ACCOUNTS_RULES,
    *SHOW_GL_SEGMENT_VALUES_RULES,
    *SHOW_GL_SEGMENTS_RULES,
    *SHOW_GOVERNING_BODIES_RULES,
    *SHOW_GPA_CALCULATIONS_RULES,
    *SHOW_GRADE_LEVELS_RULES,
    *SHOW_GRADE_SCALE_BANDS_RULES,
    *SHOW_GRADE_SCALES_RULES,
    *SHOW_GRADEBOOK_ENTRIES_RULES,
    *SHOW_GRADING_PERIODS_RULES,
    *SHOW_GUARDIANS_RULES,
    *SHOW_HEALTH_PROFILES_RULES,
    *SHOW_HR_EMPLOYEES_RULES,
    *SHOW_HR_POSITION_ASSIGNMENTS_RULES,
    *SHOW_HR_POSITIONS_RULES,
    *SHOW_IEP_PLANS_RULES,
    *SHOW_IMMUNIZATION_RECORDS_RULES,
    *SHOW_IMMUNIZATIONS_RULES,
    *SHOW_INCIDENT_PARTICIPANTS_RULES,
    *SHOW_INCIDENTS_RULES,
    *SHOW_INITIATIVES_RULES,
    *SHOW_INVOICES_RULES,
    *SHOW_JOURNAL_BATCHES_RULES,
    *SHOW_JOURNAL_ENTRIES_RULES,
    *SHOW_JOURNAL_ENTRY_LINES_RULES,
    *SHOW_KPI_DATAPOINTS_RULES,
    *SHOW_KPIS_RULES,
    *SHOW_LEASES_RULES,
    *SHOW_LIBRARY_CHECKOUTS_RULES,
    *SHOW_LIBRARY_FINES_RULES,
    *SHOW_LIBRARY_HOLDS_RULES,
    *SHOW_LIBRARY_ITEMS_RULES,
    *SHOW_LIVE_SCORINGS_RULES,
    *SHOW_MAINTENANCE_REQUESTS_RULES,
    *SHOW_MATERIALS_RULES,
    *SHOW_MEAL_ACCOUNTS_RULES,
    *SHOW_MEAL_ELIGIBILITY_STATUSES_RULES,
    *SHOW_MEAL_TRANSACTIONS_RULES,
    *SHOW_MEDICATION_ADMINISTRATIONS_RULES,
    *SHOW_MEDICATIONS_RULES,
    *SHOW_MEETING_DOCUMENTS_RULES,
    *SHOW_MEETING_FILES_RULES,
    *SHOW_MEETING_PERMISSIONS_RULES,
    *SHOW_MEETING_PUBLICATIONS_RULES,
    *SHOW_MEETING_SEARCH_INDEX_RULES,
    *SHOW_MEETINGS_RULES,
    *SHOW_MEMBERSHIPS_RULES,
    *SHOW_MESSAGE_RECIPIENTS_RULES,
    *SHOW_MESSAGES_RULES,
    *SHOW_METERS_RULES,
    *SHOW_MINUTES_RULES,
    *SHOW_MOTIONS_RULES,
    *SHOW_MOVE_ORDERS_RULES,
    *SHOW_NURSE_VISITS_RULES,
    *SHOW_OBJECTIVES_RULES,
    *SHOW_ORDER_LINE_ITEMS_RULES,
    *SHOW_ORGANIZATIONS_RULES,
    *SHOW_PART_LOCATIONS_RULES,
    *SHOW_PAY_PERIODS_RULES,
    *SHOW_PAYCHECKS_RULES,
    *SHOW_PAYMENTS_RULES,
    *SHOW_PAYROLL_RUNS_RULES,
    *SHOW_PERSON_ADDRESSES_RULES,
    *SHOW_PERSON_CONTACTS_RULES,
    *SHOW_PERSONAL_NOTES_RULES,
    *SHOW_PERSONS_RULES,
    *SHOW_PLAN_ALIGNMENTS_RULES,
    *SHOW_PLAN_ASSIGNMENTS_RULES,
    *SHOW_PLAN_FILTERS_RULES,
    *SHOW_PLAN_SEARCH_INDEX_RULES,
    *SHOW_PM_PLANS_RULES,
    *SHOW_PM_WORK_GENERATORS_RULES,
    *SHOW_POLICIES_RULES,
    *SHOW_POLICY_APPROVALS_RULES,
    *SHOW_POLICY_COMMENTS_RULES,
    *SHOW_POLICY_FILES_RULES,
    *SHOW_POLICY_LEGAL_REFS_RULES,
    *SHOW_POLICY_PUBLICATIONS_RULES,
    *SHOW_POLICY_SEARCH_INDEX_RULES,
    *SHOW_POLICY_VERSIONS_RULES,
    *SHOW_POLICY_WORKFLOW_STEPS_RULES,
    *SHOW_POLICY_WORKFLOWS_RULES,
    *SHOW_POST_ATTACHMENTS_RULES,
    *SHOW_POSTS_RULES,
    *SHOW_PROJECT_TASKS_RULES,
    *SHOW_PROJECTS_RULES,
    *SHOW_PROPOSAL_DOCUMENTS_RULES,
    *SHOW_PROPOSAL_REVIEWS_RULES,
    *SHOW_PROPOSALS_RULES,
    *SHOW_REPORT_CARDS_RULES,
    *SHOW_REQUIREMENTS_RULES,
    *SHOW_RESOLUTIONS_RULES,
    *SHOW_RETENTION_RULES_RULES,
    *SHOW_REVIEW_REQUESTS_RULES,
    *SHOW_REVIEW_ROUNDS_RULES,
    *SHOW_ROLE_PERMISSIONS_RULES,
    *SHOW_ROLES_RULES,
    *SHOW_ROOMS_RULES,
    *SHOW_ROUND_DECISIONS_RULES,
    *SHOW_SCAN_REQUESTS_RULES,
    *SHOW_SCAN_RESULTS_RULES,
    *SHOW_SCHOOLS_RULES,
    *SHOW_SCORECARD_KPIS_RULES,
    *SHOW_SCORECARDS_RULES,
    *SHOW_SECTION504_PLANS_RULES,
    *SHOW_SECTION_MEETINGS_RULES,
    *SHOW_SECTION_ROOM_ASSIGNMENTS_RULES,
    *SHOW_SIS_IMPORT_JOBS_RULES,
    *SHOW_SPACE_RESERVATIONS_RULES,
    *SHOW_SPACES_RULES,
    *SHOW_SPECIAL_EDUCATION_CASES_RULES,
    *SHOW_STANDARDIZED_TESTS_RULES,
    *SHOW_STANDARDS_RULES,
    *SHOW_STATE_REPORTING_SNAPSHOTS_RULES,
    *SHOW_STATES_RULES,
    *SHOW_STUDENT_GUARDIANS_RULES,
    *SHOW_STUDENT_PROGRAM_ENROLLMENTS_RULES,
    *SHOW_STUDENT_SCHOOL_ENROLLMENTS_RULES,
    *SHOW_STUDENT_SECTION_ENROLLMENTS_RULES,
    *SHOW_STUDENT_TRANSPORTATION_ASSIGNMENTS_RULES,
    *SHOW_SUBJECTS_RULES,
    *SHOW_SUBSCRIPTIONS_RULES,
    *SHOW_TEACHER_SECTION_ASSIGNMENTS_RULES,
    *SHOW_TEST_ADMINISTRATIONS_RULES,
    *SHOW_TEST_RESULTS_RULES,
    *SHOW_TICKET_SCANS_RULES,
    *SHOW_TICKET_TYPES_RULES,
    *SHOW_TICKETS_RULES,
    *SHOW_TRANSCRIPT_LINES_RULES,
    *SHOW_USER_ACCOUNTS_RULES,
    *SHOW_USERS_RULES,
    *SHOW_VOTES_RULES,
    *SHOW_WAIVERS_RULES,
    *SHOW_WARRANTIES_RULES,
    *SHOW_WEBHOOKS_RULES,
    *SHOW_WORK_ORDER_PARTS_RULES,
    *SHOW_WORK_ORDER_TASKS_RULES,
    *SHOW_WORK_ORDER_TIME_LOGS_RULES,
    *SHOW_WORK_ORDERS_RULES,
]

__all__ = [
    "HeuristicRule",
    "apply_heuristics",
    "ALL_RULES",
]
