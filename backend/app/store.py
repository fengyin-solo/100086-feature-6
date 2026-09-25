"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
其中 PERSIST_MODULES 里的模块（目前是船舶档案）会把改动落盘到 backend/data/ 下的
JSON 文件，刷新页面、重启服务后读到的仍是改过的那份；改动留档（audit）也一起落盘。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PERSIST_MODULES = {"vessel"}


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}
        for name, rows in SEED_ROWS.items():
            persisted = self._load_json(self._rows_path(name)) if name in PERSIST_MODULES else None
            self._tables[name] = (
                persisted if isinstance(persisted, list) and persisted else [dict(row) for row in rows]
            )
        self._audit: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for name in PERSIST_MODULES:
            persisted = self._load_json(self._audit_path(name))
            self._audit[name] = persisted if isinstance(persisted, dict) else {}

    @staticmethod
    def _rows_path(module: str) -> Path:
        return DATA_DIR / f"{module}.json"

    @staticmethod
    def _audit_path(module: str) -> Path:
        return DATA_DIR / f"{module}_audit.json"

    @staticmethod
    def _load_json(path: Path) -> Any:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def save(self, module: str) -> None:
        """把指定模块的当前数据落盘；不在 PERSIST_MODULES 里的模块仍是纯内存。"""
        if module not in PERSIST_MODULES:
            return
        self._write_json(self._rows_path(module), self.rows(module))

    def audit_trail(self, module: str, entry_id: int) -> list[dict[str, Any]]:
        """取某条记录的改动留档列表（按时间先后排列），返回的是可直接修改的引用。"""
        return self._audit.setdefault(module, {}).setdefault(str(entry_id), [])

    def save_audit(self, module: str) -> None:
        """把指定模块的改动留档落盘。"""
        if module not in PERSIST_MODULES:
            return
        self._write_json(self._audit_path(module), self._audit.get(module, {}))

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
