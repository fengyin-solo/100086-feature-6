"""船舶档案接口：维护船舶，覆盖登记船舶、标记在港、停用船舶等动作，以及船舶类型、船籍的改动留档。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.vessel import VesselService

router = APIRouter(prefix="/api/vessel", tags=["船舶档案"])

service = VesselService()

LIST_FIELDS = ["船舶编号", "船舶名称", "船舶类型", "船籍", "载重吨位", "船长", "船宽", "所属船公司", "船舶状态"]
STATUSES = ["待登记", "在册可用", "在港作业", "已停用"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按船舶编号检索"),
    name: str | None = Query(default=None, description="按船舶名称检索"),
    vessel_type: str | None = Query(default=None, description="按船舶类型检索"),
    status: str | None = Query(default=None, description="待登记、在册可用、在港作业、已停用"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按船舶编号、名称、类型与状态过滤船舶档案列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, name=name, vessel_type=vessel_type, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出船舶档案清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "vessel", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条船舶明细与改动留档；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"船舶 {entry_id} 不存在或已归档")
    return {"entry": entry, "history": service.get_history(entry_id)}


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条船舶，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="船舶已登记", entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """保存船舶类型、船籍的改动并留档；连着提交相同改动时只刷新上一条留档时间。"""
    entry, _record, message, ok = service.update_entry(
        entry_id,
        payload.values,
        operator=payload.operator or "值班管理员",
        remark=payload.remark,
    )
    if entry is None:
        raise HTTPException(status_code=404, detail=message)
    return ActionResult(ok=ok, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条船舶执行登记船舶、标记在港、停用船舶；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
