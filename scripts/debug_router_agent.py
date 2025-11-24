#!/usr/bin/env python
import asyncio
from OSSS.ai.router_agent import RouterAgent, RAGRequest, ChatMessage
from OSSS.ai.session_store import get_or_create_session

async def main():
    session = get_or_create_session(None)

    rag = RAGRequest(
        messages=[
            ChatMessage(role="user", content="Who is the DCG superintendent?"),
        ],
        index="main",
    )

    agent = RouterAgent()
    result = await agent.run(rag=rag, session=session, session_files=[])

    print("ANSWER:", result["answer"])
    print("INTENT:", result.get("intent"))
    print("AGENT TRACE:", result.get("agent_trace"))

if __name__ == "__main__":
    asyncio.run(main())
