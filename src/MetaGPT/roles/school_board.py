# src/MetaGPT/roles/school_board.py
from metagpt.roles import Role
from metagpt.logs import logger

class SchoolBoardRole(Role):
    name: str = "school_board"

    async def _act(self) -> None:
        logger.info("SchoolBoardRole is acting...")
        return
