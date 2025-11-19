# src/MetaGPT/roles/superintendent.py
from metagpt.roles import Role
from metagpt.logs import logger

class SuperintendentRole(Role):
    name: str = "superintendent"

    async def _act(self) -> None:
        logger.info("SuperintendentRole is acting...")
        return
