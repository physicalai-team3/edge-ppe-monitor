"""쿨다운 테스트 (docs/03-contracts.md §5.4)."""
from app.dedup import Cooldown


def test_same_key_within_cooldown_is_duplicate():
    c = Cooldown(30)
    assert c.should_upload("xiao-01", ["no_helmet"], now=0)
    assert not c.should_upload("xiao-01", ["no_helmet"], now=10)


def test_duplicate_does_not_restart_timer():
    c = Cooldown(30)
    c.should_upload("xiao-01", ["no_helmet"], now=0)
    c.should_upload("xiao-01", ["no_helmet"], now=25)          # duplicate
    assert c.should_upload("xiao-01", ["no_helmet"], now=30)   # 마지막 업로드(0) 기준 30초


def test_different_violations_are_separate_keys():
    c = Cooldown(30)
    c.should_upload("xiao-01", ["no_helmet"], now=0)
    assert c.should_upload("xiao-01", ["no_helmet", "no_vest"], now=5)


def test_different_devices_are_separate_keys():
    c = Cooldown(30)
    c.should_upload("xiao-01", ["no_helmet"], now=0)
    assert c.should_upload("xiao-02", ["no_helmet"], now=5)
