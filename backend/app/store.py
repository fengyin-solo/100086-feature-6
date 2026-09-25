"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

vessel 等模块的修改会通过 persist 落盘到 data 目录，进程重启后优先读快照，
真实项目里这里会换成数据库访问层。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}
        for name, seed_rows in SEED_ROWS.items():
            snapshot = self._load_snapshot(name)
            self._tables[name] = snapshot if snapshot is not None else [dict(row) for row in seed_rows]
        self._lock = threading.Lock()

    def _load_snapshot(self, module: str) -> list[dict[str, Any]] | None:
        path = DATA_DIR / f"{module}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, list) else None

    def persist(self, module: str) -> None:
        """把某个模块的当前数据原子写入快照文件，避免写到一半进程退出留下坏文件。"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = DATA_DIR / f"{module}.json"
        tmp_path = path.with_suffix(".json.tmp")
        with self._lock:
            tmp_path.write_text(
                json.dumps(self._tables[module], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_path.replace(path)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

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
