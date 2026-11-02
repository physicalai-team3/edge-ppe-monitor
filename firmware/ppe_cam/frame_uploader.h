// 👤 팀원 2 — Wi-Fi·NTP 연결, Pi gateway 로 JPEG 전송, 하트비트 (docs/03-contracts.md §3)
#pragma once
#include "person_result.h"

typedef enum {
  UP_OK = 0,           // 200 + 응답 파싱 성공
  UP_NO_WIFI = 1,      // 전송 시도 안 함
  UP_HTTP_ERROR = 2,   // 최종 4xx/5xx (http_code 참고)
  UP_TIMEOUT = 3,      // 연결 실패·타임아웃 (재시도 후에도)
  UP_BAD_RESPONSE = 4, // 200 인데 JSON 파싱 실패
} upload_status_t;

typedef enum { RES_UNKNOWN = 0, RES_VIOLATION = 1, RES_COMPLIANT = 2, RES_NO_PERSON = 3 } frame_result_t;

typedef struct {
  upload_status_t status;
  int      http_code;      // 마지막 시도의 HTTP 코드 (연결 실패면 음수)
  frame_result_t result;   // 응답 "result" (UP_OK 일 때만 의미 있음)
  uint8_t  persons;        // 응답 "persons"
  char     cloud[12];      // 응답 "cloud": queued | duplicate | disabled | none
  char     error[32];      // 에러 응답의 "error" (예: "detector_unavailable"), 없으면 ""
} upload_reply_t;

// setup()에서 1회: Wi-Fi 접속 시작 + NTP(pool.ntp.org, UTC) 설정. 블로킹하지 않는다
void uploader_begin();

// loop()마다: Wi-Fi 재접속, 하트비트 주기 처리 (블로킹 최소화)
void uploader_tick();

bool uploader_connected();

// NTP 동기화 여부: time(nullptr) > 1704067200 (2024-01-01)
bool uploader_time_synced();

// 마지막 오류를 하트비트 last_error 에 싣기 위해 기록 ("camera_init", "http_503", "timeout" …)
void uploader_set_last_error(const char* error);

// 사진 1장 전송 (블로킹, 시도당 PPE_HTTP_TIMEOUT_MS).
// 연결 실패·타임아웃·5xx 면 500ms 후 같은 X-Frame-Seq 로 1회 재시도, 4xx 는 재시도 안 함 (§3.4)
upload_reply_t uploader_send_frame(const jpeg_frame_t* frame, const person_result_t* trigger);
