from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from hotel.api.views import health
from hotel.api.auth import register, login, logout, refresh_token, me
from hotel.api.operations import dashboard, reports, guest_list, room_types, rooms, employees, services, bookings, booking_status, booking_services, booking_bill, payments, service_requests, staff_dashboard, audit_logs, staff_accounts

urlpatterns = [
    path('api/health', health),
    path('api/auth/register', register), path('api/auth/login', login), path('api/auth/logout', logout), path('api/auth/refresh', refresh_token), path('api/auth/me', me),
    path('api/dashboard', dashboard), path('api/reports', reports),
    path('api/guests', guest_list), path('api/guests/<str:record_id>', guest_list), path('api/room-types', room_types), path('api/room-types/<str:record_id>', room_types), path('api/rooms', rooms), path('api/rooms/availability', rooms), path('api/rooms/<str:record_id>', rooms),
    path('api/employees', employees), path('api/services', services), path('api/services/<str:record_id>', services),
    path('api/bookings', bookings), path('api/bookings/dues', bookings), path('api/bookings/<str:record_id>/status', booking_status), path('api/bookings/<str:record_id>/services', booking_services), path('api/bookings/<str:record_id>/bill', booking_bill), path('api/bookings/<str:record_id>', bookings),
    path('api/payments', payments),
    path('api/service-requests', service_requests), path('api/service-requests/<str:record_id>', service_requests),
    path('api/staff/dashboard', staff_dashboard), path('api/admin/audit-logs', audit_logs),
    path('api/admin/staff', staff_accounts), path('api/admin/staff/<str:record_id>', staff_accounts),
    path('api/schema', SpectacularAPIView.as_view(), name='schema'), path('api/docs', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
