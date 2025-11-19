# src/MetaGPT/roles/student.py
from metagpt.roles import Role
from metagpt.logs import logger

class StudentRole(Role):
    name: str = "student"

    async def _act(self) -> None:
        logger.info("StudentRole is acting...")
        return
