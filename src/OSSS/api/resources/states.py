# Auto-generated resource for States
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.states import State
from OSSS.schemas.state import StateCreate, StateOut

router = build_crud_router(
    model=State,
    schema_in=StateCreate,
    schema_out=StateOut,
    get_session=get_session,
    path_prefix="/admin/settings/states",
    tags=["admin"],
)

register(Resource(name="states", router=router, prefix=""))
