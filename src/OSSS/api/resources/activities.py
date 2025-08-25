# Auto-generated resource for Activities
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.activities import Activity
from OSSS.schemas.activities import ActivityCreate, ActivityOut

router = build_crud_router(
    model=Activity,
    schema_in=ActivityCreate,
    schema_out=ActivityOut,
    get_session=get_session,
    path_prefix="/activities",
    tags=["activities"],
)

register(Resource(name="activities", router=router, prefix=""))
