# src/MetaGPT/roles/parent.py
from metagpt.roles import Role
from metagpt.logs import logger

class ParentRole(Role):
    name: str = "parent"

    async def _act(self) -> None:
        logger.info("ParentRole is acting...")
        return
