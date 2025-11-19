# src/MetaGPT/roles/accountability_partner.py
from metagpt.roles import Role
from metagpt.logs import logger

class AccountabilityPartnerRole(Role):
    name: str = "accountability_partner"

    async def _act(self) -> None:
        logger.info("AccountabilityPartnerRole is acting...")
        return
