// 👤 팀원 2
#include "trigger.h"

void trigger_init(trigger_t* t, trigger_config_t cfg) {
  t->cfg = cfg;
  t->state = TRIG_IDLE;
  t->streak = 0;
  t->last_seen_ms = 0;
  t->last_shot_ms = 0;
}

bool trigger_update(trigger_t* t, bool person, uint32_t now_ms) {
  // TODO: docs/03-contracts.md §2.2 표대로 구현
  //   IDLE:    person 연속 trigger_frames → PRESENT, last_shot = now, return true / false 면 streak = 0
  //   PRESENT: person 이고 now - last_shot >= resend_ms → last_shot = now, return true
  //            now - last_seen >= absent_ms → IDLE, streak = 0
  //   시간 비교는 (uint32_t)(now - last) >= interval (millis 오버플로 안전)
  (void)t;
  (void)person;
  (void)now_ms;
  return false;
}
