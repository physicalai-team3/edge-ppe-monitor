// [contract] 팀원 1(생산) ↔ 팀원 2(소비). 수정 시 [contract] 커밋 + 공유. docs/03-contracts.md §2
#pragma once
#include <stddef.h>
#include <stdint.h>

typedef enum {
  PS_OK = 0,
  PS_CAMERA_INIT = 1,   // 카메라 초기화 실패 (재부팅 루프 금지, 이 값만 반환)
  PS_CAPTURE_FAIL = 2,  // 프레임 획득 실패
  PS_INFER_FAIL = 3,    // 모델 추론 실패
} ps_status_t;

// status != PS_OK 이면 person=false, count=0, score=0
typedef struct {
  ps_status_t status;
  bool     person;      // count > 0 과 항상 같다
  uint8_t  count;       // score >= PPE_PERSON_THRESHOLD 인 사람(FOMO 중심점) 수
  float    score;       // 그 중 최고 점수. count == 0 이면 0
  uint32_t infer_ms;    // 추론 시간
  uint32_t uptime_ms;   // 프레임을 얻은 시각의 millis()
} person_result_t;

typedef struct {
  const uint8_t* buf;   // 유효한 JPEG (FF D8 ... FF D9), 60KB 목표 / 512KB 상한
  size_t   len;
  uint16_t width;       // 640
  uint16_t height;      // 480
  void*    handle;      // 내부용 (camera_fb_t*). 건드리지 않는다
} jpeg_frame_t;
