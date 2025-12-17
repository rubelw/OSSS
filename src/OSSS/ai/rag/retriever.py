from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class RetrievedChunk:
    id: str
    text: str
    source: str            # filename/url/document id
    score: float
    meta: Optional[Dict[str, Any]] = None

class Retriever:
    async def retrieve(self, query: str, *, k: int = 6) -> List[RetrievedChunk]:
        raise NotImplementedError
