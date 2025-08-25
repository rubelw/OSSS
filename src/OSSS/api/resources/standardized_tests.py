# Auto-generated resource for Standardized Tests
from OSSS.resources import Resource, register
from OSSS.api.router_factory import build_crud_router
from OSSS.db.session import get_session
from OSSS.db.models.standardized_tests import StandardizedTest
from OSSS.schemas.standardized_test import StandardizedTestCreate, StandardizedTestOut

router = build_crud_router(
    model=StandardizedTest,
    schema_in=StandardizedTestCreate,
    schema_out=StandardizedTestOut,
    get_session=get_session,
    path_prefix="/sis/settings/standardized-tests",
    tags=["sis"],
)

register(Resource(name="standardized_tests", router=router, prefix=""))
