// 👤 팀원 2 — 조립: 센서(팀원 1) → 트리거 → 촬영 → 전송 → LED
// 흐름: docs/01-architecture.md §3, 계약: docs/03-contracts.md §2~3
#include "config.h"
#include "person_sensor.h"
#include "trigger.h"
#include "frame_uploader.h"

static trigger_t s_trigger;
static bool s_link_error = false;  // true 면 1초 주기 깜빡임 (Wi-Fi 끊김 / 마지막 전송 최종 실패)

static uint32_t s_led_toggle_ms = 0;
static bool s_led_on = false;

static void led_set(bool on) {
  s_led_on = on;
  digitalWrite(PPE_LED_PIN, on ? LOW : HIGH);  // active-low
}

static void led_blink(int times) {
  for (int i = 0; i < times; i++) {
    led_set(true);
    delay(100);
    led_set(false);
    if (i < times - 1) delay(100);
  }
}

// docs/03-contracts.md §3.5 — 최대 600ms 안에 끝난다 (3번 = 100ms × 5 + 꺼짐)
static void led_signal(const upload_reply_t& reply) {
  if (reply.status != UP_OK) {
    s_link_error = true;  // led_tick()이 1초 주기 깜빡임
    return;
  }
  s_link_error = false;
  if (reply.result == RES_VIOLATION) led_blink(3);
  else led_blink(1);
}

// 연결 문제면 1초 주기(500ms 켜짐 / 500ms 꺼짐)로 깜빡, 아니면 꺼 둔다. 블로킹 X
static void led_tick() {
  if (s_link_error || !uploader_connected()) {
    uint32_t now = millis();
    if ((uint32_t)(now - s_led_toggle_ms) >= 500) {
      s_led_toggle_ms = now;
      led_set(!s_led_on);
    }
  } else if (s_led_on) {
    led_set(false);
  }
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
