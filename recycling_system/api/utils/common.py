import json
import csv
import io
from django.http import HttpResponse


def build_csv_response(sections, filename="export.csv"):
    output = io.StringIO()
    writer = csv.writer(output)
    for section in sections:
        if section.get("title"):
            writer.writerow([section["title"]])
        if section.get("headers"):
            writer.writerow(section["headers"])
        for row in section.get("rows", []):
            writer.writerow(row)
        writer.writerow([])
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def build_json_response(data, filename="export.json"):
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def dict_to_rows(items, headers=None):
    if not items:
        return []
    if headers is None:
        headers = list(items[0].keys())
    rows = []
    for item in items:
        row = []
        for h in headers:
            val = item.get(h, "")
            if isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            row.append(val)
        rows.append(row)
    return rows


def parse_bool_param(value):
    if value is None:
        return None
    return value.lower() == "true"


def parse_list_param(value):
    if not value:
        return []
    if "," in value:
        return value.split(",")
    return [value]


def extract_filters(request, keys, bool_keys=None):
    filters = {}
    for key in keys:
        val = request.query_params.get(key)
        if val is not None and val != "":
            filters[key] = val
    if bool_keys:
        for key in bool_keys:
            raw = request.query_params.get(key)
            if raw is not None:
                filters[key] = parse_bool_param(raw)
    return filters if filters else None


def success_response(data=None, **kwargs):
    result = {"success": True}
    if data is not None:
        result["data"] = data
    result.update(kwargs)
    return result


def error_response(message, status_code=400):
    return {"success": False, "error": message}, status_code
