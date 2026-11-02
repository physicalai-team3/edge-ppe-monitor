"""위반 사진에 박스 그리기 (docs/03-contracts.md §6.2)."""
from .judge import Judgement

COLOR_VIOLATOR = "#E5484D"   # 사람 박스: 위반자
COLOR_OK = "#30A46C"         # 사람 박스: 착용자
PERSON_WIDTH = 3
GEAR_WIDTH = 1
JPEG_QUALITY = 85


def draw(image: bytes, detections: list[dict], judgement: Judgement) -> bytes:
    """원본 JPEG → 같은 해상도에 박스·라벨을 그린 JPEG."""
    # TODO: Pillow ImageDraw
    #   judgement.persons: 위반자 빨강 / 착용자 초록, 두께 3
    #   detections 중 helmet/no_helmet/vest/no_vest: 두께 1, 라벨 "no_helmet 0.78"
    return image
