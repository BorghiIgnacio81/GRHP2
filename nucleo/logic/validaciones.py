from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone

from nucleo.models import Feriado, Plan_trabajo, Solicitud_licencia, Estado_lic_vac


class ValidacionError(Exception):
    def __init__(self, motivo):
        super().__init__(motivo)
        self.motivo = motivo


def fecha_en_pasado(fecha_desde):
    hoy = date.today()
    return fecha_desde < hoy


def incluye_feriado(fecha_desde, fecha_hasta):
    return Feriado.objects.filter(fecha__range=(fecha_desde, fecha_hasta)).exists()


def dias_feriados_en_rango(fecha_desde, fecha_hasta):
    return list(Feriado.objects.filter(fecha__range=(fecha_desde, fecha_hasta)).values_list('fecha', flat=True))


def empleado_trabaja_en_rango(empleado, fecha_desde, fecha_hasta):
    # devuelve lista de dias de la semana (0=lunes) que el empleado NO trabaja
    plan = Plan_trabajo.objects.filter(idempleado=empleado).first()
    if not plan:
        # si no hay plan, asumimos que trabaja todos los días
        return True, []
    dias_no_trabaja = []
    current = fecha_desde
    dias = []
    while current <= fecha_hasta:
        weekday = current.weekday()  # 0=lunes
        trabaja = [plan.lunes, plan.martes, plan.miercoles, plan.jueves, plan.viernes, plan.sabado, plan.domingo][weekday]
        if not trabaja:
            dias_no_trabaja.append(current)
        dias.append((current, trabaja))
        current += timedelta(days=1)
    # True si hay al menos un dia laboral en el rango
    hay_dia_laboral = any(trabaja for (_, trabaja) in dias)
    return hay_dia_laboral, dias_no_trabaja


def solapa_con_licencia_existente(empleado, fecha_desde, fecha_hasta):
    # (Legacy) Esta función se reemplaza por lógica en validar_solicitud_licencia.
    # Mantener una implementación simple por compatibilidad: buscar cualquier solapamiento
    qs = Solicitud_licencia.objects.filter(idempleado=empleado)
    for s in qs:
        if not (s.fecha_hasta < fecha_desde or s.fecha_desde > fecha_hasta):
            return True, s
    return False, None


@transaction.atomic

def validar_solicitud_licencia(solicitud):
    """
    Valida una instancia de Solicitud_licencia antes de aceptarla.
    Reglas implementadas según requerimiento del cliente.

    Lanza ValidacionError con motivo si la solicitud debe ser rechazada.
    Devuelve una tupla (aceptable, warnings) donde acceptable es True/False
    y warnings es lista de strings.
    """
    warnings = []
    hoy = date.today()
    fd = solicitud.fecha_desde
    fh = solicitud.fecha_hasta

    # No permitir fechas en el pasado
    if fecha_en_pasado(fd) or fecha_en_pasado(fh):
        raise ValidacionError('fechas en el pasado')

    # Regla 1: feriados
    feriados = dias_feriados_en_rango(fd, fh)
    total_dias = (fh - fd).days + 1
    if feriados:
        # Tests expect the phrase 'contiene feriado' in messages/warnings.
        if total_dias == len(feriados):
            raise ValidacionError('contiene feriado')
        else:
            warnings.append('contiene feriado')

    # Regla 2 & 3: plan_trabajo (no laboral)
    hay_laboral, dias_no_trabaja = empleado_trabaja_en_rango(solicitud.idempleado, fd, fh)
    if not hay_laboral:
        # si todos los dias son no laborales -> rechazar
        raise ValidacionError('es su día libre')
    # Solo warning si hay día libre y NO hay feriado
    if dias_no_trabaja and not feriados:
        warnings.append('es su día libre')

    # Regla 4 (opcional): minimo 1 dia hábil
    if not hay_laboral:
        raise ValidacionError('no cubre días hábiles')

    # Regla 6: colisiones con otras solicitudes/aprobadas
    from django.db.models import Q
    from nucleo.models import Solicitud_licencia as SL, Solicitud_vacaciones as SV
    aprobado_q = Q(id_estado__estado__iexact='Aceptada') | Q(id_estado__estado__iexact='Aprobada')

    # 6a) Misma persona: si solapa con una solicitud VACÍA o LICENCIA aprobada -> rechazar
    same_lic_aprobada = SL.objects.filter(
        idempleado=solicitud.idempleado
    ).filter(aprobado_q).filter(
        fecha_desde__lte=fh,
        fecha_hasta__gte=fd,
    ).exists()
    same_vac_aprobada = SV.objects.filter(
        idempleado=solicitud.idempleado
    ).filter(id_estado__estado__iexact='Aceptada').filter(
        fecha_desde__lte=fh,
        fecha_hasta__gte=fd,
    ).exists()
    if same_lic_aprobada or same_vac_aprobada:
        raise ValidacionError('solapa con licencia/vacaciones aprobada del mismo empleado')

    # 6b) Otras personas: si solapa con licencia/vacaciones aprobada de OTRO empleado -> warning (no bloquear)
    other_lic_aprobada = SL.objects.filter(~Q(idempleado=solicitud.idempleado)).filter(aprobado_q).filter(
        fecha_desde__lte=fh,
        fecha_hasta__gte=fd,
    )
    other_vac_aprobada = SV.objects.filter(~Q(idempleado=solicitud.idempleado)).filter(id_estado__estado__iexact='Aceptada').filter(
        fecha_desde__lte=fh,
        fecha_hasta__gte=fd,
    )
    if other_lic_aprobada.exists() or other_vac_aprobada.exists():
        warnings.append('solapa con licencia/vacaciones aprobada de otro empleado')

    # Si llegamos acá, es aceptable (pero retornamos warnings si los hay)
    return True, warnings
