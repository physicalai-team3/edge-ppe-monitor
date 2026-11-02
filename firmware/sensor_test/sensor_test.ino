// 👤 팀원 1 — person_sensor 단독 테스트 스케치 (Wi-Fi·트리거·전송 없이 카메라만 검증)
//
// 준비: sh sync.sh  (../ppe_cam 의 센서 파일과 config.h 를 이 폴더로 복사. 복사본은 git 에 안 올라감)
//       → 원본은 ../ppe_cam/person_sensor.cpp 다. 복사본을 고치지 말 것 (다음 sync 때 덮어씀)
// 업로드: Arduino IDE 보드 XIAO_ESP32S3, PSRAM "OPI PSRAM", 시리얼 115200
//
// 부팅하면 자동 테스트를 1회 돌리고 PASS/FAIL 을 출력한다. 이후 시리얼 명령:
//   t  자동 테스트 다시 실행
//   c  1장 촬영해서 크기·시간 출력
//   d  1장 촬영해서 base64 로 덤프 (PC: python save_jpeg.py COM5 → 파일로 저장해서 화질·구도 확인)
//   p  poll() 5초 반복해서 fps·status 출력
//   l  촬영/반납 200회 반복 (메모리 누수 장기 확인)
#include "config.h"
#include "person_sensor.h"

#if PPE_SENSOR_STUB
#error "config.h 의 PPE_SENSOR_STUB 를 0 으로 바꾸고 sync.sh 를 다시 실행하세요"
#endif

static const size_t kTargetLen = 60 * 1024;   // 계약 목표
static const size_t kMaxLen = 512 * 1024;     // 계약 상한
static const uint32_t kCaptureLimitMs = 500;  // 계약: capture_jpeg 500ms 이내
static const size_t kLeakTolerance = 1024;    // PSRAM 여유 변동 허용치

static bool s_camera_ok = false;
static int s_fail = 0;

static void check(bool ok, const char* name) {
  Serial.printf("  [%s] %s\n", ok ? "PASS" : "FAIL", name);
  if (!ok) s_fail++;
}

static bool jpeg_markers_ok(const jpeg_frame_t& f) {
  return f.len >= 4 && f.buf[0] == 0xFF && f.buf[1] == 0xD8 &&
         f.buf[f.len - 2] == 0xFF && f.buf[f.len - 1] == 0xD9;
}

// n 회 촬영·반납하면서 크기·시간·PSRAM 을 기록한다
static void capture_loop(int n, bool verbose) {
  size_t free_before = ESP.getFreePsram();
  size_t min_len = SIZE_MAX, max_len = 0, sum_len = 0;
  uint32_t max_ms = 0;
  int ok = 0, bad_marker = 0, bad_size = 0;

  for (int i = 0; i < n; i++) {
    jpeg_frame_t f = {};
    uint32_t t0 = millis();
    if (!person_sensor_capture_jpeg(&f)) continue;
    uint32_t ms = millis() - t0;
    ok++;
    if (!jpeg_markers_ok(f)) bad_marker++;
    if (f.width != 640 || f.height != 480) bad_size++;
    min_len = min(min_len, f.len);
    max_len = max(max_len, f.len);
    sum_len += f.len;
    max_ms = max(max_ms, ms);
    if (verbose) Serial.printf("    #%d %u bytes %lums\n", i, (unsigned)f.len, (unsigned long)ms);
    person_sensor_release(&f);
  }
  size_t free_after = ESP.getFreePsram();
  long diff = (long)free_before - (long)free_after;

  Serial.printf("  captures ok=%d/%d  size min=%u avg=%u max=%u  max_time=%lums\n", ok, n,
                ok ? (unsigned)min_len : 0, ok ? (unsigned)(sum_len / ok) : 0, (unsigned)max_len,
                (unsigned long)max_ms);
  Serial.printf("  PSRAM free before=%u after=%u (diff=%ld)\n", (unsigned)free_before,
                (unsigned)free_after, diff);

  check(ok == n, "모든 촬영 성공");
  check(bad_marker == 0, "JPEG SOI(FF D8) ~ EOI(FF D9)");
  check(bad_size == 0, "VGA 640x480");
  check(max_len <= kMaxLen, "512KB 상한 이하");
  if (ok && max_len > kTargetLen) {
    Serial.println("  [WARN] 60KB 목표 초과 → config.h PPE_JPEG_QUALITY 값을 올리세요 (12→15~20)");
  }
  check(max_ms <= kCaptureLimitMs, "촬영 500ms 이내");
  check(diff <= (long)kLeakTolerance, "release 후 PSRAM 누수 없음");
}

static void run_tests() {
  s_fail = 0;
  Serial.println("\n===== person_sensor self-test =====");

  Serial.println("[1] begin()");
  check(s_camera_ok, "카메라 초기화 (PSRAM·핀·센서)");
  if (!s_camera_ok) {
    person_result_t r = person_sensor_poll();
    check(r.status == PS_CAMERA_INIT && !r.person && r.count == 0, "실패 후 poll() == PS_CAMERA_INIT");
    jpeg_frame_t f = {};
    check(!person_sensor_capture_jpeg(&f), "실패 후 capture_jpeg() == false");
    Serial.printf("===== FAIL (%d) — 배선/IDE PSRAM 설정/camera_pins.h 확인 =====\n", s_fail);
    return;
  }

  Serial.println("[2] capture/release 20회");
  capture_loop(20, false);

  Serial.println("[3] 계약 규칙");
  {
    jpeg_frame_t a = {}, b = {};
    bool first = person_sensor_capture_jpeg(&a);
    bool second = person_sensor_capture_jpeg(&b);
    check(first, "첫 capture 성공");
    check(!second, "release 전 재호출은 false");
    check(b.buf == nullptr && b.handle == nullptr, "실패 시 out 을 건드리지 않음");
    person_sensor_release(&a);
    check(a.handle == nullptr, "release 후 handle 비움");
    person_sensor_release(&a);  // 두 번 불러도 안전해야 함
    person_sensor_release(nullptr);
    check(true, "release 중복·nullptr 호출에도 멈추지 않음");
    jpeg_frame_t c = {};
    bool again = person_sensor_capture_jpeg(&c);
    check(again, "release 후 다시 capture 가능");
    if (again) person_sensor_release(&c);
  }

  Serial.println("[4] poll() 형식");
  {
    person_result_t r = person_sensor_poll();
    check(r.status == PS_OK, "status == PS_OK");
    check(r.person == (r.count > 0), "person == (count > 0)");
    check(r.count > 0 || r.score == 0.0f, "count == 0 이면 score == 0");
    Serial.printf("  person=%d count=%u score=%.2f infer=%lums\n",
                  r.person, r.count, r.score, (unsigned long)r.infer_ms);
  }

  Serial.printf("===== %s (fail=%d) =====\n", s_fail == 0 ? "ALL PASS" : "FAIL", s_fail);
}

static void poll_for(uint32_t ms) {
  uint32_t start = millis();
  int frames = 0, ok = 0;
  while ((uint32_t)(millis() - start) < ms) {
    person_result_t r = person_sensor_poll();
    frames++;
    if (r.status == PS_OK) ok++;
    Serial.printf("  status=%d person=%d count=%u score=%.2f infer=%lums\n", r.status, r.person,
                  r.count, r.score, (unsigned long)r.infer_ms);
  }
  Serial.printf("  %d frames in %lums → %.1f fps (ok=%d)\n", frames, (unsigned long)ms,
                frames * 1000.0f / ms, ok);
}

static void dump_base64() {
  jpeg_frame_t f = {};
  if (!person_sensor_capture_jpeg(&f)) {
    Serial.println("capture failed");
    return;
  }
  static const char* kB64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  Serial.printf("---JPEG BEGIN %u---\n", (unsigned)f.len);
  char line[77];
  int col = 0;
  for (size_t i = 0; i < f.len; i += 3) {
    uint32_t v = (uint32_t)f.buf[i] << 16;
    if (i + 1 < f.len) v |= (uint32_t)f.buf[i + 1] << 8;
    if (i + 2 < f.len) v |= f.buf[i + 2];
    line[col++] = kB64[(v >> 18) & 63];
    line[col++] = kB64[(v >> 12) & 63];
    line[col++] = i + 1 < f.len ? kB64[(v >> 6) & 63] : '=';
    line[col++] = i + 2 < f.len ? kB64[v & 63] : '=';
    if (col >= 76) {
      line[col] = '\0';
      Serial.println(line);
      col = 0;
    }
  }
  if (col > 0) {
    line[col] = '\0';
    Serial.println(line);
  }
  Serial.println("---JPEG END---");
  person_sensor_release(&f);
}

void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 3000) delay(10);  // USB CDC 연결 대기 (최대 3초)
  delay(500);

  s_camera_ok = person_sensor_begin();
  run_tests();
  Serial.println("\n명령: t=테스트 c=촬영 d=JPEG덤프 p=poll 5초 l=누수 200회");
}

void loop() {
  if (!Serial.available()) {
    delay(10);
    return;
  }
  char cmd = Serial.read();
  switch (cmd) {
    case 't': run_tests(); break;
    case 'c': capture_loop(1, true); break;
    case 'd': dump_base64(); break;
    case 'p': poll_for(5000); break;
    case 'l': s_fail = 0; capture_loop(200, false); break;
    default: break;
  }
}
