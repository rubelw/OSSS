# Auto-generated resource for Grading Periods
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.grading_periods import GradingPeriod
from OSSS.schemas.grading_period import GradingPeriodCreate, GradingPeriodOut

router = build_crud_router(
    model=GradingPeriod,
    schema_in=GradingPeriodCreate,
    schema_out=GradingPeriodOut,
    get_session=get_session,
    path_prefix="/sis/settings/academic/grading-periods",
    tags=["sis"],
)

register(Resource(name="grading_periods", router=router, prefix=""))
