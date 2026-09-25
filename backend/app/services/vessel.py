"""船舶档案业务规则：状态流转、字段校验、档案修改留档与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "vessel"
REQUIRED_FIELDS = ["船舶编号", "船舶名称", "船舶类型"]
# 档案详情里允许修改的字段；船舶编号是主键、船舶状态只能走状态动作，都不在编辑范围
EDITABLE_FIELDS = ["船舶名称", "船舶类型", "船籍", "载重吨位", "船长", "船宽", "所属船公司"]
STATUS_ORDER = ["待登记", "在册可用", "在港作业", "已停用"]
ACTION_RULES = {"登记船舶": "在册可用", "标记在港": "在港作业", "停用船舶": "已停用"}
NEGATIVE_ACTIONS = ["停用船舶"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    records = entry.setdefault("history", [])
    return records


class VesselService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        vessel_type: str | None = None,
        registry: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("船舶编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if vessel_type:
            rows = [row for row in rows if vessel_type in str(row.get("船舶类型", ""))]
        if registry:
            rows = [row for row in rows if registry in str(row.get("船籍", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["船籍"] = str(values.get("船籍") or "").strip() or "中国"
        entry["status"] = STATUS_ORDER[0]
        entry["船舶状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["history"] = []
        rows.append(entry)
        store.persist(MODULE)
        return entry, []

    def update_entry(
        self,
        entry_id: int,
        values: dict[str, Any],
        operator: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str]:
        """修改档案字段并留档。

        返回 (档案, 提示, code)，code 取值：
        - updated：本次确有字段变更，已新增一条变更记录；
        - refreshed：连续两次提交的改动完全相同，只刷新最近一条记录的时间，不再追加；
        - unchanged：提交内容与当前档案一致且没有可合并的最近记录，什么都没改。
        """
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"船舶 {entry_id} 不存在或已归档", "not_found"

        changes: list[dict[str, str]] = []
        for field in EDITABLE_FIELDS:
            if field not in values:
                continue
            new_value = str(values.get(field) or "").strip()
            old_value = str(entry.get(field) or "").strip()
            if new_value != old_value:
                changes.append({"field": field, "old": old_value, "new": new_value})

        if not changes:
            history = _history(entry)
            if history:
                # 连着提交两次相同改动：只保留最近一条，把时间更新为本次提交时间
                # 操作人保留第一条的提交者，留档体现的是“那次改动”而非本次重复点击
                history[-1]["time"] = _now()
                store.persist(MODULE)
                return entry, "提交内容与上次改动相同，已更新最近一条变更记录的时间", "refreshed"
            return entry, "档案没有发生改动，无需留档", "unchanged"

        changed_fields = [item["field"] for item in changes]
        for item in changes:
            entry[item["field"]] = item["new"]

        history = _history(entry)
        history.append({
            "time": _now(),
            "operator": operator or "值班管理员",
            "changes": changes,
        })
        store.persist(MODULE)
        return entry, f"船舶档案已更新，本次修改：{'、'.join(changed_fields)}", "updated"

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
        # 列表展示的“船舶状态”列与真实状态保持同源，避免两处显示对不上
        entry["船舶状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        store.persist(MODULE)
        return entry, f"船舶已{action}"
