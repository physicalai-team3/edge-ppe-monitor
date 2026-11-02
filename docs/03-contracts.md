# 03. 데이터 계약 (공동 소유)

> 이 문서, `shared/schemas/*.json`, `firmware/ppe_cam/person_result.h`, `firmware/ppe_cam/person_sensor.h`, `cloud/supabase/migrations/*.sql`은 **4명 공동 소유**다.
> 수정할 때는 커밋 메시지에 `[contract]`를 붙이고 관련된 사람에게 바로 알린다.
> 오전 첫 30분 안에 확정(동결)하고, 그 뒤에는 필드 **추가**만 허용한다 (이름 변경·삭제 금지).
> 이 문서와 코드가 다르면 **이 문서가 기준**이다. 코드를 문서에 맞추거나, `[contract]` 커밋으로 문서를 먼저 고친다.

## 1. 한눈에 보기

```
 팀원 1 ──(§2 C 구조체)──▶ 팀원 2 ──(§3 HTTP)──▶ 팀원 3 ──(§4 HTTP)──▶ detector
                                    ◀─(§3 JSON)──    │
                                                     ├──(§6 Storage + DB)──▶ Supabase ──(§7 Realtime)──▶ 팀원 4 web
```

| § | 구간 | 형식 | 생산 | 소비 | 스키마 |
|---|---|---|---|---|---|
| 2 | ESP32 내부: 센서 → 트리거·전송 | C 구조체 | 팀원 1 | 팀원 2 | `person_result.h`, `person_sensor.h` |
| 3 | ESP32 → Pi | HTTP POST (JPEG + 헤더) / JSON 응답 | 팀원 2 | 팀원 3 | `frame-response`, `heartbeat`, `error` |
| 4 | gateway → detector | HTTP POST (JPEG) / JSON 응답 | 팀원 3 | 팀원 3 | `detect-response`, `error` |
| 5 | 판정 규칙 | 문서 + 단위 테스트 | 팀원 3 | 전원 | `pi/gateway/tests/` |
| 6 | Pi → Supabase | Storage 객체 + DB 행 | 팀원 3 | 팀원 4 | `violation-row`, SQL |
| 7 | Supabase → Web | supabase-js 조회·구독 | 팀원 4 | 팀원 4 | SQL |

(스키마 파일은 모두 `shared/schemas/<이름>.schema.json`)

### 1.1 공통 규칙

| 항목 | 규칙 |
|---|---|
| `device_id` | 정규식 `^[a-z0-9-]{1,32}$`. 실제 장치 `xiao-01`(팀원 1 보드), `xiao-02`(팀원 2 보드), 가짜 `sim-01`(cam-sim), `seed-01`(cloud-seed). **보드마다 달라야 한다** |
| `gateway_id` | `pi-01` |
| 시간 형식 | ISO 8601 **UTC**, 끝은 `Z`, 밀리초는 선택 (`2026-11-02T05:31:12.345Z`) |
| 날짜 기준 | Storage 경로의 날짜 = `captured_at`의 **UTC 날짜**. 웹의 "오늘" = **한국 시간(Asia/Seoul) 0시부터** |
| 좌표 | 박스는 `[x1, y1, x2, y2]`, 원본 이미지 **픽셀 정수** (정규화 X). 왼쪽 위가 (0,0) |
| 점수 | 0~1 실수, **소수 셋째 자리까지** 반올림 |
| JSON 버전 | 모든 JSON 응답·요청에 `"v": 1`. 받는 쪽은 모르는 필드를 무시한다 |
| 문자 인코딩 | UTF-8 |

### 1.2 표준 클래스 (모델 원래 이름은 `detector`가 변환)

| 표준 이름 | 의미 |
|---|---|
| `person` | 사람 |
| `helmet` | 안전모 착용 머리 |
| `no_helmet` | 안전모 미착용 머리 |
| `vest` | 안전조끼 착용 몸통 |
| `no_vest` | 조끼 미착용 몸통 |

### 1.3 위반 종류

`violations`, `violation_types`에 들어가는 값은 `no_helmet`, `no_vest` 두 가지뿐이다. 배열은 **항상 이 순서**(`no_helmet` 먼저)로, 중복 없이 쓴다. 예: `[]`, `["no_helmet"]`, `["no_vest"]`, `["no_helmet","no_vest"]`.

---

## 2. ESP32 내부: person_result.h / person_sensor.h

팀원 1이 만들고 팀원 2가 쓴다. 이 두 헤더만 보면 서로의 `.cpp`를 읽을 필요가 없다.

```c
// person_result.h
typedef enum {
  PS_OK = 0,
  PS_CAMERA_INIT = 1,   // 카메라 초기화 실패 (재부팅 루프 금지, 이 값만 반환)
  PS_CAPTURE_FAIL = 2,  // 프레임 획득 실패
  PS_INFER_FAIL = 3,    // 모델 추론 실패
} ps_status_t;

typedef struct {
  ps_status_t status;
  bool     person;      // count > 0 과 항상 같다
  uint8_t  count;       // score >= PPE_PERSON_THRESHOLD 인 사람(FOMO 중심점) 수
  float    score;       // 그 중 최고 점수. count == 0 이면 0
  uint32_t infer_ms;    // 추론 시간
  uint32_t uptime_ms;   // 프레임을 얻은 시각의 millis()
} person_result_t;

typedef struct {
  const uint8_t* buf;   // JPEG 바이트
  size_t   len;
  uint16_t width;       // 640
  uint16_t height;      // 480
  void*    handle;      // 내부용 (camera_fb_t*). 건드리지 않는다
} jpeg_frame_t;
```

```c
// person_sensor.h
bool            person_sensor_begin();                         // setup()에서 1회. 실패하면 false
person_result_t person_sensor_poll();                          // 한 프레임 찍고 사람 검출 (블로킹, ~200ms)
bool            person_sensor_capture_jpeg(jpeg_frame_t* out); // 전송용 VGA JPEG 1장 (블로킹, 500ms 이내)
void            person_sensor_release(jpeg_frame_t* frame);    // 전송 끝나면 반드시 호출 (버퍼 반납)
```

### 2.1 센서 규칙 (팀원 1)

| 항목 | 규칙 |
|---|---|
| `status != PS_OK` | `person=false`, `count=0`, `score=0`. `begin()` 실패 후에는 `poll()`이 계속 `PS_CAMERA_INIT` |
| 원시 결과 | `poll()`은 매 프레임 정직한 결과만 낸다. 디바운스·"언제 찍을지"는 팀원 2의 `trigger`가 정한다 |
| 촬영 JPEG | **VGA 640×480**, 유효한 JPEG(SOI `FF D8` ~ EOI `FF D9`), **60KB 목표 / 512KB 절대 상한** |
| 버퍼 수명 | `capture_jpeg()`가 true면 `release()` 전까지 `buf`가 유효. false면 `out` 내용은 쓰지 않고, `release()`도 부르지 않는다 |
| 동시 사용 | 한 번에 JPEG 1장만 들고 있는다 (`release()` 전에 다시 `capture_jpeg()` 금지) |
| 호출 스레드 | `poll()`, `capture_jpeg()`, `release()`는 모두 `loop()`에서만 호출 (태스크 분리 없음) |

### 2.2 트리거 규칙 (팀원 2, `trigger.cpp`)

| 상태 | 조건 | 동작 |
|---|---|---|
| `IDLE` | `person=true`가 **연속 `PPE_TRIGGER_FRAMES`(2)** 프레임 | → `PRESENT`, **즉시 촬영·전송** (`true` 반환) |
| `IDLE` | `person=false` 1프레임 | 연속 횟수 0으로 초기화 |
| `PRESENT` | `person=true`이고 마지막 촬영 후 `PPE_RESEND_MS`(5000ms) 이상 | **재촬영·전송** (`true` 반환) |
| `PRESENT` | 마지막 `person=true` 후 `PPE_ABSENT_MS`(2000ms) 이상 | → `IDLE`, 연속 횟수 0 (`false` 반환) |
| `PRESENT` | `person=false`지만 2000ms 미만 | 상태 유지 (한두 프레임 놓쳐도 유지) |

- `status != PS_OK`인 프레임은 **`trigger_update()`에 넣지 않는다** (사람 없음으로도 치지 않음).
- "마지막 촬영 시각"은 `trigger_update()`가 `true`를 반환한 시각이다. 촬영·전송의 성공 여부와 상관없다 (실패해도 5초 동안 다시 보내지 않음).
- 시간 비교는 `(uint32_t)(now - last) >= interval` 형태로 쓴다 (`millis()` 49일 오버플로 안전).

---

## 3. ESP32 → Pi gateway (HTTP)

### 3.1 사진 전송 `POST /api/v1/frames`

- 주소: `http://<Pi IP>:8000/api/v1/frames` (HTTPS 아님, 같은 공유기 내부)
- **body = JPEG 바이트 그대로**, `Content-Length` 필수 (chunked 전송 X). multipart 아님.
- 메타데이터는 헤더로:

| 헤더 | 필수 | 형식 | 예 | 설명 |
|---|---|---|---|---|
| `Content-Type` | ✅ | `image/jpeg` | `image/jpeg` | 다르면 415 |
| `X-Device-Id` | ✅ | §1.1 정규식 | `xiao-01` | 형식이 틀리면 400 |
| `X-Device-Key` | ✅ | 문자열 | `change-me` | `.env`의 `DEVICE_API_KEY` = `config.h`의 `PPE_DEVICE_KEY`. 틀리면 401 |
| `X-Frame-Seq` | ✅ | 0 이상 정수 | `42` | 새 사진마다 1 증가 (재부팅 시 0부터). **재시도할 때는 같은 값** |
| `X-Person-Count` | ✅ | 0~255 정수 | `1` | 트리거 시점 `person_result_t.count` |
| `X-Person-Score` | ✅ | 0~1, 소수 둘째 자리 | `0.87` | 트리거 시점 `person_result_t.score` |
| `X-Captured-At` | | §1.1 시간 형식 | `2026-11-02T05:31:12.345Z` | NTP 동기화 전이면 **헤더를 아예 보내지 않는다**. 형식이 틀리면 gateway는 400 대신 무시하고 수신 시각을 쓴다 |
| `X-Fw-Version` | | 문자열 | `0.1.0` | |

- 크기: body가 0바이트거나 JPEG로 디코드되지 않으면 400 `invalid_image`, 512KB 초과 시 413.
- **NTP 동기화 판정** (팀원 2): `time(nullptr) > 1704067200` (2024-01-01 이후)이면 동기화된 것으로 본다. 서버 `pool.ntp.org`, UTC(오프셋 0).

```bash
# 보드 없이 테스트
curl -X POST http://<Pi IP>:8000/api/v1/frames \
  -H "Content-Type: image/jpeg" -H "X-Device-Id: sim-01" -H "X-Device-Key: change-me" \
  -H "X-Frame-Seq: 1" -H "X-Person-Count: 1" -H "X-Person-Score: 0.90" \
  --data-binary @shared/samples/no_helmet.jpg
```

### 3.2 응답 (200)

```json
{"v":1,"frame_seq":42,"result":"violation","persons":2,"violations":["no_helmet"],
 "violation_id":"7c1e0f3a-5b7e-4c55-9d0e-2f1a8b6c3d21","cloud":"queued","infer_ms":183}
```

| 필드 | 타입 | 설명 |
|---|---|---|
| `frame_seq` | int | 요청의 `X-Frame-Seq` 그대로 |
| `result` | `"violation"` \| `"compliant"` \| `"no_person"` | 판정 (§5). **ESP32는 이 값으로 LED를 바꾼다** |
| `persons` | int | Pi가 판정한 사람 수 (§5의 `persons` 배열 길이) |
| `violations` | string[] | §1.3. `result != violation`이면 `[]` |
| `violation_id` | uuid \| null | **`cloud = queued`일 때만** 값이 있다. 나머지는 모두 `null` |
| `cloud` | 아래 표 | 클라우드 처리 결과 |
| `infer_ms` | int | detector 추론 시간 |

| `cloud` | 조건 | `violation_id` |
|---|---|---|
| `"queued"` | 위반 + 쿨다운 통과 + `CLOUD_ENABLED=true` → outbox에 저장됨 (업로드는 백그라운드) | uuid |
| `"duplicate"` | 위반이지만 쿨다운 중 (§5.4) | `null` |
| `"disabled"` | 위반이지만 `CLOUD_ENABLED=false` | `null` |
| `"none"` | `compliant` 또는 `no_person` | `null` |

`result`·`violations`·`violation_id`·`cloud` 조합은 위 표 외에는 나오지 않는다 (`shared/schemas/frame-response.schema.json`이 검사).

### 3.3 에러 응답

모든 에러 body는 같은 형식이다 (`shared/schemas/error.schema.json`):

```json
{"v":1,"error":"detector_unavailable","detail":"connect timeout"}
```

| 코드 | `error` | 언제 | ESP32 동작 |
|---|---|---|---|
| 400 | `missing_header` | 필수 헤더 누락, 숫자 헤더 형식 오류 | 재시도 안 함, 시리얼 로그 |
| 400 | `bad_device_id` | `X-Device-Id` 정규식 불일치 | 재시도 안 함 |
| 400 | `invalid_image` | body가 비었거나 JPEG 디코드 실패 | 재시도 안 함 |
| 401 | `bad_device_key` | `X-Device-Key` 틀림 | 재시도 안 함 (`config.h` 확인) |
| 413 | `image_too_large` | 512KB 초과 | 재시도 안 함 (화질 낮추기) |
| 415 | `unsupported_media_type` | Content-Type이 `image/jpeg`가 아님 | 재시도 안 함 |
| 503 | `detector_unavailable` | detector 연결 실패·4초 타임아웃·준비 안 됨 | 1회 재시도 |
| 500 | `internal_error` | 그 밖의 서버 오류 | 1회 재시도 |

> FastAPI는 헤더 누락 시 기본으로 422를 돌려준다. gateway는 이것을 **400 `missing_header`로 바꿔서** 응답해야 한다.

### 3.4 ESP32 재시도·타임아웃 (팀원 2)

| 상황 | 동작 |
|---|---|
| HTTP 타임아웃 | `PPE_HTTP_TIMEOUT_MS` = **5000ms** (연결+응답 전체) |
| 연결 실패, 타임아웃, 5xx | **500ms 후 1회 재시도** (같은 JPEG, 같은 `X-Frame-Seq`). 또 실패하면 버림 |
| 4xx | 재시도 안 함 |
| 200인데 JSON 파싱 실패 | 재시도 안 함, `UP_BAD_RESPONSE` |
| Wi-Fi 끊김 | 전송 시도 안 함 (`UP_NO_WIFI`). 사진을 보드에 쌓지 않는다 |

gateway는 detector를 **4초**까지만 기다린다 (ESP32 5초 타임아웃 안에 503을 돌려주기 위해).

### 3.5 LED (팀원 2)

XIAO 사용자 LED (GPIO 21, active-low). 깜빡임은 `loop()`를 오래 막지 않게 **최대 600ms** 안에 끝낸다.

| 패턴 | 조건 |
|---|---|
| 빠르게 3번 (100ms 켜짐 / 100ms 꺼짐) | 응답 `result = violation` |
| 짧게 1번 (100ms) | `compliant` 또는 `no_person` |
| 1초 주기로 깜빡 (계속) | Wi-Fi 끊김, 또는 마지막 전송이 최종 실패 → 다음 전송 성공 시 멈춤 |

### 3.6 하트비트 `POST /api/v1/heartbeat` (2차 목표)

- `PPE_HEARTBEAT_MS`(30초)마다. `Content-Type: application/json`, 헤더 `X-Device-Key` 필수. 실패해도 재시도하지 않는다.

```json
{"v":1,"device_id":"xiao-01","fw_version":"0.1.0","uptime_s":3600,"rssi":-58,
 "free_heap":182340,"frames_sent":120,"last_error":null}
```

| 필드 | 필수 | 설명 |
|---|---|---|
| `device_id` | ✅ | §1.1 정규식 |
| `uptime_s` | ✅ | `millis()/1000` |
| `fw_version`, `rssi`, `free_heap` | | `WiFi.RSSI()`, `ESP.getFreeHeap()` |
| `frames_sent` | | 부팅 후 **200 응답을 받은** 전송 수 |
| `last_error` | | 마지막 오류를 짧은 문자열로 (`"camera_init"`, `"http_503"`, `"timeout"`…). 없으면 `null` |

- 응답 200: `{"v":1,"ok":true}`. 에러: 400 `invalid_heartbeat`(JSON·필수 필드 오류), 401 `bad_device_key`.
- gateway는 `CLOUD_ENABLED=true`일 때 Supabase `devices`에 upsert한다 (§6.4). 업로드 실패는 무시한다 (outbox에 넣지 않음).

### 3.7 상태 확인 `GET /healthz`

```json
{"v":1,"ok":true,"detector":"ready","outbox_pending":0,"cloud":"enabled"}
```

| 필드 | 값 |
|---|---|
| `detector` | `"ready"` (detector `/healthz`의 `ready=true`) \| `"not_ready"` (`ready=false`) \| `"unreachable"` (연결 실패) |
| `outbox_pending` | 업로드 대기 중인 위반 수 |
| `cloud` | `"enabled"` \| `"disabled"` |
| `ok` | `detector == "ready"` |

---

## 4. gateway → detector (Pi 내부 HTTP)

compose 내부망 전용(`http://detector:9000`). 호스트 포트는 열지 않는다.

### 4.1 `POST /v1/detect`

- body = JPEG 바이트 (`Content-Type: image/jpeg`). gateway가 받은 원본을 그대로 넘긴다.
- 응답 200:

```json
{"v":1,"model":"ppe","infer_ms":183,"image_w":640,"image_h":480,
 "detections":[
   {"cls":"person","score":0.912,"box":[102,40,298,470]},
   {"cls":"no_helmet","score":0.781,"box":[160,42,230,110]},
   {"cls":"vest","score":0.853,"box":[130,150,280,320]}
 ]}
```

| 필드 | 규칙 |
|---|---|
| `model` | 모델 파일 이름에서 확장자 뺀 것 (`ppe.onnx` → `ppe`). mock 모드면 `"mock"` |
| `image_w`, `image_h` | **원본** JPEG 크기 (모델 입력 640이 아님) |
| `detections` | 비어 있을 수 있다. **점수 내림차순** 정렬 |
| `cls` | §1.2의 5개만. `labels.yaml`의 `map`에 없는 클래스는 버린다 |
| `score` | `CONF_THRESHOLD`(0.4) 이상만, 소수 셋째 자리 |
| `box` | 원본 픽셀 정수, 이미지 범위 안으로 잘라냄. 클래스별 NMS(`IOU_THRESHOLD` 0.5) 적용 완료 |

### 4.2 에러

| 코드 | `error` | 언제 |
|---|---|---|
| 400 | `invalid_image` | 빈 body, JPEG 디코드 실패 |
| 503 | `model_not_ready` | onnx 모드인데 모델 파일이 없거나 로드 실패 |

gateway는 detector의 400을 그대로 400 `invalid_image`로, 503·연결 실패·4초 타임아웃은 503 `detector_unavailable`로 ESP32에 응답한다.

### 4.3 `GET /healthz`

```json
{"v":1,"ready":true,"mode":"onnx","model":"ppe","classes":["person","helmet","no_helmet","vest","no_vest"]}
```

모델 로드에 실패해도 이 엔드포인트는 200(`ready:false`)을 돌려준다 (컨테이너는 살아 있고, 원인은 로그로 확인).
`DETECTOR_MODE=mock`이면 모델 파일 없이 `ready:true`, `/v1/detect`는 **사람 1명 + `no_helmet` + `vest`**인 고정 결과를 돌려준다 (gateway 개발용, 항상 `violation`이 나온다).

---

## 5. 판정 규칙 (gateway)

`pi/gateway/app/judge.py`의 **순수 함수** `judge(detections)`로 만들고 `pi/gateway/tests/test_judge.py`로 테스트한다.

### 5.1 사람 찾기

1. `cls=person`이고 `score >= 0.5`인 박스가 사람이다. (`0.4 ~ 0.5` 사람 박스는 무시)
2. 사람이 1명 이상이면 → 5.2로.
3. 사람이 0명이면: `no_helmet`·`no_vest` 박스를 **각각 사람 1명**으로 본다 (모델이 사람을 놓친 경우). 이 가짜 사람은 **잡힌 항목만 ❌, 나머지 항목은 ✅**로 친다 (판단할 근거가 없으므로). 예: `no_helmet` 박스 하나뿐 → 사람 1명, `helmet:false, vest:true`.
4. 3번까지 했는데도 사람이 0명이면 → `no_person`.

### 5.2 사람별 착용 여부

사람 박스 높이를 `h`라 할 때 (가로는 사람 박스 전체 폭):

| 영역 | 세로 범위 |
|---|---|
| 머리 | `y1` ~ `y1 + 0.35h` |
| 몸통 | `y1 + 0.20h` ~ `y1 + 0.75h` |

- 보호구 박스의 **중심점**이 영역 안에 있으면 그 사람의 것이다 (경계 포함).
- 안전모: 머리 영역의 `helmet`·`no_helmet` 중 **점수가 가장 높은 박스**를 따른다 (`no_helmet`이면 ❌, `helmet`이면 ✅, 점수가 같으면 ❌). 둘 다 없으면 `JUDGE_UNKNOWN_AS_VIOLATION`(기본 `false`)이 `false`면 ✅, `true`면 ❌.
  - 기본값을 `false`로 둔 이유: 모델이 보호구를 놓치는 경우가 많아, "안 보이면 위반"이면 착용자도 위반으로 잡힌다 (테스트 사진 오경보 7/7 → 2/7). 대신 모델이 `no_helmet`/`no_vest`를 직접 찾아야 위반이 된다.
- 조끼: 몸통 영역에서 같은 방식 (`no_vest` / `vest`).
- 보호구 박스 하나가 여러 사람 영역에 걸치면 **모두에게** 적용한다 (단순화).
- 어느 사람 영역에도 들어가지 않는 보호구 박스는 무시한다.

### 5.3 결과

| 조건 | `result` | `violations` |
|---|---|---|
| 사람 0명 | `no_person` | `[]` |
| 모든 사람 ✅✅ | `compliant` | `[]` |
| 한 명이라도 ❌ | `violation` | 등장한 위반 종류 (§1.3 순서) |

`persons` 배열은 사람 박스의 `x1` **오름차순**(왼쪽 → 오른쪽)으로 정렬한다.

```json
{"box":[102,40,298,470],"helmet":false,"vest":true}
```

### 5.4 쿨다운 (중복 업로드 방지)

- 키 = (`device_id`, `violations` 배열). 예: (`xiao-01`, `["no_helmet"]`)
- 같은 키가 **마지막으로 업로드(queued)된 시각**에서 `VIOLATION_COOLDOWN_S`(30초) 안에 다시 나오면 `cloud:"duplicate"`. **duplicate는 타이머를 다시 시작하지 않는다** → 계속 서 있는 위반자는 30초마다 1건씩 기록된다.
- 키가 다르면 별개다: `["no_helmet"]` 다음에 `["no_helmet","no_vest"]`는 새 위반으로 올라간다.
- 쿨다운 기록은 메모리에만 둔다 (gateway 재시작 시 초기화되어도 괜찮다).
- `CLOUD_ENABLED=false`면 쿨다운을 검사하지 않고 `disabled`.

---

## 6. Pi → Supabase (DB + Storage)

gateway는 **secret 키**(`SUPABASE_SECRET_KEY`, 예전 이름 service_role)로 쓴다. 이 키는 Pi `.env`에만 있고, 웹·ESP32·git 어디에도 없다.

### 6.1 순서 (outbox)

```
위반 + 쿨다운 통과 → id = uuid4()
  → 박스 그린 JPEG + row.json 을 /data/outbox/.tmp-<id>/ 에 쓰고 /data/outbox/<id>/ 로 rename   ← 여기까지 하고 ESP32에 응답
  → 백그라운드 워커 (한 번에 1건, 오래된 것부터):
       1) Storage 업로드 (upsert)                      ← 사진 먼저: 웹이 INSERT를 받았을 때 사진이 이미 있도록
       2) violations upsert (id 충돌 시 덮어씀)          ← 재시도해도 행이 중복되지 않음
       3) 둘 다 성공 → 폴더 삭제 / 하나라도 실패 → 10초 뒤 같은 항목 재시도 (횟수 제한 없음)
```

- `row.json` = §6.3의 행에서 `created_at`을 뺀 것 그대로 (`shared/schemas/violation-row.schema.json`).
- `.tmp-`로 시작하는 폴더는 워커가 건너뛴다 (쓰는 중). gateway 시작 시 남아 있는 `.tmp-*`는 지운다.
- outbox 용량 제한은 두지 않는다 (데모 규모).

### 6.2 Storage

| 항목 | 값 |
|---|---|
| 버킷 | `violation-images` (**private**, 1MB 제한, `image/jpeg`만) |
| 경로 | `<device_id>/<YYYY-MM-DD>/<violation_id>.jpg` — 날짜는 **`captured_at`의 UTC 날짜** |
| 내용 | 원본과 **같은 해상도**에 박스를 그린 JPEG (quality 85) |
| 그리기 | 사람 박스: 위반자 빨강 `#E5484D`, 착용자 초록 `#30A46C`, 두께 3px. 보호구 박스: 1px, 라벨 `no_helmet 0.78` |
| Content-Type | `image/jpeg` |

### 6.3 DB — `public.violations` (위반 1건 = 1행)

| 컬럼 | 타입 | NULL | 예 | 값 규칙 |
|---|---|---|---|---|
| `id` | uuid PK | X | `7c1e…` | gateway가 생성, 응답의 `violation_id`와 같음 |
| `created_at` | timestamptz | X | 자동 | DB가 채움 (gateway는 보내지 않음) |
| `captured_at` | timestamptz | X | `2026-11-02T05:31:12.345Z` | `X-Captured-At`, 없거나 형식 오류면 gateway 수신 시각 |
| `device_id` | text | X | `xiao-01` | `X-Device-Id` |
| `gateway_id` | text | X | `pi-01` | `GATEWAY_ID` |
| `frame_seq` | int | O | `42` | `X-Frame-Seq` |
| `person_count` | smallint | X | `2` | §5 `persons` 길이 (≥ 1) |
| `no_helmet_count` | smallint | X | `1` | `helmet=false`인 사람 수 |
| `no_vest_count` | smallint | X | `0` | `vest=false`인 사람 수 |
| `violation_types` | text[] | X | `{no_helmet}` | §1.3 (1개 이상) |
| `image_path` | text | X | `xiao-01/2026-11-02/7c1e….jpg` | §6.2 경로 (버킷 이름 제외) |
| `image_w`, `image_h` | smallint | O | `640`, `480` | detector `image_w`, `image_h` |
| `persons` | jsonb | X | `[{"box":[...],"helmet":false,"vest":true}]` | §5.3 |
| `detections` | jsonb | X | `[{"cls":"no_helmet","score":0.781,"box":[...]}]` | §4.1 `detections` 전체 그대로 |
| `model` | text | O | `ppe` | detector `model` |
| `infer_ms` | int | O | `183` | detector `infer_ms` |

### 6.4 DB — `public.devices` (장치 1대 = 1행, 2차 목표)

| 컬럼 | 타입 | 값 규칙 |
|---|---|---|
| `device_id` | text PK | 하트비트 `device_id` |
| `gateway_id` | text | `GATEWAY_ID` |
| `last_seen` | timestamptz | 하트비트를 **받은 시각**(gateway 기준, UTC) |
| `fw_version`, `rssi`, `uptime_s`, `free_heap`, `last_error` | | 하트비트 값 그대로 (`frames_sent`는 저장하지 않음) |

### 6.5 권한 (RLS)

| 누가 | 키 | violations / devices | Storage `violation-images` |
|---|---|---|---|
| gateway, cloud-seed | secret | 읽기·쓰기 (RLS 우회) | 업로드 |
| web | publishable | **읽기만** (`select` 정책) | **읽기만** (서명 URL 발급) |

SQL 원본: [cloud/supabase/migrations/20261102000000_init.sql](../cloud/supabase/migrations/20261102000000_init.sql)

> 데모 편의상 publishable 키로 위반 사진을 읽을 수 있다. 실제 현장에 쓰려면 Supabase Auth 로그인을 붙이고 정책을 `to authenticated`로 좁혀야 한다 (작업자 얼굴 = 개인정보).

---

## 7. Supabase → Web

웹은 `config.js`의 `window.PPE_CONFIG`에서 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_BUCKET`을 읽는다 (컨테이너가 `.env`로 생성).

### 7.1 조회·구독

```js
// 1) 피드: 최근 50건 (captured_at 최신순)
db.from('violations').select('*').order('captured_at', { ascending: false }).limit(50)

// 2) 오늘 통계: 한국 시간 오늘 0시 이후 (피드 50건이 아니라 따로 조회)
const since = kstMidnightISO()   // 예: "2026-11-01T15:00:00.000Z"
db.from('violations').select('no_helmet_count, no_vest_count').gte('captured_at', since)

// 3) 실시간: 새 위반 (구독을 먼저 시작하고 1)·2) 조회 → 순서가 엇갈려도 id로 중복 제거)
db.channel('violations-feed')
  .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'violations' }, (p) => onNew(p.new))
  .subscribe()

// 4) 사진: 서명 URL 1시간
db.storage.from(BUCKET).createSignedUrl(row.image_path, 3600)

// 5) (2차) 장치 상태
db.from('devices').select('*')   // + postgres_changes event '*' 구독
```

### 7.2 표시 규칙

| 항목 | 규칙 |
|---|---|
| 중복 제거 | 카드는 `id` 기준으로 한 번만 그린다 (조회 결과와 Realtime이 겹칠 수 있음, outbox 재시도 시 UPDATE 이벤트는 구독하지 않음) |
| 정렬 | 최신 `captured_at`이 맨 위 |
| 시각 표시 | `captured_at`을 **한국 시간**으로 (`toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })`) |
| 위반 라벨 | `no_helmet` → "안전모 미착용", `no_vest` → "조끼 미착용" |
| 오늘 통계 | 전체 = 행 수, 안전모 = `no_helmet_count` 합, 조끼 = `no_vest_count` 합. 새 위반이 오면 오늘 날짜인 경우 더한다 |
| 사진 실패 | 서명 URL 발급 실패·만료 시 "사진 없음" 표시 (outbox가 아직 Storage만 올렸을 수는 없다 — §6.1 순서상 사진이 먼저) |
| 장치 온라인 (2차) | `now - last_seen <= 90초`면 온라인. 10초마다 다시 계산 |
| 연결 상태 | 구독 상태가 `SUBSCRIBED`면 "실시간", 그 외(`CHANNEL_ERROR`, `TIMED_OUT`, `CLOSED`)면 "연결 끊김" |
