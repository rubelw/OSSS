# Auto-generated resource for Schools
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.schools import School
from OSSS.schemas.school import SchoolCreate, SchoolOut

router = build_crud_router(
    model=School,
    schema_in=SchoolCreate,
    schema_out=SchoolOut,
    get_session=get_session,
    path_prefix="/admin/settings/schools",
    tags=["admin"],
)

register(Resource(name="schools", router=router, prefix=""))
