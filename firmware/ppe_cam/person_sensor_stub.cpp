// 👤 팀원 2 — 모델·카메라 없이 개발하기 위한 가짜 센서 (PPE_SENSOR_STUB 1)
// BOOT 버튼을 누르고 있으면 "사람 있음". 촬영은 test_jpeg.h 의 고정 JPEG(640x480)를 돌려준다.
#include "config.h"
#if PPE_SENSOR_STUB

#include <Arduino.h>
#include "person_sensor.h"
#include "test_jpeg.h"

bool person_sensor_begin() {
  pinMode(PPE_BOOT_PIN, INPUT_PULLUP);
  return true;
}

person_result_t person_sensor_poll() {
  uint32_t start = millis();
  delay(200);  // 실제 추론 시간 흉내
  person_result_t r = {};
  r.status = PS_OK;
  r.person = digitalRead(PPE_BOOT_PIN) == LOW;
  r.count = r.person ? 1 : 0;
  r.score = r.person ? 0.9f : 0.0f;
  r.infer_ms = millis() - start;
  r.uptime_ms = start;
  return r;
}

bool person_sensor_capture_jpeg(jpeg_frame_t* out) {
  out->buf = kTestJpeg;
  out->len = kTestJpegLen;
  out->width = 640;
  out->height = 480;
  out->handle = nullptr;
  return true;
}

void person_sensor_release(jpeg_frame_t* frame) { (void)frame; }

#endif
