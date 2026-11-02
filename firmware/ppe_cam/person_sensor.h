// [contract] 팀원 1 구현 (person_sensor.cpp), 팀원 2 사용. docs/03-contracts.md §2
// PPE_SENSOR_STUB 1 이면 person_sensor_stub.cpp 가 대신 구현한다 (BOOT 버튼 = 사람).
// 모든 함수는 loop() 에서만 호출한다 (태스크 분리 없음).
#pragma once
#include "person_result.h"

// setup()에서 1회. 실패하면 false (이후 poll()은 계속 PS_CAMERA_INIT 반환)
bool person_sensor_begin();

// 한 프레임 찍고 사람 검출 (블로킹, ~200ms)
person_result_t person_sensor_poll();

// 전송용 VGA JPEG 1장 (블로킹, 500ms 이내).
// true: out 은 release() 전까지 유효. false: out 을 쓰지 말고 release() 도 부르지 않는다.
// release() 전에 다시 호출하지 않는다 (한 번에 1장).
bool person_sensor_capture_jpeg(jpeg_frame_t* out);

// 전송이 끝나면 반드시 호출 (카메라 버퍼 반납)
void person_sensor_release(jpeg_frame_t* frame);
