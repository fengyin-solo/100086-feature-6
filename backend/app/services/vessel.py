"""船舶档案业务规则：状态流转、字段校验、改动留档与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "vessel"
REQUIRED_FIELDS = ["船舶编号", "船舶名称", "船舶类型"]
EDITABLE_FIELDS = ["船舶类型", "船籍"]
STATUS_ORDER = ["待登记", "在册可用", "在港作业", "已停用"]
ACTION_RULES = {"登记船舶": "在册可用", "标记在港": "在港作业", "停用船舶": "已停用"}
NEGATIVE_ACTIONS = ["停用船舶"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class VesselService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        vessel_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("船舶编号", ""))]
        if name:
            rows = [row for row in rows if name in str(row.get("船舶名称", ""))]
        if vessel_type:
            rows = [row for row in rows if vessel_type in str(row.get("船舶类型", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def get_history(self, entry_id: int) -> list[dict[str, Any]]:
        """改动留档按最新在前返回，详情页直接照着渲染。"""
        return list(reversed(store.audit_trail(MODULE, entry_id)))

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        store.save(MODULE)
        return entry, []

    def update_entry(
        self,
        entry_id: int,
        values: dict[str, Any],
        *,
        operator: str,
        remark: str | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str, bool]:
        """保存船舶类型、船籍的改动并留档。

        返回 (entry, record, message, ok)：record 是本次写入或刷新的留档记录。
        连着提交相同改动时不新增记录，只把上一条留档时间刷新成最新，提示已更新。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, None, f"船舶 {entry_id} 不存在或已归档", False
        provided = [field for field in EDITABLE_FIELDS if field in values]
        if not provided:
            return entry, None, f"没有提交可保存的字段（支持：{'、'.join(EDITABLE_FIELDS)}）", False
        empty = [field for field in provided if not str(values.get(field) or "").strip()]
        if empty:
            return entry, None, f"{'、'.join(empty)}不能为空", False

        changes = []
        for field in provided:
            old = str(entry.get(field) or "").strip()
            new = str(values.get(field) or "").strip()
            if new != old:
                changes.append({"字段": field, "旧值": old, "新值": new})

        history = store.audit_trail(MODULE, entry_id)
        if not changes:
            if history:
                latest = history[-1]
                latest["时间"] = _now()
                latest["操作人"] = operator
                store.save_audit(MODULE)
                return entry, latest, "与上次改动相同，已更新留档时间", True
            return entry, None, "没有检测到需要保存的改动", True

        for change in changes:
            entry[change["字段"]] = change["新值"]
        record = {
            "id": (int(history[-1].get("id", 0)) + 1) if history else 1,
            "时间": _now(),
            "操作人": operator,
            "改动": changes,
            "备注": str(remark or "").strip(),
        }
        history.append(record)
        store.save(MODULE)
        store.save_audit(MODULE)
        return entry, record, "船舶档案已保存，改动已留档", True

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"船舶 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于船舶档案可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        store.save(MODULE)
        return entry, f"船舶已{action}"
