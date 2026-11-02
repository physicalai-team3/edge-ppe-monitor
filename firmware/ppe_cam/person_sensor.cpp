// 👤 팀원 1 — 카메라 + Edge Impulse 사람 검출(FOMO) + 전송용 JPEG 촬영
#include "config.h"
#if !PPE_SENSOR_STUB

#include <Arduino.h>
#include "esp_camera.h"
#include "camera_pins.h"
#include "person_sensor.h"
// TODO: Edge Impulse 에서 내보낸 라이브러리 헤더 이름으로 바꾼다 (firmware/libraries/README.md)
// #include <Person_detection_-_FOMO_inferencing.h>

// 카메라는 VGA JPEG 로 고정한다.
//   - 전송: 프레임을 그대로 넘긴다 (해상도 전환 없음 → 전환 직후 깨진 프레임 버릴 필요 없음)
//   - 검출: poll() 에서 1/4 축소 디코드(160x120) → 96x96 흑백 (모델 통합 시 구현)
static const uint16_t kWidth = 640;
static const uint16_t kHeight = 480;
static const size_t kJpegMaxLen = 512 * 1024;  // 계약 §2.1 절대 상한
static const size_t kEoiSearchLen = 1024;      // 끝부분 패딩 안에서 EOI(FF D9) 찾는 범위
static const int kWarmupFrames = 3;            // 초기 노출·화이트밸런스 안정화용으로 버리는 프레임

static bool s_ready = false;
static bool s_holding = false;  // capture_jpeg() 후 release() 전까지 true

bool person_sensor_begin() {
  s_ready = false;
  s_holding = false;

  if (!psramFound()) {
    Serial.println("[sensor] PSRAM not found (Arduino IDE: Tools > PSRAM > OPI PSRAM)");
    return false;
  }
  Serial.printf("[sensor] PSRAM size=%u free=%u\n", ESP.getPsramSize(), ESP.getFreePsram());

  camera_config_t c = {};
  c.pin_pwdn = PWDN_GPIO_NUM;
  c.pin_reset = RESET_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM;
  c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;
  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d0 = Y2_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM;
  c.pin_href = HREF_GPIO_NUM;
  c.pin_pclk = PCLK_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.ledc_timer = LEDC_TIMER_0;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA;
  c.jpeg_quality = PPE_JPEG_QUALITY;
  c.fb_count = 2;                       // 1장은 전송 중 보관, 1장은 계속 채움
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;     // 항상 가장 최근 프레임 (오래된 버퍼 방지)

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[sensor] esp_camera_init failed: 0x%x\n", err);
    return false;  // 재부팅 루프 금지. 이후 poll() 은 PS_CAMERA_INIT
  }

  sensor_t* s = esp_camera_sensor_get();
  if (s != nullptr) {
    Serial.printf("[sensor] camera PID=0x%x\n", s->id.PID);
    if (s->id.PID == OV3660_PID) {  // XIAO Sense 일부 보드는 OV3660 (Seeed 예제 설정)
      s->set_vflip(s, 1);
      s->set_brightness(s, 1);
      s->set_saturation(s, -2);
    }
  }

  for (int i = 0; i < kWarmupFrames; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb != nullptr) esp_camera_fb_return(fb);
  }

  s_ready = true;
  Serial.printf("[sensor] camera init OK (VGA JPEG q=%d), PSRAM free=%u\n",
                PPE_JPEG_QUALITY, ESP.getFreePsram());
  return true;
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

// 계약 §2.1: VGA, SOI(FF D8) ~ EOI(FF D9), 512KB 이하. 성공 시 *len 은 EOI 까지의 길이.
static bool jpeg_valid(const camera_fb_t* fb, size_t* len) {
  if (fb->format != PIXFORMAT_JPEG) {
    Serial.printf("[sensor] not JPEG (format=%d)\n", fb->format);
    return false;
  }
  if (fb->width != kWidth || fb->height != kHeight) {
    Serial.printf("[sensor] unexpected size %ux%u\n", fb->width, fb->height);
    return false;
  }
  if (fb->len < 4 || fb->buf[0] != 0xFF || fb->buf[1] != 0xD8) {
    Serial.println("[sensor] missing JPEG SOI");
    return false;
  }
  // 센서가 EOI 뒤에 패딩을 붙이는 경우가 있어 끝에서부터 찾고 길이를 잘라낸다
  size_t stop = fb->len > kEoiSearchLen ? fb->len - kEoiSearchLen : 2;
  for (size_t i = fb->len - 1; i > stop; i--) {
    if (fb->buf[i - 1] == 0xFF && fb->buf[i] == 0xD9) {
      *len = i + 1;
      if (*len > kJpegMaxLen) {
        Serial.printf("[sensor] JPEG too large: %u bytes (raise PPE_JPEG_QUALITY)\n", *len);
        return false;
      }
      return true;
    }
  }
  Serial.println("[sensor] missing JPEG EOI");
  return false;
}

bool person_sensor_capture_jpeg(jpeg_frame_t* out) {
  if (!s_ready || out == nullptr) return false;
  if (s_holding) {  // 계약 위반: release() 전에 재호출
    Serial.println("[sensor] capture_jpeg called before release()");
    return false;
  }

  uint32_t start = millis();
  camera_fb_t* fb = esp_camera_fb_get();
  if (fb == nullptr) {
    Serial.println("[sensor] esp_camera_fb_get failed");
    return false;
  }

  size_t len = 0;
  if (!jpeg_valid(fb, &len)) {
    esp_camera_fb_return(fb);
    return false;
  }

  out->buf = fb->buf;
  out->len = len;
  out->width = fb->width;
  out->height = fb->height;
  out->handle = fb;
  s_holding = true;

#if PPE_SENSOR_LOG
  Serial.printf("[sensor] jpeg %ux%u %u bytes in %lums, PSRAM free=%u\n", out->width, out->height,
                (unsigned)out->len, (unsigned long)(millis() - start), ESP.getFreePsram());
#endif
  return true;
}

void person_sensor_release(jpeg_frame_t* frame) {
  if (frame == nullptr || frame->handle == nullptr) return;
  esp_camera_fb_return((camera_fb_t*)frame->handle);
  frame->handle = nullptr;
  frame->buf = nullptr;
  frame->len = 0;
  s_holding = false;
}

#endif
