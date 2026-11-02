"""판정 규칙 테스트 (docs/03-contracts.md §5). 실행: docker compose run --rm gateway pytest -q"""
from app.judge import judge

# 사람 박스 [100,0,300,400] → 머리 y 0~140, 몸통 y 80~300
PERSON = {"cls": "person", "score": 0.9, "box": [100, 0, 300, 400]}
HELMET = {"cls": "helmet", "score": 0.8, "box": [170, 10, 230, 60]}       # 중심 (200,35) 머리
NO_HELMET = {"cls": "no_helmet", "score": 0.8, "box": [170, 10, 230, 60]}
VEST = {"cls": "vest", "score": 0.8, "box": [120, 120, 280, 260]}        # 중심 (200,190) 몸통
NO_VEST = {"cls": "no_vest", "score": 0.8, "box": [120, 120, 280, 260]}


def test_no_person():
    j = judge([])
    assert j.result == "no_person"
    assert j.persons == [] and j.violations == []


def test_low_score_person_is_ignored():
    j = judge([{**PERSON, "score": 0.45}, HELMET, VEST])
    assert j.result == "no_person"


def test_compliant():
    j = judge([PERSON, HELMET, VEST])
    assert j.result == "compliant"
    assert j.violations == []


def test_no_helmet():
    j = judge([PERSON, NO_HELMET, VEST])
    assert j.result == "violation"
    assert j.violations == ["no_helmet"]
    assert j.no_helmet_count == 1 and j.no_vest_count == 0


def test_no_helmet_wins_over_helmet():
    j = judge([PERSON, HELMET, NO_HELMET, VEST])
    assert j.violations == ["no_helmet"]


def test_unknown_is_violation_by_default():
    assert judge([PERSON, HELMET]).violations == ["no_vest"]


def test_unknown_is_ok_when_disabled():
    assert judge([PERSON, HELMET], unknown_as_violation=False).result == "compliant"


def test_violation_order_is_fixed():
    j = judge([PERSON, NO_VEST, NO_HELMET])
    assert j.violations == ["no_helmet", "no_vest"]


def test_gear_outside_any_person_is_ignored():
    far_helmet = {"cls": "helmet", "score": 0.8, "box": [500, 10, 560, 60]}
    j = judge([PERSON, far_helmet, VEST])
    assert j.violations == ["no_helmet"]


def test_without_person_box_only_detected_item_counts():
    j = judge([NO_HELMET])
    assert j.result == "violation"
    assert len(j.persons) == 1
    assert j.persons[0].helmet is False and j.persons[0].vest is True
    assert j.violations == ["no_helmet"]


def test_persons_sorted_left_to_right():
    right = {"cls": "person", "score": 0.9, "box": [400, 0, 600, 400]}
    j = judge([right, PERSON])
    assert [p.box[0] for p in j.persons] == [100, 400]
