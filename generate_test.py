#!/usr/bin/env python3
"""
헤더 파일에서 구조체를 파싱하여 endian converter 테스트 코드를 생성하는 스크립트
"""

import re
import sys
from typing import List, Tuple, Dict, Optional
from pathlib import Path


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


def get_type_size(type_str: str) -> int:
    """타입 문자열에서 바이트 크기를 추출"""
    type_str = type_str.strip()
    
    # 기본 타입 크기 확인
    if type_str in TYPE_SIZES:
        return TYPE_SIZES[type_str]
    
    # 배열 타입 처리 (예: uint32_t[10])
    array_match = re.match(r'(\w+)\[(\d+)\]', type_str)
    if array_match:
        base_type = array_match.group(1)
        array_size = int(array_match.group(2))
        base_size = TYPE_SIZES.get(base_type, 0)
        return base_size * array_size
    
    # 매크로 정의된 배열 크기 처리 (예: uint32_t[MAX_DATA_BUFFER_SIZE])
    # 이 경우 크기를 알 수 없으므로 0 반환
    if '[' in type_str:
        return 0
    
    return 0


def remove_comments(text: str) -> str:
    """C 주석 제거"""
    # 여러 줄 주석 제거
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # 한 줄 주석 제거
    text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
    return text


def parse_struct_block(struct_block: str) -> Tuple[Optional[str], List[Tuple[str, str, int]]]:
    """
    구조체 블록을 파싱하여 이름과 필드 리스트 반환
    """
    # 주석 제거
    clean_block = remove_comments(struct_block)
    
    # 구조체 이름 추출: } 다음에 오는 이름
    # 패턴: } [attribute] 이름; 또는 } 이름 [attribute];
    # 먼저 } 다음의 모든 텍스트 추출
    after_brace = re.search(r'\}(.*?);', clean_block, re.DOTALL)
    if not after_brace:
        return None, []
    
    name_part = after_brace.group(1).strip()
    
    # attribute 제거
    name_part = re.sub(r'__attribute__\([^)]+\)', '', name_part)
    name_part = re.sub(r'PACKED_STRUCT', '', name_part)
    name_part = re.sub(r'ALIGNED_STRUCT\([^)]+\)', '', name_part)
    
    # 남은 단어 중 마지막이 구조체 이름
    words = [w for w in name_part.split() if w]
    if not words:
        return None, []
    
    struct_name = words[-1]
    
    # 구조체 본문 추출 ({ ... } 사이)
    body_match = re.search(r'\{([^}]+)\}', clean_block, re.DOTALL)
    if not body_match:
        return struct_name, []
    
    body = body_match.group(1)
    fields = []
    
    # 각 줄 파싱
    for line in body.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # 필드 파싱
        field = parse_field_line(line)
        if field:
            fields.append(field)
    
    return struct_name, fields


def parse_field_line(line: str) -> Optional[Tuple[str, str, int]]:
    """한 줄에서 필드 정보 추출 (타입, 이름, 크기)"""
    line = line.strip()
    
    if not line:
        return None
    
    # 세미콜론 기준으로 분리 (필드 정의와 주석 분리)
    if ';' in line:
        line = line.split(';')[0].strip()
    
    if not line:
        return None
    
    # 주석 제거 (세미콜론 제거 후 남은 주석)
    line = re.sub(r'//.*$', '', line)
    line = re.sub(r'/\*.*?\*/', '', line)
    line = line.strip()
    
    if not line:
        return None
    
    # 배열 필드 처리
    # 예: "uint32_t data_buffer[MAX_DATA_BUFFER_SIZE]"
    # 배열은 필드 이름 뒤에 오므로, 필드 이름을 먼저 찾고 그 뒤의 배열을 추출
    array_match = re.search(r'(\w+)\s*(\[[^\]]+\])', line)
    array_part = ""
    field_name = None
    
    if array_match:
        # 배열이 있는 경우: 필드 이름과 배열 부분 추출
        field_name = array_match.group(1)
        array_part = array_match.group(2)
        # 타입 부분 추출 (배열 이전 부분)
        type_part = line[:array_match.start()].strip()
    else:
        # 배열이 없는 경우: 일반 필드 파싱
        parts = [p for p in line.split() if p]
        if len(parts) < 2:
            return None
        field_name = parts[-1]
        type_part = ' '.join(parts[:-1])
    
    if not field_name or not type_part:
        return None
    
    field_type = type_part + array_part
    
    # 크기 계산
    size = get_type_size(field_type)
    
    # 크기를 알 수 없는 경우도 반환 (나중에 필터링)
    return (field_type, field_name, size)


def parse_header_file(header_path: Path) -> List[Dict]:
    """헤더 파일에서 모든 구조체 파싱"""
    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    structs = []
    
    # typedef struct 블록 찾기 (여러 줄에 걸쳐 있을 수 있음)
    # 패턴: typedef struct [이름]? { ... } [이름];
    
    # 정규식으로 구조체 블록 찾기
    # { 와 } 의 매칭을 위해 간단한 방법 사용
    pattern = r'typedef\s+struct\s*(?:\w+)?\s*\{'
    
    for match in re.finditer(pattern, content):
        start_pos = match.start()
        
        # { 부터 시작해서 매칭되는 } 찾기
        brace_count = 0
        pos = match.end() - 1  # { 위치로 이동
        struct_start = pos
        
        while pos < len(content):
            if content[pos] == '{':
                brace_count += 1
            elif content[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    # 구조체 블록 종료
                    struct_end = pos + 1
                    # 세미콜론까지 포함
                    while struct_end < len(content) and content[struct_end] != ';':
                        struct_end += 1
                    if struct_end < len(content):
                        struct_end += 1
                    
                    struct_block = content[match.start():struct_end]
                    struct_name, fields = parse_struct_block(struct_block)
                    
                    if struct_name and fields:
                        structs.append({
                            'name': struct_name,
                            'fields': fields
                        })
                    break
            pos += 1
    
    return structs


def is_macro_array(field_type: str) -> bool:
    """필드 타입이 매크로 배열인지 확인"""
    # 배열이 있고, 숫자가 아닌 매크로 이름이 들어있는 경우
    array_match = re.search(r'\[([^\]]+)\]', field_type)
    if array_match:
        array_size = array_match.group(1).strip()
        # 숫자만 있는 경우가 아니면 매크로 배열로 간주
        if not array_size.isdigit():
            return True
    return False


def get_macro_name(field_type: str) -> Optional[str]:
    """필드 타입에서 매크로 이름 추출"""
    array_match = re.search(r'\[([^\]]+)\]', field_type)
    if array_match:
        array_size = array_match.group(1).strip()
        if not array_size.isdigit():
            return array_size
    return None


def find_missing_structs(structs: List[Dict], structs_dict: Dict[str, List[Tuple[str, str, int]]]) -> List[str]:
    """
    구조체 필드에서 참조되지만 정의되지 않은 구조체 찾기
    Returns: 누락된 구조체 이름 리스트
    """
    missing = set()
    checked = set()  # 이미 확인한 구조체 타입 (순환 참조 방지)
    
    def check_fields(fields: List[Tuple[str, str, int]]):
        for field_type, field_name, size in fields:
            # 배열 제거
            base_type = re.sub(r'\[.*?\]', '', field_type).strip()
            
            # 이미 확인한 타입은 스킵
            if base_type in checked:
                continue
            checked.add(base_type)
            
            # 기본 타입이 아니고, 구조체 딕셔너리에 없는 경우
            if base_type not in TYPE_SIZES and base_type not in structs_dict:
                # 중첩 구조체인지 확인 (크기가 0이고 매크로 배열이 아닌 경우)
                if size == 0 and not is_macro_array(field_type):
                    missing.add(base_type)
            # 구조체 딕셔너리에 있는 경우, 그 구조체의 필드도 재귀적으로 확인
            elif base_type in structs_dict:
                nested_fields = structs_dict[base_type]
                check_fields(nested_fields)
    
    for struct in structs:
        check_fields(struct['fields'])
    
    return sorted(list(missing))


def get_header_path_for_struct(missing_struct: str, base_path: Path) -> Optional[Path]:
    """사용자로부터 구조체가 정의된 헤더 파일 경로 입력 받기"""
    print(f"\n구조체 '{missing_struct}'를 찾을 수 없습니다.")
    print(f"이 구조체가 정의된 헤더 파일의 경로를 입력해주세요.")
    print(f"(현재 디렉토리 기준: {base_path.absolute()})")
    
    while True:
        try:
            header_input = input("헤더 파일 경로: ").strip()
            if not header_input:
                print("경로를 입력해주세요.")
                continue
            
            # 경로 처리
            if header_input.startswith('./') or (not header_input.startswith('/') and '/' in header_input):
                header_path = base_path / header_input
            elif not header_input.startswith('/'):
                # 같은 디렉토리의 파일
                header_path = base_path / header_input
            else:
                # 절대 경로
                header_path = Path(header_input)
            
            # 경로 정규화
            header_path = header_path.resolve()
            
            if not header_path.exists():
                print(f"파일을 찾을 수 없습니다: {header_path}")
                retry = input("다시 입력하시겠습니까? (y/n): ").strip().lower()
                if retry != 'y':
                    return None
                continue
            
            if header_path.suffix not in ['.h', '.hpp']:
                print(f"헤더 파일이 아닙니다: {header_path}")
                retry = input("다시 입력하시겠습니까? (y/n): ").strip().lower()
                if retry != 'y':
                    return None
                continue
            
            # 헤더 파일에서 구조체 확인
            structs = parse_header_file(header_path)
            struct_names = [s['name'] for s in structs]
            
            if missing_struct not in struct_names:
                print(f"경고: '{header_path}'에서 '{missing_struct}' 구조체를 찾을 수 없습니다.")
                print(f"발견된 구조체: {', '.join(struct_names) if struct_names else '없음'}")
                retry = input("다시 입력하시겠습니까? (y/n): ").strip().lower()
                if retry != 'y':
                    return None
                continue
            
            return header_path
            
        except KeyboardInterrupt:
            print("\n취소되었습니다.")
            return None
        except Exception as e:
            print(f"오류 발생: {e}")
            retry = input("다시 입력하시겠습니까? (y/n): ").strip().lower()
            if retry != 'y':
                return None


def collect_macro_arrays(structs: List[Dict], structs_dict: Dict[str, List[Tuple[str, str, int]]]) -> Dict[Tuple[str, str], Dict]:
    """
    모든 구조체에서 매크로 배열 필드를 수집
    Returns: {(struct_name, field_path): info_dict} 딕셔너리
    """
    macro_arrays = {}
    
    def collect_from_fields(struct_name: str, fields: List[Tuple[str, str, int]], prefix: str = ""):
        for field_type, field_name, size in fields:
            full_field_name = f"{prefix}.{field_name}" if prefix else field_name
            
            if size == 0:
                if is_macro_array(field_type):
                    macro_name = get_macro_name(field_type)
                    key = (struct_name, full_field_name)
                    if key not in macro_arrays:
                        macro_arrays[key] = {
                            'macro_name': macro_name,
                            'field_type': field_type,
                            'field_name': field_name
                        }
                else:
                    # 중첩 구조체인지 확인
                    base_type = field_type.strip()
                    nested_fields = structs_dict.get(base_type)
                    if nested_fields:
                        # 중첩 구조체의 필드들도 재귀적으로 수집
                        collect_from_fields(struct_name, nested_fields, full_field_name)
    
    for struct in structs:
        struct_name = struct['name']
        fields = struct['fields']
        collect_from_fields(struct_name, fields)
    
    return macro_arrays


def get_macro_array_sizes(macro_arrays: Dict) -> Dict[Tuple[str, str], int]:
    """사용자로부터 매크로 배열 크기 입력 받기"""
    macro_sizes = {}
    
    if not macro_arrays:
        return macro_sizes
    
    print("\n=== 매크로 배열 크기 입력 ===")
    for (struct_name, field_path), info in macro_arrays.items():
        macro_name = info['macro_name']
        field_type = info['field_type']
        field_name = info['field_name']
        
        print(f"\n구조체: {struct_name}")
        print(f"필드: {field_path}")
        print(f"타입: {field_type}")
        print(f"매크로: {macro_name}")
        
        while True:
            try:
                size_input = input(f"{macro_name}의 배열 크기를 입력하세요: ").strip()
                if not size_input:
                    print("값을 입력해주세요.")
                    continue
                array_size = int(size_input)
                if array_size < 0:
                    print("0 이상의 값을 입력해주세요.")
                    continue
                macro_sizes[(struct_name, field_path)] = array_size
                break
            except ValueError:
                print("올바른 숫자를 입력해주세요.")
            except KeyboardInterrupt:
                print("\n취소되었습니다.")
                sys.exit(1)
    
    return macro_sizes


def generate_big_endian_bytes(struct_name: str, fields: List[Tuple[str, str, int]], structs_dict: Dict[str, List[Tuple[str, str, int]]] = None, macro_sizes: Dict[Tuple[str, str], int] = None, field_path: str = "") -> str:
    """Big endian 바이트 배열 생성"""
    if structs_dict is None:
        structs_dict = {}
    if macro_sizes is None:
        macro_sizes = {}
    
    lines = []
    lines.append(f"    uint8_t big_endian_raw_{struct_name}[] = ")
    lines.append("    {")
    
    # 원본 형식: 0xA1, 0xB2, 0xC3, 0xD4 패턴 사용
    byte_pattern = [0xA1, 0xB2, 0xC3, 0xD4]
    
    for field_type, field_name, size in fields:
        current_field_path = f"{field_path}.{field_name}" if field_path else field_name
        
        if size == 0:
            # 크기를 알 수 없는 경우
            if is_macro_array(field_type):
                # 매크로 배열인 경우 사용자 입력 크기 사용
                key = (struct_name, current_field_path)
                array_size = macro_sizes.get(key, 0)
                if array_size > 0:
                    base_type = re.sub(r'\[.*?\]', '', field_type).strip()
                    base_size = TYPE_SIZES.get(base_type, 0)
                    
                    # 중첩 구조체 배열인지 확인
                    nested_fields = structs_dict.get(base_type)
                    if nested_fields:
                        # 중첩 구조체 배열인 경우
                        for elem_idx in range(array_size):
                            lines.append(f"        // Start: {base_type} {field_name}[{elem_idx}]")
                            # 중첩 구조체의 필드들을 재귀적으로 처리
                            nested_bytes = generate_big_endian_bytes(struct_name, nested_fields, structs_dict, macro_sizes, f"{current_field_path}[{elem_idx}]")
                            # 중첩 구조체의 바이트만 추출 (첫 두 줄과 마지막 줄 제거)
                            nested_lines = nested_bytes.split('\n')[2:-1]
                            lines.extend(nested_lines)
                            lines.append(f"        // End: {base_type} {field_name}[{elem_idx}]")
                    elif base_size > 0:
                        # 기본 타입 배열인 경우
                        for elem_idx in range(array_size):
                            bytes_list = []
                            for i in range(base_size):
                                bytes_list.append(f"0x{byte_pattern[i % len(byte_pattern)]:02X}")
                            bytes_str = ", ".join(bytes_list)
                            lines.append(f"        {bytes_str}, //{base_type} {field_name}[{elem_idx}];")
                    else:
                        # 알 수 없는 타입
                        base_type = re.sub(r'\[.*?\]', '', field_type).strip()
                        array_part = re.search(r'\[.*?\]', field_type)
                        array_str = array_part.group(0) if array_part else ""
                        lines.append(f"        // {base_type} {field_name}{array_str}; (타입 크기 알 수 없음)")
                else:
                    # 크기가 입력되지 않은 경우 (발생하지 않아야 함)
                    base_type = re.sub(r'\[.*?\]', '', field_type).strip()
                    array_part = re.search(r'\[.*?\]', field_type)
                    array_str = array_part.group(0) if array_part else ""
                    lines.append(f"        // {base_type} {field_name}{array_str}; (크기 미입력)")
            else:
                # 중첩 구조체인지 확인
                base_type = field_type.strip()
                nested_fields = structs_dict.get(base_type)
                if nested_fields:
                    # 중첩 구조체인 경우
                    lines.append(f"        // Start: {field_type} {field_name}")
                    # 중첩 구조체의 필드들을 재귀적으로 처리
                    nested_bytes = generate_big_endian_bytes(struct_name, nested_fields, structs_dict, macro_sizes, current_field_path)
                    # 중첩 구조체의 바이트만 추출 (첫 두 줄과 마지막 줄 제거)
                    nested_lines = nested_bytes.split('\n')[2:-1]  # 첫 두 줄(배열 선언)과 마지막 줄(}) 제거
                    lines.extend(nested_lines)
                    lines.append(f"        // End: {field_type} {field_name}")
                else:
                    # 알 수 없는 타입은 스킵
                    continue
        else:
            # Big endian: 상위 바이트부터
            bytes_list = []
            for i in range(size):
                bytes_list.append(f"0x{byte_pattern[i % len(byte_pattern)]:02X}")
            
            bytes_str = ", ".join(bytes_list)
            lines.append(f"        {bytes_str}, //{field_type} {field_name};")
    
    lines.append("    }")
    return "\n".join(lines)


def generate_little_endian_bytes(struct_name: str, fields: List[Tuple[str, str, int]], structs_dict: Dict[str, List[Tuple[str, str, int]]] = None, macro_sizes: Dict[Tuple[str, str], int] = None, field_path: str = "") -> str:
    """Little endian 바이트 배열 생성"""
    if structs_dict is None:
        structs_dict = {}
    if macro_sizes is None:
        macro_sizes = {}
    
    lines = []
    lines.append(f"    uint8_t little_endian_raw_{struct_name}[] = ")
    lines.append("    {")
    
    # 원본 형식: 0xA1, 0xB2, 0xC3, 0xD4 패턴 사용
    byte_pattern = [0xA1, 0xB2, 0xC3, 0xD4]
    
    for field_type, field_name, size in fields:
        current_field_path = f"{field_path}.{field_name}" if field_path else field_name
        
        if size == 0:
            # 크기를 알 수 없는 경우
            if is_macro_array(field_type):
                # 매크로 배열인 경우 사용자 입력 크기 사용
                key = (struct_name, current_field_path)
                array_size = macro_sizes.get(key, 0)
                if array_size > 0:
                    base_type = re.sub(r'\[.*?\]', '', field_type).strip()
                    base_size = TYPE_SIZES.get(base_type, 0)
                    
                    # 중첩 구조체 배열인지 확인
                    nested_fields = structs_dict.get(base_type)
                    if nested_fields:
                        # 중첩 구조체 배열인 경우
                        for elem_idx in range(array_size):
                            lines.append(f"        // Start: {base_type} {field_name}[{elem_idx}]")
                            # 중첩 구조체의 필드들을 재귀적으로 처리
                            nested_bytes = generate_little_endian_bytes(struct_name, nested_fields, structs_dict, macro_sizes, f"{current_field_path}[{elem_idx}]")
                            # 중첩 구조체의 바이트만 추출 (첫 두 줄과 마지막 줄 제거)
                            nested_lines = nested_bytes.split('\n')[2:-1]
                            lines.extend(nested_lines)
                            lines.append(f"        // End: {base_type} {field_name}[{elem_idx}]")
                    elif base_size > 0:
                        # 기본 타입 배열인 경우 (Little endian)
                        for elem_idx in range(array_size):
                            bytes_list = []
                            for i in range(base_size - 1, -1, -1):
                                bytes_list.append(f"0x{byte_pattern[i % len(byte_pattern)]:02X}")
                            bytes_str = ", ".join(bytes_list)
                            lines.append(f"        {bytes_str}, //{base_type} {field_name}[{elem_idx}];")
                    else:
                        # 알 수 없는 타입
                        base_type = re.sub(r'\[.*?\]', '', field_type).strip()
                        array_part = re.search(r'\[.*?\]', field_type)
                        array_str = array_part.group(0) if array_part else ""
                        lines.append(f"        // {base_type} {field_name}{array_str}; (타입 크기 알 수 없음)")
                else:
                    # 크기가 입력되지 않은 경우 (발생하지 않아야 함)
                    base_type = re.sub(r'\[.*?\]', '', field_type).strip()
                    array_part = re.search(r'\[.*?\]', field_type)
                    array_str = array_part.group(0) if array_part else ""
                    lines.append(f"        // {base_type} {field_name}{array_str}; (크기 미입력)")
            else:
                # 중첩 구조체인지 확인
                base_type = field_type.strip()
                nested_fields = structs_dict.get(base_type)
                if nested_fields:
                    # 중첩 구조체인 경우
                    lines.append(f"        // Start: {field_type} {field_name}")
                    # 중첩 구조체의 필드들을 재귀적으로 처리
                    nested_bytes = generate_little_endian_bytes(struct_name, nested_fields, structs_dict, macro_sizes, current_field_path)
                    # 중첩 구조체의 바이트만 추출 (첫 두 줄과 마지막 줄 제거)
                    nested_lines = nested_bytes.split('\n')[2:-1]  # 첫 두 줄(배열 선언)과 마지막 줄(}) 제거
                    lines.extend(nested_lines)
                    lines.append(f"        // End: {field_type} {field_name}")
                else:
                    # 알 수 없는 타입은 스킵
                    continue
        else:
            # Little endian: 하위 바이트부터 (역순)
            bytes_list = []
            for i in range(size - 1, -1, -1):
                bytes_list.append(f"0x{byte_pattern[i % len(byte_pattern)]:02X}")
            
            bytes_str = ", ".join(bytes_list)
            lines.append(f"        {bytes_str}, //{field_type} {field_name};")
    
    lines.append("    }")
    return "\n".join(lines)


def generate_test_code(structs: List[Dict], header_name: str, macro_sizes: Dict[Tuple[str, str], int]) -> str:
    """테스트 코드 생성"""
    lines = []
    
    # 헤더 파일 이름에서 include 이름 생성
    include_name = header_name
    
    lines.append("#include <gtest/gtest.h>")
    lines.append("")
    lines.append("extern \"C\" {")
    lines.append(f"#include \"{include_name}\"")
    lines.append("}")
    lines.append("")
    
    # 구조체 딕셔너리 생성 (이름 -> 필드 리스트)
    structs_dict = {struct['name']: struct['fields'] for struct in structs}
    
    for struct in structs:
        struct_name = struct['name']
        fields = struct['fields']
        
        # 모든 필드 사용 (매크로 배열도 포함)
        # 크기를 알 수 없는 필드가 하나라도 있으면 포함
        valid_fields = fields
        if not valid_fields:
            continue
        
        # 테스트 케이스 이름 생성
        test_name = f"{struct_name}_endian_converter"
        # 구조체 이름을 Test 클래스 이름으로 변환 (첫 글자 대문자, 언더스코어 제거)
        test_class_parts = [part.capitalize() for part in struct_name.split('_')]
        test_class = ''.join(test_class_parts) + "Test"
        
        lines.append(f"TEST({test_class}, {test_name}) {{")
        
        # Big endian 바이트 배열
        big_endian = generate_big_endian_bytes(struct_name, valid_fields, structs_dict, macro_sizes)
        lines.append(big_endian)
        lines.append("")
        
        # Little endian 바이트 배열
        little_endian = generate_little_endian_bytes(struct_name, valid_fields, structs_dict, macro_sizes)
        lines.append(little_endian)
        lines.append("")
        
        # 배열 크기 검증
        lines.append(f"    EXPECT_EQ(sizeof(big_endian_raw_{struct_name}), sizeof({struct_name}));")
        lines.append(f"    EXPECT_EQ(sizeof(little_endian_raw_{struct_name}), sizeof({struct_name}));")
        lines.append("")
        
        # endian_converter 호출 및 검증
        lines.append(f"    endian_converter(big_endian_raw_{struct_name}, {struct_name});")
        lines.append(f"    EXPECT_EQ(0, memcmp(big_endian_raw_{struct_name}, little_endian_raw_{struct_name}, sizeof({struct_name})));")
        lines.append("}")
        lines.append("")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 generate_tests.py <헤더파일> [출력파일]")
        print("예: python3 generate_tests.py external_struct.h ut_external_struct.cc")
        sys.exit(1)
    
    header_path = Path(sys.argv[1])
    if not header_path.exists():
        print(f"오류: 파일을 찾을 수 없습니다: {header_path}")
        sys.exit(1)
    
    # 구조체 파싱
    print(f"헤더 파일 파싱 중: {header_path}")
    structs = parse_header_file(header_path)
    
    if not structs:
        print("경고: 구조체를 찾을 수 없습니다.")
        sys.exit(1)
    
    print(f"발견된 구조체: {len(structs)}개")
    for struct in structs:
        print(f"  - {struct['name']} ({len(struct['fields'])}개 필드)")
    
    # 구조체 딕셔너리 생성
    structs_dict = {struct['name']: struct['fields'] for struct in structs}
    
    # 누락된 구조체 찾기 및 사용자로부터 헤더 파일 경로 입력받기
    base_path = header_path.parent
    while True:
        missing_structs = find_missing_structs(structs, structs_dict)
        if not missing_structs:
            break
        
        print(f"\n=== 누락된 구조체 발견 ===")
        for missing_struct in missing_structs:
            header_path_for_struct = get_header_path_for_struct(missing_struct, base_path)
            if header_path_for_struct:
                # 헤더 파일 파싱하여 구조체 추가
                additional_structs = parse_header_file(header_path_for_struct)
                for add_struct in additional_structs:
                    if add_struct['name'] not in structs_dict:
                        structs.append(add_struct)
                        structs_dict[add_struct['name']] = add_struct['fields']
                        print(f"  ✓ '{add_struct['name']}' 구조체 추가됨")
            else:
                print(f"  ✗ '{missing_struct}' 구조체를 건너뜁니다.")
                # 건너뛴 구조체는 더 이상 확인하지 않도록 처리
                # 임시로 빈 필드 리스트를 추가하여 에러 방지
                structs_dict[missing_struct] = []
    
    # 매크로 배열 수집
    macro_arrays = collect_macro_arrays(structs, structs_dict)
    
    # 사용자로부터 매크로 배열 크기 입력 받기
    macro_sizes = get_macro_array_sizes(macro_arrays)
    
    # 테스트 코드 생성
    header_name = header_path.name
    test_code = generate_test_code(structs, header_name, macro_sizes)
    
    # 출력
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(test_code)
        print(f"\n테스트 코드가 생성되었습니다: {output_path}")
    else:
        print("\n=== 생성된 테스트 코드 ===")
        print(test_code)


if __name__ == "__main__":
    main()
