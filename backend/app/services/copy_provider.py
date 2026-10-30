"""Mock implementation and explicit factory; no vendor SDK imported in Mock mode."""
import json
from app.services.copy_contract import CopyPayload, CopyProvider, ProviderResult

class MockCopyProvider:
    name = 'mock'
    model = 'mock-copy-v1'
    def generate(self, payload: CopyPayload) -> ProviderResult:
        return ProviderResult(json.dumps({'variants': [
            {'strategy': 'emotional', 'copy': {'headline': '일상에 더하는 작은 여유', 'body': '오늘의 한순간을 나만의 시간으로 만나보세요.', 'cta': '한순간을 골라보세요'}},
            {'strategy': 'price', 'copy': {'headline': '가격을 확인하고 선택하세요', 'body': '표시된 상품과 가격을 함께 살펴보세요.', 'cta': '상품 정보를 확인하세요'}},
            {'strategy': 'visual', 'copy': {'headline': '사진 속 상품을 만나보세요', 'body': '직접 올린 사진으로 상품을 살펴보세요.', 'cta': '사진을 확인하세요'}},
            {'strategy': 'brand', 'copy': {'headline': '우리 가게와 만나는 시간', 'body': '가게의 이름과 함께 상품을 기억해 보세요.', 'cta': '가게를 만나보세요'}}
        ]}, ensure_ascii=False))

    def close(self) -> None:
        pass


def build_copy_provider(settings) -> CopyProvider:
    if settings.copy_provider == 'mock':
        return MockCopyProvider()
    from app.services.copy_openai import OpenAICopyProvider
    from app.services.copy_budget import CopyBudget
    return OpenAICopyProvider(
        settings.copy_model,
        settings.openai_api_key.get_secret_value() if settings.openai_api_key else None,
        settings.copy_allow_paid, CopyBudget(settings.copy_budget_path, settings.copy_max_requests, settings.copy_budget_usd),
    )
