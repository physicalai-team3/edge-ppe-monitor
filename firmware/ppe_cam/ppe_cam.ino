// 👤 팀원 2 — 조립: 센서(팀원 1) → 트리거 → 촬영 → 전송 → LED
// 흐름: docs/01-architecture.md §3, 계약: docs/03-contracts.md §2~3
#include "config.h"
#include "person_sensor.h"
#include "trigger.h"
#include "frame_uploader.h"

static trigger_t s_trigger;
static bool s_link_error = false;  // true 면 1초 주기 깜빡임 (Wi-Fi 끊김 / 마지막 전송 최종 실패)

static void led_signal(const upload_reply_t& reply) {
  // TODO: docs/03-contracts.md §3.5 (active-low, 최대 600ms 안에 끝내기)
  //   UP_OK + RES_VIOLATION → 100ms 켜짐/꺼짐 3번
  //   UP_OK + 그 외         → 100ms 1번, s_link_error = false
  //   실패                  → s_link_error = true
  (void)reply;
}

static void led_tick() {
  // TODO: s_link_error 또는 !uploader_connected() 이면 1초 주기 깜빡임 (millis 기반, 블로킹 X)
}

void setup() {
  Serial.begin(115200);
  pinMode(PPE_LED_PIN, OUTPUT);
  digitalWrite(PPE_LED_PIN, HIGH);  // active-low: 끔

  if (!person_sensor_begin()) {
    Serial.println("[ppe] person_sensor_begin failed");  // 재부팅하지 않고 계속 (poll 이 PS_CAMERA_INIT)
    uploader_set_last_error("camera_init");
  }
  trigger_init(&s_trigger, trigger_config_t{PPE_TRIGGER_FRAMES, PPE_RESEND_MS, PPE_ABSENT_MS});
  uploader_begin();
}

void loop() {
  uploader_tick();
  led_tick();

  person_result_t r = person_sensor_poll();
#if PPE_SENSOR_LOG
  Serial.printf("[ppe] status=%d person=%d count=%u score=%.2f infer=%lums\n",
                r.status, r.person, r.count, r.score, (unsigned long)r.infer_ms);
#endif
  if (r.status != PS_OK) {  // 실패 프레임은 트리거에 넣지 않는다 (§2.2)
    delay(1000);
    return;
  }

  if (!trigger_update(&s_trigger, r.person, r.uptime_ms)) return;

  jpeg_frame_t frame;
  if (!person_sensor_capture_jpeg(&frame)) {  // false 면 release() 하지 않는다
    Serial.println("[ppe] capture failed");
    uploader_set_last_error("capture");
    return;
  }
  upload_reply_t reply = uploader_send_frame(&frame, &r);
  person_sensor_release(&frame);

  Serial.printf("[ppe] upload status=%d http=%d result=%d persons=%u cloud=%s error=%s\n",
                reply.status, reply.http_code, reply.result, reply.persons, reply.cloud, reply.error);
  led_signal(reply);
}
