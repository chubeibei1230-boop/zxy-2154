import json
from django.http import HttpResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from . import storage
from .permissions import IsAdmin, IsAdminOrFieldStaff, IsAdminOrReadOnly, CanWriteOrReadOnly


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        token, uid, user = storage.authenticate(username, password)
        if not token:
            return Response(
                {"success": False, "error": "用户名或密码错误"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response({
            "success": True,
            "data": {
                "token": token,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "name": user["name"],
                    "role": user["role"],
                    "areas": user["areas"],
                },
            },
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.auth
        storage.logout(token)
        return Response({"success": True, "data": "已退出登录"})


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "success": True,
            "data": {
                "id": user["id"],
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "areas": user["areas"],
            },
        })


class UserListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = storage.list_users()
        for u in users:
            u.pop("password", None)
        return Response({"success": True, "data": users})

    def post(self, request):
        required = ["username", "password", "role"]
        for f in required:
            if not request.data.get(f):
                return Response(
                    {"success": False, "error": f"缺少必填字段: {f}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if request.data["role"] not in ("admin", "field_staff", "observer"):
            return Response(
                {"success": False, "error": "无效的角色类型"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        existing = [u for u in storage.list_users() if u["username"] == request.data["username"]]
        if existing:
            return Response(
                {"success": False, "error": "用户名已存在"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = storage.create_user(request.data)
        user.pop("password", None)
        return Response({"success": True, "data": user}, status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request, uid):
        user = storage.get_user(uid)
        if not user:
            return Response(
                {"success": False, "error": "用户不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.pop("password", None)
        return Response({"success": True, "data": user})

    def put(self, request, uid):
        user = storage.update_user(uid, request.data)
        if not user:
            return Response(
                {"success": False, "error": "用户不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.pop("password", None)
        return Response({"success": True, "data": user})

    def delete(self, request, uid):
        if storage.delete_user(uid):
            return Response({"success": True, "data": "用户已删除"})
        return Response(
            {"success": False, "error": "用户不存在"},
            status=status.HTTP_404_NOT_FOUND,
        )


class PointListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = {}
        for key in ("area", "status", "responsible_person"):
            if request.query_params.get(key):
                filters[key] = request.query_params.get(key)
        points = storage.list_points(filters if filters else None)
        return Response({"success": True, "data": points, "count": len(points)})

    def post(self, request):
        if request.user.get("role") != "admin":
            return Response(
                {"success": False, "error": "仅管理员可创建回收点"},
                status=status.HTTP_403_FORBIDDEN,
            )
        required = ["name", "area", "capacity"]
        for f in required:
            if request.data.get(f) is None:
                return Response(
                    {"success": False, "error": f"缺少必填字段: {f}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        point = storage.create_point(request.data)
        return Response({"success": True, "data": point}, status=status.HTTP_201_CREATED)


class PointDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pid):
        point = storage.get_point(pid)
        if not point:
            return Response(
                {"success": False, "error": "回收点不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "data": point})

    def put(self, request, pid):
        if request.user.get("role") != "admin":
            return Response(
                {"success": False, "error": "仅管理员可修改回收点"},
                status=status.HTTP_403_FORBIDDEN,
            )
        point = storage.update_point(pid, request.data)
        if not point:
            return Response(
                {"success": False, "error": "回收点不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "data": point})

    def delete(self, request, pid):
        if request.user.get("role") != "admin":
            return Response(
                {"success": False, "error": "仅管理员可删除回收点"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if storage.delete_point(pid):
            return Response({"success": True, "data": "回收点已删除"})
        return Response(
            {"success": False, "error": "回收点不存在"},
            status=status.HTTP_404_NOT_FOUND,
        )


class PointStatusView(APIView):
    permission_classes = [IsAdminOrFieldStaff]

    def patch(self, request, pid):
        new_status = request.data.get("status")
        valid = [s[0] for s in storage.STATUS_CHOICES]
        if new_status not in valid:
            return Response(
                {"success": False, "error": f"无效状态，可选值: {valid}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.user.get("role") == "field_staff" and new_status == "temporarily_disabled":
            return Response(
                {"success": False, "error": "现场人员无法设置停用状态"},
                status=status.HTTP_403_FORBIDDEN,
            )
        point = storage.update_point_status(pid, new_status, request.user["id"])
        if not point:
            return Response(
                {"success": False, "error": "回收点不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "data": point})


class InspectionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = {}
        for key in ("area", "point_id", "inspector", "date_from", "date_to"):
            if request.query_params.get(key):
                filters[key] = request.query_params.get(key)
        if request.query_params.get("overflow") is not None:
            filters["overflow"] = request.query_params.get("overflow").lower() == "true"
        inspections = storage.list_inspections(filters if filters else None)
        return Response({"success": True, "data": inspections, "count": len(inspections)})

    def post(self, request):
        if request.user.get("role") not in ("admin", "field_staff"):
            return Response(
                {"success": False, "error": "仅现场人员或管理员可登记巡查"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not request.data.get("point_id"):
            return Response(
                {"success": False, "error": "缺少必填字段: point_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.data.get("capacity_pct") is None:
            return Response(
                {"success": False, "error": "缺少必填字段: capacity_pct"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        inspection = storage.create_inspection(request.data, request.user["id"])
        if not inspection:
            return Response(
                {"success": False, "error": "回收点不存在"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": inspection}, status=status.HTTP_201_CREATED)


class InspectionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, iid):
        inspection = storage.get_inspection(iid)
        if not inspection:
            return Response(
                {"success": False, "error": "巡查记录不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "data": inspection})


class CleaningRequestListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = {}
        for key in ("area", "point_id", "status", "requester", "date_from", "date_to"):
            if request.query_params.get(key):
                filters[key] = request.query_params.get(key)
        requests = storage.list_cleaning_requests(filters if filters else None)
        return Response({"success": True, "data": requests, "count": len(requests)})

    def post(self, request):
        if request.user.get("role") not in ("admin", "field_staff"):
            return Response(
                {"success": False, "error": "仅现场人员或管理员可申请清运"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not request.data.get("point_id"):
            return Response(
                {"success": False, "error": "缺少必填字段: point_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        req = storage.create_cleaning_request(request.data, request.user["id"])
        if not req:
            return Response(
                {"success": False, "error": "回收点不存在"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": req}, status=status.HTTP_201_CREATED)


class CleaningRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, rid):
        req = storage.get_cleaning_request(rid)
        if not req:
            return Response(
                {"success": False, "error": "清运请求不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "data": req})


class CleaningRequestApproveView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, rid):
        notes = request.data.get("notes", "")
        req, error = storage.approve_cleaning_request(rid, request.user["id"], notes)
        if error:
            return Response(
                {"success": False, "error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": req})


class CleaningRequestCompleteView(APIView):
    permission_classes = [IsAdminOrFieldStaff]

    def post(self, request, rid):
        notes = request.data.get("notes", "")
        if not notes:
            return Response(
                {"success": False, "error": "请补充清运完成说明"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        req, error = storage.complete_cleaning_request(rid, request.user["id"], notes)
        if error:
            return Response(
                {"success": False, "error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": req})


class CleaningRequestConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, rid):
        req = storage.get_cleaning_request(rid)
        if not req:
            return Response(
                {"success": False, "error": "清运请求不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        point = storage.get_point(req["point_id"])
        is_admin = request.user.get("role") == "admin"
        is_confirm_person = point and point.get("confirm_person") == request.user["id"]
        if not (is_admin or is_confirm_person):
            return Response(
                {"success": False, "error": "无权限确认，仅管理员或指定确认人可操作"},
                status=status.HTTP_403_FORBIDDEN,
            )
        notes = request.data.get("notes", "")
        req, error = storage.confirm_cleaning_request(rid, request.user["id"], notes)
        if error:
            return Response(
                {"success": False, "error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": req})


class CleaningRequestRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, rid):
        req = storage.get_cleaning_request(rid)
        if not req:
            return Response(
                {"success": False, "error": "清运请求不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        point = storage.get_point(req["point_id"])
        is_admin = request.user.get("role") == "admin"
        is_confirm_person = point and point.get("confirm_person") == request.user["id"]
        if not (is_admin or is_confirm_person):
            return Response(
                {"success": False, "error": "无权限退回，仅管理员或指定确认人可操作"},
                status=status.HTTP_403_FORBIDDEN,
            )
        reason = request.data.get("reason", "")
        if not reason:
            return Response(
                {"success": False, "error": "请填写退回原因"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        req, error = storage.reject_cleaning_request(rid, request.user["id"], reason)
        if error:
            return Response(
                {"success": False, "error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": req})


class CleaningRequestResubmitView(APIView):
    permission_classes = [IsAdminOrFieldStaff]

    def post(self, request, rid):
        notes = request.data.get("notes", "")
        if not notes:
            return Response(
                {"success": False, "error": "请补充重新提交说明"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        req, error = storage.resubmit_cleaning_request(rid, request.user["id"], notes)
        if error:
            return Response(
                {"success": False, "error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"success": True, "data": req})


class AlertListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = {}
        for key in ("type", "area", "severity"):
            if request.query_params.get(key):
                filters[key] = request.query_params.get(key)
        if request.query_params.get("resolved") is not None:
            filters["resolved"] = request.query_params.get("resolved").lower() == "true"
        alerts = storage.list_alerts(filters if filters else None)
        return Response({"success": True, "data": alerts, "count": len(alerts)})


class AlertDetectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_alerts = storage.detect_alerts()
        return Response({"success": True, "data": new_alerts, "count": len(new_alerts)})


class AlertResolveView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, aid):
        alert = storage.resolve_alert(aid)
        if not alert:
            return Response(
                {"success": False, "error": "告警不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"success": True, "data": alert})


class StatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = {}
        for key in ("area", "date_from", "date_to"):
            if request.query_params.get(key):
                filters[key] = request.query_params.get(key)
        stats = storage.compute_statistics(filters if filters else None)
        return Response({"success": True, "data": stats})


class ExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filters = {}
        for key in ("area", "status", "responsible_person", "date_from", "date_to"):
            if request.query_params.get(key):
                filters[key] = request.query_params.get(key)
        export_format = request.query_params.get("format", "json")
        data = storage.export_data(filters if filters else None)

        if export_format == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["=== 导出信息 ==="])
            writer.writerow(["导出时间", data["export_time"]])
            writer.writerow(["筛选条件", json.dumps(data["filter_conditions"], ensure_ascii=False)])
            writer.writerow([])
            writer.writerow(["=== 统计摘要 ==="])
            for k, v in data["statistics_summary"].items():
                writer.writerow([k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v])
            writer.writerow([])
            writer.writerow(["=== 回收点明细 ==="])
            if data["record_details"]["points"]:
                headers = list(data["record_details"]["points"][0].keys())
                writer.writerow(headers)
                for p in data["record_details"]["points"]:
                    writer.writerow([p.get(h, "") for h in headers])
            writer.writerow([])
            writer.writerow(["=== 巡查记录明细 ==="])
            if data["record_details"]["inspections"]:
                headers = list(data["record_details"]["inspections"][0].keys())
                writer.writerow(headers)
                for i in data["record_details"]["inspections"]:
                    writer.writerow([i.get(h, "") for h in headers])
            writer.writerow([])
            writer.writerow(["=== 清运请求明细 ==="])
            if data["record_details"]["cleaning_requests"]:
                headers = list(data["record_details"]["cleaning_requests"][0].keys())
                writer.writerow(headers)
                for r in data["record_details"]["cleaning_requests"]:
                    row = []
                    for h in headers:
                        val = r.get(h, "")
                        if isinstance(val, list):
                            val = json.dumps(val, ensure_ascii=False)
                        row.append(val)
                    writer.writerow(row)
            output.seek(0)
            response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8-sig")
            response["Content-Disposition"] = "attachment; filename=recycling_export.csv"
            return response

        response = HttpResponse(
            json.dumps(data, ensure_ascii=False, indent=2),
            content_type="application/json; charset=utf-8",
        )
        response["Content-Disposition"] = "attachment; filename=recycling_export.json"
        return response
