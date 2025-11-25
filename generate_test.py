#!/usr/bin/env python3
"""
헤더 파일에서 구조체를 파싱하여 endian converter 테스트 코드를 생성하는 스크립트
"""

import re
import sys
import json
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


def parse_macros_from_header(header_path: Path) -> Dict[str, int]:
    """헤더 파일에서 #define 매크로 정의 파싱"""
    macros = {}
    try:
        with open(header_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # #define 매크로 패턴 찾기
        # 예: #define MAX_SENSOR_COUNT 16
        # 예: #define MAX_SENSOR_COUNT       16
        pattern = r'#define\s+(\w+)\s+(\d+)'
        matches = re.findall(pattern, content)
        
        for macro_name, macro_value in matches:
            try:
                macros[macro_name] = int(macro_value)
            except ValueError:
                pass  # 숫자가 아닌 값은 무시
    except (IOError, UnicodeDecodeError):
        pass
    
    return macros


def parse_macros_from_compile_commands(compile_commands_path: Path) -> Dict[str, int]:
    """compile_commands.json 파일에서 컴파일러 플래그(-D)로 정의된 매크로 파싱"""
    macros = {}
    try:
        with open(compile_commands_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # compile_commands.json은 배열 형식
        if not isinstance(data, list):
            return macros
        
        # 각 컴파일 명령어에서 -D 플래그 추출
        for entry in data:
            if not isinstance(entry, dict):
                continue
            
            # "command" 필드에서 -D 플래그 찾기
            command = entry.get('command', '')
            if not command:
                # "arguments" 필드가 있는 경우 (일부 도구는 이 형식 사용)
                arguments = entry.get('arguments', [])
                if isinstance(arguments, list):
                    command = ' '.join(str(arg) for arg in arguments)
            
            # -D 플래그 패턴 찾기
            # 형식 1: -DMAX_SENSOR_COUNT=16
            # 형식 2: -D MAX_SENSOR_COUNT=16 (공백 포함)
            # 형식 3: -D"MAX_SENSOR_COUNT=16" (따옴표 포함)
            # 형식 4: -D MAX_SENSOR_COUNT (값 없음, 1로 간주)
            
            # 통합 패턴: -D 다음에 공백/따옴표가 있을 수 있고, 매크로 이름과 선택적 값
            # 모든 -D 플래그를 찾되, 중복 제거를 위해 set 사용
            define_pattern = r'-D\s*(?:["\'])?(\w+)(?:=(\d+))?(?:["\'])?(?=\s|$|")'
            matches = re.findall(define_pattern, command)
            
            for macro_name, macro_value in matches:
                if macro_value:
                    # 값이 있는 경우
                    try:
                        macros[macro_name] = int(macro_value)
                    except ValueError:
                        pass
                else:
                    # 값이 없는 경우 1로 설정
                    macros[macro_name] = 1
                    
    except (IOError, json.JSONDecodeError, KeyError, AttributeError):
        pass
    
    return macros


def parse_macros_from_compile_json(compile_json_path: Path) -> Dict[str, int]:
    """compile.json 파일에서 매크로 정의 파싱"""
    macros = {}
    try:
        with open(compile_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # compile.json의 다양한 형식 지원
        # 형식 1: { "defines": { "MAX_SENSOR_COUNT": 16, ... } }
        if isinstance(data, dict):
            if 'defines' in data and isinstance(data['defines'], dict):
                for key, value in data['defines'].items():
                    if isinstance(value, (int, str)):
                        try:
                            macros[key] = int(value)
                        except (ValueError, TypeError):
                            pass
            
            # 형식 2: { "macros": { "MAX_SENSOR_COUNT": 16, ... } }
            elif 'macros' in data and isinstance(data['macros'], dict):
                for key, value in data['macros'].items():
                    if isinstance(value, (int, str)):
                        try:
                            macros[key] = int(value)
                        except (ValueError, TypeError):
                            pass
    except (IOError, json.JSONDecodeError, KeyError):
        pass
    
    return macros


def collect_macros_from_headers(structs: List[Dict], base_path: Path, header_paths: List[Path]) -> Dict[str, int]:
    """구조체에서 참조하는 헤더 파일들에서 매크로 수집"""
    all_macros = {}
    
    # 이미 파싱한 헤더 파일들
    parsed_headers = set()
    
    # 기본 헤더 파일들 파싱
    for header_path in header_paths:
        if header_path.exists() and header_path not in parsed_headers:
            macros = parse_macros_from_header(header_path)
            all_macros.update(macros)
            parsed_headers.add(header_path)
    
    # 구조체에서 참조하는 헤더 파일 찾기
    # include 문을 찾기 위해 헤더 파일들을 다시 읽어야 함
    for header_path in header_paths:
        if not header_path.exists():
            continue
        
        try:
            with open(header_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # #include "..." 패턴 찾기
            include_pattern = r'#include\s+"([^"]+)"'
            includes = re.findall(include_pattern, content)
            
            for include_file in includes:
                include_path = base_path / include_file
                if include_path.exists() and include_path not in parsed_headers:
                    macros = parse_macros_from_header(include_path)
                    all_macros.update(macros)
                    parsed_headers.add(include_path)
        except (IOError, UnicodeDecodeError):
            continue
    
    return all_macros


def is_likely_macro_name(name: str) -> bool:
    """이름이 매크로 이름일 가능성이 있는지 확인"""
    # 매크로는 보통 대문자로만 구성되거나, 대문자와 언더스코어로 구성됨
    # 예: MAX_SIZE, MAX_DATA_BUFFER_SIZE
    if not name:
        return False
    # 모두 대문자이거나 대문자와 언더스코어로만 구성된 경우 매크로로 간주
    if name.isupper() or (name.replace('_', '').isupper() and '_' in name):
        return True
    return False


def find_missing_structs(structs: List[Dict], structs_dict: Dict[str, List[Tuple[str, str, int]]], discovered_macros: Dict[str, int] = None) -> List[str]:
    """
    구조체 필드에서 참조되지만 정의되지 않은 구조체 찾기
    Returns: 누락된 구조체 이름 리스트
    """
    if discovered_macros is None:
        discovered_macros = {}
    
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
            
            # 매크로 이름인지 확인 (발견된 매크로 목록에 있거나 매크로 패턴인 경우)
            if base_type in discovered_macros or is_likely_macro_name(base_type):
                continue  # 매크로는 구조체가 아니므로 스킵
            
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


def load_cache(cache_path: Path) -> Dict:
    """캐시 파일 로드"""
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_cache(cache_path: Path, cache: Dict):
    """캐시 파일 저장"""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except IOError:
        pass  # 캐시 저장 실패해도 계속 진행


def get_header_path_for_struct(missing_struct: str, base_path: Path, cache: Dict, structs_dict: Dict) -> Tuple[Optional[Path], List[Dict]]:
    """사용자로부터 구조체가 정의된 헤더 파일 경로 입력 받기"""
    # 캐시에서 확인
    cache_key = f"struct_header_paths.{missing_struct}"
    if 'struct_header_paths' in cache and missing_struct in cache['struct_header_paths']:
        cached_path_str = cache['struct_header_paths'][missing_struct]
        cached_path = Path(cached_path_str).resolve()
        if cached_path.exists():
            print(f"\n구조체 '{missing_struct}'의 헤더 파일 경로를 캐시에서 찾았습니다: {cached_path}")
            use_cache = input("이 경로를 사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()
            if not use_cache or use_cache == 'y':
                # 헤더 파일에서 모든 구조체 파싱하여 structs_dict에 추가
                structs = parse_header_file(cached_path)
                struct_names = [s['name'] for s in structs]
                # 헤더 파일의 모든 구조체를 structs_dict에 추가
                added_structs = []
                found_in_cache = False
                for struct in structs:
                    if struct['name'] == missing_struct:
                        found_in_cache = True
                    if struct['name'] not in structs_dict:
                        structs_dict[struct['name']] = struct['fields']
                        added_structs.append(struct)
                        print(f"  ✓ '{struct['name']}' 구조체 추가됨")
                    else:
                        # 이미 있는 구조체도 추가된 구조체 목록에 포함
                        added_structs.append(struct)
                
                if found_in_cache:
                    return cached_path, added_structs
                else:
                    print(f"경고: 캐시된 경로 '{cached_path}'에서 '{missing_struct}' 구조체를 찾을 수 없습니다.")
                    # 그래도 헤더 파일의 모든 구조체는 추가했으므로 계속 진행
            # 캐시된 경로가 유효하지 않거나 사용자가 거부한 경우 계속 진행
    
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
            
            # 헤더 파일에서 모든 구조체 파싱
            structs = parse_header_file(header_path)
            struct_names = [s['name'] for s in structs]
            
            # 헤더 파일의 모든 구조체를 structs_dict에 추가
            found_missing = False
            added_structs = []
            for struct in structs:
                # 누락된 구조체가 발견되었는지 먼저 확인
                if struct['name'] == missing_struct:
                    found_missing = True
                
                if struct['name'] not in structs_dict:
                    structs_dict[struct['name']] = struct['fields']
                    added_structs.append(struct)
                    print(f"  ✓ '{struct['name']}' 구조체 추가됨")
                else:
                    # 이미 있는 구조체도 추가된 구조체 목록에 포함 (필드 업데이트 확인용)
                    added_structs.append(struct)
            
            if not found_missing:
                print(f"경고: '{header_path}'에서 '{missing_struct}' 구조체를 찾을 수 없습니다.")
                print(f"발견된 구조체: {', '.join(struct_names) if struct_names else '없음'}")
                retry = input("다시 입력하시겠습니까? (y/n): ").strip().lower()
                if retry != 'y':
                    return None, []
                continue
            
            # 캐시에 저장
            if 'struct_header_paths' not in cache:
                cache['struct_header_paths'] = {}
            cache['struct_header_paths'][missing_struct] = str(header_path.resolve())
            
            return header_path, added_structs
            
        except KeyboardInterrupt:
            print("\n취소되었습니다.")
            return None, []
        except Exception as e:
            print(f"오류 발생: {e}")
            retry = input("다시 입력하시겠습니까? (y/n): ").strip().lower()
            if retry != 'y':
                return None, []


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


def get_macro_array_sizes(macro_arrays: Dict, cache: Dict, discovered_macros: Dict[str, int] = None) -> Dict[Tuple[str, str], int]:
    """사용자로부터 매크로 배열 크기 입력 받기 (헤더 파일이나 compile.json에서 발견한 매크로 우선 사용)"""
    macro_sizes = {}
    
    if not macro_arrays:
        return macro_sizes
    
    if discovered_macros is None:
        discovered_macros = {}
    
    total_count = len(macro_arrays)
    current_count = 0
    
    print(f"\n=== 매크로 배열 크기 입력 ===")
    print(f"총 {total_count}개의 매크로 배열 크기가 필요합니다.\n")
    
    for (struct_name, field_path), info in macro_arrays.items():
        current_count += 1
        macro_name = info['macro_name']
        field_type = info['field_type']
        field_name = info['field_name']
        
        # 1. 헤더 파일이나 compile.json에서 발견한 매크로 확인
        if macro_name in discovered_macros:
            discovered_size = discovered_macros[macro_name]
            print(f"\n[{current_count}/{total_count}] 구조체: {struct_name}")
            print(f"필드: {field_path}")
            print(f"타입: {field_type}")
            print(f"매크로: {macro_name}")
            print(f"헤더 파일/compile.json에서 발견한 값: {discovered_size}")
            use_discovered = input("이 값을 사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()
            if not use_discovered or use_discovered == 'y':
                macro_sizes[(struct_name, field_path)] = discovered_size
                # 캐시에도 저장
                cache_key = f"{struct_name}.{field_path}"
                if 'macro_sizes' not in cache:
                    cache['macro_sizes'] = {}
                cache['macro_sizes'][cache_key] = discovered_size
                continue
        
        # 2. 캐시에서 확인
        cache_key = f"{struct_name}.{field_path}"
        if 'macro_sizes' in cache and cache_key in cache['macro_sizes']:
            cached_size = cache['macro_sizes'][cache_key]
            print(f"\n[{current_count}/{total_count}] 구조체: {struct_name}")
            print(f"필드: {field_path}")
            print(f"타입: {field_type}")
            print(f"매크로: {macro_name}")
            print(f"캐시된 배열 크기: {cached_size}")
            use_cache = input("이 크기를 사용하시겠습니까? (y/n, 기본값: y): ").strip().lower()
            if not use_cache or use_cache == 'y':
                macro_sizes[(struct_name, field_path)] = cached_size
                continue
        
        # 3. 사용자 입력 요청
        print(f"\n[{current_count}/{total_count}] 구조체: {struct_name}")
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
                
                # 캐시에 저장
                if 'macro_sizes' not in cache:
                    cache['macro_sizes'] = {}
                cache['macro_sizes'][cache_key] = array_size
                
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
                                # uint8_t의 경우 첫 번째 바이트 값만 반복
                                if base_type == 'uint8_t' or base_type == 'int8_t' or base_type == 'char':
                                    bytes_list.append(f"0x{byte_pattern[0]:02X}")
                                else:
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
            # 필드 타입 추출 (배열 제거)
            base_type = re.sub(r'\[.*?\]', '', field_type).strip()
            for i in range(size):
                # uint8_t의 경우 첫 번째 바이트 값만 반복
                if base_type == 'uint8_t' or base_type == 'int8_t' or base_type == 'char':
                    bytes_list.append(f"0x{byte_pattern[0]:02X}")
                else:
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
                                # uint8_t의 경우 첫 번째 바이트 값만 반복
                                if base_type == 'uint8_t' or base_type == 'int8_t' or base_type == 'char':
                                    bytes_list.append(f"0x{byte_pattern[0]:02X}")
                                else:
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
            # 필드 타입 추출 (배열 제거)
            base_type = re.sub(r'\[.*?\]', '', field_type).strip()
            for i in range(size - 1, -1, -1):
                # uint8_t의 경우 첫 번째 바이트 값만 반복
                if base_type == 'uint8_t' or base_type == 'int8_t' or base_type == 'char':
                    bytes_list.append(f"0x{byte_pattern[0]:02X}")
                else:
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
        lines.append(f"    EXPECT_EQ(sizeof(big_endian_raw_{struct_name}), ")
        lines.append(f"sizeof({struct_name}));")
        lines.append(f"    EXPECT_EQ(sizeof(little_endian_raw_{struct_name}), ")
        lines.append(f"sizeof({struct_name}));")
        lines.append("")
        
        # 구조체 ID 매크로 이름 생성 (소문자로 유지)
        # 구조체 이름이 _type으로 끝나면 _id로 변경
        if struct_name.endswith('_type'):
            struct_id_macro = struct_name[:-5] + "_id"  # _type 제거 후 _id 추가
        else:
            struct_id_macro = struct_name + "_id"
        
        # 포인터 선언 및 필드 설정 (msgType 필드 사용)
        lines.append(f"    messageHdr_type *pBigEndianMsgHdr = (messageHdr_type *)big_endian_raw_{struct_name};")
        lines.append(f"    messageHdr_type *pLittleEndianMsgHdr = (messageHdr_type *)little_endian_raw_{struct_name};")
        lines.append(f"    pBigEndianMsgHdr ->msgType = {struct_id_macro};")
        lines.append(f"    pLittleEndianMsgHdr->msgType = ntohs({struct_id_macro});")
        lines.append("")
        
        # Gcci_EndianH2N 호출
        lines.append(f"    Gcci_EndianH2N(big_endian_raw_{struct_name}, sizeof({struct_name}));")
        lines.append("")
        
        # memcmp 검증
        lines.append(f"    EXPECT_EQ(0, memcmp(big_endian_raw_{struct_name}, ")
        lines.append(f"little_endian_raw_{struct_name},")
        lines.append(f"sizeof(little_endian_raw_{struct_name})));")
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
    
    # 캐시 파일 경로 설정 (현재 디렉토리의 .endian_converter_cache.json)
    base_path = header_path.parent
    cache_path = base_path / '.endian_converter_cache.json'
    
    # 캐시 로드
    cache = load_cache(cache_path)
    
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
    
    # 헤더 파일과 compile.json, compile_commands.json에서 매크로 정의 자동 수집
    discovered_macros = {}
    
    # 1. compile_commands.json 파일 확인 (CMake 빌드 시 생성)
    compile_commands_path = base_path / 'compile_commands.json'
    if not compile_commands_path.exists():
        # build 디렉토리나 상위 디렉토리에서도 찾기
        for search_path in [base_path.parent / 'build', base_path.parent, base_path]:
            potential_path = search_path / 'compile_commands.json'
            if potential_path.exists():
                compile_commands_path = potential_path
                break
    
    if compile_commands_path.exists():
        print(f"\ncompile_commands.json 파일에서 매크로 정의를 찾는 중... ({compile_commands_path})")
        compile_commands_macros = parse_macros_from_compile_commands(compile_commands_path)
        if compile_commands_macros:
            print(f"  발견된 매크로: {', '.join(compile_commands_macros.keys())}")
            discovered_macros.update(compile_commands_macros)
    
    # 2. compile.json 파일 확인
    compile_json_path = base_path / 'compile.json'
    if compile_json_path.exists():
        print(f"\ncompile.json 파일에서 매크로 정의를 찾는 중...")
        compile_macros = parse_macros_from_compile_json(compile_json_path)
        if compile_macros:
            print(f"  발견된 매크로: {', '.join(compile_macros.keys())}")
            discovered_macros.update(compile_macros)
    
    # 3. 헤더 파일들에서 매크로 정의 수집
    # 구조체가 정의된 헤더 파일과 include된 헤더 파일들 확인
    header_paths = [header_path]
    # 캐시에서 추가된 헤더 파일 경로들도 포함
    if 'struct_header_paths' in cache:
        for cached_path_str in cache['struct_header_paths'].values():
            cached_path = Path(cached_path_str)
            if cached_path.exists() and cached_path not in header_paths:
                header_paths.append(cached_path)
    
    print(f"\n헤더 파일들에서 매크로 정의를 찾는 중...")
    header_macros = collect_macros_from_headers(structs, base_path, header_paths)
    if header_macros:
        print(f"  발견된 매크로: {', '.join(header_macros.keys())}")
        discovered_macros.update(header_macros)
    
    # 누락된 구조체 찾기 및 사용자로부터 헤더 파일 경로 입력받기
    while True:
        missing_structs = find_missing_structs(structs, structs_dict, discovered_macros)
        if not missing_structs:
            break
        
        print(f"\n=== 누락된 구조체 발견 ===")
        for missing_struct in missing_structs:
            header_path_for_struct, added_structs = get_header_path_for_struct(missing_struct, base_path, cache, structs_dict)
            # 캐시 저장 (경로가 추가되었을 수 있음)
            save_cache(cache_path, cache)
            
            if header_path_for_struct:
                # get_header_path_for_struct 함수에서 반환한 모든 구조체를 structs 리스트에 추가
                for add_struct in added_structs:
                    if add_struct['name'] not in [s['name'] for s in structs]:
                        structs.append(add_struct)
            else:
                print(f"  ✗ '{missing_struct}' 구조체를 건너뜁니다.")
                # 건너뛴 구조체는 더 이상 확인하지 않도록 처리
                # 임시로 빈 필드 리스트를 추가하여 에러 방지
                structs_dict[missing_struct] = []
    
    # 매크로 배열 수집
    macro_arrays = collect_macro_arrays(structs, structs_dict)
    
    # 헤더 파일과 compile.json, compile_commands.json에서 매크로 정의 자동 수집
    discovered_macros = {}
    
    # 1. compile_commands.json 파일 확인 (CMake 빌드 시 생성)
    compile_commands_path = base_path / 'compile_commands.json'
    if not compile_commands_path.exists():
        # build 디렉토리나 상위 디렉토리에서도 찾기
        for search_path in [base_path.parent / 'build', base_path.parent, base_path]:
            potential_path = search_path / 'compile_commands.json'
            if potential_path.exists():
                compile_commands_path = potential_path
                break
    
    if compile_commands_path.exists():
        print(f"\ncompile_commands.json 파일에서 매크로 정의를 찾는 중... ({compile_commands_path})")
        compile_commands_macros = parse_macros_from_compile_commands(compile_commands_path)
        if compile_commands_macros:
            print(f"  발견된 매크로: {', '.join(compile_commands_macros.keys())}")
            discovered_macros.update(compile_commands_macros)
    
    # 2. compile.json 파일 확인
    compile_json_path = base_path / 'compile.json'
    if compile_json_path.exists():
        print(f"\ncompile.json 파일에서 매크로 정의를 찾는 중...")
        compile_macros = parse_macros_from_compile_json(compile_json_path)
        if compile_macros:
            print(f"  발견된 매크로: {', '.join(compile_macros.keys())}")
            discovered_macros.update(compile_macros)
    
    # 3. 헤더 파일들에서 매크로 정의 수집
    # 구조체가 정의된 헤더 파일과 include된 헤더 파일들 확인
    header_paths = [header_path]
    # 캐시에서 추가된 헤더 파일 경로들도 포함
    if 'struct_header_paths' in cache:
        for cached_path_str in cache['struct_header_paths'].values():
            cached_path = Path(cached_path_str)
            if cached_path.exists() and cached_path not in header_paths:
                header_paths.append(cached_path)
    
    print(f"\n헤더 파일들에서 매크로 정의를 찾는 중...")
    header_macros = collect_macros_from_headers(structs, base_path, header_paths)
    if header_macros:
        print(f"  발견된 매크로: {', '.join(header_macros.keys())}")
        discovered_macros.update(header_macros)
    
    # 사용자로부터 매크로 배열 크기 입력 받기 (발견한 매크로 우선 사용)
    macro_sizes = get_macro_array_sizes(macro_arrays, cache, discovered_macros)
    # 캐시 저장 (매크로 크기가 추가되었을 수 있음)
    save_cache(cache_path, cache)
    
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
