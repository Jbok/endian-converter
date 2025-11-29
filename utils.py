"""공통 유틸리티 함수"""

import re
from typing import List, Optional, Dict, Tuple
from constants import TYPE_SIZES


def extract_array_dimensions(type_str: str) -> List[str]:
    """배열 차원을 모두 추출 (예: uint32_t[10][20] -> ['10', '20'])"""
    dimensions = []
    # 모든 [내용] 패턴 찾기
    for match in re.finditer(r'\[([^\]]+)\]', type_str):
        dimensions.append(match.group(1).strip())
    return dimensions


def get_type_size(type_str: str) -> int:
    """타입 문자열에서 바이트 크기를 추출 (2차원 배열 지원)"""
    type_str = type_str.strip()
    
    # 기본 타입 크기 확인
    if type_str in TYPE_SIZES:
        return TYPE_SIZES[type_str]
    
    # 배열 차원 추출
    dimensions = extract_array_dimensions(type_str)
    if not dimensions:
        return 0
    
    # 기본 타입 추출 (모든 배열 제거)
    base_type = re.sub(r'\[.*?\]', '', type_str).strip()
    base_size = TYPE_SIZES.get(base_type, 0)
    if base_size == 0:
        # 매크로 정의된 배열 크기 처리
        # 이 경우 크기를 알 수 없으므로 0 반환
        return 0
    
    # 모든 차원이 숫자인 경우에만 크기 계산
    total_size = base_size
    for dim in dimensions:
        if dim.isdigit():
            total_size *= int(dim)
        else:
            # 매크로가 포함된 경우 크기를 알 수 없음
            return 0
    
    return total_size


def remove_comments(text: str) -> str:
    """C 주석 제거"""
    # 여러 줄 주석 제거
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # 한 줄 주석 제거
    text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
    return text


def append_bytes_with_wrap(lines: List[str], bytes_list: List[str], 
                          comment: str = "", indent: str = "        ", 
                          max_per_line: int = 16) -> None:
    """bytes_list를 최대 max_per_line개씩 끊어서 여러 줄로 추가"""
    for idx in range(0, len(bytes_list), max_per_line):
        chunk = bytes_list[idx:idx + max_per_line]
        chunk_str = ", ".join(chunk)
        # 첫 줄에만 주석 출력
        if idx == 0 and comment:
            lines.append(f"{indent}{chunk_str}, {comment}")
        else:
            lines.append(f"{indent}{chunk_str},")


def is_macro_array(field_type: str) -> bool:
    """필드 타입이 매크로 배열인지 확인 (2차원 배열 지원)"""
    dimensions = extract_array_dimensions(field_type)
    # 하나라도 매크로(숫자가 아닌)가 있으면 매크로 배열로 간주
    for dim in dimensions:
        if not dim.isdigit():
            return True
    return False


def get_macro_name(field_type: str) -> Optional[str]:
    """필드 타입에서 첫 번째 매크로 이름 추출 (하위 호환성 유지)"""
    dimensions = extract_array_dimensions(field_type)
    for dim in dimensions:
        if not dim.isdigit():
            return dim
    return None


def get_array_dimensions_info(field_type: str, macro_sizes: Dict[str, int] = None) -> List[Tuple[str, Optional[int]]]:
    """배열 차원 정보 추출 (차원 이름, 크기) 반환
    Returns: [(dimension_name, size), ...]
    예: uint32_t[10][MAX_SIZE] -> [('10', 10), ('MAX_SIZE', macro_sizes['MAX_SIZE'])]
    """
    if macro_sizes is None:
        macro_sizes = {}
    
    dimensions = extract_array_dimensions(field_type)
    result = []
    for dim in dimensions:
        if dim.isdigit():
            result.append((dim, int(dim)))
        else:
            # 매크로인 경우
            size = macro_sizes.get(dim, None)
            result.append((dim, size))
    return result


def is_likely_macro_name(name: str) -> bool:
    """이름이 매크로 이름일 가능성이 있는지 확인"""
    if not name:
        return False
    # 모두 대문자이거나 대문자와 언더스코어로만 구성된 경우 매크로로 간주
    if name.isupper() or (name.replace('_', '').isupper() and '_' in name):
        return True
    return False


def get_struct_id_macro(struct_name: str) -> str:
    """구조체 ID 매크로 이름 생성"""
    if struct_name.endswith('_type'):
        return struct_name[:-5] + "_id"
    return struct_name + "_id"


def format_test_class_name(struct_name: str) -> str:
    """구조체 이름을 Test 클래스 이름으로 변환"""
    test_class_parts = [part.capitalize() for part in struct_name.split('_')]
    return ''.join(test_class_parts) + "Test"

