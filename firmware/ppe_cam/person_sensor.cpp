// 👤 팀원 1 — 카메라 + Edge Impulse 사람 검출(FOMO) + 전송용 JPEG 촬영
#include "config.h"
#if !PPE_SENSOR_STUB

#include <Arduino.h>
#include "esp_camera.h"
#include "camera_pins.h"
#include "person_sensor.h"
// TODO: Edge Impulse 에서 내보낸 라이브러리 헤더 이름으로 바꾼다 (firmware/libraries/README.md)
// #include <Person_detection_-_FOMO_inferencing.h>

static bool s_ready = false;

bool person_sensor_begin() {
  // TODO: camera_config_t 를 camera_pins.h 핀으로 채우고 esp_camera_init()
  //   - PSRAM 필수 (psramFound() 확인), fb_count 2, fb_location CAMERA_FB_IN_PSRAM
  //   - 검출용 프레임과 전송용 VGA JPEG 를 어떻게 얻을지 결정 (set_framesize 전환 또는 JPEG 디코드)
  s_ready = false;
  return s_ready;
}

person_result_t person_sensor_poll() {
  person_result_t r = {};
  r.uptime_ms = millis();
  if (!s_ready) {
    r.status = PS_CAMERA_INIT;
    return r;
  }
  // TODO: 프레임 획득 → 모델 입력 크기(96x96)로 축소 → run_classifier()
  //   → bounding_boxes 중 label == "person" && value >= PPE_PERSON_THRESHOLD 개수·최고점
  r.status = PS_OK;
  return r;
}

bool person_sensor_capture_jpeg(jpeg_frame_t* out) {
  // TODO: VGA(640x480) JPEG 1장. out->handle 에 camera_fb_t* 보관
  (void)out;
  return false;
}

void person_sensor_release(jpeg_frame_t* frame) {
  // TODO: esp_camera_fb_return((camera_fb_t*)frame->handle)
  (void)frame;
}

#endif
