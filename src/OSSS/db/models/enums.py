from enum import Enum




class WorkType(str, Enum):
    ASSIGNMENT = "ASSIGNMENT"
    SHORT_ANSWER_QUESTION = "SHORT_ANSWER_QUESTION"
    MULTIPLE_CHOICE_QUESTION = "MULTIPLE_CHOICE_QUESTION"
    MATERIAL = "MATERIAL"

class SubmissionState(str, Enum):
    NEW = "NEW"
    CREATED = "CREATED"
    TURNED_IN = "TURNED_IN"
    RETURNED = "RETURNED"
    RECLAIMED_BY_STUDENT = "RECLAIMED_BY_STUDENT"

class Gender(str, Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class GuardianInvitationState(str, Enum):
    GUARDIAN_INVITATION_STATE_UNSPECIFIED = "GUARDIAN_INVITATION_STATE_UNSPECIFIED"
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"

class MaterialType(str, Enum):
    DRIVE_FILE = "DRIVE_FILE"
    YOUTUBE = "YOUTUBE"
    LINK = "LINK"
    FORM = "FORM"

class CourseState(str, Enum):
    PROVISIONED = "PROVISIONED"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DECLINED = "DECLINED"
    SUSPENDED = "SUSPENDED"

class PublicationState(str, Enum):
    PUBLISHED = "PUBLISHED"
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"

class GradeLevels(str, Enum):
    PREK = "Pre-Kindergarten"
    KINDERGARTEN = "Kingergarten"
    FIRST = "1st_Grade"
    SECOND = "2nd_Grade"
    THIRD = "3rd_Grade"
    FOURTH = "4th_Grade"
    FIFTH = "5th_Grade"
    SIXTH = "6th_Grade"
    SEVENTH = "7th_Grade"
    EIGHTH = "8th_Grade"
    NINETH = "9th_Grade"
    TENTH = "10th_Grade"
    ELEVENTH = "11th_Grade"
    TWELFTH = "12th_Grade"

# Canonical grade → ordinal mapping
GRADE_LEVEL_ORDINALS: dict[GradeLevels, int] = {
    GradeLevels.PREK: 0,
    GradeLevels.KINDERGARTEN: 1,
    GradeLevels.FIRST: 2,
    GradeLevels.SECOND: 3,
    GradeLevels.THIRD: 4,
    GradeLevels.FOURTH: 5,
    GradeLevels.FIFTH: 6,
    GradeLevels.SIXTH: 7,
    GradeLevels.SEVENTH: 8,
    GradeLevels.EIGHTH: 9,
    GradeLevels.NINETH: 10,
    GradeLevels.TENTH: 11,
    GradeLevels.ELEVENTH: 12,
    GradeLevels.TWELFTH: 13,
}