from django.views.decorators.cache import never_cache
import logging
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from datetime import date
from django.db import models
from nucleo.models import Solicitud_licencia, Solicitud_vacaciones, Vacaciones_otorgadas, Empleado_el, Empleado
from nucleo.views.utils import (
    actualizar_licencias_consumidas,
    actualizar_vacaciones_consumidas,
)
from nucleo.models.licencias import eliminar_licencias_discontinuadas_sin_solicitudes

@never_cache
def login_view(request):
    password_reset_success = request.GET.get("password_reset_success") == "1"
    show_logout_modal = request.GET.get("logout_modal") == "1"

    # Si un usuario autenticado intenta un nuevo login vía POST, cerrar la sesión previa
    if request.user.is_authenticated and request.method == "POST":
        logout(request)

    if request.user.is_authenticated:
        if request.method == "GET":
            return render(
                request,
                "nucleo/login.html",
                {
                    "show_logout_modal": show_logout_modal,
                    "current_user": request.user,
                    "password_reset_success": password_reset_success,
                },
            )
        if request.user.is_staff:
            return redirect('nucleo:dashboard_gestor')
        return redirect('nucleo:dashboard_empleado')

    error_message = None
    blocked_message = None
    show_block_modal = False

    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        failed_attempts = _get_failed_attempts(request)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            _reset_failed_attempts(request)

            try:
                empleado_obj = Empleado.objects.filter(idempleado=user).first()
                if not empleado_obj and not user.is_staff:
                    error_message = (
                        "Tu usuario aún no está vinculado a un legajo de empleado. "
                        "Contactá con Recursos Humanos para completar el alta."
                    )
                    return render(request, "nucleo/login.html", {
                        "error_message": error_message,
                        "password_reset_success": password_reset_success,
                    })

                block_result = _check_employee_status(user)
                if block_result:
                    blocked_message = block_result
                    try:
                        logout(request)
                    except Exception:
                        pass
                    return render(request, "nucleo/login.html", {
                        "error_message": None,
                        "blocked_message": blocked_message,
                        "password_reset_success": password_reset_success,
                    })
            except Exception:
                pass

            login(request, user)
            if user.is_staff:
                return redirect('nucleo:dashboard_gestor')
            return redirect('nucleo:dashboard_empleado')

        failed_attempts += 1
        _set_failed_attempts(request, failed_attempts)
        if failed_attempts >= 3:
            show_block_modal = True
        else:
            error_message = "Por favor ingrese Usuario o password correcto"

    return render(request, "nucleo/login.html", {
        "error_message": error_message,
        "blocked_message": blocked_message,
        "show_block_modal": show_block_modal,
        "password_reset_success": password_reset_success,
    })


def _get_failed_attempts(request):
    return request.session.get('login_failed_attempts', 0)


def _set_failed_attempts(request, attempts):
    request.session['login_failed_attempts'] = attempts


def _reset_failed_attempts(request):
    if 'login_failed_attempts' in request.session:
        del request.session['login_failed_attempts']


def _check_employee_status(user):
    try:
        empleado_obj = Empleado.objects.filter(idempleado=user).first()
        if empleado_obj:
            el_latest = Empleado_el.objects.filter(idempleado=empleado_obj).order_by('-fecha_el', '-id').first()
            estado_id = getattr(getattr(el_latest, 'id_estado', None), 'id_estado', None) if el_latest else None
            try:
                with open('/tmp/login_blocked_debug.log', 'a') as _f:
                    _f.write(f"LOGIN_CHECK user={getattr(user,'username',None)} empleado_id={getattr(empleado_obj,'idempleado_id',None)} estado_id={estado_id}\n")
            except Exception:
                pass
            if estado_id == 2:
                return (
                    "Usted ha sido dado de baja, por lo que se le ha bloqueado el ingreso, "
                    "para mas informacion comuniquese con nosotros a traves de \n"
                    "farmaciagomezdegalarze@gmail.com"
                )
    except Exception:
        pass
    return None

def profile(request):
    return render(request, 'nucleo/profile.html')


@login_required
def mi_perfil(request):
    # Mostrar ficha de solo lectura del empleado logueado
    user = request.user
    empleado = Empleado.objects.filter(idempleado=user).first()

    perfil = None
    if empleado:
        # Campos básicos y copia de relaciones
        perfil = {
            'nombres': getattr(empleado, 'nombres', ''),
            'apellido': getattr(empleado, 'apellido', ''),
            'dni': getattr(empleado, 'dni', ''),
            'email': getattr(user, 'email', ''),
            'telefono': getattr(empleado, 'telefono', ''),
            'puesto': '',
            'fecha_alta': None,
            'fecha_nac': getattr(empleado, 'fecha_nac', None),
            'cuil': getattr(empleado, 'cuil', ''),
            'dr_personal': getattr(empleado, 'dr_personal', ''),
            'num_hijos': getattr(empleado, 'num_hijos', ''),
        }

        # Relaciones por defecto (se sobrescriben si encontramos registros)
        perfil.update({
            'nacionalidad': '',
            'estado_civil': '',
            'sexo': '',
            'plan_trabajo': '',
            'dias_trabajo': '',
            'horario_inicio': '',
            'horario_fin': '',
            'sucursal_direccion': '',
            'sucursal_mail': '',
            'sucursal': '',
            'estado': '',
            'localidad': '',
            'provincia': '',
            'convenio': '',
            'fecha_est': None,
            'alta_ant': None,
            'is_gestor': request.user.is_staff,
        })

        # Formateos legibles (máscaras)
        def mask_dni(dni_raw):
            try:
                s = ''.join(ch for ch in str(dni_raw) if ch.isdigit())
                if len(s) <= 2:
                    return s
                if len(s) <= 5:
                    return f"{s[:2]}.{s[2:]}"
                if len(s) <= 8:
                    return f"{s[:-6]}.{s[-6:-3]}.{s[-3:]}"
                return s
            except Exception:
                return str(dni_raw)

        def mask_cuil(cuil_raw):
            try:
                s = ''.join(ch for ch in str(cuil_raw) if ch.isdigit())
                if len(s) == 11:
                    # formato esperado: AA-BB.CCC.DDD-E -> 20-12.345.678-9
                    return f"{s[0:2]}-{s[2:4]}.{s[4:7]}.{s[7:10]}-{s[10]}"
                return str(cuil_raw)
            except Exception:
                return str(cuil_raw)

        perfil['dni_masked'] = mask_dni(perfil.get('dni', ''))
        perfil['cuil_masked'] = mask_cuil(perfil.get('cuil', ''))

        # Extraer relaciones directas si existen
        try:
            if getattr(empleado, 'id_localidad', None):
                perfil['localidad'] = empleado.id_localidad.localidad
                perfil['provincia'] = empleado.id_localidad.provincia.provincia
        except Exception:
            pass

        try:
            perfil['nacionalidad'] = getattr(empleado.id_nacionalidad, 'nacionalidad', '')
        except Exception:
            pass
        try:
            perfil['estado_civil'] = getattr(empleado.id_civil, 'estado_civil', '')
        except Exception:
            pass
        try:
            perfil['sexo'] = getattr(empleado.id_sexo, 'sexo', '')
        except Exception:
            pass

        # Sucursal más reciente
        try:
            from nucleo.models import Empleado_eo, Plan_trabajo as PlanModel
            eo = Empleado_eo.objects.filter(idempleado=empleado).order_by('-fecha_eo').first()
            if eo and getattr(eo, 'id_sucursal', None):
                suc = eo.id_sucursal
                perfil['sucursal'] = getattr(suc, 'sucursal', '')
                perfil['sucursal_direccion'] = getattr(suc, 'suc_dire', '')
                perfil['sucursal_mail'] = getattr(suc, 'suc_mail', '')
        except Exception:
            pass

        # Estado laboral / puesto / convenio / fechas desde Empleado_el (último)
        try:
            emp_el = Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el', '-id').first()
            if emp_el:
                perfil['estado'] = getattr(emp_el.id_estado, 'estado', '')
                perfil['puesto'] = getattr(emp_el.id_puesto, 'tipo_puesto', '')
                perfil['convenio'] = getattr(emp_el.id_convenio, 'tipo_convenio', '')
                perfil['fecha_est'] = getattr(emp_el, 'fecha_est', None) or getattr(emp_el, 'fecha_el', None)
                perfil['fecha_alta'] = getattr(emp_el, 'fecha_el', None)
                perfil['alta_ant'] = getattr(emp_el, 'alta_ant', None)
        except Exception:
            pass

        # Plan de trabajo legible
        try:
            plan = PlanModel.objects.filter(idempleado=empleado).order_by('-id').first()
            if plan:
                days_order = ['lunes','martes','miercoles','jueves','viernes','sabado','domingo']
                selected = [d for d in days_order if getattr(plan, d, False)]
                def cap(s):
                    return s.capitalize()
                if selected:
                    idxs = [days_order.index(d) for d in selected]
                    if max(idxs) - min(idxs) + 1 == len(idxs):
                        label_days = f"de {cap(days_order[min(idxs)])} a {cap(days_order[max(idxs)])}"
                    else:
                        label_days = ', '.join(cap(d) for d in selected)
                else:
                    label_days = ''
                # populate separate fields for template
                perfil['dias_trabajo'] = label_days or ''
                if getattr(plan, 'start_time', None):
                    try:
                        perfil['horario_inicio'] = plan.start_time.strftime('%H:%M')
                    except Exception:
                        perfil['horario_inicio'] = str(plan.start_time)
                else:
                    perfil['horario_inicio'] = ''
                if getattr(plan, 'end_time', None):
                    try:
                        perfil['horario_fin'] = plan.end_time.strftime('%H:%M')
                    except Exception:
                        perfil['horario_fin'] = str(plan.end_time)
                else:
                    perfil['horario_fin'] = ''
                # also keep a combined human-readable plan_trabajo for compatibility
                horario = ''
                if perfil['horario_inicio'] and perfil['horario_fin']:
                    horario = f"de {perfil['horario_inicio']} a {perfil['horario_fin']}"
                perfil['plan_trabajo'] = f"{label_days} {horario}".strip()
        except Exception:
            pass

    return render(request, 'nucleo/mi_perfil.html', {'perfil': perfil, 'empleado': empleado})

@login_required
def dashboard_empleado(request):
    actualizar_licencias_consumidas()
    actualizar_vacaciones_consumidas()
    eliminar_licencias_discontinuadas_sin_solicitudes()
    user = request.user
    empleado = Empleado.objects.get(idempleado=user)
    # Licencias (contar días, no solicitudes)
    # Licencias (contar solicitudes por estado)
    licencias = Solicitud_licencia.objects.filter(idempleado=empleado)

    lic_aprobadas = licencias.filter(id_estado__estado__iexact="Aceptada").count()
    lic_espera = licencias.filter(id_estado__estado__iexact="En espera").count()
    lic_rechazadas = licencias.filter(id_estado__estado__iexact="Rechazada").count()

    # Vacaciones
    year = date.today().year
    empleado_el = Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el').first()
    alta_ant = empleado_el.alta_ant if empleado_el else None

    from nucleo.views.vacaciones import calcular_dias_vacaciones
    # Use actual Vacaciones_otorgadas DB values when present (prefer authoritative source)
    vac_agg = Vacaciones_otorgadas.objects.filter(idempleado=empleado, inicio_consumo__year=year).aggregate(
        total_otorgados=models.Sum('dias_disponibles'),
        total_consumidos=models.Sum('dias_consumidos')
    )
    total_otorgados = vac_agg.get('total_otorgados') or 0
    total_consumidos = vac_agg.get('total_consumidos') or 0
    # Subtract also the days currently in 'En espera' from disponibles
    # Compute total 'En espera' days overlapping the year for this empleado
    from datetime import date as _date
    start_of_year = _date(year, 1, 1)
    end_of_year = _date(year, 12, 31)
    solicitudes_vac_all = Solicitud_vacaciones.objects.filter(idempleado=empleado)
    dias_espera = 0
    for s in solicitudes_vac_all:
        inicio = s.fecha_desde
        fin = s.fecha_hasta
        overlap_start = inicio if inicio >= start_of_year else start_of_year
        overlap_end = fin if fin <= end_of_year else end_of_year
        if overlap_start and overlap_end and overlap_start <= overlap_end:
            dias = (overlap_end - overlap_start).days + 1
            estado = (getattr(getattr(s, 'id_estado', None), 'estado', '') or '').strip().lower()
            if estado == 'en espera' or estado == 'espera':
                dias_espera += dias

    dias_disponibles = max(int(total_otorgados) - int(total_consumidos) - int(dias_espera), 0)

    # Compute requested/approved/waiting days overlapping the year (better than filtering by fecha_desde__year)
    from datetime import date as _date
    start_of_year = _date(year, 1, 1)
    end_of_year = _date(year, 12, 31)
    solicitudes_vac_all = Solicitud_vacaciones.objects.filter(idempleado=empleado)
    dias_solicitados = 0
    dias_aprobadas = 0
    dias_espera = 0
    for s in solicitudes_vac_all:
        # determine overlap with current year
        inicio = s.fecha_desde
        fin = s.fecha_hasta
        overlap_start = inicio if inicio >= start_of_year else start_of_year
        overlap_end = fin if fin <= end_of_year else end_of_year
        if overlap_start and overlap_end and overlap_start <= overlap_end:
            dias = (overlap_end - overlap_start).days + 1
            dias_solicitados += dias
            estado = (getattr(getattr(s, 'id_estado', None), 'estado', '') or '').strip().lower()
            if estado == 'aceptada' or estado == 'aprobada':
                dias_aprobadas += dias
            elif estado == 'en espera' or estado == 'espera':
                dias_espera += dias
    dias_consumidos = int(total_consumidos)

    # Licencias por año (últimos 5 años)
    licencias_por_anio = []
    anios = range(year-4, year+1)
    for anio in anios:
        licencias_anio = licencias.filter(fecha_desde__year=anio)
        dias = sum((lic.fecha_hasta - lic.fecha_desde).days + 1 for lic in licencias_anio)
        licencias_por_anio.append(dias)

    context = {
        "lic_aprobadas": lic_aprobadas,
        "lic_espera": lic_espera,
        "lic_rechazadas": lic_rechazadas,
        "dias_disponibles": dias_disponibles,
        "dias_consumidos": dias_consumidos,
        "dias_solicitados": dias_solicitados,
        # Chart segments expected by template
        "dias_aprobadas": dias_aprobadas,
        "dias_espera": dias_espera,
        "licencias_por_anio": licencias_por_anio,
        "anios": list(anios),
        # Datos estructurados para dashboard modularizado
        "mis_licencias": {
            "aprobadas": lic_aprobadas,
            "espera": lic_espera,
            "rechazadas": lic_rechazadas,
        },
        "mis_vacaciones": {
            "disponibles": dias_disponibles,
            "espera": dias_espera,
            "aprobadas": dias_aprobadas,
        },
    }
    # DEBUG: volcar métricas a /tmp para inspección si es necesario
    try:
        import json, os
        emp_id = getattr(empleado, 'idempleado_id', getattr(empleado, 'pk', 'anon'))
        dump_path = f"/tmp/dashboard_empleado_{emp_id}.json"
        # also include detailed solicitudes for debugging
        solicitudes_debug = []
        for s in Solicitud_vacaciones.objects.filter(idempleado=empleado):
            inicio = s.fecha_desde
            fin = s.fecha_hasta
            overlap_start = inicio if inicio >= start_of_year else start_of_year
            overlap_end = fin if fin <= end_of_year else end_of_year
            dias_overlap = 0
            if overlap_start and overlap_end and overlap_start <= overlap_end:
                dias_overlap = (overlap_end - overlap_start).days + 1
            solicitudes_debug.append({
                'pk': s.pk,
                'fecha_desde': str(s.fecha_desde),
                'fecha_hasta': str(s.fecha_hasta),
                'estado': getattr(getattr(s, 'id_estado', None), 'estado', None),
                'dias_overlap': dias_overlap,
            })
        with open(dump_path, 'w') as f:
            json.dump({**{k: context.get(k) for k in ['dias_disponibles','dias_consumidos','dias_aprobadas','dias_espera','dias_solicitados']}, 'solicitudes': solicitudes_debug}, f)
    except Exception:
        pass
    return render(request, "nucleo/dashboard_empleado.html", context)

@login_required
def dashboard_gestor(request):
    actualizar_licencias_consumidas()
    actualizar_vacaciones_consumidas()
    eliminar_licencias_discontinuadas_sin_solicitudes()

    def suma_dias(qs):
        total = 0
        for solicitud in qs:
            fecha_desde = getattr(solicitud, "fecha_desde", None)
            fecha_hasta = getattr(solicitud, "fecha_hasta", fecha_desde)
            if not fecha_desde:
                continue
            if not fecha_hasta or fecha_hasta < fecha_desde:
                fecha_hasta = fecha_desde
            total += (fecha_hasta - fecha_desde).days + 1
        return total

    # Licencias de toda la plantilla (contar solicitudes por estado)
    licencias = Solicitud_licencia.objects.all()
    lic_aprobadas = licencias.filter(id_estado__estado__iexact="Aceptada").count()
    lic_espera = licencias.filter(id_estado__estado__iexact="En espera").count()
    lic_rechazadas = licencias.filter(id_estado__estado__iexact="Rechazada").count()

    # Vacaciones de toda la plantilla (año actual)
    year = date.today().year
    empleados = Empleado.objects.all()
    from nucleo.views.vacaciones import calcular_dias_vacaciones

    # Vacaciones por estado (general) - sumar días, no cantidad de solicitudes
    # NOTA: Las solicitudes aceptadas ya están incluidas en dias_consumidos de Vacaciones_otorgadas
    # Por lo tanto, NO deben mostrarse por separado para evitar duplicación
    vac_aprobadas_qs = Solicitud_vacaciones.objects.filter(fecha_desde__year=year, id_estado__estado__iexact="Aceptada")
    vac_espera_qs = Solicitud_vacaciones.objects.filter(fecha_desde__year=year, id_estado__estado__iexact="En espera")
    vac_rechazadas = Solicitud_vacaciones.objects.filter(fecha_desde__year=year, id_estado__estado__iexact="Rechazada").count()

    # Aggregate Vacaciones_otorgadas across all employees for the year
    vac_agg_all = Vacaciones_otorgadas.objects.filter(inicio_consumo__year=year).aggregate(
        total_otorgados=models.Sum('dias_disponibles'),
        total_consumidos=models.Sum('dias_consumidos')
    )
    total_otorgados_all = vac_agg_all.get('total_otorgados') or 0
    total_consumidos_all = vac_agg_all.get('total_consumidos') or 0
    
    # vac_aprobadas = 0  # Comentado: necesitamos mostrar días aprobados/consumidos
    vac_aprobadas = int(total_consumidos_all)  # Días ya consumidos/aprobados
    vac_espera = suma_dias(vac_espera_qs)
    
    # Calcular días disponibles: días otorgados menos días consumidos menos días en espera
    dias_disponibles = max(int(total_otorgados_all) - int(total_consumidos_all) - int(vac_espera), 0)

    # Solicitudes totals (days requested) across all employees
    dias_solicitados = 0
    for emp in empleados:
        solicitudes_vac = Solicitud_vacaciones.objects.filter(idempleado=emp, fecha_desde__year=year)
        dias_solicitados += sum((s.fecha_hasta - s.fecha_desde).days + 1 for s in solicitudes_vac)
    dias_consumidos = int(total_consumidos_all)

    context = {
        "lic_aprobadas": lic_aprobadas,
        "lic_espera": lic_espera,
        "lic_rechazadas": lic_rechazadas,
        "vac_aprobadas": vac_aprobadas,
        "vac_espera": vac_espera,
        "vac_rechazadas": vac_rechazadas,
        "dias_disponibles": dias_disponibles,
        "dias_consumidos": dias_consumidos,
        "dias_solicitados": dias_solicitados,
    }
    # DEBUG: dump gestor dashboard metrics
    try:
        import json
        dump_path = "/tmp/dashboard_gestor.json"
        with open(dump_path, 'w') as f:
            json.dump({
                'dias_disponibles': context.get('dias_disponibles'),
                'dias_consumidos': context.get('dias_consumidos'),
                'vac_aprobadas': context.get('vac_aprobadas'),
                'vac_espera': context.get('vac_espera'),
                'total_otorgados_all': int(total_otorgados_all),
                'total_consumidos_all': int(total_consumidos_all),
                'calculo_disponibles': f"{int(total_otorgados_all)} - {int(total_consumidos_all)} = {dias_disponibles}"
            }, f)
    except Exception:
        pass
    # Mis licencias: métricas del gestor actual (si existe un Empleado asociado al user)
    emp_gestor = Empleado.objects.filter(idempleado=request.user).first()
    if emp_gestor:
        mis_licencias = Solicitud_licencia.objects.filter(idempleado=emp_gestor)
        mis_lic_aprobadas = mis_licencias.filter(id_estado__estado__iexact="Aceptada").count()
        mis_lic_espera = mis_licencias.filter(id_estado__estado__iexact="En espera").count()
        mis_lic_rechazadas = mis_licencias.filter(id_estado__estado__iexact="Rechazada").count()
        # Mis Vacaciones: sumar por estado y calcular disponibles
        mis_vacaciones = Solicitud_vacaciones.objects.filter(idempleado=emp_gestor, fecha_desde__year=year)
        # Calculamos días en vez de contar solicitudes
        mis_vac_aprobadas_qs = mis_vacaciones.filter(id_estado__estado__iexact="Aceptada")
        mis_vac_espera_qs = mis_vacaciones.filter(id_estado__estado__iexact="En espera")
        mis_vac_rechazadas_qs = mis_vacaciones.filter(id_estado__estado__iexact="Rechazada")
        
        # Usar suma_dias para contar días totales en vez del número de solicitudes
        mis_vac_aprobadas = suma_dias(mis_vac_aprobadas_qs)
        mis_vac_espera = suma_dias(mis_vac_espera_qs)
        mis_vac_rechazadas = suma_dias(mis_vac_rechazadas_qs)
        
        mis_vac_agg = Vacaciones_otorgadas.objects.filter(idempleado=emp_gestor, inicio_consumo__year=year).aggregate(
            total_otorgados=models.Sum('dias_disponibles'),
            total_consumidos=models.Sum('dias_consumidos')
        )
        # Calcular mis días disponibles: días otorgados menos días consumidos
        # Los días aprobados ya están incluidos en dias_consumidos cuando se actualizan
        # Also subtract pending (en espera) days from the manager's own disponibles
        mis_vac_disponibles = max((mis_vac_agg.get('total_otorgados') or 0) - (mis_vac_agg.get('total_consumidos') or 0) - int(mis_vac_espera or 0), 0)
    else:
        mis_lic_aprobadas = mis_lic_espera = mis_lic_rechazadas = 0
        mis_vac_aprobadas = mis_vac_espera = mis_vac_rechazadas = 0
        mis_vac_disponibles = 0

    # Log mis-licencias y mis-vacaciones para debug
    logger = logging.getLogger(__name__)
    try:
        logger.info(
            "dashboard_gestor: mis_lic_aprobadas=%s mis_lic_espera=%s mis_lic_rechazadas=%s mis_vac_aprobadas=%s mis_vac_espera=%s mis_vac_rechazadas=%s mis_vac_disponibles=%s",
            mis_lic_aprobadas,
            mis_lic_espera,
            mis_lic_rechazadas,
            mis_vac_aprobadas,
            mis_vac_espera,
            mis_vac_rechazadas,
            mis_vac_disponibles,
        )
        # Guardar también información detallada en archivo para debug
        import json
        try:
            dump_path = "/tmp/mis_vacaciones_debug.json"
            with open(dump_path, 'w') as f:
                json.dump({
                    'mis_vac_disponibles': mis_vac_disponibles,
                    'mis_vac_aprobadas': mis_vac_aprobadas,
                    'mis_vac_espera': mis_vac_espera,
                    'mis_vac_rechazadas': mis_vac_rechazadas
                }, f)
        except Exception:
            pass
    except Exception:
        pass

    show_mis_licencias = request.user.id != 1
    context.update({
        "mis_lic_aprobadas": mis_lic_aprobadas,
        "mis_lic_espera": mis_lic_espera,
        "mis_lic_rechazadas": mis_lic_rechazadas,
        "mis_vac_aprobadas": mis_vac_aprobadas,
        "mis_vac_espera": mis_vac_espera,
        "mis_vac_rechazadas": mis_vac_rechazadas,
        "mis_vac_disponibles": mis_vac_disponibles,
        "show_mis_licencias": show_mis_licencias,
    })
    return render(request, "nucleo/dashboard_gestor.html", context)