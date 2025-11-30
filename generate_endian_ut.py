#!/usr/bin/env python3
"""
헤더 파일에서 구조체를 파싱하여 endian converter 테스트 코드를 생성하는 스크립트
"""

import sys, re
import itertools
from typing import Dict
from pathlib import Path

macros: Dict[str, int] = {}


def parse_macros_from_header(header_path: Path) -> Dict[str, int]:
    """헤더 파일에서 #define 매크로 정의 파싱
    - #define FOO 123
    - #define FOO (123)
    - #define FOO ((123))
    처럼 숫자에 괄호만 감싸진 경우까지 지원
    """
    try:
        with open(header_path, "r", encoding="utf-8") as f:
            content = f.read()

        # #define NAME VALUE
        # VALUE 부분은 숫자와 괄호만으로 이루어진 토큰을 허용
        # ex) 123, (123), ((123))
        pattern = r"#define\s+(\w+)\s+([()\d]+)"
        matches = re.findall(pattern, content)

        for macro_name, macro_value in matches:
            # 괄호 제거
            cleaned = re.sub(r"[()]", "", macro_value).strip()

            # 괄호 제거 후가 순수 숫자인 경우만 처리
            if cleaned.isdigit():
                try:
                    macros[macro_name] = int(cleaned)
                except ValueError:
                    # 이론상 여긴 거의 안 들어오지만 안전용
                    pass
            else:
                # 숫자가 아닌 경우 사용자에게 입력 받기
                while True:
                    user_input = input(
                        f"매크로 '{macro_name}'의 값 '{macro_value}'는 숫자가 아닙니다.\n"
                        f"이 매크로에 사용할 정수 값을 입력하세요 (건너뛰려면 그냥 Enter): "
                    ).strip()

                    # 그냥 Enter 치면 스킵
                    if user_input == "":
                        print(f"매크로 '{macro_name}'는 스킵합니다.")
                        break
                    try:
                        # int(..., 0) 은 10진수/16진수(0x..)/8진수(0o..) 등 자동 처리
                        value = int(user_input, 0)
                        macros[macro_name] = value
                        print(f"매크로 '{macro_name}' = {value} 로 설정했습니다.")
                        break
                    except ValueError:
                        print("유효한 정수를 입력해주세요. 예: 123, 0x10, 077 등")

            # 숫자 + 연산자 같은 건 (1+2) 이런 건 스킵
    except (IOError, UnicodeDecodeError):
        pass

    return macros


def collect_struct_blocks(content: str):
    """헤더 전체에서 typedef struct 블록 텍스트만 추출"""
    blocks: List[str] = []
    pattern = r"typedef\s+struct\s*(?:\w+)?\s*\{"

    for match in re.finditer(pattern, content):
        brace_count = 0
        pos = match.end() - 1  # { 위치

        while pos < len(content):
            if content[pos] == "{":
                brace_count += 1
            elif content[pos] == "}":
                brace_count -= 1
                if brace_count == 0:
                    struct_end = pos + 1
                    # 세미콜론까지 포함
                    while struct_end < len(content) and content[struct_end] != ";":
                        struct_end += 1
                    if struct_end < len(content):
                        struct_end += 1

                    struct_block = content[match.start() : struct_end]
                    blocks.append(struct_block)
                    break
            pos += 1
    return blocks


def remove_comments(text: str) -> str:
    """C 주석 제거"""
    # 여러 줄 주석 제거
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # 한 줄 주석 제거
    text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
    return text


def parse_c_array_decl(line: str):
    """
    C 스타일 변수 선언 한 줄을 파싱해서
    - 타입명
    - 변수명
    - 배열 여부
    - 배열 차수
    - 각 차수별 크기
    로 분리해서 반환.

    지원 예:
        uint8_t data[10];
        uint8_t matrix[10][20];
        uint8_t buf [MAX_SIZE][COUNT];
        uint8_t value;   // 배열 아님
    """
    # 앞뒤 공백 + 끝 세미콜론 제거
    line = line.strip()
    if not line:
        return None

    # 세미콜론 제거
    if line.endswith(";"):
        line = line[:-1].strip()

    # 한 줄 안의 주석 제거
    line = re.sub(r"//.*$", "", line)
    line = re.sub(r"/\*.*?\*/", "", line)
    line = line.strip()
    if not line:
        return None

    # 정규식으로 "타입, 이름, 배열부분" 분리
    #  - type_part: uint8_t, unsigned int 등
    #  - var_name: data, matrix, buf 등
    #  - array_part: [10][20], [MAX_SIZE][COUNT] 등 전체
    pattern = r"""
        ^\s*
        (?P<type>[\w\s]+?)      # 타입 (공백 포함, lazy)
        \s+
        (?P<name>\w+)           # 변수명
        \s*
        (?P<arrays>(\[[^\]]*\]\s*)*)  # 0개 이상 배열 부분
        $
    """
    m = re.match(pattern, line, re.VERBOSE)
    if not m:
        # 매칭 실패 → 우리가 처리하지 않는 형식
        return None

    type_part = m.group("type").strip()
    var_name = m.group("name").strip()
    arrays_str = m.group("arrays") or ""

    # 배열 차원 추출: [10][20] → ["10", "20"]
    raw_dims = re.findall(r"\[([^\]]*)\]", arrays_str)

    def _process_dim_value(dim: str) -> None:
        """
        dim이 숫자면 패스.
        dim이 매크로면 macros 딕셔너리에 없을 때 사용자에게 값을 입력받아 추가.
        dims 리스트 자체는 문자열 그대로 유지.
        """
        dim = dim.strip()

        # 1) dim 이 숫자면 끝
        if dim.isdigit():
            return

        # 2) 이미 macros 에 있으면 끝
        if dim in macros:
            return

        # 3) 숫자도 아니고, macros 에도 없으면 사용자에게 물어봄
        while True:
            user_input = input(
                f"배열 크기 매크로 '{dim}'의 값을 찾을 수 없습니다.\n"
                f"정수 값을 입력하세요 (건너뛰면 0으로 처리): "
            ).strip()

            if user_input == "":
                print(f"[경고] '{dim}' 는 0으로 처리됩니다.")
                macros[dim] = 0
                return

            try:
                value = int(user_input, 0)  # 10진/16진 자동 처리
                macros[dim] = value
                print(f"매크로 '{dim}' = {value} 로 설정했습니다.")
                return
            except ValueError:
                print("유효한 정수 값을 입력하세요. 예: 10, 0x20")

    # dims 처리
    dims = []
    for d in raw_dims:
        dim = d.strip()
        _process_dim_value(dim)  # ★ 여기서 사용자 입력 처리
        dims.append(dim)

    is_array = len(dims) > 0
    dim_count = len(dims)

    result = {
        "type": type_part,
        "name": var_name,
        "is_array": is_array,
        "dim_count": dim_count,
        "dims": [d.strip() for d in dims],  # 공백 제거
    }
    return result


def parse_struct_block_basic(
    struct_block: str,
):
    """당신이 가진 parse_struct_block에서 'union 제외, 이름 찾기, body 분리' 정도만 하는 버전"""
    clean_block = remove_comments(struct_block)

    # union인지 확인 (union은 제외)
    if re.search(r"typedef\s+union\s", clean_block):
        return None, []

    # 구조체 이름 추출: } 다음에 오는 이름
    after_brace = re.search(r"\}(.*?);", clean_block, re.DOTALL)
    if not after_brace:
        return None, []

    name_part = after_brace.group(1).strip()

    # attribute 제거
    name_part = re.sub(r"__attribute__\([^)]+\)", "", name_part)
    name_part = re.sub(r"PACKED_STRUCT", "", name_part)
    name_part = re.sub(r"ALIGNED_STRUCT\([^)]+\)", "", name_part)

    # 남은 단어 중 마지막이 구조체 이름
    words = [w for w in name_part.split() if w]
    if not words:
        return None, []

    struct_name = words[-1]

    # 구조체 본문 추출 ({ ... } 사이)
    body_match = re.search(r"\{([^}]+)\}", clean_block, re.DOTALL)
    if not body_match:
        return struct_name, []

    body = body_match.group(1)

    fields = []
    # 각 줄 파싱
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue

        field = parse_c_array_decl(line)
        if field:
            fields.append(field)

    d = {"struct": struct_name, "name": name_part, "fields": fields}
    return d


def parse_struct_from_header(header_path: Path) -> list:
    with open(header_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1단계: 블록 텍스트만 모두 수집
    blocks = collect_struct_blocks(content)

    list = []
    for block in blocks:
        list.append(parse_struct_block_basic(block))

    return list


def get_struct_id_macro(struct_name: str) -> str:
    """구조체 ID 매크로 이름 생성"""
    struct_name = struct_name.strip()
    if struct_name.endswith("_type"):
        return struct_name[:-5] + "_id"
    return struct_name + "_id"


# 타입별 바이트 크기 매핑
TYPE_SIZES = {
    "uint8_t": 1,
    "int8_t": 1,
    "char": 1,
    "int16_t": 2,
    "uint16_t": 2,
    "short": 2,
    "int": 4,
    "unsigned int": 4,
    "uint32_t": 4,
    "int32_t": 4,
    "uint64_t": 8,
    "int64_t": 8,
    "float": 4,
    "double": 8,
}

# 바이트 패턴 (Big/Little endian 생성용)
BYTE_PATTERN = [0xA1, 0xB2, 0xC3, 0xD4]


def _generate_bytes_list(base_type: str, size: int, is_big_endian: bool) -> list[str]:
    """바이트 리스트 생성 (endian에 따라 순서 결정)"""
    bytes_list = []
    if is_big_endian:
        # Big endian: 정순
        for i in range(size):
            if base_type in ["uint8_t", "int8_t", "char"]:
                bytes_list.append(f"0x{BYTE_PATTERN[0]:02X}")
            else:
                bytes_list.append(f"0x{BYTE_PATTERN[i % TYPE_SIZES[base_type]]:02X}")
    else:
        # Little endian: 역순
        for i in range(size - 1, -1, -1):
            if base_type in ["uint8_t", "int8_t", "char"]:
                bytes_list.append(f"0x{BYTE_PATTERN[0]:02X}")
            else:
                bytes_list.append(f"0x{BYTE_PATTERN[i % TYPE_SIZES[base_type]]:02X}")
    return bytes_list


def append_bytes_with_wrap(
    lines: list[str],
    bytes_list: list[str],
    comment: str,
    indent: str = "        ",
    max_per_line: int = 16,
) -> None:
    """bytes_list를 최대 max_per_line개씩 끊어서 여러 줄로 추가"""
    for idx in range(0, len(bytes_list), max_per_line):
        chunk = bytes_list[idx : idx + max_per_line]
        chunk_str = ", ".join(chunk)

        # 첫 줄에만 주석 출력
        if idx == 0 and comment:
            lines.append(f"{indent}{chunk_str}, {comment}")
        else:
            lines.append(f"{indent}{chunk_str},")


def _generate_endian_bytes(
    msg_id: str,
    structs: list,
    struct: list,
    is_big_endian: bool,
) -> str:
    endian_prefix = "big_endian" if is_big_endian else "little_endian"
    lines = []
    lines.append(f"    uint8_t {endian_prefix}_raw_{msg_id}[] = ")
    lines.append("    {")

    def _generate_endian_bytes_sub(
        msg_id: str,
        structs: list,
        struct: list,
        is_big_endian: bool,
    ) -> str:
        for field in struct["fields"]:
            if field["type"] not in TYPE_SIZES:
                for s in structs:
                    if s["struct"] == field["type"]:
                        for idx_tuple in itertools.product(*(range(int(size)) for size in field["dims"])):
                            idx_str = "".join(f"[{i}]" for i in idx_tuple)
                            lines.append(f"        // Start: {field['type']} {field['name']}{idx_str}")
                            _generate_endian_bytes_sub(msg_id, structs, s, is_big_endian)
                            lines.append(f"        // End: {field['type']} {field['name']}{idx_str}")
                            
            else:
                # 일반 필드: 바이트 리스트 생성
                size = TYPE_SIZES[field["type"]]
                arr_size_str = ""
                for i in range(field["dim_count"]):
                    if field["dims"][i] in macros:
                        arr_size_str += "[" + str(macros[field["dims"][i]]) + "]"
                        size *= int(macros[field["dims"][i]])
                    else:
                        arr_size_str += "[" + field["dims"][i] + "]"
                        size *= int(field["dims"][i])

                bytes_list = _generate_bytes_list(field["type"], size, is_big_endian)
                comment = f"//{field["type"]} {field["name"]}{arr_size_str};"
                append_bytes_with_wrap(lines, bytes_list, comment)

    _generate_endian_bytes_sub(
        msg_id,
        structs,
        struct,
        is_big_endian,
    )

    lines.append("    };")
    return "\n".join(lines)


def generate_big_endian_bytes(msg_id: str, structs: list, struct: list) -> str:
    """Big endian 바이트 배열 생성"""
    return _generate_endian_bytes(msg_id, structs, struct, True)


def generate_little_endian_bytes(
    msg_id: str,
    structs: list,
    struct: list,
) -> str:
    """Little endian 바이트 배열 생성"""
    return _generate_endian_bytes(msg_id, structs, struct, False)


def generate_test_code(
    structs: list,
    header_name: str,
) -> str:
    """테스트 코드 생성"""
    lines = []
    include_name = header_name

    lines.append("#include <gtest/gtest.h>")
    lines.append("")
    lines.append('extern "C" {')
    lines.append(f'#include "{include_name}"')
    lines.append("}")
    lines.append("")

    structs_dict = {struct["name"]: struct["fields"] for struct in structs}
    print(structs_dict)
    for struct in structs:
        struct_name = struct["name"]
        fields = struct["fields"]

        if not fields:
            continue

        test_class = "TestCaseName"
        msg_id = get_struct_id_macro(struct_name)
        test_name = f"{msg_id}_endian_converter"

        lines.append(f"TEST({test_class}, {test_name})")
        lines.append("{")

        # Big endian 바이트 배열
        big_endian = generate_big_endian_bytes(msg_id, structs, struct)
        lines.append(big_endian)
        lines.append("")

        # Little endian 바이트 배열
        little_endian = generate_little_endian_bytes(msg_id, structs, struct)
        lines.append(little_endian)
        lines.append("")

        # 배열 크기 검증
        lines.append(f"    EXPECT_EQ(sizeof(big_endian_raw_{msg_id}),")
        lines.append(f"              sizeof({struct_name}));")
        lines.append(f"    EXPECT_EQ(sizeof(little_endian_raw_{msg_id}),")
        lines.append(f"              sizeof({struct_name}));")
        lines.append("")

        # 포인터 선언 및 필드 설정
        lines.append(
            f"    messageHdr_type *pBigEndianMsgHdr = (messageHdr_type *)big_endian_raw_{msg_id};"
        )
        lines.append(
            f"    messageHdr_type *pLittleEndianMsgHdr = (messageHdr_type *)little_endian_raw_{msg_id};"
        )
        lines.append(f"    pBigEndianMsgHdr->msgType = htons({msg_id});")
        lines.append(f"    pLittleEndianMsgHdr->msgType = ({msg_id});")
        lines.append("")

        # EndianConvertFunc 호출
        lines.append(
            f"    EndianConvertFunc(big_endian_raw_{msg_id}, sizeof({struct_name}));"
        )
        lines.append("")

        # memcmp 검증
        lines.append(f"    EXPECT_EQ(0, memcmp(big_endian_raw_{msg_id},")
        lines.append(f"                        little_endian_raw_{msg_id},")
        lines.append(f"                        sizeof(little_endian_raw_{msg_id})));")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 generate_endian_ut.py <헤더파일> [출력파일]")
        print(
            "예: python3 generate_endian_ut.py external_struct.h ut_external_struct.cc"
        )
        sys.exit(1)

    header_path = Path(sys.argv[1])
    if not header_path.exists():
        print(f"오류: 파일을 찾을 수 없습니다: {header_path}")
        sys.exit(1)

    # 매크로 파싱
    print(f"매크로 파싱 중: {header_path}")
    macros = parse_macros_from_header(header_path)
    if not macros:
        print("경고: 매크로를 찾을 수 없습니다.")
        sys.exit(1)
    print(f"발견된 매크로: {len(macros)}개")
    for macro_name, macro_value in macros.items():
        print(f"  - {macro_name}: {macro_value}")

    # 구조체 파싱
    print(f"헤더 파일 파싱 중: {header_path}")
    structs = parse_struct_from_header(header_path)
    if not structs:
        print("경고: 구조체를 찾을 수 없습니다.")
        sys.exit(1)
    print(f"발견된 구조체: {len(structs)}개")
    for struct in structs:
        print(f"  - {struct['name']} ({len(struct['fields'])}개 필드)")
        for field in struct["fields"]:
            print(f"      * {field}")

    # 테스트 코드 생성
    header_name = header_path.name
    test_code = generate_test_code(structs, header_name)

    # 출력
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(test_code)
        print(f"\n테스트 코드가 생성되었습니다: {output_path}")

    else:
        print("\n=== 생성된 테스트 코드 ===")
        print(test_code)


if __name__ == "__main__":
    print("Generating endian converter unit tests...")
    main()
