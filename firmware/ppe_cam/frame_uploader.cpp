// 👤 팀원 2
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "config.h"
#include "frame_uploader.h"

static uint32_t s_frame_seq = 0;       // 새 사진마다 +1, 재시도는 같은 값
static uint32_t s_frames_sent = 0;     // 200 받은 전송 수 (하트비트 frames_sent)
static uint32_t s_last_heartbeat_ms = 0;
static char s_last_error[32] = "";

void uploader_begin() {
  // TODO: WiFi.mode(WIFI_STA); WiFi.begin(PPE_WIFI_SSID, PPE_WIFI_PASS);
  //       configTime(0, 0, "pool.ntp.org");  // UTC
}

void uploader_tick() {
  // TODO: 끊겼으면 재접속 (블로킹 금지)
  // TODO: PPE_HEARTBEAT_MS 마다 POST /api/v1/heartbeat (2차 목표, docs/03-contracts.md §3.6)
  //       frames_sent = s_frames_sent, last_error = s_last_error (빈 문자열이면 null)
  (void)s_last_heartbeat_ms;
}

bool uploader_connected() { return WiFi.status() == WL_CONNECTED; }

bool uploader_time_synced() { return time(nullptr) > 1704067200; }

void uploader_set_last_error(const char* error) {
  strncpy(s_last_error, error, sizeof(s_last_error) - 1);
  s_last_error[sizeof(s_last_error) - 1] = '\0';
}

upload_reply_t uploader_send_frame(const jpeg_frame_t* frame, const person_result_t* trigger) {
  upload_reply_t reply = {};
  if (!uploader_connected()) {
    reply.status = UP_NO_WIFI;
    return reply;
  }
  uint32_t seq = s_frame_seq++;
  // TODO: docs/03-contracts.md §3.1, §3.4
  //   URL  http://PPE_GATEWAY_HOST:PPE_GATEWAY_PORT/api/v1/frames
  //   헤더 Content-Type: image/jpeg, X-Device-Id, X-Device-Key, X-Frame-Seq(seq),
  //        X-Person-Count(trigger->count), X-Person-Score("%.2f", trigger->score),
  //        X-Captured-At(uploader_time_synced() 일 때만, "%Y-%m-%dT%H:%M:%SZ"), X-Fw-Version
  //   body http.POST((uint8_t*)frame->buf, frame->len)   ← Content-Length 자동
  //   200 → ArduinoJson 으로 result/persons/cloud 파싱, s_frames_sent++
  //   4xx/5xx → body 의 "error" 를 reply.error 에, uploader_set_last_error("http_<코드>")
  //   연결 실패·타임아웃·5xx → delay(500) 후 같은 seq 로 1회 재시도
  (void)frame;
  (void)trigger;
  (void)seq;
  reply.status = UP_HTTP_ERROR;
  return reply;
}
