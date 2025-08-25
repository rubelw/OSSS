# Auto-generated resource for Attendance Codes
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.attendance_codes import AttendanceCode
from OSSS.schemas.attendance_code import AttendanceCodeCreate, AttendanceCodeOut

router = build_crud_router(
    model=AttendanceCode,
    schema_in=AttendanceCodeCreate,
    schema_out=AttendanceCodeOut,
    get_session=get_session,
    path_prefix="/sis/settings/attendance-codes",
    tags=["sis"],
)

register(Resource(name="attendance_codes", router=router, prefix=""))
