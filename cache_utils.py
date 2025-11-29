"""캐시 관련 유틸리티 함수"""

import json
from pathlib import Path
from typing import Dict


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

