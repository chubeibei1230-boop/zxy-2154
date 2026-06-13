import threading
import uuid
from datetime import datetime, timedelta
from copy import deepcopy

from django.conf import settings

_lock = threading.Lock()

USERS = {}
TOKENS = {}
POINTS = {}
INSPECTIONS = []
CLEANING_REQUESTS = {}
ALERTS = []

_user_id_counter = 0
_point_id_counter = 0
_inspection_id_counter = 0
_request_id_counter = 0
_alert_id_counter = 0


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
        return deepcopy(req), None


def complete_cleaning_request(rid, operator_id, notes=""):
    with _lock:
        req = CLEANING_REQUESTS.get(rid)
        if not req:
            return None, "请求不存在"
        if req["status"] != "cleaning_in_progress":
            return None, f"当前状态为{req['status']}，无法完成"
        req["status"] = "pending_confirmation"
        req["updated_at"] = _now()
        _add_processing_record(req, "complete", operator_id, notes)
        point = POINTS.get(req["point_id"])
        if point:
            point["status"] = "pending_confirmation"
            point["updated_at"] = _now()
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
