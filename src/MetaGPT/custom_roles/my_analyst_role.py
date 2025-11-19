from metagpt.roles import Role


class MyAnalystRole(Role):
    """
    A minimal MetaGPT role that:
    - receives a user query
    - thinks about it
    - acts on it
    """

    name: str = "analyst"
    profile: str = "Analyzes text and produces structured insights."

    async def _think(self, query: str):
        """
        (Optional) internal reasoning step.
        You can store intermediate thoughts on self.
        """

        # This is just an example — normally you'd use an LLM call here.
        self.thought = f"[Thinking deeply about]: {query}"

        return self.thought

    async def _act(self, query: str):
        """
        The action step should return the final output.
        """
        # Normally you'd generate an LLM completion or chain-of-thought here.
        response = {
            "summary": f"Analysis of: {query}",
            "insight": f"This text appears to involve: {query[:50]}...",
            "reasoning_step": getattr(self, "thought", "(none)")
        }
        return response

    async def run(self, query: str):
        """
        Main MetaGPT entrypoint.

        The standard pattern:
        1. think
        2. act
        3. return final result
        """
        await self._think(query)
        result = await self._act(query)
        return result
