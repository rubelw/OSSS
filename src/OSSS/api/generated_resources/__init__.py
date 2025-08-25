
# Dynamic FastAPI routers for OSSS models
from .factory import create_router_for_model
from .register_all import generate_routers_for_all_models
__all__ = ["create_router_for_model", "generate_routers_for_all_models"]
