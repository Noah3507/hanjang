"""Supplement v3 diagnostics using actual alpha/placement, leaving v2 rules intact."""
from app.schemas.diagnostics import RuleResult


def image_rules(measurement):
    placement=measurement.get('image_placement') or {}
    known=placement.get('subject_known') is True
    occupancy=placement.get('subject_linear_occupancy')
    small=known and isinstance(occupancy,(float,int)) and occupancy<.55
    upscale=placement.get('scale',0)>2
    crop=placement.get('unintended_clip')
    def item(name,status,value,criterion,explanation,action):
        return RuleResult(rule_id=name,status=status,coverage='unavailable' if status=='unavailable' else 'complete',
            measured_value=value,unit='PNG geometry',criterion=criterion,explanation=explanation,action=action)
    return [item('subject_size','unavailable' if not known else 'caution' if small or upscale else 'normal',
        {'linear_occupancy':occupancy if known else None,'scale':placement.get('scale')},
        '알파 피사체가 슬롯 긴 축의 55% 미만 또는 2배 초과 업스케일이면 주의 (초기 휴리스틱)',
        '알파 지지 영역으로만 계산합니다. 배경 있는 사진의 실제 상품 영역은 인식하지 않습니다.',
        '실제 PNG에서 상품 크기와 원본 해상도를 확인해 주세요.'),
        item('image_crop','unavailable' if crop is None else 'problem' if crop else 'caution' if placement.get('decorative_occlusions') else 'normal',
        {'unintended_clip':crop,'policy':placement.get('policy'),'decorative_occlusions':placement.get('decorative_occlusions',[]),'discarded_low_alpha_mass_ratio':placement.get('discarded_low_alpha_mass_ratio')},
        '고정 임계값 이상의 모든 알파 영역 또는 불투명 사진 전체를 슬롯 경계 안에 유지',
        '의도적인 사진 크롭을 자동 적용하지 않습니다. 매우 낮은 알파 여백 정리는 기록하며 원본은 보존합니다.',
        '경계 또는 배경 제거 품질이 불확실하면 원본 사진과 비교해 주세요.')]
