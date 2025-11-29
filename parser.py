"""헤더 파일 파싱 관련 함수"""

import re
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from utils import get_type_size, remove_comments


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
    
    # 배열 필드 처리 (2차원 배열 지원)
    # 모든 배열 차원 찾기 (예: [10][20] 또는 [MAX_SIZE][MAX_COUNT])
    array_dims = re.findall(r'\[([^\]]+)\]', line)
    array_part = ""
    field_name = None
    
    if array_dims:
        # 배열이 있는 경우: 모든 배열 차원 추출
        array_part = "".join([f"[{dim}]" for dim in array_dims])
        # 필드 이름 찾기 (배열 이전의 마지막 단어)
        # 예: "uint32_t data[10][20]" -> "data"
        # 배열 부분을 제거한 후 마지막 단어가 필드 이름
        line_without_array = re.sub(r'\[[^\]]+\]', '', line)
        parts = [p for p in line_without_array.split() if p]
        if len(parts) < 2:
            return None
        field_name = parts[-1]
        type_part = ' '.join(parts[:-1])
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


def parse_struct_block(struct_block: str) -> Tuple[Optional[str], List[Tuple[str, str, int]]]:
    """구조체 블록을 파싱하여 이름과 필드 리스트 반환"""
    clean_block = remove_comments(struct_block)
    
    # union인지 확인 (union은 제외)
    if re.search(r'typedef\s+union\s', clean_block):
        return None, []
    
    # 구조체 이름 추출: } 다음에 오는 이름
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
        
        field = parse_field_line(line)
        if field:
            fields.append(field)
    
    return struct_name, fields


def parse_header_file(header_path: Path) -> List[Dict]:
    """헤더 파일에서 모든 구조체 파싱 (union 제외)"""
    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    structs = []
    
    # typedef struct 블록 찾기
    pattern = r'typedef\s+struct\s*(?:\w+)?\s*\{'
    
    for match in re.finditer(pattern, content):
        start_pos = match.start()
        
        # { 부터 시작해서 매칭되는 } 찾기
        brace_count = 0
        pos = match.end() - 1  # { 위치로 이동
        
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

