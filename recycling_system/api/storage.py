import threading
import uuid
from datetime import datetime, timedelta
from copy import deepcopy

from django.conf import settings

_lock = threading.RLock()

USERS = {}
TOKENS = {}
POINTS = {}
INSPECTIONS = []
CLEANING_REQUESTS = {}
ALERTS = []
TASKS = {}

_user_id_counter = 0
_point_id_counter = 0
_inspection_id_counter = 0
_request_id_counter = 0
_alert_id_counter = 0
_task_id_counter = 0


def _next_id(prefix, counter_name):
    globals()[counter_name] += 1
    return f"{prefix}{globals()[counter_name]}"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def seed_data():
    with _lock:
        if USERS:
            return
        for u in [
            {"username": "admin", "password": "admin123", "role": "admin", "name": "系统管理员", "areas": []},
            {"username": "staff1", "password": "staff123", "role": "field_staff", "name": "张现场", "areas": ["A区", "B区"]},
            {"username": "staff2", "password": "staff123", "role": "field_staff", "name": "李巡查", "areas": ["B区", "C区"]},
            {"username": "observer1", "password": "obs123", "role": "observer", "name": "王观察", "areas": []},
        ]:
            uid = _next_id("u", "_user_id_counter")
            USERS[uid] = {**u, "id": uid}

        for p in [
            {"name": "A区1号回收点", "area": "A区", "capacity": 200, "location": "A区入口左侧", "responsible_person": "u2", "confirm_person": "u1"},
            {"name": "A区2号回收点", "area": "A区", "capacity": 150, "location": "A区食堂旁", "responsible_person": "u2", "confirm_person": "u1"},
            {"name": "B区1号回收点", "area": "B区", "capacity": 200, "location": "B区主通道", "responsible_person": "u2", "confirm_person": "u1"},
            {"name": "B区2号回收点", "area": "B区", "capacity": 180, "location": "B区休息区", "responsible_person": "u3", "confirm_person": "u1"},
            {"name": "C区1号回收点", "area": "C区", "capacity": 160, "location": "C区出口", "responsible_person": "u3", "confirm_person": "u1"},
        ]:
            pid = _next_id("p", "_point_id_counter")
            POINTS[pid] = {
                **p, "id": pid, "current_capacity": 0, "current_capacity_pct": 0,
                "status": "normal", "created_at": _now(), "updated_at": _now(),
            }


STATUS_CHOICES = [
    ("normal", "正常"),
    ("near_full", "接近满载"),
    ("request_cleaning", "申请清运"),
    ("cleaning_in_progress", "清运中"),
    ("pending_confirmation", "待确认"),
    ("confirmed", "已确认"),
    ("temporarily_disabled", "暂时停用"),
]

ROLE_CHOICES = [
    ("admin", "管理员"),
    ("field_staff", "现场人员"),
    ("observer", "观察员"),
]


def authenticate(username, password):
    with _lock:
        for uid, user in USERS.items():
            if user["username"] == username and user["password"] == password:
                token = uuid.uuid4().hex
                TOKENS[token] = uid
                return token, uid, user
        return None, None, None


def get_user_by_token(token):
    with _lock:
        uid = TOKENS.get(token)
        if uid and uid in USERS:
            return deepcopy(USERS[uid])
        return None


def logout(token):
    with _lock:
        TOKENS.pop(token, None)


def create_user(data):
    with _lock:
        uid = _next_id("u", "_user_id_counter")
        user = {
            "id": uid,
            "username": data.get("username"),
            "password": data.get("password"),
            "role": data.get("role", "field_staff"),
            "name": data.get("name", ""),
            "areas": data.get("areas", []),
        }
        USERS[uid] = user
        return deepcopy(user)


def list_users():
    with _lock:
        return [deepcopy(u) for u in USERS.values()]


def get_user(uid):
    with _lock:
        return deepcopy(USERS.get(uid))


def update_user(uid, data):
    with _lock:
        if uid not in USERS:
            return None
        user = USERS[uid]
        for k in ("username", "password", "role", "name", "areas"):
            if k in data:
                user[k] = data[k]
        return deepcopy(user)


def delete_user(uid):
    with _lock:
        return USERS.pop(uid, None) is not None


def create_point(data):
    with _lock:
        pid = _next_id("p", "_point_id_counter")
        now = _now()
        point = {
            "id": pid,
            "name": data.get("name", ""),
            "area": data.get("area", ""),
            "capacity": data.get("capacity", 100),
            "current_capacity": data.get("current_capacity", 0),
            "current_capacity_pct": 0,
            "location": data.get("location", ""),
            "status": "normal",
            "responsible_person": data.get("responsible_person", ""),
            "confirm_person": data.get("confirm_person", ""),
            "created_at": now,
            "updated_at": now,
        }
        cap = point["capacity"]
        if cap > 0:
            point["current_capacity_pct"] = round(point["current_capacity"] / cap * 100, 1)
        POINTS[pid] = point
        return deepcopy(point)


def list_points(filters=None):
    with _lock:
        results = list(POINTS.values())
    if filters:
        results = _apply_point_filters(results, filters)
    return [deepcopy(p) for p in results]


def get_point(pid):
    with _lock:
        return deepcopy(POINTS.get(pid))


def update_point(pid, data):
    with _lock:
        if pid not in POINTS:
            return None
        point = POINTS[pid]
        for k in ("name", "area", "capacity", "current_capacity", "location", "responsible_person", "confirm_person"):
            if k in data:
                point[k] = data[k]
        cap = point["capacity"]
        if cap > 0:
            point["current_capacity_pct"] = round(point["current_capacity"] / cap * 100, 1)
        if "status" in data:
            point["status"] = data["status"]
        point["updated_at"] = _now()
        return deepcopy(point)


def update_point_status(pid, status, operator_id=None):
    with _lock:
        if pid not in POINTS:
            return None
        point = POINTS[pid]
        point["status"] = status
        point["updated_at"] = _now()
        sync_tasks_from_business()
        return deepcopy(point)


def delete_point(pid):
    with _lock:
        return POINTS.pop(pid, None) is not None


def _apply_point_filters(points, filters):
    result = points
    if filters.get("area"):
        result = [p for p in result if p["area"] == filters["area"]]
    if filters.get("status"):
        vals = filters["status"].split(",") if "," in filters["status"] else [filters["status"]]
        result = [p for p in result if p["status"] in vals]
    if filters.get("responsible_person"):
        result = [p for p in result if p["responsible_person"] == filters["responsible_person"]]
    return result


def create_inspection(data, inspector_id):
    with _lock:
        iid = _next_id("i", "_inspection_id_counter")
        now = _now()
        pid = data.get("point_id")
        point = POINTS.get(pid)
        if not point:
            return None
        cap_pct = data.get("capacity_pct", 0)
        overflow = data.get("overflow", False)
        inspection = {
            "id": iid,
            "point_id": pid,
            "point_name": point["name"],
            "area": point["area"],
            "inspector": inspector_id,
            "inspector_name": USERS.get(inspector_id, {}).get("name", ""),
            "capacity_pct": cap_pct,
            "overflow": overflow,
            "notes": data.get("notes", ""),
            "timestamp": now,
        }
        INSPECTIONS.append(inspection)
        point["current_capacity_pct"] = cap_pct
        if cap_pct > 0 and point["capacity"] > 0:
            point["current_capacity"] = int(point["capacity"] * cap_pct / 100)
        if overflow:
            point["status"] = "near_full"
        elif cap_pct >= 90:
            point["status"] = "near_full"
        elif cap_pct >= 80:
            if point["status"] not in ("request_cleaning", "cleaning_in_progress", "pending_confirmation", "temporarily_disabled"):
                point["status"] = "near_full"
        elif point["status"] in ("normal", "near_full", "confirmed"):
            point["status"] = "normal"
        point["updated_at"] = now
        sync_tasks_from_business()
        return deepcopy(inspection)


def list_inspections(filters=None):
    with _lock:
        results = list(INSPECTIONS)
    if filters:
        results = _apply_inspection_filters(results, filters)
    return [deepcopy(i) for i in results]


def get_inspection(iid):
    with _lock:
        for insp in INSPECTIONS:
            if insp["id"] == iid:
                return deepcopy(insp)
        return None


def _apply_inspection_filters(inspections, filters):
    result = inspections
    if filters.get("area"):
        result = [i for i in result if i["area"] == filters["area"]]
    if filters.get("point_id"):
        result = [i for i in result if i["point_id"] == filters["point_id"]]
    if filters.get("inspector"):
        result = [i for i in result if i["inspector"] == filters["inspector"]]
    if filters.get("date_from"):
        result = [i for i in result if i["timestamp"] >= filters["date_from"]]
    if filters.get("date_to"):
        result = [i for i in result if i["timestamp"] <= filters["date_to"] + " 23:59:59"]
    if filters.get("overflow") is not None:
        result = [i for i in result if i["overflow"] == filters["overflow"]]
    if filters.get("responsible_person"):
        rp = filters["responsible_person"]
        result = [i for i in result if POINTS.get(i["point_id"], {}).get("responsible_person") == rp]
    return result


def create_cleaning_request(data, requester_id):
    with _lock:
        rid = _next_id("c", "_request_id_counter")
        now = _now()
        pid = data.get("point_id")
        point = POINTS.get(pid)
        if not point:
            return None
        req = {
            "id": rid,
            "point_id": pid,
            "point_name": point["name"],
            "area": point["area"],
            "requester": requester_id,
            "requester_name": USERS.get(requester_id, {}).get("name", ""),
            "status": "request_cleaning",
            "reason": data.get("reason", ""),
            "created_at": now,
            "updated_at": now,
            "processing_records": [
                {
                    "id": "r1",
                    "action": "create",
                    "operator": requester_id,
                    "operator_name": USERS.get(requester_id, {}).get("name", ""),
                    "notes": data.get("reason", ""),
                    "timestamp": now,
                }
            ],
        }
        CLEANING_REQUESTS[rid] = req
        point["status"] = "request_cleaning"
        point["updated_at"] = now
        sync_tasks_from_business()
        return deepcopy(req)


def list_cleaning_requests(filters=None):
    with _lock:
        results = list(CLEANING_REQUESTS.values())
    if filters:
        results = _apply_request_filters(results, filters)
    return [deepcopy(r) for r in results]


def get_cleaning_request(rid):
    with _lock:
        return deepcopy(CLEANING_REQUESTS.get(rid))


def _apply_request_filters(requests, filters):
    result = requests
    if filters.get("area"):
        result = [r for r in result if r["area"] == filters["area"]]
    if filters.get("point_id"):
        result = [r for r in result if r["point_id"] == filters["point_id"]]
    if filters.get("status"):
        vals = filters["status"].split(",") if "," in filters["status"] else [filters["status"]]
        result = [r for r in result if r["status"] in vals]
    if filters.get("requester"):
        result = [r for r in result if r["requester"] == filters["requester"]]
    if filters.get("date_from"):
        result = [r for r in result if r["created_at"] >= filters["date_from"]]
    if filters.get("date_to"):
        result = [r for r in result if r["created_at"] <= filters["date_to"] + " 23:59:59"]
    if filters.get("responsible_person"):
        rp = filters["responsible_person"]
        result = [r for r in result if POINTS.get(r["point_id"], {}).get("responsible_person") == rp]
    return result


def _add_processing_record(req, action, operator_id, notes=""):
    record_num = len(req["processing_records"]) + 1
    record = {
        "id": f"r{record_num}",
        "action": action,
        "operator": operator_id,
        "operator_name": USERS.get(operator_id, {}).get("name", ""),
        "notes": notes,
        "timestamp": _now(),
    }
    req["processing_records"].append(record)
    return record


def approve_cleaning_request(rid, operator_id, notes=""):
    with _lock:
        req = CLEANING_REQUESTS.get(rid)
        if not req:
            return None, "请求不存在"
        if req["status"] != "request_cleaning":
            return None, f"当前状态为{req['status']}，无法审批"
        req["status"] = "cleaning_in_progress"
        req["updated_at"] = _now()
        _add_processing_record(req, "approve", operator_id, notes)
        point = POINTS.get(req["point_id"])
        if point:
            point["status"] = "cleaning_in_progress"
            point["updated_at"] = _now()
        sync_tasks_from_business()
        return deepcopy(req), None


def complete_cleaning_request(rid, operator_id, notes=""):
    with _lock:
        req = CLEANING_REQUESTS.get(rid)
        if not req:
            return None, "请求不存在"
        if req["status"] not in ("pending_confirmation", "cleaning_in_progress"):
            return None, f"当前状态为{req['status']}，无法补充完成说明"
        if req["status"] == "cleaning_in_progress":
            req["status"] = "pending_confirmation"
        req["updated_at"] = _now()
        _add_processing_record(req, "complete", operator_id, notes)
        point = POINTS.get(req["point_id"])
        if point:
            if point["status"] == "cleaning_in_progress":
                point["status"] = "pending_confirmation"
            point["updated_at"] = _now()
        sync_tasks_from_business()
        return deepcopy(req), None


def confirm_cleaning_request(rid, operator_id, notes=""):
    with _lock:
        req = CLEANING_REQUESTS.get(rid)
        if not req:
            return None, "请求不存在"
        if req["status"] != "pending_confirmation":
            return None, f"当前状态为{req['status']}，无法确认"
        req["status"] = "confirmed"
        req["updated_at"] = _now()
        _add_processing_record(req, "confirm", operator_id, notes)
        point = POINTS.get(req["point_id"])
        if point:
            point["status"] = "normal"
            point["current_capacity_pct"] = 0
            point["current_capacity"] = 0
            point["updated_at"] = _now()
        sync_tasks_from_business()
        return deepcopy(req), None


def reject_cleaning_request(rid, operator_id, reason=""):
    with _lock:
        req = CLEANING_REQUESTS.get(rid)
        if not req:
            return None, "请求不存在"
        if req["status"] != "pending_confirmation":
            return None, f"当前状态为{req['status']}，无法退回"
        req["status"] = "cleaning_in_progress"
        req["updated_at"] = _now()
        _add_processing_record(req, "reject", operator_id, reason)
        point = POINTS.get(req["point_id"])
        if point:
            point["status"] = "cleaning_in_progress"
            point["updated_at"] = _now()
        sync_tasks_from_business()
        return deepcopy(req), None


def resubmit_cleaning_request(rid, operator_id, notes=""):
    with _lock:
        req = CLEANING_REQUESTS.get(rid)
        if not req:
            return None, "请求不存在"
        has_reject = any(r["action"] == "reject" for r in req["processing_records"])
        if not has_reject:
            return None, "该请求未被退回，无需重新提交"
        if req["status"] != "cleaning_in_progress":
            return None, f"当前状态为{req['status']}，无法重新提交"
        req["status"] = "pending_confirmation"
        req["updated_at"] = _now()
        _add_processing_record(req, "resubmit", operator_id, notes)
        point = POINTS.get(req["point_id"])
        if point:
            point["status"] = "pending_confirmation"
            point["updated_at"] = _now()
        sync_tasks_from_business()
        return deepcopy(req), None


def detect_alerts():
    with _lock:
        new_alerts = []
        now = datetime.now()

        for pid, point in POINTS.items():
            if point["status"] == "temporarily_disabled":
                continue

            recent = sorted(
                [i for i in INSPECTIONS if i["point_id"] == pid],
                key=lambda x: x["timestamp"],
                reverse=True,
            )[:settings.CONTINUOUS_FULL_THRESHOLD]

            if len(recent) >= settings.CONTINUOUS_FULL_THRESHOLD:
                full_count = sum(1 for i in recent if i["capacity_pct"] >= 90 or i["overflow"])
                if full_count >= settings.CONTINUOUS_FULL_THRESHOLD:
                    existing = any(
                        a["point_id"] == pid and a["type"] == "continuous_full" and not a["resolved"]
                        for a in ALERTS
                    )
                    if not existing:
                        aid = _next_id("a", "_alert_id_counter")
                        alert = {
                            "id": aid,
                            "type": "continuous_full",
                            "point_id": pid,
                            "point_name": point["name"],
                            "area": point["area"],
                            "description": f"{point['name']}连续{settings.CONTINUOUS_FULL_THRESHOLD}次巡查满载",
                            "severity": "high",
                            "created_at": _now(),
                            "resolved": False,
                        }
                        ALERTS.append(alert)
                        new_alerts.append(alert)

        for rid, req in CLEANING_REQUESTS.items():
            if req["status"] == "cleaning_in_progress":
                created = _parse_dt(req["created_at"])
                if created and (now - created) > timedelta(hours=settings.CLEANING_TIMEOUT_HOURS):
                    existing = any(
                        a.get("request_id") == rid and a["type"] == "cleaning_timeout" and not a["resolved"]
                        for a in ALERTS
                    )
                    if not existing:
                        aid = _next_id("a", "_alert_id_counter")
                        alert = {
                            "id": aid,
                            "type": "cleaning_timeout",
                            "point_id": req["point_id"],
                            "point_name": req["point_name"],
                            "area": req["area"],
                            "request_id": rid,
                            "description": f"{req['point_name']}清运超时（超过{settings.CLEANING_TIMEOUT_HOURS}小时）",
                            "severity": "high",
                            "created_at": _now(),
                            "resolved": False,
                        }
                        ALERTS.append(alert)
                        new_alerts.append(alert)

            if req["status"] == "pending_confirmation":
                updated = _parse_dt(req["updated_at"])
                if updated and (now - updated) > timedelta(hours=settings.CONFIRMATION_TIMEOUT_HOURS):
                    existing = any(
                        a.get("request_id") == rid and a["type"] == "confirmation_missing" and not a["resolved"]
                        for a in ALERTS
                    )
                    if not existing:
                        aid = _next_id("a", "_alert_id_counter")
                        alert = {
                            "id": aid,
                            "type": "confirmation_missing",
                            "point_id": req["point_id"],
                            "point_name": req["point_name"],
                            "area": req["area"],
                            "request_id": rid,
                            "description": f"{req['point_name']}确认缺失（超过{settings.CONFIRMATION_TIMEOUT_HOURS}小时未确认）",
                            "severity": "medium",
                            "created_at": _now(),
                            "resolved": False,
                        }
                        ALERTS.append(alert)
                        new_alerts.append(alert)

        areas = {}
        for pid, point in POINTS.items():
            if point["status"] in ("near_full", "request_cleaning", "cleaning_in_progress", "pending_confirmation"):
                areas.setdefault(point["area"], []).append(point)

        for area, pts in areas.items():
            if len(pts) >= settings.AREA_ANOMALY_THRESHOLD:
                existing = any(
                    a["area"] == area and a["type"] == "area_anomaly" and not a["resolved"]
                    for a in ALERTS
                )
                if not existing:
                    aid = _next_id("a", "_alert_id_counter")
                    alert = {
                        "id": aid,
                        "type": "area_anomaly",
                        "point_id": None,
                        "point_name": None,
                        "area": area,
                        "description": f"{area}异常集中（{len(pts)}个回收点异常）",
                        "severity": "medium",
                        "created_at": _now(),
                        "resolved": False,
                    }
                    ALERTS.append(alert)
                    new_alerts.append(alert)

        return [deepcopy(a) for a in new_alerts]


def list_alerts(filters=None):
    with _lock:
        results = list(ALERTS)
    if filters:
        if filters.get("type"):
            results = [a for a in results if a["type"] == filters["type"]]
        if filters.get("area"):
            results = [a for a in results if a["area"] == filters["area"]]
        if filters.get("severity"):
            results = [a for a in results if a["severity"] == filters["severity"]]
        if filters.get("resolved") is not None:
            results = [a for a in results if a["resolved"] == filters["resolved"]]
    return [deepcopy(a) for a in results]


def resolve_alert(aid):
    with _lock:
        for alert in ALERTS:
            if alert["id"] == aid:
                alert["resolved"] = True
                return deepcopy(alert)
        return None


def compute_statistics(filters=None):
    with _lock:
        points = list(POINTS.values())
        inspections = list(INSPECTIONS)
        requests = list(CLEANING_REQUESTS.values())

    if filters:
        if filters.get("area"):
            points = [p for p in points if p["area"] == filters["area"]]
            inspections = [i for i in inspections if i["area"] == filters["area"]]
            requests = [r for r in requests if r["area"] == filters["area"]]
        if filters.get("responsible_person"):
            rp = filters["responsible_person"]
            point_ids = [p["id"] for p in points if p["responsible_person"] == rp]
            points = [p for p in points if p["responsible_person"] == rp]
            inspections = [i for i in inspections if i["point_id"] in point_ids]
            requests = [r for r in requests if r["point_id"] in point_ids]
        if filters.get("date_from"):
            inspections = [i for i in inspections if i["timestamp"] >= filters["date_from"]]
            requests = [r for r in requests if r["created_at"] >= filters["date_from"]]
        if filters.get("date_to"):
            inspections = [i for i in inspections if i["timestamp"] <= filters["date_to"] + " 23:59:59"]
            requests = [r for r in requests if r["created_at"] <= filters["date_to"] + " 23:59:59"]

    status_summary = {}
    for point in points:
        status_summary[point["status"]] = status_summary.get(point["status"], 0) + 1

    from collections import defaultdict
    date_counts = defaultdict(int)
    for insp in inspections:
        if insp["capacity_pct"] >= 90 or insp["overflow"]:
            date_key = insp["timestamp"][:10]
            date_counts[date_key] += 1
    full_load_trend = [{"date": d, "count": c} for d, c in sorted(date_counts.items())]

    pending_list = []
    for req in requests:
        if req["status"] == "pending_confirmation":
            pending_list.append({
                "request_id": req["id"],
                "point_id": req["point_id"],
                "point_name": req["point_name"],
                "area": req["area"],
                "requester_name": req["requester_name"],
                "created_at": req["created_at"],
                "updated_at": req["updated_at"],
            })

    durations = []
    for req in requests:
        if req["status"] == "confirmed":
            created = _parse_dt(req["created_at"])
            last_record = req["processing_records"][-1] if req["processing_records"] else None
            if last_record and last_record["action"] == "confirm":
                confirmed_at = _parse_dt(last_record["timestamp"])
                if created and confirmed_at:
                    delta = (confirmed_at - created).total_seconds() / 3600
                    durations.append(round(delta, 2))

    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0

    return {
        "total_points": len(points),
        "status_summary": status_summary,
        "total_inspections": len(inspections),
        "total_requests": len(requests),
        "full_load_trend": full_load_trend,
        "pending_confirmation_list": pending_list,
        "avg_cleaning_duration_hours": avg_duration,
        "cleaning_duration_details": durations,
    }


def export_data(filters=None):
    stats = compute_statistics(filters)

    points = list_points(filters)
    inspections = list_inspections(filters)
    requests = list_cleaning_requests(filters)

    return {
        "export_time": _now(),
        "filter_conditions": filters or {},
        "statistics_summary": stats,
        "record_details": {
            "points": points,
            "inspections": inspections,
            "cleaning_requests": requests,
        },
    }


TASK_TYPES = [
    ("point_anomaly", "回收点异常"),
    ("cleaning_pending", "待清运申请"),
    ("cleaning_in_progress", "清运中事项"),
    ("pending_confirmation", "待确认事项"),
    ("timeout_risk", "超时/高风险提醒"),
]

TASK_STATUSES = [
    ("pending", "待处理"),
    ("assigned", "已分派"),
    ("in_progress", "处理中"),
    ("completed", "已完成"),
    ("closed", "已关闭"),
]

TASK_PRIORITIES = [
    ("low", "低"),
    ("medium", "中"),
    ("high", "高"),
    ("critical", "紧急"),
]


def _determine_task_priority(task_type, point=None, alert=None):
    if task_type == "timeout_risk":
        if alert and alert.get("severity") == "high":
            return "critical"
        return "high"
    if task_type == "point_anomaly":
        if point and point.get("current_capacity_pct", 0) >= 95:
            return "critical"
        if point and point.get("current_capacity_pct", 0) >= 90:
            return "high"
        return "medium"
    if task_type == "pending_confirmation":
        return "medium"
    if task_type == "cleaning_pending":
        if point and point.get("current_capacity_pct", 0) >= 90:
            return "high"
        return "medium"
    if task_type == "cleaning_in_progress":
        return "low"
    return "medium"


def _determine_suggested_action(task_type, point=None, request=None, alert=None):
    actions = {
        "point_anomaly": "请尽快前往现场巡查，确认回收点状态，如满载请申请清运",
        "cleaning_pending": "请审批清运申请，或安排现场人员进行清运",
        "cleaning_in_progress": "请跟进清运进度，确保按时完成清运工作",
        "pending_confirmation": "请尽快确认清运完成情况，如有问题请退回",
        "timeout_risk": "高优先级！请立即处理该超时事项，避免影响系统运行",
    }
    return actions.get(task_type, "请查看任务详情并及时处理")


def _get_latest_inspection(point_id):
    inspections = sorted(
        [i for i in INSPECTIONS if i["point_id"] == point_id],
        key=lambda x: x["timestamp"],
        reverse=True,
    )
    return inspections[0] if inspections else None


def _get_cleaning_progress(request):
    if not request:
        return None
    status_map = {
        "request_cleaning": "已申请清运，等待审批",
        "cleaning_in_progress": "清运进行中",
        "pending_confirmation": "清运完成，等待确认",
        "confirmed": "已确认完成",
    }
    steps = []
    for record in request.get("processing_records", []):
        action_map = {
            "create": "提交清运申请",
            "approve": "审批通过",
            "complete": "清运完成",
            "confirm": "确认完成",
            "reject": "退回",
            "resubmit": "重新提交",
        }
        steps.append({
            "action": action_map.get(record["action"], record["action"]),
            "operator_name": record.get("operator_name", ""),
            "timestamp": record.get("timestamp", ""),
            "notes": record.get("notes", ""),
        })
    return {
        "current_status": status_map.get(request["status"], request["status"]),
        "steps": steps,
    }


def _build_task(task_type, point_id, area=None, request=None, alert=None, point=None):
    if point is None:
        point = POINTS.get(point_id)
    if point is None:
        return None
    if area is None:
        area = point["area"]

    latest_insp = _get_latest_inspection(point_id)
    priority = _determine_task_priority(task_type, point=point, alert=alert)
    suggested_action = _determine_suggested_action(task_type, point=point, request=request, alert=alert)
    cleaning_progress = _get_cleaning_progress(request)

    related_request_id = request["id"] if request else None
    related_alert_id = alert["id"] if alert else None

    task_key = f"{task_type}_{point_id}_{related_request_id or 'none'}_{related_alert_id or 'none'}"

    now = _now()
    task = {
        "id": None,
        "task_type": task_type,
        "task_type_name": dict(TASK_TYPES).get(task_type, task_type),
        "title": None,
        "description": None,
        "priority": priority,
        "priority_name": dict(TASK_PRIORITIES).get(priority, priority),
        "status": "pending",
        "status_name": dict(TASK_STATUSES).get("pending", "pending"),
        "area": area,
        "point_id": point_id,
        "point_name": point["name"],
        "point_status": point["status"],
        "point_capacity_pct": point.get("current_capacity_pct", 0),
        "responsible_person": point.get("responsible_person", ""),
        "responsible_person_name": USERS.get(point.get("responsible_person", ""), {}).get("name", ""),
        "assignee": None,
        "assignee_name": None,
        "related_request_id": related_request_id,
        "related_alert_id": related_alert_id,
        "latest_inspection": latest_insp,
        "cleaning_progress": cleaning_progress,
        "suggested_action": suggested_action,
        "is_timeout": False,
        "is_high_risk": priority in ("high", "critical"),
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
        "closed_by": None,
        "closed_reason": None,
        "_task_key": task_key,
    }

    title_map = {
        "point_anomaly": f"{point['name']}状态异常",
        "cleaning_pending": f"{point['name']}待清运审批",
        "cleaning_in_progress": f"{point['name']}清运进行中",
        "pending_confirmation": f"{point['name']}清运待确认",
        "timeout_risk": f"{point['name']}超时告警",
    }
    task["title"] = title_map.get(task_type, task_type)

    desc_map = {
        "point_anomaly": f"回收点当前状态：{point['status']}，容量：{point.get('current_capacity_pct', 0)}%",
        "cleaning_pending": f"清运申请已提交，请及时审批处理",
        "cleaning_in_progress": f"清运正在进行中，请跟进进度",
        "pending_confirmation": f"清运已完成，请及时确认",
        "timeout_risk": alert.get("description", "存在超时/高风险，需要立即处理") if alert else "存在超时/高风险",
    }
    task["description"] = desc_map.get(task_type, "")

    if task_type == "timeout_risk":
        task["is_timeout"] = True

    return task


def sync_tasks_from_business():
    with _lock:
        now = datetime.now()
        existing_keys = {t["_task_key"]: tid for tid, t in TASKS.items() if t["status"] not in ("completed", "closed")}
        processed_keys = set()

        for pid, point in POINTS.items():
            if point["status"] == "temporarily_disabled":
                continue

            if point["status"] in ("near_full",):
                task = _build_task("point_anomaly", pid, point=point)
                if task:
                    processed_keys.add(task["_task_key"])
                    if task["_task_key"] not in existing_keys:
                        tid = _next_id("t", "_task_id_counter")
                        task["id"] = tid
                        TASKS[tid] = task

            if point["status"] == "request_cleaning":
                req = next((r for r in CLEANING_REQUESTS.values() if r["point_id"] == pid and r["status"] == "request_cleaning"), None)
                task = _build_task("cleaning_pending", pid, point=point, request=req)
                if task:
                    processed_keys.add(task["_task_key"])
                    if task["_task_key"] not in existing_keys:
                        tid = _next_id("t", "_task_id_counter")
                        task["id"] = tid
                        TASKS[tid] = task
                    else:
                        tid = existing_keys[task["_task_key"]]
                        if tid in TASKS:
                            TASKS[tid]["updated_at"] = _now()
                            TASKS[tid]["point_status"] = point["status"]
                            TASKS[tid]["point_capacity_pct"] = point.get("current_capacity_pct", 0)
                            TASKS[tid]["latest_inspection"] = _get_latest_inspection(pid)
                            TASKS[tid]["cleaning_progress"] = _get_cleaning_progress(req)

            if point["status"] == "cleaning_in_progress":
                req = next((r for r in CLEANING_REQUESTS.values() if r["point_id"] == pid and r["status"] == "cleaning_in_progress"), None)
                task = _build_task("cleaning_in_progress", pid, point=point, request=req)
                if task:
                    processed_keys.add(task["_task_key"])
                    if task["_task_key"] not in existing_keys:
                        tid = _next_id("t", "_task_id_counter")
                        task["id"] = tid
                        TASKS[tid] = task
                    else:
                        tid = existing_keys[task["_task_key"]]
                        if tid in TASKS:
                            TASKS[tid]["updated_at"] = _now()
                            TASKS[tid]["point_status"] = point["status"]
                            TASKS[tid]["point_capacity_pct"] = point.get("current_capacity_pct", 0)
                            TASKS[tid]["latest_inspection"] = _get_latest_inspection(pid)
                            TASKS[tid]["cleaning_progress"] = _get_cleaning_progress(req)

            if point["status"] == "pending_confirmation":
                req = next((r for r in CLEANING_REQUESTS.values() if r["point_id"] == pid and r["status"] == "pending_confirmation"), None)
                task = _build_task("pending_confirmation", pid, point=point, request=req)
                if task:
                    processed_keys.add(task["_task_key"])
                    if task["_task_key"] not in existing_keys:
                        tid = _next_id("t", "_task_id_counter")
                        task["id"] = tid
                        TASKS[tid] = task
                    else:
                        tid = existing_keys[task["_task_key"]]
                        if tid in TASKS:
                            TASKS[tid]["updated_at"] = _now()
                            TASKS[tid]["point_status"] = point["status"]
                            TASKS[tid]["point_capacity_pct"] = point.get("current_capacity_pct", 0)
                            TASKS[tid]["latest_inspection"] = _get_latest_inspection(pid)
                            TASKS[tid]["cleaning_progress"] = _get_cleaning_progress(req)

        for alert in ALERTS:
            if alert.get("resolved"):
                continue
            if alert["type"] in ("continuous_full", "cleaning_timeout", "confirmation_missing"):
                pid = alert.get("point_id")
                if not pid:
                    continue
                point = POINTS.get(pid)
                req = None
                if alert.get("request_id"):
                    req = CLEANING_REQUESTS.get(alert["request_id"])
                task = _build_task("timeout_risk", pid, point=point, request=req, alert=alert)
                if task:
                    processed_keys.add(task["_task_key"])
                    if task["_task_key"] not in existing_keys:
                        tid = _next_id("t", "_task_id_counter")
                        task["id"] = tid
                        TASKS[tid] = task
                    else:
                        tid = existing_keys[task["_task_key"]]
                        if tid in TASKS:
                            TASKS[tid]["updated_at"] = _now()
                            TASKS[tid]["latest_inspection"] = _get_latest_inspection(pid)
                            TASKS[tid]["cleaning_progress"] = _get_cleaning_progress(req)

        for key, tid in existing_keys.items():
            if key not in processed_keys and tid in TASKS:
                task = TASKS[tid]
                if task["task_type"] == "timeout_risk":
                    if task.get("related_alert_id"):
                        alert = next((a for a in ALERTS if a["id"] == task["related_alert_id"]), None)
                        if alert and not alert.get("resolved"):
                            continue
                if task["task_type"] == "point_anomaly":
                    point = POINTS.get(task["point_id"])
                    if point and point["status"] == "near_full":
                        continue
                if task["task_type"] in ("cleaning_pending", "cleaning_in_progress", "pending_confirmation"):
                    point = POINTS.get(task["point_id"])
                    if point and point["status"] == task["task_type"].replace("cleaning_pending", "request_cleaning"):
                        continue
                    if point and point["status"] == task["task_type"]:
                        continue
                TASKS[tid]["status"] = "completed"
                TASKS[tid]["status_name"] = dict(TASK_STATUSES)["completed"]
                TASKS[tid]["updated_at"] = _now()

        return list(TASKS.values())


def list_tasks(filters=None, user=None):
    detect_alerts()
    sync_tasks_from_business()
    with _lock:
        results = list(TASKS.values())

    if user:
        role = user.get("role")
        if role == "field_staff":
            user_areas = user.get("areas", [])
            results = [
                t for t in results
                if t["area"] in user_areas
                or t["responsible_person"] == user.get("id")
                or t["assignee"] == user.get("id")
            ]

    if filters:
        results = _apply_task_filters(results, filters)

    results = sorted(results, key=lambda x: (
        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x["priority"], 99),
        x["created_at"],
    ))

    return [_sanitize_task(deepcopy(t)) for t in results]


def _sanitize_task(task):
    task.pop("_task_key", None)
    return task


def _apply_task_filters(tasks, filters):
    result = tasks
    if filters.get("area"):
        vals = filters["area"].split(",") if "," in filters["area"] else [filters["area"]]
        result = [t for t in result if t["area"] in vals]
    if filters.get("responsible_person"):
        result = [t for t in result if t["responsible_person"] == filters["responsible_person"]]
    if filters.get("assignee"):
        result = [t for t in result if t["assignee"] == filters["assignee"]]
    if filters.get("task_type"):
        vals = filters["task_type"].split(",") if "," in filters["task_type"] else [filters["task_type"]]
        result = [t for t in result if t["task_type"] in vals]
    if filters.get("priority"):
        vals = filters["priority"].split(",") if "," in filters["priority"] else [filters["priority"]]
        result = [t for t in result if t["priority"] in vals]
    if filters.get("status"):
        vals = filters["status"].split(",") if "," in filters["status"] else [filters["status"]]
        result = [t for t in result if t["status"] in vals]
    if filters.get("is_timeout") is not None:
        is_timeout = filters["is_timeout"].lower() == "true"
        result = [t for t in result if t["is_timeout"] == is_timeout]
    if filters.get("is_high_risk") is not None:
        is_high_risk = filters["is_high_risk"].lower() == "true"
        result = [t for t in result if t["is_high_risk"] == is_high_risk]
    if filters.get("point_id"):
        result = [t for t in result if t["point_id"] == filters["point_id"]]
    return result


def get_task(tid):
    sync_tasks_from_business()
    with _lock:
        task = TASKS.get(tid)
        return _sanitize_task(deepcopy(task)) if task else None


def assign_task(tid, assignee_id, operator_id):
    with _lock:
        task = TASKS.get(tid)
        if not task:
            return None, "任务不存在"
        if task["status"] in ("completed", "closed"):
            return None, f"任务状态为{task['status_name']}，无法分派"
        assignee = USERS.get(assignee_id)
        if not assignee:
            return None, "指定的负责人不存在"
        task["assignee"] = assignee_id
        task["assignee_name"] = assignee.get("name", "")
        task["status"] = "assigned"
        task["status_name"] = dict(TASK_STATUSES)["assigned"]
        task["updated_at"] = _now()
        return _sanitize_task(deepcopy(task)), None


def close_task(tid, operator_id, reason=""):
    with _lock:
        task = TASKS.get(tid)
        if not task:
            return None, "任务不存在"
        if task["status"] == "closed":
            return None, "任务已关闭"
        task["status"] = "closed"
        task["status_name"] = dict(TASK_STATUSES)["closed"]
        task["closed_at"] = _now()
        task["closed_by"] = operator_id
        task["closed_reason"] = reason
        task["updated_at"] = _now()
        return _sanitize_task(deepcopy(task)), None


def start_task(tid, operator_id):
    with _lock:
        task = TASKS.get(tid)
        if not task:
            return None, "任务不存在"
        if task["status"] not in ("pending", "assigned"):
            return None, f"任务状态为{task['status_name']}，无法开始处理"
        operator = USERS.get(operator_id)
        if operator and operator.get("role") == "field_staff":
            user_areas = operator.get("areas", [])
            if (task["area"] not in user_areas
                    and task["responsible_person"] != operator_id
                    and task.get("assignee") != operator_id):
                return None, "无权限处理该区域任务"
        task["status"] = "in_progress"
        task["status_name"] = dict(TASK_STATUSES)["in_progress"]
        task["updated_at"] = _now()
        return _sanitize_task(deepcopy(task)), None


def compute_task_statistics(filters=None, user=None):
    tasks = list_tasks(filters, user=user)

    area_stats = {}
    for task in tasks:
        area = task["area"]
        if area not in area_stats:
            area_stats[area] = {
                "area": area,
                "total_pending": 0,
                "total_timeout": 0,
                "total_high_priority": 0,
                "by_type": {},
                "by_status": {},
            }
        is_active = task["status"] not in ("completed", "closed")
        if is_active:
            area_stats[area]["total_pending"] += 1
            if task["is_timeout"]:
                area_stats[area]["total_timeout"] += 1
            if task["priority"] in ("high", "critical"):
                area_stats[area]["total_high_priority"] += 1

        tt = task["task_type_name"]
        area_stats[area]["by_type"][tt] = area_stats[area]["by_type"].get(tt, 0) + 1

        ts = task["status_name"]
        area_stats[area]["by_status"][ts] = area_stats[area]["by_status"].get(ts, 0) + 1

    overall = {
        "total_tasks": len(tasks),
        "total_pending": sum(1 for t in tasks if t["status"] not in ("completed", "closed")),
        "total_timeout": sum(1 for t in tasks if t["status"] not in ("completed", "closed") and t["is_timeout"]),
        "total_high_priority": sum(1 for t in tasks if t["status"] not in ("completed", "closed") and t["priority"] in ("high", "critical")),
        "by_priority": {},
        "by_type": {},
        "by_status": {},
    }
    for task in tasks:
        p = task["priority_name"]
        overall["by_priority"][p] = overall["by_priority"].get(p, 0) + 1
        tt = task["task_type_name"]
        overall["by_type"][tt] = overall["by_type"].get(tt, 0) + 1
        ts = task["status_name"]
        overall["by_status"][ts] = overall["by_status"].get(ts, 0) + 1

    return {
        "overall": overall,
        "by_area": list(area_stats.values()),
    }


def export_task_data(filters=None, user=None):
    stats = compute_task_statistics(filters, user=user)
    tasks = list_tasks(filters, user=user)

    export_tasks = []
    for t in tasks:
        latest_insp = t.get("latest_inspection") or {}
        export_tasks.append({
            "任务ID": t.get("id", ""),
            "任务类型": t.get("task_type_name", ""),
            "标题": t.get("title", ""),
            "描述": t.get("description", ""),
            "优先级": t.get("priority_name", ""),
            "状态": t.get("status_name", ""),
            "区域": t.get("area", ""),
            "回收点ID": t.get("point_id", ""),
            "回收点名称": t.get("point_name", ""),
            "回收点状态": t.get("point_status", ""),
            "回收点容量%": t.get("point_capacity_pct", 0),
            "负责人ID": t.get("responsible_person", ""),
            "负责人姓名": t.get("responsible_person_name", ""),
            "处理人ID": t.get("assignee", ""),
            "处理人姓名": t.get("assignee_name", ""),
            "关联清运申请ID": t.get("related_request_id", ""),
            "关联告警ID": t.get("related_alert_id", ""),
            "最近巡查时间": latest_insp.get("timestamp", ""),
            "最近巡查人": latest_insp.get("inspector_name", ""),
            "最近巡查容量%": latest_insp.get("capacity_pct", ""),
            "是否溢出": "是" if latest_insp.get("overflow") else "否",
            "是否超时": "是" if t.get("is_timeout") else "否",
            "是否高风险": "是" if t.get("is_high_risk") else "否",
            "建议处理动作": t.get("suggested_action", ""),
            "创建时间": t.get("created_at", ""),
            "更新时间": t.get("updated_at", ""),
            "关闭时间": t.get("closed_at", ""),
            "关闭原因": t.get("closed_reason", ""),
        })

    return {
        "export_time": _now(),
        "filter_conditions": filters or {},
        "statistics": stats,
        "tasks": export_tasks,
    }


def get_task_board(filters=None, user=None):
    tasks = list_tasks(filters, user=user)

    area_groups = {}
    for task in tasks:
        area = task["area"]
        if area not in area_groups:
            area_groups[area] = {
                "area": area,
                "summary": {
                    "total_tasks": 0,
                    "pending_count": 0,
                    "timeout_count": 0,
                    "high_priority_count": 0,
                    "by_type": {},
                    "by_status": {},
                },
                "tasks": [],
            }
        group = area_groups[area]
        group["summary"]["total_tasks"] += 1
        is_active = task["status"] not in ("completed", "closed")
        if is_active:
            group["summary"]["pending_count"] += 1
            if task.get("is_timeout"):
                group["summary"]["timeout_count"] += 1
            if task.get("priority") in ("high", "critical"):
                group["summary"]["high_priority_count"] += 1

        tt_name = task.get("task_type_name", "")
        group["summary"]["by_type"][tt_name] = group["summary"]["by_type"].get(tt_name, 0) + 1
        ts_name = task.get("status_name", "")
        group["summary"]["by_status"][ts_name] = group["summary"]["by_status"].get(ts_name, 0) + 1

        group["tasks"].append(task)

    area_list = sorted(area_groups.values(), key=lambda x: (
        -x["summary"]["high_priority_count"],
        -x["summary"]["timeout_count"],
        -x["summary"]["pending_count"],
    ))

    overall = {
        "total_areas": len(area_list),
        "total_tasks": len(tasks),
        "total_pending": sum(1 for t in tasks if t["status"] not in ("completed", "closed")),
        "total_timeout": sum(1 for t in tasks if t["status"] not in ("completed", "closed") and t.get("is_timeout")),
        "total_high_priority": sum(1 for t in tasks if t["status"] not in ("completed", "closed") and t.get("priority") in ("high", "critical")),
        "by_type": {},
        "by_status": {},
        "by_priority": {},
    }
    for task in tasks:
        tt_name = task.get("task_type_name", "")
        overall["by_type"][tt_name] = overall["by_type"].get(tt_name, 0) + 1
        ts_name = task.get("status_name", "")
        overall["by_status"][ts_name] = overall["by_status"].get(ts_name, 0) + 1
        tp_name = task.get("priority_name", "")
        overall["by_priority"][tp_name] = overall["by_priority"].get(tp_name, 0) + 1

    return {
        "overall_summary": overall,
        "areas": area_list,
    }
