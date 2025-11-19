# src/MetaGPT/roles/teacher.py
from metagpt.roles import Role
from metagpt.logs import logger

class TeacherRole(Role):
    name: str = "teacher"

    async def _act(self) -> None:
        logger.info("TeacherRole is acting...")
        return
