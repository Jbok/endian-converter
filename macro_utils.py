"""매크로 관련 유틸리티 함수"""

import re
import json
from typing import Dict, List
from pathlib import Path
from parser import parse_header_file


def parse_macros_from_header(header_path: Path) -> Dict[str, int]:
    """헤더 파일에서 #define 매크로 정의 파싱"""
    macros = {}
    try:
        with open(header_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # #define 매크로 패턴 찾기
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
        
        if not isinstance(data, list):
            return macros
        
        for entry in data:
            if not isinstance(entry, dict):
                continue
            
            command = entry.get('command', '')
            if not command:
                arguments = entry.get('arguments', [])
                if isinstance(arguments, list):
                    command = ' '.join(str(arg) for arg in arguments)
            
            # -D 플래그 패턴 찾기
            define_pattern = r'-D\s*(?:["\'])?(\w+)(?:=(\d+))?(?:["\'])?(?=\s|$|")'
            matches = re.findall(define_pattern, command)
            
            for macro_name, macro_value in matches:
                if macro_value:
                    try:
                        macros[macro_name] = int(macro_value)
                    except ValueError:
                        pass
                else:
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
        
        if isinstance(data, dict):
            # 형식 1: { "defines": { "MAX_SENSOR_COUNT": 16, ... } }
            if 'defines' in data and isinstance(data['defines'], dict):
                for key, value in data['defines'].items():
                    if isinstance(value, (int, str)):
                        try:
                            macros[key] = int(value)
                        except (ValueError, TypeError):
                            pass
            
            # 형식 2: { "macros": { "MAX_SENSOR_COUNT": 16, ... } }
            if 'macros' in data and isinstance(data['macros'], dict):
                for key, value in data['macros'].items():
                    if isinstance(value, (int, str)):
                        try:
                            macros[key] = int(value)
                        except (ValueError, TypeError):
                            pass
    except (IOError, json.JSONDecodeError, KeyError):
        pass
    
    return macros


def collect_macros_from_headers(structs: List[Dict], base_path: Path, 
                                header_paths: List[Path]) -> Dict[str, int]:
    """구조체에서 참조하는 헤더 파일들에서 매크로 수집"""
    all_macros = {}
    parsed_headers = set()
    
    # 기본 헤더 파일들 파싱
    for header_path in header_paths:
        if header_path.exists() and header_path not in parsed_headers:
            macros = parse_macros_from_header(header_path)
            all_macros.update(macros)
            parsed_headers.add(header_path)
    
    # 구조체에서 참조하는 헤더 파일 찾기
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


def collect_macro_arrays(structs: List[Dict], 
                         structs_dict: Dict[str, List]) -> Dict:
    """모든 구조체에서 매크로 배열 필드를 수집"""
    from utils import is_macro_array, get_macro_name
    
    macro_arrays = {}
    
    def collect_from_fields(struct_name: str, fields: List, prefix: str = ""):
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
                        collect_from_fields(struct_name, nested_fields, full_field_name)
    
    for struct in structs:
        struct_name = struct['name']
        fields = struct['fields']
        collect_from_fields(struct_name, fields)
    
    return macro_arrays


def discover_all_macros(base_path: Path, header_path: Path, 
                       cache: Dict) -> Dict[str, int]:
    """모든 소스에서 매크로를 수집하는 통합 함수"""
    discovered_macros = {}
    
    # 1. compile_commands.json 파일 확인
    compile_commands_path = find_compile_commands(base_path)
    if compile_commands_path and compile_commands_path.exists():
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
    header_paths = [header_path]
    if 'struct_header_paths' in cache:
        for cached_path_str in cache['struct_header_paths'].values():
            cached_path = Path(cached_path_str)
            if cached_path.exists() and cached_path not in header_paths:
                header_paths.append(cached_path)
    
    print(f"\n헤더 파일들에서 매크로 정의를 찾는 중...")
    header_macros = collect_macros_from_headers([], base_path, header_paths)
    if header_macros:
        print(f"  발견된 매크로: {', '.join(header_macros.keys())}")
        discovered_macros.update(header_macros)
    
    return discovered_macros


def find_compile_commands(base_path: Path) -> Path:
    """compile_commands.json 파일 경로 찾기"""
    compile_commands_path = base_path / 'compile_commands.json'
    if not compile_commands_path.exists():
        for search_path in [base_path.parent / 'build', base_path.parent, base_path]:
            potential_path = search_path / 'compile_commands.json'
            if potential_path.exists():
                return potential_path
    return compile_commands_path


def get_macro_array_sizes(macro_arrays: Dict, cache: Dict, 
                         discovered_macros: Dict[str, int] = None) -> Dict[str, int]:
    """사용자로부터 매크로 배열 크기 입력 받기"""
    import sys
    
    macro_sizes: Dict[str, int] = {}
    
    if not macro_arrays:
        return macro_sizes
    
    if discovered_macros is None:
        discovered_macros = {}
    
    # 서로 다른 매크로 이름 개수 기준으로 카운트
    unique_macro_names = sorted({info['macro_name'] for info in macro_arrays.values()})
    total_count = len(unique_macro_names)
    current_count = 0
    processed_macros = set()
    
    print(f"\n=== 매크로 배열 크기 입력 ===")
    print(f"총 {total_count}개의 매크로 배열 크기가 필요합니다.\n")
    
    for (struct_name, field_path), info in macro_arrays.items():
        macro_name = info['macro_name']
        field_type = info['field_type']
        field_name = info['field_name']

        # 같은 매크로 이름은 한 번만 처리
        if macro_name in processed_macros:
            continue
        processed_macros.add(macro_name)
        current_count += 1
        
        # 1. 캐시에서 확인
        if 'macro_sizes' in cache and macro_name in cache['macro_sizes']:
            cached_size = cache['macro_sizes'][macro_name]
            print(f"\n[{current_count}/{total_count}] 매크로: {macro_name}")
            print(f"예시 구조체: {struct_name}")
            print(f"예시 필드: {field_path}")
            print(f"타입: {field_type}")
            print(f"캐시된 배열 크기: {cached_size} (자동 사용)")
            macro_sizes[macro_name] = cached_size
            continue
        
        # 2. 헤더 파일이나 compile.json에서 발견한 매크로 확인
        if macro_name in discovered_macros:
            discovered_size = discovered_macros[macro_name]
            print(f"\n[{current_count}/{total_count}] 매크로: {macro_name}")
            print(f"예시 구조체: {struct_name}")
            print(f"예시 필드: {field_path}")
            print(f"타입: {field_type}")
            print(f"헤더 파일/compile.json에서 발견한 값: {discovered_size} (자동 사용)")
            macro_sizes[macro_name] = discovered_size
            # 캐시에도 저장
            if 'macro_sizes' not in cache:
                cache['macro_sizes'] = {}
            cache['macro_sizes'][macro_name] = discovered_size
            continue
        
        # 3. 사용자 입력 요청
        print(f"\n[{current_count}/{total_count}] 매크로: {macro_name}")
        print(f"예시 구조체: {struct_name}")
        print(f"예시 필드: {field_path}")
        print(f"타입: {field_type}")
        print(f"스킵하려면 'skip'을 입력하세요.")
        
        while True:
            try:
                size_input = input(f"{macro_name}의 배열 크기를 입력하세요 (또는 'skip'): ").strip()
                if not size_input:
                    print("값을 입력해주세요.")
                    continue
                
                if size_input.lower() == 'skip':
                    print(f"  ⏭ '{macro_name}' 매크로를 스킵합니다.")
                    break
                
                array_size = int(size_input)
                if array_size < 0:
                    print("0 이상의 값을 입력해주세요.")
                    continue
                macro_sizes[macro_name] = array_size
                
                # 캐시에 저장
                if 'macro_sizes' not in cache:
                    cache['macro_sizes'] = {}
                cache['macro_sizes'][macro_name] = array_size
                
                break
            except ValueError:
                print("올바른 숫자를 입력해주세요.")
            except KeyboardInterrupt:
                print("\n취소되었습니다.")
                sys.exit(1)
    
    return macro_sizes

