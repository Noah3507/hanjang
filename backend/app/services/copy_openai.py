"""Deferred OpenAI text adapter: vendor SDK, parameters, pricing, and errors only."""
import json
from app.services.copy_contract import CopyFailure, CopyPayload, ProviderResult, ProviderUsage
from app.services.copy_prompt import SYSTEM_PROMPT, input_bound
from app.schemas.copy import Variants


def openai_usage(inputs: int, outputs: int) -> ProviderUsage:
    return ProviderUsage(inputs, outputs, (inputs*.75 + outputs*4.5)/1_000_000)


class OpenAICopyProvider:
    name = 'openai'

    def __init__(self, model, api_key, allow_paid, budget, client=None):
        self.model, self.api_key, self.allow_paid = model, api_key, allow_paid
        self.budget, self.client = budget, client
        self.checked_model = False

    def generate(self, payload: CopyPayload) -> ProviderResult:
        if not self.allow_paid:
            raise CopyFailure('COPY_PAID_DISABLED')
        if not self.api_key:
            raise CopyFailure('COPY_KEY_MISSING')
        if self.model != 'gpt-5.4-mini-2026-03-17':
            raise CopyFailure('COPY_MODEL_NOT_APPROVED')
        if input_bound(payload) > 6000:
            raise CopyFailure('COPY_INPUT_LIMIT')
        import openai  # Deferred: Mock never imports or initializes the SDK.
        if self.client is None:
            self.client = openai.OpenAI(api_key=self.api_key, base_url='https://api.openai.com/v1', timeout=30., max_retries=0)
        if not self.checked_model:
            try:
                self.client.models.retrieve(self.model)
            except Exception:
                raise CopyFailure('COPY_MODEL_UNAVAILABLE') from None
            self.checked_model = True
        call = self.budget.reserve()
        from app.services.copy_budget import MAX_COST
        receipt = ProviderUsage(reserved_unknown_cost_usd=MAX_COST)
        try:
            response = self.client.responses.create(model=self.model,
                instructions=SYSTEM_PROMPT,
                input=[{'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                text={'format': {'type': 'json_schema', 'name': 'copy_variants', 'schema': Variants.model_json_schema(), 'strict': True}},
                reasoning={'effort': 'none'}, max_output_tokens=2048, store=False)
            usage = response.usage
            if usage is None:
                raise CopyFailure('COPY_USAGE_UNKNOWN')
            self.budget.settle(call, usage.input_tokens, usage.output_tokens)
            receipt = openai_usage(usage.input_tokens, usage.output_tokens)
            if response.status != 'completed' or not response.output_text:
                raise CopyFailure('COPY_OUTPUT_INCOMPLETE')
            return ProviderResult(response.output_text, receipt)
        except CopyFailure as failure:
            raise CopyFailure(failure.code, failure.retryable, receipt) from None
        except openai.APITimeoutError:
            raise CopyFailure('COPY_PROVIDER_TIMEOUT', usage=receipt) from None
        except openai.RateLimitError as error:
            raise CopyFailure('COPY_RATE_LIMIT', getattr(error, 'code', '') != 'insufficient_quota', receipt) from None
        except openai.InternalServerError:
            raise CopyFailure('COPY_PROVIDER_UNAVAILABLE', True, receipt) from None
        except Exception:
            raise CopyFailure('COPY_PROVIDER_FAILED', usage=receipt) from None

    def close(self):
        if self.client:
            self.client.close()
