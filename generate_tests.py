#!/usr/bin/env python3
"""
헤더 파일에서 구조체를 파싱하여 endian converter 테스트 코드를 생성하는 스크립트
"""

import sys
from pathlib import Path
from parser import parse_header_file
from cache_utils import load_cache, save_cache
from struct_resolver import find_missing_structs, get_header_path_for_struct
from macro_utils import (
    discover_all_macros, collect_macro_arrays, get_macro_array_sizes,
    find_compile_commands
)
from code_generator import generate_test_code


def resolve_missing_structs(structs, structs_dict, base_path, cache, cache_path):
    """누락된 구조체를 해결하는 함수"""
    excluded_structs = cache.get('excluded_structs', [])
    if excluded_structs:
        print(f"\n제외된 구조체: {', '.join(excluded_structs)}")
    
    discovered_macros = discover_all_macros(base_path, base_path / "dummy.h", cache)
    
    while True:
        missing_structs = find_missing_structs(structs, structs_dict, discovered_macros, excluded_structs)
        if not missing_structs:
            break
        
        print(f"\n=== 누락된 구조체 발견 ===")
        for missing_struct in missing_structs:
            header_path_for_struct, added_structs = get_header_path_for_struct(
                missing_struct, base_path, cache, structs_dict)
            save_cache(cache_path, cache)
            
            if header_path_for_struct:
                for add_struct in added_structs:
                    if add_struct['name'] not in [s['name'] for s in structs]:
                        structs.append(add_struct)
            else:
                print(f"  ✗ '{missing_struct}' 구조체를 제외합니다.")
                structs_dict[missing_struct] = []
                if 'excluded_structs' not in cache:
                    cache['excluded_structs'] = []
                if missing_struct not in cache['excluded_structs']:
                    cache['excluded_structs'].append(missing_struct)
                save_cache(cache_path, cache)


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 generate_tests.py <헤더파일> [출력파일]")
        print("예: python3 generate_tests.py external_struct.h ut_external_struct.cc")
        sys.exit(1)
    
    header_path = Path(sys.argv[1])
    if not header_path.exists():
        print(f"오류: 파일을 찾을 수 없습니다: {header_path}")
        sys.exit(1)
    
    # 캐시 파일 경로 설정
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
    
    # 누락된 구조체 해결
    resolve_missing_structs(structs, structs_dict, base_path, cache, cache_path)
    
    # 매크로 배열 수집
    macro_arrays = collect_macro_arrays(structs, structs_dict)
    
    # 매크로 수집
    discovered_macros = discover_all_macros(base_path, header_path, cache)
    
    # 매크로 배열 크기 입력 받기
    macro_sizes = get_macro_array_sizes(macro_arrays, cache, discovered_macros)
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
