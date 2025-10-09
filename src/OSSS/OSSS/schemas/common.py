
from __future__ import annotations
from typing import Literal

Level = Literal["Varsity", "JV", "Freshman", "MiddleSchool"]
EventType = Literal["Game", "Practice", "Camp", "Fundraiser", "Concession", "Other"]
OrderStatus = Literal["pending", "paid", "refunded", "canceled"]
AssignmentStatus = Literal["pending", "confirmed", "declined", "completed"]
LiveStatus = Literal["scheduled", "live", "final", "canceled"]
MessageChannel = Literal["Email", "SMS", "AppPush"]
