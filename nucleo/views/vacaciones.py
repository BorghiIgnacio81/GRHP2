import logging
import math
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import render

from nucleo.models import (
    Empleado,
    Empleado_el,
    Estado_lic_vac,
    Solicitud_licencia,
    Solicitud_vacaciones,
    Vacaciones_otorgadas,
)
from nucleo.views.utils import calcular_antiguedad


logger = logging.getLogger(__name__)


def obtener_empleado_el_actual(empleado):
    """Devuelve el registro Empleado_el más reciente por ``fecha_el``.

    Si hay múltiples registros en la misma fecha se prioriza el ID más alto
    (registro creado más recientemente).
    """
    return (
        Empleado_el.objects.filter(idempleado=empleado)
        .order_by('-fecha_el', '-id')
        .first()
    )


def obtener_fecha_corte_generacion(year):
    """Devuelve la fecha de corte (fin de ciclo) para calcular días de vacaciones."""
    return date(year, 12, 31)


def calcular_dias_vacaciones(alta_ant, fecha_referencia=None):
    """
    Calcula días de vacaciones usando base 30/360 para proporcionalidades.
    - Todos los meses cuentan 30 días y el año 360.
    - Días 31 y 28/29 se ajustan a 30 antes del cálculo.
    - Mantiene los tramos tradicionales (14/21/28/35) según antigüedad real.
    """
    if not alta_ant:
        return 0

    if fecha_referencia is None:
        fecha_referencia = date.today()

    if alta_ant > fecha_referencia:
        return 0

    def _fecha_a_base_30(fecha):
        """Convierte una fecha a su equivalente en base 30/360."""
        dia = fecha.day
        if fecha.month == 2 and dia >= 28:
            dia = 30
        elif dia > 30:
            dia = 30
        return fecha.year * 360 + (fecha.month - 1) * 30 + dia

    dias_antiguedad_real = (fecha_referencia - alta_ant).days
    dias_antiguedad_base = max(_fecha_a_base_30(fecha_referencia) - _fecha_a_base_30(alta_ant), 0)
    corte_junio = date(fecha_referencia.year, 6, 1)

    def _dias_proporcionales():
        base = max(dias_antiguedad_base // 30, 0)
        resto = dias_antiguedad_base % 30
        if resto >= 15:
            base += 1
        return base

    if alta_ant.year == fecha_referencia.year:
        if alta_ant <= corte_junio:
            return 14
        return _dias_proporcionales()

    if dias_antiguedad_base < 180:
        return _dias_proporcionales()

    años = fecha_referencia.year - alta_ant.year - (
        (fecha_referencia.month, fecha_referencia.day) < (alta_ant.month, alta_ant.day)
    )
    if años < 5:
        return 14
    if años < 10:
        return 21
    if años < 20:
        return 28
    return 35


def consumir_dias_vacaciones(empleado, fecha_desde, fecha_hasta):
    """Descuenta los días solicitados de los periodos disponibles del empleado.

    Prioriza consumir días de periodos anteriores al año de la solicitud y luego
    del año actual. Si aún quedan días pendientes, registra un nuevo periodo con
    los días consumidos para mantener el historial consistente.
    """
    if not (empleado and fecha_desde and fecha_hasta):
        return 0

    dias_a_consumir = (fecha_hasta - fecha_desde).days + 1
    if dias_a_consumir <= 0:
        return 0

    year_actual = fecha_desde.year
    periodos_previos = Vacaciones_otorgadas.objects.filter(
        idempleado=empleado,
        inicio_consumo__lt=date(year_actual, 1, 1)
    ).order_by('inicio_consumo', 'pk')
    periodos_actuales = Vacaciones_otorgadas.objects.filter(
        idempleado=empleado,
        inicio_consumo__year=year_actual
    ).order_by('inicio_consumo', 'pk')

    restante = dias_a_consumir

    with transaction.atomic():
        for periodo in list(periodos_previos) + list(periodos_actuales):
            if restante <= 0:
                break
            disponibles_totales = periodo.dias_disponibles or 0
            consumidos = periodo.dias_consumidos or 0
            disponibles = max(disponibles_totales - consumidos, 0)
            if disponibles <= 0:
                continue
            a_consumir = min(disponibles, restante)
            if a_consumir <= 0:
                continue
            periodo.dias_consumidos = consumidos + a_consumir
            periodo.save(update_fields=['dias_consumidos'])
            restante -= a_consumir

        if restante > 0:
            Vacaciones_otorgadas.objects.create(
                idempleado=empleado,
                inicio_consumo=fecha_desde,
                fin_consumo=fecha_hasta,
                dias_disponibles=restante,
                dias_consumidos=restante,
            )

    return dias_a_consumir - restante


def aprobar_solicitud_vacaciones(solicitud, texto_gestor=None, enviar_notificacion=True):
    """Marca la solicitud como aprobada, consume los días y notifica al empleado."""
    if solicitud is None:
        raise ValueError("Solicitud de vacaciones inválida")

    estado_aceptada = Estado_lic_vac.objects.get(estado__iexact="Aceptada")
    solicitud.id_estado = estado_aceptada
    solicitud.save(update_fields=['id_estado'])

    dias_consumidos = consumir_dias_vacaciones(
        empleado=solicitud.idempleado,
        fecha_desde=solicitud.fecha_desde,
        fecha_hasta=solicitud.fecha_hasta,
    )

    if enviar_notificacion:
        from nucleo.utils_mail import enviar_mail_estado_licencia

        empleado = solicitud.idempleado
        usuario_empleado = getattr(empleado, 'idempleado', None)
        email = getattr(usuario_empleado, 'email', None)
        nombre_empleado = f"{empleado.nombres} {empleado.apellido}"
        if email:
            logger.info(
                "[VACACIONES] Enviando notificación de aprobación - solicitud=%s email=%s dias_consumidos=%s",
                solicitud.pk,
                email,
                dias_consumidos,
            )
            enviar_mail_estado_licencia(
                email=email,
                nombre_empleado=nombre_empleado,
                tipo="vacaciones",
                estado="Aceptada",
                texto_gestor=texto_gestor,
                fecha_desde=getattr(solicitud, 'fecha_desde', None),
                fecha_hasta=getattr(solicitud, 'fecha_hasta', None),
            )

    return dias_consumidos


def rechazar_solicitud_vacaciones(solicitud, motivo, enviar_notificacion=True):
    """Actualiza la solicitud con el rechazo y notifica al empleado."""
    if solicitud is None:
        raise ValueError("Solicitud de vacaciones inválida")

    estado_rechazada = Estado_lic_vac.objects.get(estado__iexact="Rechazada")
    comentario_actual = solicitud.comentario or ""
    motivo = (motivo or "").strip()

    if comentario_actual.strip() and motivo:
        comentario_final = f"{comentario_actual.strip()} - Motivo rechazo: {motivo}"
    elif motivo:
        comentario_final = f"Motivo rechazo: {motivo}"
    else:
        comentario_final = comentario_actual

    solicitud.id_estado = estado_rechazada
    solicitud.comentario = comentario_final
    solicitud.save(update_fields=['id_estado', 'comentario'])

    if enviar_notificacion:
        from nucleo.utils_mail import enviar_mail_estado_licencia

        empleado = solicitud.idempleado
        usuario_empleado = getattr(empleado, 'idempleado', None)
        email = getattr(usuario_empleado, 'email', None)
        nombre_empleado = f"{empleado.nombres} {empleado.apellido}"
        if email:
            logger.info(
                "[VACACIONES] Enviando notificación de rechazo - solicitud=%s email=%s motivo=%s",
                solicitud.pk,
                email,
                motivo,
            )
            enviar_mail_estado_licencia(
                email=email,
                nombre_empleado=nombre_empleado,
                tipo="vacaciones",
                estado="Rechazada",
                texto_gestor=motivo,
                fecha_desde=getattr(solicitud, 'fecha_desde', None),
                fecha_hasta=getattr(solicitud, 'fecha_hasta', None),
            )

    return comentario_final

@login_required
def generar_vacaciones(request):
    year = date.today().year
    generado = False
    empleados_data = []

    # Detectar si ya existen registros generados para este año
    already_generated = Vacaciones_otorgadas.objects.filter(inicio_consumo__year=year).exists()
    fecha_corte_calculo = obtener_fecha_corte_generacion(year)

    def build_empleados_data(empleados_qs):
        data = []
        for emp in empleados_qs:
            empleado_el_obj = obtener_empleado_el_actual(emp)
            if not empleado_el_obj:
                continue
            fecha_estado = empleado_el_obj.fecha_est or empleado_el_obj.fecha_el
            alta_ant = empleado_el_obj.alta_ant or fecha_estado
            dias_vacaciones = None
            # Preferir registro existente en Vacaciones_otorgadas para este año
            vac_ot = Vacaciones_otorgadas.objects.filter(idempleado=emp, inicio_consumo__year=year).first()
            if vac_ot:
                dias_vacaciones = vac_ot.dias_disponibles if vac_ot else 0
                dias_consumidos_reg = vac_ot.dias_consumidos if vac_ot else 0
                dias_consumidos = dias_consumidos_reg
                dias_disponibles = max(dias_vacaciones - dias_consumidos, 0)
            else:
                dias_vacaciones = calcular_dias_vacaciones(alta_ant, fecha_corte_calculo)
                dias_consumidos_reg = 0

            fecha_fin_ciclo = date(year, 12, 31)
            antiguedad_str = calcular_antiguedad(alta_ant, fecha_fin_ciclo)
            antiguedad_fin_ciclo_str = calcular_antiguedad(alta_ant, fecha_fin_ciclo)

            dias_consumidos = dias_consumidos_reg

            solicitudes = Solicitud_vacaciones.objects.filter(
                idempleado=emp, fecha_desde__year=year
            )
            vacaciones_solicitadas = sum(
                (s.fecha_hasta - s.fecha_desde).days + 1 for s in solicitudes
            )

            otorgadas_previas = Vacaciones_otorgadas.objects.filter(
                idempleado=emp, inicio_consumo__lt=date(year, 1, 1)
            )
            dias_permisados_previos = otorgadas_previas.aggregate(total=Sum('dias_disponibles'))['total'] or 0
            dias_consumidos_previos = otorgadas_previas.aggregate(total=Sum('dias_consumidos'))['total'] or 0
            dias_acumulados = max(dias_permisados_previos - dias_consumidos_previos, 0)

            periodo_vacaciones = f"01/10/{year} a 30/04/{year+1}"

            solicitud_vac = Solicitud_vacaciones.objects.filter(
                idempleado=emp,
                fecha_desde__year=year
            ).order_by('-fecha_desde').first()

            if solicitud_vac:
                periodo_solicitado = f"{solicitud_vac.fecha_desde.strftime('%d/%m/%Y')} a {solicitud_vac.fecha_hasta.strftime('%d/%m/%Y')}"
            else:
                periodo_solicitado = ""

            licencias_consumidas = Solicitud_licencia.objects.filter(
                idempleado=emp,
                id_estado__estado__iexact="Consumida"
            )
            dias_licencia = sum((l.fecha_hasta - l.fecha_desde).days + 1 for l in licencias_consumidas)

            # Disponibles para el año corriente: otorgados para el año menos consumidos en el año
            dias_disponibles = max((dias_vacaciones or 0) - (dias_consumidos or 0), 0)
            # Días disponibles es la resta entre otorgados y consumidos

            data.append({
                "nombre_apellido": f"{emp.nombres} {emp.apellido}",
                "alta": alta_ant,
                "antiguedad_reconocida": antiguedad_str,
                "dias_otorgados": dias_vacaciones,
                "dias_consumidos": dias_consumidos,
                "dias_disponibles": dias_disponibles,
                "vacaciones_solicitadas": vacaciones_solicitadas,
                "dias_acumulados": dias_acumulados,
                "periodo_vacaciones": periodo_vacaciones,
                "periodo_solicitado": periodo_solicitado,
                "dias_licencia": dias_licencia,
            })
        return data

    if request.method == "POST":
        # Si ya fue generado, requerimos el flag 'force' para sobrescribir
        force = request.POST.get('force') == '1'
        empleados = Empleado.objects.exclude(idempleado=1)
        if already_generated and not force:
            # En lugar de devolver sin datos, mostramos la tabla ya generada para que el usuario la vea
            empleados_data = build_empleados_data(empleados)
            return render(request, "nucleo/generar_vacaciones.html", {
                "year": year,
                "empleados": empleados_data,
                "generado": False,
                "already_generated": True,
            })
        # Si force y ya existían, NO borramos los registros para preservar dias_consumidos
        # Solo actualizaremos los dias_disponibles (otorgados)
        for emp in empleados:
            empleado_el_obj = obtener_empleado_el_actual(emp)
            if not empleado_el_obj:
                continue

            fecha_estado = empleado_el_obj.fecha_est or empleado_el_obj.fecha_el
            alta_ant = empleado_el_obj.alta_ant or fecha_estado
            dias_vacaciones = calcular_dias_vacaciones(alta_ant, fecha_corte_calculo)

            fecha_fin_ciclo = date(year, 12, 31)
            antiguedad_str = calcular_antiguedad(alta_ant, fecha_fin_ciclo)
            antiguedad_fin_ciclo_str = calcular_antiguedad(alta_ant, fecha_fin_ciclo)

            # Vacaciones solicitadas (solicitud_vacaciones)
            solicitudes = Solicitud_vacaciones.objects.filter(
                idempleado=emp, fecha_desde__year=year
            )
            vacaciones_solicitadas = sum(
                (s.fecha_hasta - s.fecha_desde).days + 1 for s in solicitudes
            )

            # Días acumulados (de años anteriores sin consumir)
            otorgadas_previas = Vacaciones_otorgadas.objects.filter(
                idempleado=emp, inicio_consumo__lt=date(year, 1, 1)
            )
            dias_permisados_previos = otorgadas_previas.aggregate(total=Sum('dias_disponibles'))['total'] or 0
            dias_consumidos_previos = otorgadas_previas.aggregate(total=Sum('dias_consumidos'))['total'] or 0
            dias_acumulados = max(dias_permisados_previos - dias_consumidos_previos, 0)

            periodo_vacaciones = f"01/10/{year} a 30/04/{year+1}"

            solicitud_vac = Solicitud_vacaciones.objects.filter(
                idempleado=emp,
                fecha_desde__year=year
            ).order_by('-fecha_desde').first()

            if solicitud_vac:
                periodo_solicitado = f"{solicitud_vac.fecha_desde.strftime('%d/%m/%Y')} a {solicitud_vac.fecha_hasta.strftime('%d/%m/%Y')}"
            else:
                periodo_solicitado = ""

            licencias_consumidas = Solicitud_licencia.objects.filter(
                idempleado=emp,
                id_estado__estado__iexact="Consumida"
            )
            dias_licencia = sum((l.fecha_hasta - l.fecha_desde).days + 1 for l in licencias_consumidas)

            # Crear o actualizar registro en Vacaciones_otorgadas para cada empleado y año
            # IMPORTANTE: Preservar dias_consumidos existentes, solo actualizar dias_disponibles
            vac_otorgada, created = Vacaciones_otorgadas.objects.get_or_create(
                idempleado=emp,
                inicio_consumo=date(year, 1, 1),
                fin_consumo=date(year, 12, 31),
                defaults={
                    'dias_disponibles': dias_vacaciones,
                    'dias_consumidos': 0,  # Solo para nuevos registros
                }
            )
            
            # Si el registro ya existía, solo actualizar dias_disponibles, preservar dias_consumidos
            if not created:
                vac_otorgada.dias_disponibles = dias_vacaciones
                # NO tocar vac_otorgada.dias_consumidos - preservar valor existente
                vac_otorgada.save()
                
            # Actualizar dias_consumidos para usar el valor correcto (preservado o 0 para nuevos)
            dias_consumidos = vac_otorgada.dias_consumidos

            dias_disponibles = max((dias_vacaciones or 0) - (dias_consumidos or 0), 0)

            empleados_data.append({
                "nombre_apellido": f"{emp.nombres} {emp.apellido}",
                "alta": alta_ant,
                "antiguedad_reconocida": antiguedad_str,
                "dias_otorgados": dias_vacaciones,
                "dias_consumidos": dias_consumidos,
                "dias_disponibles": dias_disponibles,
                "vacaciones_solicitadas": vacaciones_solicitadas,
                "dias_acumulados": dias_acumulados,
                "periodo_vacaciones": periodo_vacaciones,
                "periodo_solicitado": periodo_solicitado,
                "dias_licencia": dias_licencia,
            })
        # Marca que se generó en esta llamada POST
        generado = True

        return render(request, "nucleo/generar_vacaciones.html", {
            "year": year,
            "empleados": empleados_data,
            "generado": generado,
            "already_generated": already_generated,
        })
        
    # Si es GET y ya existen registros generados, mostramos la tabla existente
    if request.method != "POST" and already_generated:
        empleados = Empleado.objects.exclude(idempleado=1)
        empleados_data = build_empleados_data(empleados)
        return render(request, "nucleo/generar_vacaciones.html", {
            "year": year,
            "empleados": empleados_data,
            "generado": False,
            "already_generated": True,
        })

    return render(request, "nucleo/generar_vacaciones.html", {
        "year": year,
        "empleados": empleados_data,
        "generado": False,
        "already_generated": already_generated,
    })
