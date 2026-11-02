// 👤 팀원 2 — trigger 단위 테스트 (PC g++). 실행: docker compose --profile firmware run --rm fw sh test.sh
#include <cstdio>
#include "trigger.h"

static int failures = 0;
#define CHECK(cond)                                               \
  do {                                                            \
    if (!(cond)) {                                                \
      std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
      failures++;                                                 \
    }                                                             \
  } while (0)

static trigger_t make() {
  trigger_t t;
  trigger_init(&t, trigger_config_t{2, 5000, 2000});
  return t;
}

static void test_two_frames_trigger() {
  trigger_t t = make();
  CHECK(!trigger_update(&t, true, 0));     // 1프레임: 아직
  CHECK(trigger_update(&t, true, 200));    // 2프레임 연속: 촬영
  CHECK(t.state == TRIG_PRESENT);
}

static void test_single_frame_ignored() {
  trigger_t t = make();
  CHECK(!trigger_update(&t, true, 0));
  CHECK(!trigger_update(&t, false, 200));  // 끊김 → 연속 아님
  CHECK(!trigger_update(&t, true, 400));
}

static void test_resend_while_present() {
  trigger_t t = make();
  trigger_update(&t, true, 0);
  trigger_update(&t, true, 200);           // 촬영 @200
  CHECK(!trigger_update(&t, true, 3000));
  CHECK(trigger_update(&t, true, 5200));   // 5초 뒤 재촬영
}

static void test_absent_resets() {
  trigger_t t = make();
  trigger_update(&t, true, 0);
  trigger_update(&t, true, 200);
  CHECK(!trigger_update(&t, false, 2300)); // 2초 이상 안 보임 → IDLE
  CHECK(t.state == TRIG_IDLE);
  CHECK(!trigger_update(&t, true, 2500));  // 다시 연속 2프레임이 필요
  CHECK(trigger_update(&t, true, 2700));
}

static void test_short_miss_keeps_present() {
  trigger_t t = make();
  trigger_update(&t, true, 0);
  trigger_update(&t, true, 200);
  CHECK(!trigger_update(&t, false, 1000)); // 2초 미만 놓침 → 유지
  CHECK(t.state == TRIG_PRESENT);
  CHECK(!trigger_update(&t, true, 1200));  // 다시 보여도 재전송은 5초 주기대로
  CHECK(trigger_update(&t, true, 5200));
}

static void test_millis_overflow() {
  trigger_t t = make();
  const uint32_t near_max = 0xFFFFFF00u;
  trigger_update(&t, true, near_max);
  CHECK(trigger_update(&t, true, near_max + 200));
  CHECK(trigger_update(&t, true, near_max + 5200)); // 0을 넘어가도 5초 주기 유지
}

int main() {
  test_two_frames_trigger();
  test_single_frame_ignored();
  test_resend_while_present();
  test_absent_resets();
  test_short_miss_keeps_present();
  test_millis_overflow();
  if (failures) {
    std::printf("%d failure(s)\n", failures);
    return 1;
  }
  std::printf("all trigger tests passed\n");
  return 0;
}
