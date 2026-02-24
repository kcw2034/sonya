"""
pytest 루트 conftest
- pip install -e . 없이도 sonya_core 패키지를 import할 수 있도록 sys.path 설정
"""

import sys
from pathlib import Path

_src = Path(__file__).parent / "src"
_core = _src / "sonya-core"

if str(_core) not in sys.path:
    sys.path.insert(0, str(_core))

# sonya-core 디렉토리를 sonya_core로 import 가능하게 매핑
import importlib
if "sonya_core" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "sonya_core",
        _core / "__init__.py",
        submodule_search_locations=[str(_core)],
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules["sonya_core"] = module
        spec.loader.exec_module(module)
