// 👤 팀원 2
#include "trigger.h"

// millis() 오버플로(약 49일)에도 안전한 경과 시간 비교
static inline bool elapsed(uint32_t now, uint32_t since, uint32_t interval) {
  return (uint32_t)(now - since) >= interval;
}

void trigger_init(trigger_t* t, trigger_config_t cfg) {
  t->cfg = cfg;
  t->state = TRIG_IDLE;
  t->streak = 0;
  t->last_seen_ms = 0;
  t->last_shot_ms = 0;
}

// docs/03-contracts.md §2.2
bool trigger_update(trigger_t* t, bool person, uint32_t now_ms) {
  if (t->state == TRIG_IDLE) {
    if (!person) {
      t->streak = 0;  // 연속이 끊기면 처음부터
      return false;
    }
    if (t->streak < 255) t->streak++;
    t->last_seen_ms = now_ms;
    if (t->streak >= t->cfg.trigger_frames) {
      t->state = TRIG_PRESENT;
      t->last_shot_ms = now_ms;  // 전송 성공 여부와 무관하게 "촬영 시각"
      return true;
    }
    return false;
  }

  // TRIG_PRESENT
  if (person) {
    t->last_seen_ms = now_ms;
    if (elapsed(now_ms, t->last_shot_ms, t->cfg.resend_ms)) {
      t->last_shot_ms = now_ms;
      return true;
    }
    return false;
  }

  // 사람이 안 보이는 프레임: absent_ms 이상이면 IDLE, 아니면 상태 유지
  if (elapsed(now_ms, t->last_seen_ms, t->cfg.absent_ms)) {
    t->state = TRIG_IDLE;
    t->streak = 0;
  }
  return false;
}
