"""상수 정의"""

# 타입별 바이트 크기 매핑
TYPE_SIZES = {
    'uint8_t': 1,
    'int8_t': 1,
    'uint16_t': 2,
    'int16_t': 2,
    'uint32_t': 4,
    'int32_t': 4,
    'uint64_t': 8,
    'int64_t': 8,
    'char': 1,
    'float': 4,
    'double': 8,
}

# 바이트 패턴 (Big/Little endian 생성용)
BYTE_PATTERN = [0xA1, 0xB2, 0xC3, 0xD4]

# 바이트 출력 시 한 줄에 최대 개수
MAX_BYTES_PER_LINE = 16

