"""
pytest 루트 conftest
- packages/*/src 디렉토리를 sys.path에 추가하여 sonya 패키지를 import 가능하게 설정
"""
import sys
from pathlib import Path

_packages = Path(__file__).parent / "packages"

for pkg_dir in sorted(_packages.iterdir()):
    src = pkg_dir / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
