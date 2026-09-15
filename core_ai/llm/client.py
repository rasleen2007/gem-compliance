"""LLM client abstraction. Providers: gemini | openai | local.

Used only for operator=llm_judge rules. Prompts include the extracted evidence
spans so the model grounds its verdict in the document text.

TODO implement in Phase P3:
- provider switch from settings (LLM_PROVIDER / LLM_MODEL / LLM_API_KEY)
- structured output: {"verdict": "pass|fail|warn", "reason": "...", "confidence": 0.x}
- input truncation to the evidence spans (token-budget safe)
"""


class LLMClient:
    def judge(self, instruction: str, evidence_text: str) -> dict:
        """Return {'verdict', 'reason', 'confidence'}."""
        raise NotImplementedError("implement in MVP Phase P3")