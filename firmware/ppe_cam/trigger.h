// 👤 팀원 2 — "언제 찍어서 보낼지" 결정하는 상태 머신 (docs/03-contracts.md §2 트리거 규칙)
// Arduino 의존성 없음 → test/test_trigger.cpp 로 PC 에서 테스트한다.
#pragma once
#include <stdint.h>

typedef enum { TRIG_IDLE = 0, TRIG_PRESENT = 1 } trigger_state_t;

typedef struct {
  uint8_t  trigger_frames;  // 연속 N프레임 사람 → PRESENT + 촬영 (PPE_TRIGGER_FRAMES)
  uint32_t resend_ms;       // PRESENT 동안 재촬영 주기 (PPE_RESEND_MS)
  uint32_t absent_ms;       // 마지막 검출 후 N ms → IDLE (PPE_ABSENT_MS)
} trigger_config_t;

typedef struct {
  trigger_config_t cfg;
  trigger_state_t  state;
  uint8_t  streak;          // 연속 검출 프레임 수
  uint32_t last_seen_ms;    // 마지막으로 사람을 본 시각
  uint32_t last_shot_ms;    // 마지막 촬영 시각
} trigger_t;

void trigger_init(trigger_t* t, trigger_config_t cfg);

// 매 프레임 호출. 지금 촬영·전송해야 하면 true
bool trigger_update(trigger_t* t, bool person, uint32_t now_ms);
