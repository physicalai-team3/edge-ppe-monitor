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


def _center(box: list[int]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _in_region(person: list[int], region: tuple[float, float], point: tuple[float, float]) -> bool:
    """point 가 사람 박스 폭 전체 × 높이 비율 region 안에 있나 (경계 포함)."""
    x1, y1, x2, y2 = person
    h = y2 - y1
    x, y = point
    return x1 <= x <= x2 and y1 + region[0] * h <= y <= y1 + region[1] * h


def _wearing(person: list[int], region: tuple[float, float], gear: list[dict],
             ok_cls: str, bad_cls: str, unknown_as_violation: bool) -> bool:
    """영역 안에 bad_cls 가 있으면 False → ok_cls 가 있으면 True → 둘 다 없으면 판단 불가 (5.2)."""
    found = {d["cls"] for d in gear if _in_region(person, region, _center(d["box"]))}
    if bad_cls in found:
        return False
    if ok_cls in found:
        return True
    return not unknown_as_violation


def judge(detections: list[dict], unknown_as_violation: bool = True) -> Judgement:
    """detector 의 detections → 사람별 착용 여부 + 전체 결과."""
    people = [d["box"] for d in detections if d["cls"] == "person" and d["score"] >= PERSON_MIN_SCORE]
    gear = [d for d in detections if d["cls"] != "person"]

    if people:
        persons = [PersonVerdict(box=box,
                                 helmet=_wearing(box, HEAD_REGION, gear, "helmet", "no_helmet", unknown_as_violation),
                                 vest=_wearing(box, TORSO_REGION, gear, "vest", "no_vest", unknown_as_violation))
                   for box in people]
    else:
        # 5.1-3 모델이 사람을 놓친 경우: no_* 박스 하나 = 사람 1명, 잡힌 항목만 ❌
        persons = [PersonVerdict(box=d["box"], helmet=d["cls"] != "no_helmet", vest=d["cls"] != "no_vest")
                   for d in gear if d["cls"] in VIOLATION_ORDER]

    if not persons:
        return Judgement(result="no_person")

    persons.sort(key=lambda p: p.box[0])
    found = set()
    for p in persons:
        if not p.helmet:
            found.add("no_helmet")
        if not p.vest:
            found.add("no_vest")
    violations = [v for v in VIOLATION_ORDER if v in found]
    return Judgement(result="violation" if violations else "compliant", persons=persons, violations=violations)
