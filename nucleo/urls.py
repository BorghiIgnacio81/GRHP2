from django.urls import path

# Necesario para namespacing en templates
app_name = 'nucleo'
from django.contrib.auth.views import LogoutView
from nucleo.views import (
    AltaEmpleadoWizard, password_reset_request, solicitar_licencia,
    consultar_licencia, gestion_reporte_licencias, alta_tipo_licencia, modificar_borrar_licencia,
    alta_feriado, modificar_borrar_feriado, crear_localidad, detalle_licencia, mi_perfil, ver_empleados, buscar_empleados_ajax
)
from nucleo.views.empleados import ver_log_auditoria
from nucleo.views.licencias import eliminar_solicitud, ver_feriados
from nucleo.views.crud_tipo_licencia import ver_tipo_licencia
from nucleo.views.vacaciones import generar_vacaciones
from nucleo.views.utils import localidades_por_provincia, buscar_localidades, direccion_sucursal


from nucleo import views
from nucleo.views import ajax

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard_empleado, name='dashboard_empleado'),
    path('dashboard_gestor/', views.dashboard_gestor, name='dashboard_gestor'),
    path('logout/', LogoutView.as_view(next_page='nucleo:login'), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('empleados/alta/', AltaEmpleadoWizard.as_view(), name='alta_empleado'),
    path('ajax/localidades/', buscar_localidades, name='ajax_localidades'),
    path('ajax/crear_localidad/', crear_localidad, name='ajax_crear_localidad'),
    path('ajax/direccion_sucursal/', direccion_sucursal, name='ajax_direccion_sucursal'),
    path('empleados/modificar/', views.modificar_borrar_empleado, name='modificar_borrar_empleado'),
    path('empleados/modificar/<int:empleado_id>/', views.modificar_borrar_empleado, name='modificar_borrar_empleado_id'),
    path('ajax/buscar_empleados/', buscar_empleados_ajax, name='buscar_empleados_ajax'),
    # path('actualizar_empleado_ajax/<int:empleado_id>/', views.actualizar_empleado_ajax, name='actualizar_empleado_ajax'),  # Eliminado - función no existe
    path('ajax/get_is_staff/', ajax.get_is_staff, name='ajax_get_is_staff'),
    path('password_reset/', password_reset_request, name='password_reset'),
    path('solicitar_licencia/', solicitar_licencia, name='solicitar_licencia'),  
    path('consultar_licencia/', consultar_licencia, name='consultar_licencia'),
    path('gestion_reporte_licencias/', gestion_reporte_licencias, name='gestion_reporte_licencias'),
    path('gestionar_estado_solicitud/', views.gestionar_estado_solicitud, name='gestionar_estado_solicitud'),
    path('gestion_solicitudes/', views.gestionar_solicitudes, name='gestion_solicitudes'),
    path('detalle_licencia/<int:solicitud_id>/', detalle_licencia, name='detalle_licencia'),
    path('eliminar_solicitud/', eliminar_solicitud, name='eliminar_solicitud'),
    path('alta_tipo_licencia/', alta_tipo_licencia, name='alta_tipo_licencia'),
    path('modificar_borrar_licencia/', modificar_borrar_licencia, name='modificar_borrar_licencia'),
    path('ver_tipo_licencia/', ver_tipo_licencia, name='ver_tipo_licencia'),
    path('alta_feriado/', alta_feriado, name='alta_feriado'),
    path('modificar_borrar_feriado/', modificar_borrar_feriado, name='modificar_borrar_feriado'),
    path('ver_feriados/', ver_feriados, name='ver_feriados'),
    path('generar_vacaciones/', generar_vacaciones, name='generar_vacaciones'),
    path('emitir_certificado/<int:empleado_id>/', views.emitir_certificado, name='emitir_certificado'),
    path('ver_empleados/', ver_empleados, name='ver_empleados'),
    path('exportar_empleados_excel/', views.exportar_empleados_excel, name='exportar_empleados_excel'),
    path('log_auditoria/', ver_log_auditoria, name='log_auditoria'),
    path('mi_perfil/', mi_perfil, name='mi_perfil'),  # Agregado - función existe
]