# 테스트 사진

`cam-sim`(가짜 ESP32)과 `cloud-seed`(가짜 Pi)가 이 폴더의 `*.jpg`를 사용한다. 비어 있으면 회색 더미 이미지를 만들어 쓴다.

권장 파일 (640×480 JPEG, 직접 찍거나 데이터셋에서 골라 넣기):

| 파일 | 내용 | 기대 판정 |
|---|---|---|
| `ok.jpg` | 안전모 + 조끼 착용 | `compliant` |
| `no_helmet.jpg` | 조끼만 착용 | `violation` (`no_helmet`) |
| `no_vest.jpg` | 안전모만 착용 | `violation` (`no_vest`) |
| `none.jpg` | 둘 다 미착용 | `violation` (`no_helmet`, `no_vest`) |
| `empty.jpg` | 사람 없음 | `no_person` |

> 실제 사람 얼굴이 나온 사진은 본인 동의를 받은 것만 커밋한다.
