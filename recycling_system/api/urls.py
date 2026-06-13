from django.urls import path
from . import views

urlpatterns = [
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.CurrentUserView.as_view(), name="current-user"),

    path("users/", views.UserListView.as_view(), name="user-list"),
    path("users/<str:uid>/", views.UserDetailView.as_view(), name="user-detail"),

    path("points/", views.PointListView.as_view(), name="point-list"),
    path("points/<str:pid>/", views.PointDetailView.as_view(), name="point-detail"),
    path("points/<str:pid>/status/", views.PointStatusView.as_view(), name="point-status"),

    path("inspections/", views.InspectionListView.as_view(), name="inspection-list"),
    path("inspections/<str:iid>/", views.InspectionDetailView.as_view(), name="inspection-detail"),

    path("cleaning-requests/", views.CleaningRequestListView.as_view(), name="cleaning-request-list"),
    path("cleaning-requests/<str:rid>/", views.CleaningRequestDetailView.as_view(), name="cleaning-request-detail"),
    path("cleaning-requests/<str:rid>/approve/", views.CleaningRequestApproveView.as_view(), name="cleaning-request-approve"),
    path("cleaning-requests/<str:rid>/complete/", views.CleaningRequestCompleteView.as_view(), name="cleaning-request-complete"),
    path("cleaning-requests/<str:rid>/confirm/", views.CleaningRequestConfirmView.as_view(), name="cleaning-request-confirm"),
    path("cleaning-requests/<str:rid>/reject/", views.CleaningRequestRejectView.as_view(), name="cleaning-request-reject"),
    path("cleaning-requests/<str:rid>/resubmit/", views.CleaningRequestResubmitView.as_view(), name="cleaning-request-resubmit"),

    path("alerts/", views.AlertListView.as_view(), name="alert-list"),
    path("alerts/detect/", views.AlertDetectView.as_view(), name="alert-detect"),
    path("alerts/<str:aid>/resolve/", views.AlertResolveView.as_view(), name="alert-resolve"),

    path("statistics/", views.StatisticsView.as_view(), name="statistics"),
    path("export/", views.ExportView.as_view(), name="export"),
]
