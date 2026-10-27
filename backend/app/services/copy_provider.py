"""Mock default. Live adapter exists but is gated off and never used by CI."""
from dataclasses import dataclass
import json
from app.services.copy_prompt import SYSTEM_PROMPT, input_bound
from app.services.copy_validation import CopyFailure
from app.schemas.copy import Variants

@dataclass
class ProviderResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None

class MockCopyProvider:
    name = 'mock'
    model = 'mock-copy-v1'
    def generate(self, payload):
        return ProviderResult(json.dumps({'variants': [
            {'strategy': 'emotional', 'copy': {'headline': '일상에 더하는 작은 여유', 'body': '오늘의 한순간을 나만의 시간으로 만나보세요.', 'cta': '한순간을 골라보세요'}},
            {'strategy': 'price', 'copy': {'headline': '가격을 확인하고 선택하세요', 'body': '표시된 상품과 가격을 함께 살펴보세요.', 'cta': '상품 정보를 확인하세요'}},
            {'strategy': 'visual', 'copy': {'headline': '사진 속 상품을 만나보세요', 'body': '직접 올린 사진으로 상품을 살펴보세요.', 'cta': '사진을 확인하세요'}},
            {'strategy': 'brand', 'copy': {'headline': '우리 가게와 만나는 시간', 'body': '가게의 이름과 함께 상품을 기억해 보세요.', 'cta': '가게를 만나보세요'}}
        ]}, ensure_ascii=False))

class OpenAICopyProvider:
    name = 'openai'
    def __init__(self, model, api_key, allow_paid, budget, client=None):
        self.model, self.api_key, self.allow_paid = model, api_key, allow_paid
        self.budget, self.client = budget, client
        self.checked_model = False

    def generate(self, payload):
        self.last_usage = None
        self.last_reserved_unknown = 0
        if not self.allow_paid:
            raise CopyFailure('COPY_PAID_DISABLED')
        if not self.api_key:
            raise CopyFailure('COPY_KEY_MISSING')
        if self.model != 'gpt-5.4-mini-2026-03-17':
            raise CopyFailure('COPY_MODEL_NOT_APPROVED')
        if input_bound(payload) > 6000:
            raise CopyFailure('COPY_INPUT_LIMIT')
        import openai
        if self.client is None:
            self.client = openai.OpenAI(api_key=self.api_key, base_url='https://api.openai.com/v1', timeout=30., max_retries=0)
        if not self.checked_model:
            try:
                self.client.models.retrieve(self.model)  # metadata only, no generated tokens
            except Exception:
                raise CopyFailure('COPY_MODEL_UNAVAILABLE') from None
            self.checked_model = True
        call = self.budget.reserve()
        from app.services.copy_budget import MAX_COST
        self.last_reserved_unknown = MAX_COST
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
            self.last_usage = (usage.input_tokens, usage.output_tokens)
            self.last_reserved_unknown = 0
            if response.status != 'completed' or not response.output_text:
                raise CopyFailure('COPY_OUTPUT_INCOMPLETE')
            return ProviderResult(response.output_text, usage.input_tokens, usage.output_tokens)
        except CopyFailure:
            raise
        except openai.APITimeoutError:
            raise CopyFailure('COPY_PROVIDER_TIMEOUT') from None
        except openai.RateLimitError as error:
            raise CopyFailure('COPY_RATE_LIMIT', getattr(error, 'code', '') != 'insufficient_quota') from None
        except openai.InternalServerError:
            raise CopyFailure('COPY_PROVIDER_UNAVAILABLE', True) from None
        except Exception:
            raise CopyFailure('COPY_PROVIDER_FAILED') from None

    def close(self):
        if self.client:
            self.client.close()
