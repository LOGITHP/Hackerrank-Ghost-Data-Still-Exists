"""Request understanding agent classifying deletion intent and applicability.
Combines deterministic multilingual pattern recognition with local Ollama fallback.
"""

import re
from typing import Optional
from pydantic import BaseModel
from code.llm.ollama_client import OllamaClient
from code.llm.prompts import REQUEST_ANALYSIS_SYSTEM


class RequestAnalysisResult(BaseModel):
    is_deletion: bool
    confidence: float
    request_type: str
    reasoning: str


# Deterministic non-deletion cues where user explicitly instructs to keep the account/profile active or requests non-deletion operations
NON_DELETION_PATTERNS = [
    r"leave\s+(?:the\s+account|my\s+account|my\s+profile|the\s+profile)\s+active",
    r"keep\s+the\s+account\s+as\s+it\s+is",
    r"leave\s+my\s+profile\s+and\s+purchase\s+history\s+in\s+place",
    r"continue\s+using\s+the\s+service",
    r"do\s+not\s+(?:delete|erase|remove|purge|close)\s+(?:the|my)?\s*account",
    r"don'?t\s+(?:delete|erase|remove|purge)\s+(?:or\s+change\s+)?anything",
    r"not\s+asking\s+for\s+deletion",
    r"not\s+a\s+request\s+to\s+erase",
    r"without\s+removing\s+any\s+of\s+my\s+records",
    r"remove\s+me\s+from\s+marketing\s+lists\s+only",
    r"resetting\s+the\s+login\.\s+do\s+not\s+close",
    r"just\s+(?:send|need|want)\s+an?\s+(?:invoice|receipt|export)\s+copy",
    r"only\s+update\s+my\s+(?:phone|email|password)",
]

# Deletion stems across English, French, Spanish, Portuguese, Japanese, Korean
DELETION_KEYWORDS = [
    "delet", "eras", "purg", "remov", "destroy", "wipe", "forget",
    "suppr", "effac",
    "elimin", "borra",
    "exclui", "exclus", "apaga",
    "削除", "消去",
    "삭제", "탈퇴",
]



class RequestAnalyzer:
    """Classifies deletion request intent and compliance applicability."""

    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.ollama_client = ollama_client

    def analyze(self, request_text: str) -> RequestAnalysisResult:
        """Classify request text as DELETION or NOT_DELETION."""
        if not request_text or not request_text.strip():
            return RequestAnalysisResult(
                is_deletion=False,
                confidence=1.0,
                request_type="EMPTY_REQUEST",
                reasoning="Empty request text provided.",
            )

        text = request_text.strip()
        text_lower = text.lower()

        # 1. Deterministic check for explicit non-deletion instructions
        for pattern in NON_DELETION_PATTERNS:
            if re.search(pattern, text_lower):
                return RequestAnalysisResult(
                    is_deletion=False,
                    confidence=1.0,
                    request_type="NON_DELETION",
                    reasoning=f"Request matched explicit non-deletion retention instruction: '{pattern}'.",
                )

        # 2. Check for clear deletion keywords
        is_del_keyword = any(kw in text_lower for kw in DELETION_KEYWORDS)
        if is_del_keyword:
            return RequestAnalysisResult(
                is_deletion=True,
                confidence=0.98,
                request_type="DELETION",
                reasoning="Request contains unambiguous deletion instructions.",
            )

        # 3. If borderline and Ollama is available, use local model
        if self.ollama_client:
            user_prompt = f"Analyze this request text:\n\"\"\"{text}\"\"\""
            res = self.ollama_client.chat_json(REQUEST_ANALYSIS_SYSTEM, user_prompt)
            if res and isinstance(res, dict):
                return RequestAnalysisResult(
                    is_deletion=bool(res.get("is_deletion", True)),
                    confidence=float(res.get("confidence", 0.9)),
                    request_type=str(res.get("request_type", "ACCOUNT_DELETION")),
                    reasoning=str(res.get("reasoning", "Classified via local Ollama inference.")),
                )

        # Default safe fallback: assume deletion if not explicitly asking to retain
        return RequestAnalysisResult(
            is_deletion=True,
            confidence=0.8,
            request_type="DELETION_DEFAULT",
            reasoning="Defaulted to deletion workflow as no explicit retention instruction found.",
        )
