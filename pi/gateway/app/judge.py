"""판정 규칙 — 순수 함수 (docs/03-contracts.md §5). 네트워크·파일 접근 금지 → tests/test_judge.py."""
from dataclasses import dataclass, field

PERSON_MIN_SCORE = 0.5
HEAD_REGION = (0.0, 0.35)    # 사람 박스 높이 비율 (y1 기준, 경계 포함)
TORSO_REGION = (0.20, 0.75)
VIOLATION_ORDER = ("no_helmet", "no_vest")   # violations 배열은 항상 이 순서 (03 §1.3)


@dataclass
class PersonVerdict:
    box: list[int]
    helmet: bool
    vest: bool


@dataclass
class Judgement:
    result: str                                   # violation | compliant | no_person
    persons: list[PersonVerdict] = field(default_factory=list)   # box x1 오름차순
    violations: list[str] = field(default_factory=list)          # VIOLATION_ORDER 순서, 중복 없음

    @property
    def no_helmet_count(self) -> int:
        return sum(not p.helmet for p in self.persons)

    @property
    def no_vest_count(self) -> int:
        return sum(not p.vest for p in self.persons)


def judge(detections: list[dict], unknown_as_violation: bool = True) -> Judgement:
    """detector 의 detections → 사람별 착용 여부 + 전체 결과."""
    # TODO: 03 §5 규칙 구현
    #   5.1 person(score>=0.5) 찾기. 0명이면 no_helmet/no_vest 박스 각각을 사람 1명으로
    #       (잡힌 항목만 ❌, 나머지 ✅)
    #   5.2 보호구 박스 중심점이 머리/몸통 영역 안이면 그 사람의 것. no_* 우선, 없으면 unknown_as_violation
    #   5.3 result, violations(VIOLATION_ORDER), persons(x1 오름차순)
    return Judgement(result="no_person")
