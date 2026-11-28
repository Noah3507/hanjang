"""Provider-neutral text-only boundary. No SDK, pricing, or image transport here."""
from dataclasses import dataclass, field
from typing import NotRequired, Protocol, TypedDict


class VisualHint(TypedDict):
    category: str
    candidate_id: str
    label: str
    similarity: float


class CopyPayload(TypedDict):
    store_name: str
    product_name: str
    price_text: str
    mood: str
    product_features: str | None
    visual_hints: list[VisualHint]
    address: NotRequired[str]
    ad_goal: NotRequired[str]
    displayed_facts_by_strategy: NotRequired[dict[str, list[str]]]
    template_copy_limits: NotRequired[dict]


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    reserved_unknown_cost_usd: float = 0


@dataclass(frozen=True)
class ProviderResult:
    text: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    warnings: tuple[str,...] = ()


class CopyFailure(Exception):
    def __init__(self, code: str, retryable: bool = False, usage: ProviderUsage | None = None, reason: str | None = None):
        # reason names the rule and, for vocabulary/number rules, the offending token. It never holds private input.
        self.code, self.retryable, self.usage, self.reason = code, retryable, usage, reason
        super().__init__(code)


class CopyProvider(Protocol):
    name: str
    model: str

    def generate(self, payload: CopyPayload) -> ProviderResult: ...

    def close(self) -> None: ...
