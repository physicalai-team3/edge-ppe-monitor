// 👤 팀원 1 — 카메라 + Edge Impulse 사람 검출(FOMO) + 전송용 JPEG 촬영
#include "config.h"
#if !PPE_SENSOR_STUB

#include <Arduino.h>
#include "esp_camera.h"
#include "camera_pins.h"
#include "person_sensor.h"
#include <string.h>
#include "esp_jpg_decode.h"
#include <Person_detection_FOMO_inferencing.h>  // firmware/libraries/Person_detection_FOMO_inferencing

// 카메라는 VGA JPEG 로 고정한다.
//   - 전송: 프레임을 그대로 넘긴다 (해상도 전환 없음 → 전환 직후 깨진 프레임 버릴 필요 없음)
//   - 검출: 1/4 축소 디코드(160x120 흑백, PPE_SENSOR_DECODE_DIV) → 모델 입력 96x96 (FIT_LONGEST: 96x72 + 위아래 검정 패딩)
static const uint16_t kWidth = 640;
static const uint16_t kHeight = 480;

// Edge Impulse 프로젝트의 사람 라벨. 이 모델(Person detection FOMO)은 "person" 이 아니라 "hum" 이다.
// 모델을 바꾸면 Studio 의 라벨 이름과 맞춘다.
static const char* kPersonLabel = "hum";

#ifndef PPE_SENSOR_PROFILE
#define PPE_SENSOR_PROFILE 0  // 1: poll() 마다 단계별 시간(디코드·리사이즈·추론) 출력. config.h 에서 켠다
#endif

// 검출용 축소 디코드 배율 (config.h PPE_SENSOR_DECODE_DIV, 4 또는 8). 실측 XIAO S3 + OV3660:
//   4 [기본]: 160x120 → 96x72 축소. decode 198ms, 3.2fps. 사람 앞에서 대부분 person=1
//   8: 80x60 → 96x72 확대. DC 계수만 써서 IDCT 생략. decode 33ms, 6.6fps. 검출 약함(33프레임 중 1~5회)
#ifndef PPE_SENSOR_DECODE_DIV
#define PPE_SENSOR_DECODE_DIV 4
#endif
#if PPE_SENSOR_DECODE_DIV == 8
static const jpg_scale_t kDecodeScale = JPG_SCALE_8X;
#elif PPE_SENSOR_DECODE_DIV == 4
static const jpg_scale_t kDecodeScale = JPG_SCALE_4X;
#else
#error "PPE_SENSOR_DECODE_DIV 는 4 또는 8"
#endif
static const uint16_t kSmallW = kWidth / PPE_SENSOR_DECODE_DIV;
static const uint16_t kSmallH = kHeight / PPE_SENSOR_DECODE_DIV;
static const int kInW = EI_CLASSIFIER_INPUT_WIDTH;   // 96
static const int kInH = EI_CLASSIFIER_INPUT_HEIGHT;  // 96

static_assert(EI_CLASSIFIER_INPUT_WIDTH == 96 && EI_CLASSIFIER_INPUT_HEIGHT == 96,
              "모델 입력 크기가 바뀌면 리사이즈 코드를 확인할 것");
static_assert(EI_CLASSIFIER_OBJECT_DETECTION == 1, "FOMO(객체 검출) 모델이어야 한다");
static_assert(EI_CLASSIFIER_RESIZE_MODE == EI_CLASSIFIER_RESIZE_FIT_LONGEST,
              "Studio 의 resize mode 가 바뀌면 to_model_input() 을 맞출 것");

static uint8_t s_small[kSmallW * kSmallH];  // 축소 디코드 결과 (흑백)
static uint8_t s_input[kInW * kInH];        // 모델 입력 (흑백)
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

// ── 검출용 전처리 ─────────────────────────────────────────────

struct decode_ctx_t {
  const uint8_t* src;
  size_t len;
};

static size_t jpg_read(void* arg, size_t index, uint8_t* buf, size_t len) {
  decode_ctx_t* c = (decode_ctx_t*)arg;
  if (index >= c->len) return 0;
  if (index + len > c->len) len = c->len - index;
  if (buf != nullptr) memcpy(buf, c->src + index, len);
  return len;
}

// 디코더가 RGB888 블록을 넘겨준다. 흑백으로 바꿔 s_small 에 쓴다.
// (R + 2G + B) / 4 는 R·B 순서와 무관하다 (esp32-camera 의 RGB/BGR 순서 이슈 회피)
static bool jpg_write(void* arg, uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint8_t* data) {
  (void)arg;
  if (data == nullptr) return true;  // 시작/끝 알림
  for (uint16_t j = 0; j < h; j++) {
    uint16_t yy = y + j;
    if (yy >= kSmallH) break;
    const uint8_t* p = data + (size_t)j * w * 3;
    for (uint16_t i = 0; i < w; i++, p += 3) {
      uint16_t xx = x + i;
      if (xx >= kSmallW) continue;
      s_small[yy * kSmallW + xx] = (uint8_t)((p[0] + 2 * p[1] + p[2]) >> 2);
    }
  }
  return true;
}

// 축소 디코드 이미지 → 96x96. Edge Impulse FIT_LONGEST 과 같게: 비율 유지 96x72 (양선형) + 위아래 12줄 검정
static void to_model_input() {
  const int rw = kInW;
  const int rh = kInW * kSmallH / kSmallW;  // 72
  const int top = (kInH - rh) / 2;          // 12
  memset(s_input, 0, sizeof(s_input));
  for (int y = 0; y < rh; y++) {
    float fy = (y + 0.5f) * kSmallH / rh - 0.5f;
    if (fy < 0) fy = 0;
    int y0 = (int)fy;
    int y1 = y0 + 1 < kSmallH ? y0 + 1 : y0;
    float wy = fy - y0;
    for (int x = 0; x < rw; x++) {
      float fx = (x + 0.5f) * kSmallW / rw - 0.5f;
      if (fx < 0) fx = 0;
      int x0 = (int)fx;
      int x1 = x0 + 1 < kSmallW ? x0 + 1 : x0;
      float wx = fx - x0;
      float top_v = s_small[y0 * kSmallW + x0] * (1 - wx) + s_small[y0 * kSmallW + x1] * wx;
      float bot_v = s_small[y1 * kSmallW + x0] * (1 - wx) + s_small[y1 * kSmallW + x1] * wx;
      s_input[(top + y) * kInW + x] = (uint8_t)(top_v * (1 - wy) + bot_v * wy + 0.5f);
    }
  }
}

// Edge Impulse 이미지 신호는 픽셀당 0xRRGGBB 를 float 로 받는다 (흑백은 R=G=B)
static int get_signal_data(size_t offset, size_t length, float* out) {
  for (size_t i = 0; i < length; i++) {
    uint32_t g = s_input[offset + i];
    out[i] = (float)((g << 16) | (g << 8) | g);
  }
  return 0;
}

person_result_t person_sensor_poll() {
  person_result_t r = {};
  r.uptime_ms = millis();
  if (!s_ready) {
    r.status = PS_CAMERA_INIT;
    return r;
  }

  camera_fb_t* fb = esp_camera_fb_get();
  if (fb == nullptr) {
    r.status = PS_CAPTURE_FAIL;
    return r;
  }
  r.uptime_ms = millis();  // 프레임을 얻은 시각

  // infer_ms = 디코드 + 리사이즈 + run_classifier (poll 한 번의 처리 시간)
  uint32_t t_dec = micros();
  decode_ctx_t ctx = {fb->buf, fb->len};
  esp_err_t err = esp_jpg_decode(fb->len, kDecodeScale, jpg_read, jpg_write, &ctx);
  esp_camera_fb_return(fb);
  if (err != ESP_OK) {
    r.status = PS_CAPTURE_FAIL;
    r.infer_ms = millis() - r.uptime_ms;
    return r;
  }
  uint32_t t_rsz = micros();
  to_model_input();
  uint32_t t_cls = micros();

  signal_t signal;
  signal.total_length = kInW * kInH;
  signal.get_data = &get_signal_data;
  ei_impulse_result_t result = {};
  EI_IMPULSE_ERROR ei_err = run_classifier(&signal, &result, false);
  r.infer_ms = millis() - r.uptime_ms;
#if PPE_SENSOR_PROFILE
  uint32_t t_end = micros();
  Serial.printf("[profile] decode=%lums resize=%lums run_classifier=%lums (dsp=%dms nn=%dms post=%dms)\n",
                (unsigned long)((t_rsz - t_dec) / 1000), (unsigned long)((t_cls - t_rsz) / 1000),
                (unsigned long)((t_end - t_cls) / 1000), result.timing.dsp,
                result.timing.classification, result.timing.postprocessing);
#endif
  if (ei_err != EI_IMPULSE_OK) {
    r.status = PS_INFER_FAIL;
    return r;
  }

  // 참고: run_classifier 가 모델 자체 임계값(0.5) 미만 박스는 이미 버린다.
  //       PPE_PERSON_THRESHOLD 는 0.5 이상일 때만 효과가 있다.
  uint32_t count = 0;
  float best = 0.0f;
  for (uint32_t i = 0; i < result.bounding_boxes_count; i++) {
    const ei_impulse_result_bounding_box_t& bb = result.bounding_boxes[i];
    if (bb.value <= 0.0f || bb.label == nullptr) continue;
    if (strcmp(bb.label, kPersonLabel) != 0) continue;
    if (bb.value < PPE_PERSON_THRESHOLD) continue;
    count++;
    if (bb.value > best) best = bb.value;
  }
  r.status = PS_OK;
  r.count = count > 255 ? 255 : (uint8_t)count;
  r.person = r.count > 0;
  r.score = r.person ? best : 0.0f;
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
