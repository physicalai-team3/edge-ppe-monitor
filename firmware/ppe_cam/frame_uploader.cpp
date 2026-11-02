// 👤 팀원 2
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <sys/time.h>
#include "config.h"
#include "frame_uploader.h"

#define PPE_WIFI_RETRY_MS       10000  // 끊겼을 때 재접속 시도 간격
#define PPE_RETRY_DELAY_MS      500    // 전송 재시도 전 대기 (docs/03-contracts.md §3.4)
#define PPE_HEARTBEAT_TIMEOUT_MS 2000  // 하트비트는 loop()를 오래 막지 않게 짧게

static uint32_t s_frame_seq = 0;       // 새 사진마다 +1, 재시도는 같은 값
static uint32_t s_frames_sent = 0;     // 200 받은 전송 수 (하트비트 frames_sent)
static uint32_t s_last_heartbeat_ms = 0;
static uint32_t s_last_wifi_try_ms = 0;
static bool s_was_connected = false;
static bool s_time_logged = false;
static char s_last_error[32] = "";

static String gateway_url(const char* path) {
  return String("http://") + PPE_GATEWAY_HOST + ":" + String(PPE_GATEWAY_PORT) + path;
}

static void copy_str(char* dst, size_t cap, const char* src) {
  strncpy(dst, src ? src : "", cap - 1);
  dst[cap - 1] = '\0';
}

// ── Wi-Fi · NTP ─────────────────────────────────────────

void uploader_begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(PPE_WIFI_SSID, PPE_WIFI_PASS);  // 비동기. 결과는 uploader_tick()에서 확인
  s_last_wifi_try_ms = millis();
  configTime(0, 0, "pool.ntp.org");          // UTC (오프셋 0), 백그라운드 SNTP
  Serial.printf("[net] connecting to \"%s\" ...\n", PPE_WIFI_SSID);
}

bool uploader_connected() { return WiFi.status() == WL_CONNECTED; }

bool uploader_time_synced() { return time(nullptr) > 1704067200; }

void uploader_set_last_error(const char* error) {
  copy_str(s_last_error, sizeof(s_last_error), error);
}

static void send_heartbeat() {
  JsonDocument doc;
  doc["v"] = 1;
  doc["device_id"] = PPE_DEVICE_ID;
  doc["fw_version"] = PPE_FW_VERSION;
  doc["uptime_s"] = millis() / 1000;
  doc["rssi"] = WiFi.RSSI();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["frames_sent"] = s_frames_sent;
  if (s_last_error[0]) doc["last_error"] = s_last_error;
  else doc["last_error"] = nullptr;

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.setConnectTimeout(PPE_HEARTBEAT_TIMEOUT_MS);
  http.setTimeout(PPE_HEARTBEAT_TIMEOUT_MS);
  if (!http.begin(gateway_url("/api/v1/heartbeat"))) return;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", PPE_DEVICE_KEY);
  int code = http.POST(body);  // 실패해도 재시도하지 않는다 (§3.6)
  http.end();
  Serial.printf("[net] heartbeat http=%d\n", code);
}

void uploader_tick() {
  uint32_t now = millis();
  bool connected = uploader_connected();

  // 연결 상태가 바뀔 때만 로그
  if (connected != s_was_connected) {
    if (connected) {
      Serial.printf("[net] wifi connected ip=%s rssi=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else {
      Serial.println("[net] wifi disconnected");
      uploader_set_last_error("wifi_lost");
    }
    s_was_connected = connected;
  }

  // 끊겼으면 일정 간격으로 재접속 (블로킹 X)
  if (!connected) {
    if ((uint32_t)(now - s_last_wifi_try_ms) >= PPE_WIFI_RETRY_MS) {
      s_last_wifi_try_ms = now;
      Serial.println("[net] wifi reconnect ...");
      WiFi.reconnect();
    }
    return;
  }

  if (!s_time_logged && uploader_time_synced()) {
    s_time_logged = true;
    Serial.println("[net] NTP synced (UTC)");
  }

  // 하트비트 (2차 목표, §3.6)
  if ((uint32_t)(now - s_last_heartbeat_ms) >= PPE_HEARTBEAT_MS) {
    s_last_heartbeat_ms = now;
    send_heartbeat();
  }
}

// ── 사진 전송 ────────────────────────────────────────────

// ISO 8601 UTC, 밀리초 포함: 2026-11-02T05:31:12.345Z
static bool format_captured_at(char* out, size_t cap) {
  if (!uploader_time_synced()) return false;
  struct timeval tv;
  gettimeofday(&tv, nullptr);
  struct tm tm_utc;
  gmtime_r(&tv.tv_sec, &tm_utc);
  size_t n = strftime(out, cap, "%Y-%m-%dT%H:%M:%S", &tm_utc);
  if (n == 0) return false;
  snprintf(out + n, cap - n, ".%03ldZ", (long)(tv.tv_usec / 1000));
  return true;
}

static bool parse_ok_body(const String& body, upload_reply_t* reply) {
  JsonDocument doc;
  if (deserializeJson(doc, body)) return false;
  const char* result = doc["result"] | "";
  if (strcmp(result, "violation") == 0) reply->result = RES_VIOLATION;
  else if (strcmp(result, "compliant") == 0) reply->result = RES_COMPLIANT;
  else if (strcmp(result, "no_person") == 0) reply->result = RES_NO_PERSON;
  else return false;
  reply->persons = doc["persons"] | 0;
  copy_str(reply->cloud, sizeof(reply->cloud), doc["cloud"] | "none");
  return true;
}

static void parse_error_body(const String& body, upload_reply_t* reply) {
  JsonDocument doc;
  if (deserializeJson(doc, body)) return;
  copy_str(reply->error, sizeof(reply->error), doc["error"] | "");
}

// 1회 시도. HTTP 코드 반환 (연결 실패·타임아웃이면 음수)
static int post_once(const jpeg_frame_t* frame, const person_result_t* trigger,
                     uint32_t seq, String* body_out) {
  HTTPClient http;
  http.setConnectTimeout(PPE_HTTP_TIMEOUT_MS);
  http.setTimeout(PPE_HTTP_TIMEOUT_MS);
  if (!http.begin(gateway_url("/api/v1/frames"))) return HTTPC_ERROR_CONNECTION_REFUSED;

  char buf[40];
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Device-Id", PPE_DEVICE_ID);
  http.addHeader("X-Device-Key", PPE_DEVICE_KEY);
  snprintf(buf, sizeof(buf), "%lu", (unsigned long)seq);
  http.addHeader("X-Frame-Seq", buf);
  snprintf(buf, sizeof(buf), "%u", (unsigned)trigger->count);
  http.addHeader("X-Person-Count", buf);
  float score = trigger->score < 0 ? 0 : (trigger->score > 1 ? 1 : trigger->score);
  snprintf(buf, sizeof(buf), "%.2f", score);
  http.addHeader("X-Person-Score", buf);
  if (format_captured_at(buf, sizeof(buf))) {  // NTP 전이면 헤더 자체를 안 보낸다
    http.addHeader("X-Captured-At", buf);
  }
  http.addHeader("X-Fw-Version", PPE_FW_VERSION);

  // body = JPEG 그대로, Content-Length 자동 (chunked X)
  int code = http.POST((uint8_t*)frame->buf, frame->len);
  if (code > 0) *body_out = http.getString();
  http.end();
  return code;
}

upload_reply_t uploader_send_frame(const jpeg_frame_t* frame, const person_result_t* trigger) {
  upload_reply_t reply = {};
  copy_str(reply.cloud, sizeof(reply.cloud), "none");
  if (!uploader_connected()) {
    reply.status = UP_NO_WIFI;
    reply.http_code = -1;
    copy_str(reply.error, sizeof(reply.error), "no_wifi");
    return reply;
  }

  uint32_t seq = s_frame_seq++;  // 재시도는 같은 seq
  String body;
  int code = 0;

  for (int attempt = 0; attempt < 2; attempt++) {
    if (attempt > 0) {
      Serial.printf("[net] retry seq=%lu (prev http=%d)\n", (unsigned long)seq, code);
      delay(PPE_RETRY_DELAY_MS);
    }
    body = "";
    code = post_once(frame, trigger, seq, &body);
    bool retryable = (code < 0) || (code >= 500);  // 연결 실패·타임아웃·5xx 만 재시도
    if (!retryable) break;
  }
  reply.http_code = code;

  if (code == 200) {
    if (parse_ok_body(body, &reply)) {
      reply.status = UP_OK;
      s_frames_sent++;
    } else {
      reply.status = UP_BAD_RESPONSE;
      copy_str(reply.error, sizeof(reply.error), "bad_response");
      uploader_set_last_error("bad_response");
    }
    return reply;
  }

  if (code < 0) {
    reply.status = UP_TIMEOUT;
    copy_str(reply.error, sizeof(reply.error), "timeout");
    uploader_set_last_error("timeout");
    return reply;
  }

  // 4xx / 5xx (그 밖의 2xx·3xx 도 실패로 본다)
  reply.status = UP_HTTP_ERROR;
  parse_error_body(body, &reply);
  char err[16];
  snprintf(err, sizeof(err), "http_%d", code);
  uploader_set_last_error(err);
  return reply;
}
