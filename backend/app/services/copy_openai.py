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
        # No uncounted models.retrieve call. Access is determined by the generation
        # response, and every generation attempt (including retries/errors) is reserved.
        call = self.budget.reserve()
        from app.services.copy_budget import MAX_COST
        receipt = ProviderUsage(reserved_unknown_cost_usd=MAX_COST)
        try:
            self.budget.dispatched(call)
            response = self.client.responses.create(model=self.model,
                instructions=SYSTEM_PROMPT,
                input=[{'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}],
                text={'format': {'type': 'json_schema', 'name': 'copy_variants', 'schema': Variants.model_json_schema(), 'strict': True}},
                reasoning={'effort': 'none'}, max_output_tokens=2048, store=False)
            usage = response.usage
            if usage is None or any(type(getattr(usage, name, None)) is not int or getattr(usage, name) < 0
                                    for name in ('input_tokens', 'output_tokens')):
                raise CopyFailure('COPY_USAGE_UNKNOWN')
            self.budget.settle(call, usage.input_tokens, usage.output_tokens)
            receipt = openai_usage(usage.input_tokens, usage.output_tokens)
            if usage.input_tokens > 6000 or usage.output_tokens > 2048:
                raise CopyFailure('COPY_USAGE_LIMIT_EXCEEDED')
            if any(getattr(content, 'type', None) == 'refusal'
                for item in (getattr(response, 'output', None) or [])
                for content in (getattr(item, 'content', None) or [])):
                raise CopyFailure('COPY_REFUSED')
            if response.status != 'completed' or not response.output_text:
                raise CopyFailure('COPY_OUTPUT_INCOMPLETE')
            return ProviderResult(response.output_text, receipt)
        except CopyFailure as failure:
            self.budget.failed(call, failure.code)
            raise CopyFailure(failure.code, failure.retryable, receipt) from None
        except openai.APITimeoutError:
            self.budget.failed(call, 'COPY_PROVIDER_TIMEOUT')
            raise CopyFailure('COPY_PROVIDER_TIMEOUT', usage=receipt) from None
        except openai.RateLimitError as error:
            self.budget.failed(call, 'COPY_RATE_LIMIT')
            raise CopyFailure('COPY_RATE_LIMIT', getattr(error, 'code', '') != 'insufficient_quota', receipt) from None
        except openai.InternalServerError:
            self.budget.failed(call, 'COPY_PROVIDER_UNAVAILABLE')
            raise CopyFailure('COPY_PROVIDER_UNAVAILABLE', True, receipt) from None
        except openai.AuthenticationError:
            self.budget.failed(call, 'COPY_AUTH_FAILED')
            raise CopyFailure('COPY_AUTH_FAILED', usage=receipt) from None
        except openai.NotFoundError:
            self.budget.failed(call, 'COPY_MODEL_UNAVAILABLE')
            raise CopyFailure('COPY_MODEL_UNAVAILABLE', usage=receipt) from None
        except Exception:
            self.budget.failed(call, 'COPY_PROVIDER_FAILED')
            raise CopyFailure('COPY_PROVIDER_FAILED', usage=receipt) from None

    def close(self):
        if self.client:
            self.client.close()
