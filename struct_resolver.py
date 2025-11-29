"""구조체 해결 관련 함수"""

import re
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from parser import parse_header_file
from utils import is_likely_macro_name, is_macro_array
from constants import TYPE_SIZES


def find_missing_structs(structs: List[Dict], 
                         structs_dict: Dict[str, List], 
                         discovered_macros: Dict[str, int] = None, 
                         excluded_structs: List[str] = None) -> List[str]:
    """구조체 필드에서 참조되지만 정의되지 않은 구조체 찾기"""
    if discovered_macros is None:
        discovered_macros = {}
    if excluded_structs is None:
        excluded_structs = []
    
    missing = set()
    checked = set()  # 이미 확인한 구조체 타입 (순환 참조 방지)
    
    def check_fields(fields: List):
        for field_type, field_name, size in fields:
            # 배열 제거
            base_type = re.sub(r'\[.*?\]', '', field_type).strip()
            
            # 이미 확인한 타입은 스킵
            if base_type in checked:
                continue
            checked.add(base_type)
            
            # 제외된 구조체는 스킵
            if base_type in excluded_structs:
                continue
            
            # 매크로 이름인지 확인
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


def get_header_path_for_struct(missing_struct: str, base_path: Path, 
                               cache: Dict, structs_dict: Dict) -> Tuple[Optional[Path], List[Dict]]:
    """사용자로부터 구조체가 정의된 헤더 파일 경로 입력 받기"""
    # 캐시에서 확인
    if 'struct_header_paths' in cache and missing_struct in cache['struct_header_paths']:
        cached_path_str = cache['struct_header_paths'][missing_struct]
        cached_path = Path(cached_path_str).resolve()
        if cached_path.exists():
            print(f"\n구조체 '{missing_struct}'의 헤더 파일 경로를 캐시에서 찾았습니다: {cached_path}")
            structs = parse_header_file(cached_path)
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
                    added_structs.append(struct)
            
            if found_in_cache:
                return cached_path, added_structs
            else:
                print(f"경고: 캐시된 경로 '{cached_path}'에서 '{missing_struct}' 구조체를 찾을 수 없습니다.")
    
    print(f"\n구조체 '{missing_struct}'를 찾을 수 없습니다.")
    print(f"이 구조체가 정의된 헤더 파일의 경로를 입력해주세요.")
    print(f"(현재 디렉토리 기준: {base_path.absolute()})")
    print(f"스킵하려면 'skip'을 입력하세요.")
    
    while True:
        try:
            header_input = input("헤더 파일 경로 (또는 'skip'): ").strip()
            if not header_input:
                print("경로를 입력해주세요.")
                continue
            
            if header_input.lower() == 'skip':
                return None, []
            
            # 경로 처리
            if header_input.startswith('./') or (not header_input.startswith('/') and '/' in header_input):
                header_path = base_path / header_input
            elif not header_input.startswith('/'):
                header_path = base_path / header_input
            else:
                header_path = Path(header_input)
            
            header_path = header_path.resolve()
            
            if not header_path.exists():
                print(f"파일을 찾을 수 없습니다: {header_path}")
                retry = input("다시 입력하시겠습니까? (y/n/skip): ").strip().lower()
                if retry == 'skip' or retry != 'y':
                    return None, []
                continue
            
            if header_path.suffix not in ['.h', '.hpp']:
                print(f"헤더 파일이 아닙니다: {header_path}")
                retry = input("다시 입력하시겠습니까? (y/n/skip): ").strip().lower()
                if retry == 'skip' or retry != 'y':
                    return None, []
                continue
            
            # 헤더 파일에서 모든 구조체 파싱
            structs = parse_header_file(header_path)
            struct_names = [s['name'] for s in structs]
            
            found_missing = False
            added_structs = []
            for struct in structs:
                if struct['name'] == missing_struct:
                    found_missing = True
                
                if struct['name'] not in structs_dict:
                    structs_dict[struct['name']] = struct['fields']
                    added_structs.append(struct)
                    print(f"  ✓ '{struct['name']}' 구조체 추가됨")
                else:
                    added_structs.append(struct)
            
            if not found_missing:
                print(f"경고: '{header_path}'에서 '{missing_struct}' 구조체를 찾을 수 없습니다.")
                print(f"발견된 구조체: {', '.join(struct_names) if struct_names else '없음'}")
                print("옵션:")
                print("  y: 다시 입력")
                print("  n: 이 구조체 제외 (건너뛰기)")
                retry = input("선택하세요 (y/n, 기본값: y): ").strip().lower()
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

