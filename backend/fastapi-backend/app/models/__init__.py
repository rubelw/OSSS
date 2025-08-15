# app/models/__init__.py
# backend/fastapi-backend/app/models/__init__.py


from .core import (
 Organization,
 Body,
 File,
 Tag,
 EntityTag,
 AuditLog,
 Embed,
 Webhook,
 Notification,
 FeatureFlag,
 RetentionRule
)

from .evaluations import (
 EvaluationTemplate,
 EvaluationSection,
 EvaluationQuestion,
 EvaluationCycle,
 EvaluationAssignment,
 EvaluationResponse,
 EvaluationSignoff,
 EvaluationFile,
 EvaluationReport
)

from .behavior_codes import (
   BehaviorCode
)

from .consequence_types import (
  ConsequenceType
)

from .user_models import User  # or from .user import User

from .consequences import (
  Consequence
)

from .incidents import (
Incident
)

from .behavior_interventions import (
  BehaviorIntervention
)

from .incident_participants import (
  IncidentParticipant
)

# Import every module that defines ORM classes
from .meetings import (
    Meeting,
    MeetingPermission,
    AgendaItem,
    AgendaWorkflow,
    AgendaWorkflowStep,
    AgendaItemApproval,
    Motion,
    Vote,
    Attendance,
    Minutes,
    MeetingFile,
    AgendaItemFile,
    PersonalNote,
    MeetingPublication,
    MeetingSearchIndex,
)
from .policies import (
    Policy, PolicyVersion, PolicyLegalRef, PolicyComment, PolicyWorkflow,
    PolicyWorkflowStep, PolicyApproval, PolicyFile, PolicyPublication
)
from .planning import (
    Plan, Goal, Objective, Initiative, KPI, KPIDatapoint, Scorecard, ScorecardKPI,
    PlanAssignment, PlanAlignment, PlanFilter
)
from .repo import (
    Folder, Document, DocumentVersion, DocumentPermission,
    DocumentNotification, DocumentActivity
)
from .communications import (
    Channel, Post, PostAttachment, Subscription, Delivery, Page, DocumentLink
)

from .state import (
    State
)

from .sis import (
    District,
    School,
    AcademicTerm,
    GradingPeriod,
    Calendar,
    CalendarDay,
    BellSchedule,
    Period,
    GradeLevel,
    Department,
    Subject,
    Course,
    CourseSection,
    Room,
    Person,
    Student,
    Staff,
    Guardian,
    UserAccount,
    Role,
    Permission,
    RolePermission,
    Address,
    Contact,
    PersonAddress,
    PersonContact,
    StudentGuardian,
    ExternalId,
    StudentSchoolEnrollment,
    StudentProgramEnrollment,
    SpecialEducationCase,
    IepPlan,
    Accommodation,
    EllPlan,
    Section504Plan,
    SectionMeeting,
    TeacherSectionAssignment,
    StudentSectionEnrollment,
    CoursePrerequisite,
    SectionRoomAssignment,
    AttendanceCode,
    AttendanceEvent,
    AttendanceDailySummary,
    GradeScale,
    GradeScaleBand,
    AssignmentCategory,
    Assignment,
    GradebookEntry,
    FinalGrade,
    GpaCalculation,
    ClassRank,
    ReportCard,
    TranscriptLine,
    StandardizedTest,
    TestAdministration,
    TestResult,
    Message,
    MessageRecipient,
    FamilyPortalAccess,
    StateReportingSnapshot,
    ExportRun,
    AuditLog,
    DataSharingAgreement,
    SisImportJob,
    DataQualityIssue,
    Fee,
    Invoice,
    Payment,
    Waiver,
    MealAccount,
    MealTransaction,
    MealEligibilityStatus,
    BusRoute,
    BusStop,
    BusStopTime,
    StudentTransportationAssignment,
    LibraryItem,
    LibraryCheckout,
    LibraryHold,
    LibraryFine,
    HealthProfile,
    Immunization,
    ImmunizationRecord,
    Medication,
    MedicationAdministration,
    NurseVisit,
    EmergencyContact, Consent
)

from .finance_hr_payroll import (
     GLSegment,
     GLSegmentValue,
     GLAccount,
     GLAccountSegment,
     FiscalYear,
     FiscalPeriod,
     JournalBatch,
     JournalEntry,
     JournalEntryLine,
     HREmployee,
     HRPosition,
     HRPositionAssignment,
     PayPeriod,
     PayrollRun,
     EarningCode,
     DeductionCode,
     EmployeeEarning,
     EmployeeDeduction,
     Paycheck,
)


from .cmms_iwms import (
    Facility,
    Building,
    Floor,
    Space,
    Vendor,
    Part,
    PartLocation,
    Asset,
    AssetPart,
    Meter,
    MaintenanceRequest,
    WorkOrder,
    WorkOrderTask,
    WorkOrderTimeLog,
    WorkOrderPart,
    PMPlan,
    PMWorkGenerator,
    Warranty,
    ComplianceRecord,
    SpaceReservation,
    Lease,
    Project,
    ProjectTask,
    MoveOrder,

)


from .cic import (
    CICCommittee,
    CICMembership,
    CICMeeting,
    CICAgendaItem,
    CICMotion,
    CICVote,
    CICResolution,
    CICProposal,
    CICProposalReview,
    CICProposalDocument,
    CICMeetingDocument, CICPublication
)




# Finally, after *all* model imports:
from sqlalchemy.orm import configure_mappers
configure_mappers()
