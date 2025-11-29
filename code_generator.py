"""테스트 코드 생성 관련 함수"""

import re
from typing import List, Tuple, Dict, Optional
from constants import TYPE_SIZES, BYTE_PATTERN, MAX_BYTES_PER_LINE
from utils import append_bytes_with_wrap, is_macro_array, get_macro_name
from utils import get_struct_id_macro, format_test_class_name


def _generate_bytes_list(base_type: str, size: int, is_big_endian: bool) -> List[str]:
    """바이트 리스트 생성 (endian에 따라 순서 결정)"""
    bytes_list = []
    if is_big_endian:
        # Big endian: 정순
        for i in range(size):
            if base_type in ['uint8_t', 'int8_t', 'char']:
                bytes_list.append(f"0x{BYTE_PATTERN[0]:02X}")
            else:
                bytes_list.append(f"0x{BYTE_PATTERN[i % len(BYTE_PATTERN)]:02X}")
    else:
        # Little endian: 역순
        for i in range(size - 1, -1, -1):
            if base_type in ['uint8_t', 'int8_t', 'char']:
                bytes_list.append(f"0x{BYTE_PATTERN[0]:02X}")
            else:
                bytes_list.append(f"0x{BYTE_PATTERN[i % len(BYTE_PATTERN)]:02X}")
    return bytes_list


def _process_multi_dim_array(field_type: str, field_name: str, current_field_path: str,
                             struct_name: str, macro_sizes: Dict[str, int],
                             structs_dict: Dict[str, List[Tuple[str, str, int]]],
                             lines: List[str], is_big_endian: bool,
                             dims_info: List[Tuple[str, Optional[int]]],
                             dim_index: int = 0, indices: List[int] = None) -> None:
    """다차원 배열 처리 (재귀적으로)"""
    if indices is None:
        indices = []
    
    if dim_index >= len(dims_info):
        return
    
    dim_name, dim_size = dims_info[dim_index]
    
    if dim_size is None or dim_size <= 0:
        # 크기를 알 수 없는 차원
        base_type = re.sub(r'\[.*?\]', '', field_type).strip()
        array_str = "".join([f"[{d[0]}]" for d in dims_info])
        lines.append(f"        // {base_type} {field_name}{array_str}; (크기 미입력)")
        return
    
    # 마지막 차원인 경우
    if dim_index == len(dims_info) - 1:
        base_type = re.sub(r'\[.*?\]', '', field_type).strip()
        base_size = TYPE_SIZES.get(base_type, 0)
        nested_fields = structs_dict.get(base_type)
        
        if nested_fields:
            # 중첩 구조체 배열
            for elem_idx in range(dim_size):
                current_indices = indices + [elem_idx]
                array_indices = "".join([f"[{idx}]" for idx in current_indices])
                lines.append(f"        // Start: {base_type} {field_name}{array_indices}")
                nested_bytes = _generate_endian_bytes(
                    struct_name, nested_fields, structs_dict, macro_sizes,
                    f"{current_field_path}[{elem_idx}]", is_big_endian)
                nested_lines = nested_bytes.split('\n')[2:-1]
                lines.extend(nested_lines)
                lines.append(f"        // End: {base_type} {field_name}{array_indices}")
        elif base_size > 0:
            # 기본 타입 배열
            for elem_idx in range(dim_size):
                bytes_list = _generate_bytes_list(base_type, base_size, is_big_endian)
                bytes_str = ", ".join(bytes_list)
                current_indices = indices + [elem_idx]
                array_indices = "".join([f"[{idx}]" for idx in current_indices])
                lines.append(f"        {bytes_str}, //{base_type} {field_name}{array_indices};")
        else:
            array_str = "".join([f"[{d[0]}]" for d in dims_info])
            lines.append(f"        // {base_type} {field_name}{array_str}; (타입 크기 알 수 없음)")
    else:
        # 중간 차원: 재귀적으로 처리
        for elem_idx in range(dim_size):
            new_path = f"{current_field_path}[{elem_idx}]"
            new_indices = indices + [elem_idx]
            _process_multi_dim_array(
                field_type, field_name, new_path, struct_name,
                macro_sizes, structs_dict, lines, is_big_endian,
                dims_info, dim_index + 1, new_indices)


def _process_macro_array_field(field_type: str, field_name: str, current_field_path: str,
                               struct_name: str, macro_sizes: Dict[str, int],
                               structs_dict: Dict[str, List[Tuple[str, str, int]]],
                               lines: List[str], is_big_endian: bool) -> None:
    """매크로 배열 필드 처리 (2차원 배열 지원)"""
    from utils import get_array_dimensions_info
    
    dims_info = get_array_dimensions_info(field_type, macro_sizes)
    
    if not dims_info:
        base_type = re.sub(r'\[.*?\]', '', field_type).strip()
        lines.append(f"        // {base_type} {field_name}; (배열 차원 파싱 실패)")
        return
    
    # 모든 차원의 크기를 알 수 있는지 확인
    all_sizes_known = all(size is not None and size > 0 for _, size in dims_info)
    
    if all_sizes_known:
        # 다차원 배열 처리
        _process_multi_dim_array(
            field_type, field_name, current_field_path, struct_name,
            macro_sizes, structs_dict, lines, is_big_endian, dims_info)
    else:
        # 크기를 알 수 없는 차원이 있는 경우
        base_type = re.sub(r'\[.*?\]', '', field_type).strip()
        array_str = "".join([f"[{d[0]}]" for d in dims_info])
        lines.append(f"        // {base_type} {field_name}{array_str}; (크기 미입력)")


def _process_nested_struct_field(field_type: str, field_name: str, current_field_path: str,
                                struct_name: str, structs_dict: Dict[str, List[Tuple[str, str, int]]],
                                macro_sizes: Dict[str, int], lines: List[str],
                                is_big_endian: bool) -> bool:
    """중첩 구조체 필드 처리. 처리 성공 여부 반환"""
    base_type = field_type.strip()
    nested_fields = structs_dict.get(base_type)
    if nested_fields:
        lines.append(f"        // Start: {field_type} {field_name}")
        nested_bytes = _generate_endian_bytes(
            struct_name, nested_fields, structs_dict, macro_sizes, current_field_path, is_big_endian)
        nested_lines = nested_bytes.split('\n')[2:-1]
        lines.extend(nested_lines)
        lines.append(f"        // End: {field_type} {field_name}")
        return True
    return False


def _generate_endian_bytes(msg_id: str, fields: List[Tuple[str, str, int]],
                          structs_dict: Dict[str, List[Tuple[str, str, int]]],
                          macro_sizes: Dict[str, int], field_path: str,
                          is_big_endian: bool) -> str:
    """Endian 바이트 배열 생성 (공통 함수)"""
    if structs_dict is None:
        structs_dict = {}
    if macro_sizes is None:
        macro_sizes = {}
    
    endian_prefix = "big_endian" if is_big_endian else "little_endian"
    lines = []
    lines.append(f"    uint8_t {endian_prefix}_raw_{msg_id}[] = ")
    lines.append("    {")
    
    for field_type, field_name, size in fields:
        current_field_path = f"{field_path}.{field_name}" if field_path else field_name
        
        if size == 0:
            # 크기를 알 수 없는 경우
            if is_macro_array(field_type):
                _process_macro_array_field(
                    field_type, field_name, current_field_path, msg_id,
                    macro_sizes, structs_dict, lines, is_big_endian)
            else:
                # 중첩 구조체인지 확인
                if not _process_nested_struct_field(
                    field_type, field_name, current_field_path, msg_id,
                    structs_dict, macro_sizes, lines, is_big_endian):
                    continue
        else:
            # 일반 필드: 바이트 리스트 생성
            base_type = re.sub(r'\[.*?\]', '', field_type).strip()
            bytes_list = _generate_bytes_list(base_type, size, is_big_endian)
            comment = f"//{field_type} {field_name};"
            append_bytes_with_wrap(lines, bytes_list, comment=comment)
    
    lines.append("    };")
    return "\n".join(lines)


def generate_big_endian_bytes(msg_id: str, fields: List[Tuple[str, str, int]], 
                             structs_dict: Dict[str, List[Tuple[str, str, int]]] = None, 
                             macro_sizes: Dict[str, int] = None, 
                             field_path: str = "") -> str:
    """Big endian 바이트 배열 생성"""
    return _generate_endian_bytes(msg_id, fields, structs_dict, macro_sizes, field_path, True)


def generate_little_endian_bytes(msg_id: str, fields: List[Tuple[str, str, int]], 
                                structs_dict: Dict[str, List[Tuple[str, str, int]]] = None, 
                                macro_sizes: Dict[str, int] = None, 
                                field_path: str = "") -> str:
    """Little endian 바이트 배열 생성"""
    return _generate_endian_bytes(msg_id, fields, structs_dict, macro_sizes, field_path, False)

def generate_test_code(structs: List[Dict], header_name: str, 
                      macro_sizes: Dict[str, int]) -> str:
    """테스트 코드 생성"""
    lines = []
    include_name = header_name
    
    lines.append("#include <gtest/gtest.h>")
    lines.append("")
    lines.append("extern \"C\" {")
    lines.append(f"#include \"{include_name}\"")
    lines.append("}")
    lines.append("")
    
    structs_dict = {struct['name']: struct['fields'] for struct in structs}
    
    for struct in structs:
        struct_name = struct['name']
        fields = struct['fields']
        
        if not fields:
            continue
        
        test_class = "GcciEndianConverterDfcbTest"
        msg_id = get_struct_id_macro(struct_name)
        test_name = f"{msg_id}_endian_converter"
        
        lines.append(f"TEST({test_class}, {msg_id})")
        lines.append("{")

        # Big endian 바이트 배열
        big_endian = generate_big_endian_bytes(msg_id, fields, structs_dict, macro_sizes)
        lines.append(big_endian)
        lines.append("")
        
        # Little endian 바이트 배열
        little_endian = generate_little_endian_bytes(msg_id, fields, structs_dict, macro_sizes)
        lines.append(little_endian)
        lines.append("")
        
        # 배열 크기 검증
        lines.append(f"    EXPECT_EQ(sizeof(big_endian_raw_{msg_id}),")
        lines.append(f"              sizeof({struct_name}));")
        lines.append(f"    EXPECT_EQ(sizeof(little_endian_raw_{msg_id}),")
        lines.append(f"              sizeof({struct_name}));")
        lines.append("")
        
        
        # 포인터 선언 및 필드 설정
        lines.append(f"    messageHdr_type *pBigEndianMsgHdr = (messageHdr_type *)big_endian_raw_{msg_id};")
        lines.append(f"    messageHdr_type *pLittleEndianMsgHdr = (messageHdr_type *)little_endian_raw_{msg_id};")
        lines.append(f"    pBigEndianMsgHdr ->msgType = htons({msg_id});")
        lines.append(f"    pLittleEndianMsgHdr->msgType = ({msg_id});")
        lines.append("")
        
        # Gcci_EndianH2N 호출
        lines.append(f"    Gcci_EndianH2N(little_endian_raw_{msg_id}, sizeof({struct_name}));")
        lines.append("")
        
        # memcmp 검증
        lines.append(f"    EXPECT_EQ(0, memcmp(big_endian_raw_{msg_id},")
        lines.append(f"                        little_endian_raw_{msg_id},")
        lines.append(f"                        sizeof(little_endian_raw_{msg_id})));")
        lines.append("}")
        lines.append("")
    
    return "\n".join(lines)
