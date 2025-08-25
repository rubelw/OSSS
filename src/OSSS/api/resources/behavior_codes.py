# Auto-generated resource for Behavior Codes
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.behavior_codes import BehaviorCode
from OSSS.schemas.behavior_code import BehaviorCodeCreate, BehaviorCodeOut

router = build_crud_router(
    model=BehaviorCode,
    schema_in=BehaviorCodeCreate,
    schema_out=BehaviorCodeOut,
    get_session=get_session,
    path_prefix="/sis/settings/behavior-codes",
    tags=["sis"],
)

register(Resource(name="behavior_codes", router=router, prefix=""))
