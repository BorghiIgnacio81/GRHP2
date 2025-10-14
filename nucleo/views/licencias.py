from dataclasses import dataclass, field
from typing import List, Optional

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.core.paginator import Paginator
from django.db import models, transaction
from django.utils import timezone
import os
import json
import logging

from nucleo.models import (
    Empleado,
    Tipo_licencia,
    Solicitud_licencia,
    Solicitud_vacaciones,
    Estado_lic_vac,
    Vacaciones_otorgadas,
    Feriado,
)
from nucleo.views.vacaciones import (
    aprobar_solicitud_vacaciones,
    rechazar_solicitud_vacaciones,
)


logger = logging.getLogger(__name__)


@dataclass
class AccionSolicitudResult:
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    tipo: Optional[str] = None


def _determinar_tipo_solicitud(solicitud) -> Optional[str]:
    if isinstance(solicitud, Solicitud_vacaciones):
        return "vacacion"
    if isinstance(solicitud, Solicitud_licencia):
        return "licencia"
    return None


def _obtener_email_y_nombre(solicitud):
    empleado = getattr(solicitud, "idempleado", None)
    usuario = getattr(empleado, "idempleado", None)
    email = getattr(usuario, "email", None)
    nombres = getattr(empleado, "nombres", "")
    apellidos = getattr(empleado, "apellido", "")
    nombre = " ".join(part for part in [nombres, apellidos] if part).strip()
    if not nombre and usuario:
        nombre = getattr(usuario, "get_full_name", lambda: "")() or getattr(usuario, "username", "")
    return email, nombre


def aprobar_solicitud_licencia(solicitud, comentario=None, enviar_notificacion=True) -> AccionSolicitudResult:
    if solicitud is None:
        return AccionSolicitudResult(success=False, error="Solicitud de licencia inválida", tipo="licencia")

    from nucleo.logic.validaciones import validar_solicitud_licencia, ValidacionError

    try:
        _, warnings = validar_solicitud_licencia(solicitud)
    except ValidacionError as ve:
        estado_rechazada = Estado_lic_vac.objects.get(estado__iexact="Rechazada")
        texto_actual = (solicitud.texto_gestor or "").strip()
        motivo = str(ve).strip()
        nuevo_texto = f"{texto_actual}\n{motivo}".strip() if texto_actual else motivo
        Solicitud_licencia.objects.filter(pk=solicitud.pk).update(
            id_estado_id=estado_rechazada.id_estado,
            texto_gestor=nuevo_texto,
        )
        solicitud.refresh_from_db()
        return AccionSolicitudResult(
            success=False,
            error=f"Solicitud rechazada automáticamente: {ve}",
            tipo="licencia",
        )

    warnings_list = list(warnings or [])
    nuevo_texto = (solicitud.texto_gestor or "").strip()
    comentario = (comentario or "").strip()
    if comentario:
        nuevo_texto = f"{nuevo_texto}\n{comentario}".strip() if nuevo_texto else comentario
    if warnings_list:
        advertencias_txt = "Advertencias: " + "; ".join(warnings_list)
        nuevo_texto = f"{nuevo_texto}\n{advertencias_txt}".strip() if nuevo_texto else advertencias_txt

    estado_aceptada = Estado_lic_vac.objects.get(estado__iexact="Aceptada")
    texto_gestor_actualizado = nuevo_texto if nuevo_texto else ""
    Solicitud_licencia.objects.filter(pk=solicitud.pk).update(
        id_estado_id=estado_aceptada.id_estado,
        texto_gestor=texto_gestor_actualizado,
    )
    solicitud.refresh_from_db()

    if enviar_notificacion:
        email, nombre_empleado = _obtener_email_y_nombre(solicitud)
        if email:
            logger.info(
                "[LICENCIAS] Enviando notificación de aprobación - solicitud=%s email=%s",
                solicitud.pk,
                email,
            )
            from nucleo.utils_mail import enviar_mail_estado_licencia

            enviar_mail_estado_licencia(
                email=email,
                nombre_empleado=nombre_empleado,
                tipo="licencia",
                estado="Aceptada",
                texto_gestor=nuevo_texto,
                fecha_desde=getattr(solicitud, "fecha_desde", None),
                fecha_hasta=getattr(solicitud, "fecha_hasta", None),
            )

    return AccionSolicitudResult(
        success=True,
        message="Solicitud aprobada correctamente",
        warnings=warnings_list,
        tipo="licencia",
    )


def rechazar_solicitud_licencia(solicitud, motivo=None, enviar_notificacion=True) -> AccionSolicitudResult:
    if solicitud is None:
        return AccionSolicitudResult(success=False, error="Solicitud de licencia inválida", tipo="licencia")

    estado_rechazada = Estado_lic_vac.objects.get(estado__iexact="Rechazada")
    texto = (motivo or "").strip()
    texto_gestor_actualizado = texto if texto else ""
    Solicitud_licencia.objects.filter(pk=solicitud.pk).update(
        id_estado_id=estado_rechazada.id_estado,
        texto_gestor=texto_gestor_actualizado,
    )
    solicitud.refresh_from_db()

    if enviar_notificacion:
        email, nombre_empleado = _obtener_email_y_nombre(solicitud)
        if email:
            logger.info(
                "[LICENCIAS] Enviando notificación de rechazo - solicitud=%s email=%s",
                solicitud.pk,
                email,
            )
            from nucleo.utils_mail import enviar_mail_estado_licencia

            enviar_mail_estado_licencia(
                email=email,
                nombre_empleado=nombre_empleado,
                tipo="licencia",
                estado="Rechazada",
                texto_gestor=texto,
                fecha_desde=getattr(solicitud, "fecha_desde", None),
                fecha_hasta=getattr(solicitud, "fecha_hasta", None),
            )

    return AccionSolicitudResult(
        success=True,
        message="Solicitud rechazada correctamente",
        tipo="licencia",
    )


def procesar_accion_solicitud(solicitud, accion, usuario_actual, comentario=None, enviar_notificacion=True) -> AccionSolicitudResult:
    if not solicitud:
        return AccionSolicitudResult(success=False, error="No se encontró la solicitud.")

    tipo = _determinar_tipo_solicitud(solicitud)
    if not tipo:
        return AccionSolicitudResult(success=False, error="Tipo de solicitud desconocido.")

    empleado_user_id = getattr(getattr(solicitud, "idempleado", None), "idempleado_id", None)
    comentario = (comentario or "").strip()

    if accion == "aprobar":
        if usuario_actual and empleado_user_id and usuario_actual.pk == empleado_user_id:
            return AccionSolicitudResult(
                success=False,
                error="❌ No puedes aprobar tus propias solicitudes. Debe hacerlo otro gestor.",
                tipo=tipo,
            )
        if tipo == "vacacion":
            aprobar_solicitud_vacaciones(solicitud, texto_gestor=comentario or None, enviar_notificacion=enviar_notificacion)
            solicitud.refresh_from_db()
            return AccionSolicitudResult(success=True, message="Solicitud aprobada correctamente", tipo=tipo)
        return aprobar_solicitud_licencia(solicitud, comentario=comentario, enviar_notificacion=enviar_notificacion)

    if accion == "rechazar":
        if not usuario_actual or not usuario_actual.is_staff:
            return AccionSolicitudResult(
                success=False,
                error="No tienes permisos para rechazar solicitudes.",
                tipo=tipo,
            )
        if tipo == "vacacion":
            rechazar_solicitud_vacaciones(solicitud, comentario, enviar_notificacion=enviar_notificacion)
            solicitud.refresh_from_db()
            return AccionSolicitudResult(success=True, message="Solicitud rechazada correctamente", tipo=tipo)
        return rechazar_solicitud_licencia(solicitud, motivo=comentario, enviar_notificacion=enviar_notificacion)

    if accion == "comentario":
        if tipo == "vacacion":
            update_kwargs = {}
            if hasattr(solicitud, "texto_gestor"):
                update_kwargs["texto_gestor"] = comentario or None
            else:
                valor = comentario or getattr(solicitud, "comentario", "")
                update_kwargs["comentario"] = valor
            if update_kwargs:
                Solicitud_vacaciones.objects.filter(pk=solicitud.pk).update(**update_kwargs)
        else:
            texto_actualizado = comentario if comentario else ""
            Solicitud_licencia.objects.filter(pk=solicitud.pk).update(texto_gestor=texto_actualizado)
        solicitud.refresh_from_db()
        return AccionSolicitudResult(success=True, message="Comentario guardado correctamente", tipo=tipo)

    return AccionSolicitudResult(success=False, error="Acción no reconocida.", tipo=tipo)
@login_required
def eliminar_solicitud(request):
    """Endpoint POST para marcar o eliminar una solicitud.
    Reglas:
    - Sólo permitido por el propio dueño (para cancelar) o por un gestor (is_staff) para solicitudes en estado 'En espera' o 'Aceptada' (si no están consumidas).
    - Buscamos tanto en Solicitud_licencia como Solicitud_vacaciones.
    - En vez de borrar físicamente, cambiamos estado a 'Cancelada' si existe; si no existe ese estado, borramos la instancia (suave fallback).
    """
    if request.method != 'POST':
        from django.contrib import messages
        messages.error(request, "Acción no permitida (sólo POST).")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('nucleo:gestion_reporte_licencias')

    solicitud_id = request.POST.get('solicitud_id')
    if not solicitud_id:
        from django.contrib import messages
        messages.error(request, "Solicitud inválida.")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('nucleo:gestion_reporte_licencias')

    usuario = request.user
    # Busca en licencias o vacaciones
    solicitud = Solicitud_licencia.objects.filter(pk=solicitud_id).first()
    tipo = 'licencia'
    if not solicitud:
        solicitud = Solicitud_vacaciones.objects.filter(pk=solicitud_id).first()
        tipo = 'vacaciones'

    if not solicitud:
        from django.contrib import messages
        messages.error(request, "No se encontró la solicitud solicitada.")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('nucleo:gestion_reporte_licencias')

    # Estado actual (texto en minúsculas para comparar)
    estado_text = getattr(solicitud.id_estado, 'estado', '').lower()

    # Regla: permitir sólo si estado es 'aprobada'/'aceptada' o 'en espera'
    allowed_states = {'aprobada', 'aceptada', 'en espera', 'rechazada'}
    if estado_text not in allowed_states:
        from django.contrib import messages
        messages.error(request, "No puede eliminar/cancelar esta solicitud en su estado actual.")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('nucleo:gestion_reporte_licencias')


    # Permisos: dueño puede cancelar su propia solicitud; gestor (is_staff) puede eliminar también
    # Hacemos la comprobación de dueño más robusta porque dependiendo del modelo
    # la referencia al usuario puede resolverse como `idempleado_id` (int) o como
    # un objeto `Empleado` que a su vez referencia al User.
    es_dueno = False
    try:
        # caso común: atributo FK idempleado_id con PK del Empleado (que es el id de User)
        if getattr(solicitud, 'idempleado_id', None) == usuario.pk:
            es_dueno = True
        else:
            # caso alternativo: `solicitud.idempleado` es un objeto Empleado
            emp = getattr(solicitud, 'idempleado', None)
            if emp is not None:
                # Empleado.idempleado es OneToOneField a User, Django crea emp.idempleado_id
                emp_user_id = getattr(emp, 'idempleado_id', None) or getattr(emp, 'pk', None) or getattr(emp, 'id', None)
                if emp_user_id == usuario.pk:
                    es_dueno = True
    except Exception:
        es_dueno = False

    # Verificaciones extra: impedir eliminación si está en curso o ya consumida
    from datetime import date as _date
    hoy = _date.today()
    # Eliminada la restricción por fecha pasada: ahora se puede eliminar cualquier solicitud, incluso si la fecha ya pasó.

    if not (es_dueno or usuario.is_staff):
        from django.contrib import messages
        messages.error(request, "No tienes permisos para eliminar/cancelar esta solicitud.")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('nucleo:gestion_reporte_licencias')

    # Si es una vacación aprobada/aceptada, revertir el consumo de días antes de eliminar
    if tipo == 'vacaciones' and estado_text in ['aceptada', 'aprobada']:
        try:
            from nucleo.models import Vacaciones_otorgadas
            dias_a_liberar = (solicitud.fecha_hasta - solicitud.fecha_desde).days + 1
            
            # Buscar los registros de Vacaciones_otorgadas que fueron afectados
            # Primero el año actual, luego años anteriores
            year_solicitud = solicitud.fecha_desde.year
            vac_actual = Vacaciones_otorgadas.objects.filter(
                idempleado=solicitud.idempleado,
                inicio_consumo__year=year_solicitud
            ).first()
            
            if vac_actual and vac_actual.dias_consumidos >= dias_a_liberar:
                # Si el año actual tiene suficientes días consumidos, revertir ahí
                vac_actual.dias_consumidos -= dias_a_liberar
                vac_actual.save()
            else:
                # Si no, hay que revertir proporcionalmente en múltiples años
                restante = dias_a_liberar
                
                # Empezar por el año actual si tiene días consumidos
                if vac_actual and vac_actual.dias_consumidos > 0:
                    a_revertir = min(vac_actual.dias_consumidos, restante)
                    vac_actual.dias_consumidos -= a_revertir
                    vac_actual.save()
                    restante -= a_revertir
                
                # Luego años anteriores, empezando por el más reciente
                if restante > 0:
                    vac_anteriores = Vacaciones_otorgadas.objects.filter(
                        idempleado=solicitud.idempleado,
                        inicio_consumo__lt=solicitud.fecha_desde
                    ).order_by('-inicio_consumo')  # Más reciente primero
                    
                    for vac in vac_anteriores:
                        if restante <= 0:
                            break
                        if vac.dias_consumidos > 0:
                            a_revertir = min(vac.dias_consumidos, restante)
                            vac.dias_consumidos -= a_revertir
                            vac.save()
                            restante -= a_revertir
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al revertir días consumidos al eliminar vacación: {e}")

    # Intentar cambiar a estado 'Cancelada' si existe
    try:
        estado_cancelada = Estado_lic_vac.objects.filter(estado__iexact='Cancelada').first()
        if estado_cancelada:
            solicitud.id_estado = estado_cancelada
            # También añadir texto_gestor si lo borró un gestor
            if usuario.is_staff and not es_dueno:
                solicitud.texto_gestor = (solicitud.texto_gestor or '') + f"\nCancelado por {usuario.get_full_name() or usuario.username}"
            solicitud.save()
        else:
            # Si no existe estado, eliminar físicamente como fallback
            solicitud.delete()
    except Exception:
        # En caso de error, informar y volver en lugar de 403
        from django.contrib import messages
        messages.error(request, "Error al procesar la eliminación de la solicitud.")
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        return redirect('nucleo:gestion_reporte_licencias')

    # Al terminar, redirigimos a la página previa o a la gestión
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('nucleo:gestion_reporte_licencias')

@login_required
def detalle_licencia(request, solicitud_id):
    # Solo gestor o admin pueden acceder
    if not request.user.is_staff:
        return HttpResponseForbidden()
    from nucleo.models import Tipo_licencia, Solicitud_licencia
    solicitud = get_object_or_404(Solicitud_licencia, pk=solicitud_id)
    tipos_licencia = Tipo_licencia.objects.all()
    mensaje_exito = None
    mensaje_error = None
    # Manejo POST: aprobar/rechazar o guardar comentario
    if request.method == "POST":
        from django.contrib import messages

        accion = (request.POST.get("accion") or "comentario").lower()
        texto_gestor = request.POST.get("texto_gestor", "").strip()

        resultado = procesar_accion_solicitud(
            solicitud,
            accion,
            request.user,
            comentario=texto_gestor,
            enviar_notificacion=True,
        )

        if resultado.success:
            for advertencia in resultado.warnings:
                messages.warning(request, f"Advertencia: {advertencia}")

            if accion in {"aprobar", "rechazar"}:
                mensaje_redirect = resultado.message or (
                    "Solicitud aprobada correctamente" if accion == "aprobar" else "Solicitud rechazada correctamente"
                )
                return redirect(_build_redirect_with_filters_from_post(request, mensaje_redirect))

            mensaje_exito = resultado.message or "Comentario guardado."
            solicitud.refresh_from_db()
        else:
            mensaje_error = resultado.error or "Error al procesar la acción."
            messages.error(request, mensaje_error)
            solicitud.refresh_from_db()

    return render(request, "nucleo/detalle_licencia.html", {
        "solicitud": solicitud,
        "tipos_licencia": tipos_licencia,
        "mensaje_exito": mensaje_exito,
        "mensaje_error": mensaje_error,
        "is_owner": getattr(solicitud, 'idempleado_id', None) == request.user.pk,
        # bandera usada por la plantilla para mostrar/ocultar botones de aprobación
        "is_pending": (getattr(getattr(solicitud, 'id_estado', None), 'estado', '') or '').strip().lower() == 'en espera',
    })


@login_required
def solicitar_licencia(request):
    # DEBUG seguro: Si necesitas depurar, usa logging en vez de print para evitar errores en producción
    # Proveer datos mínimos para que el template y su JS funcionen correctamente.
    tipos_licencia = Tipo_licencia.objects.all()
    # Mapa id_licencia -> dias (JS accede con select.value que es string)
    # Use None for 'licencia libre' so JSON -> null and client JS can display 'Libre'
    dias_por_licencia = {str(t.id_licencia): (t.dias if t.dias is not None else None) for t in tipos_licencia}
    # Feriados como lista de strings YYYY-MM-DD
    from datetime import date
    feriados_qs = Feriado.objects.all()
    feriados = [f.fecha.strftime('%Y-%m-%d') for f in feriados_qs]
    # Información de vacaciones real para el usuario actual:
    # total disponible, total consumido y periodos otorgados (inicio/fin/dias)
    from nucleo.models import Vacaciones_otorgadas
    # Resolver el objeto Empleado de forma robusta: por pk (id), por relación al User
    # o por campos de usuario si fuera necesario. Esto evita que `empleado_obj` quede None
    # y se saltee la validación del Plan_trabajo en la creación de solicitudes.
    empleado_obj = Empleado.objects.filter(idempleado_id=request.user.id).first()
    if not empleado_obj:
        # intentar por relación inversa (idempleado es OneToOne a User)
        empleado_obj = Empleado.objects.filter(idempleado__username=request.user.username).first()
    if not empleado_obj:
        # fallback por nombre/apellido (poco fiable, pero ayuda en casos de usuarios importados)
        nombre = (request.user.first_name or '').strip()
        apellido = (request.user.last_name or '').strip()
        if nombre and apellido:
            empleado_obj = Empleado.objects.filter(nombres__iexact=nombre, apellido__iexact=apellido).first()
    # Solo obtener registros de vacaciones hasta el año actual (no años futuros)
    current_year = date.today().year
    vac_otorgadas_qs = Vacaciones_otorgadas.objects.filter(
        idempleado=empleado_obj,
        inicio_consumo__year__lte=current_year
    ) if empleado_obj else Vacaciones_otorgadas.objects.none()
    periods = []
    total_available = 0
    total_consumed = 0
    for v in vac_otorgadas_qs:
        anio_v = v.inicio_consumo.year
        # Solo procesar si el año es <= al año actual
        if anio_v <= current_year:
            dias_otorgados_val = v.dias_disponibles or 0
            dias_consumidos_val = v.dias_consumidos or 0
            dias_disponibles_rest = max(dias_otorgados_val - dias_consumidos_val, 0)
            # Mostrar todos los años con días otorgados > 0
            if dias_otorgados_val > 0:
                # Provide both the original granted days and the remaining available days
                # so the frontend can choose the correct fields without ambiguity.
                periods.append({
                    "inicio_consumo": v.inicio_consumo.strftime('%Y-%m-%d'),
                    "fin_consumo": v.fin_consumo.strftime('%Y-%m-%d'),
                    "anio": anio_v,
                    "dias_otorgados": dias_otorgados_val,
                    "dias_consumidos": dias_consumidos_val,
                    # original total granted for that period
                    "dias_disponibles": dias_otorgados_val,
                    # remaining days after consumption (frontend expects this key)
                    "dias_disponibles_rest": dias_disponibles_rest,
                })
    # La lógica de years ya está manejada en el bucle principal arriba

    # Para el template necesitamos una lista iterables de años con dias; usamos inicio_consumo.year como 'anio'
    vacaciones_info_list = []
    # Totales por años anteriores y año actual
    prev_available = 0
    prev_consumed = 0
    curr_available = 0
    curr_consumed = 0
    from datetime import date as _date
    # current_year ya está definido arriba
    for v in vac_otorgadas_qs:
        anio = v.inicio_consumo.year
        # Solo procesar si el año es <= al año actual
        if anio <= current_year:
            dias_disponibles_val = v.dias_disponibles or 0
            dias_consumidos_val = v.dias_consumidos or 0
            vacaciones_info_list.append({
                'anio': anio,
                'dias_disponibles': dias_disponibles_val,
                'dias_consumidos': dias_consumidos_val,
                'dias_otorgados': dias_disponibles_val,
                'dias_disponibles_rest': max(dias_disponibles_val - dias_consumidos_val, 0),
            })
            if anio == current_year:
                curr_available += (v.dias_disponibles or 0)
                curr_consumed += (v.dias_consumidos or 0)
            else:
                prev_available += (v.dias_disponibles or 0)
                prev_consumed += (v.dias_consumidos or 0)

    # LÓGICA DE ESTIMACIÓN DESHABILITADA:
    # Los días de vacaciones solo se deben generar cuando un gestor 
    # presiona el botón "Generar Vacaciones" en la página generar_vacaciones.
    # No se deben mostrar estimaciones automáticas en la tabla.
    
    # Si no hay registros generados por el gestor, simplemente no mostrar nada
    # en la tabla hasta que se generen oficialmente los días de vacaciones.

    # JSON para JS en el cliente (suma totales y periodos con fechas)
    # Aseguramos que 'periods' contiene todos los años con días disponibles > 0
    vacaciones_info_json = {
        "empleado_id": getattr(empleado_obj, 'idempleado_id', None),
        "total_available": total_available,
        "total_consumed": total_consumed,
        "periods": periods,
    }
    # DEBUG: Volcar vacaciones_info_json a archivo temporal para inspección (no usar print en producción)
    try:
        import json, os
        user_id = getattr(empleado_obj, 'idempleado_id', 'anon')
        dump_path = f"/tmp/vacaciones_debug_{user_id}.json"
        with open(dump_path, 'w') as f:
            json.dump(vacaciones_info_json, f, default=str)
    except Exception:
        pass
    # 'year' usado por el template; obtener aquí
    year = _date.today().year

    mensaje_exito = None
    mensaje_error = None
    mensaje_advertencia = None

    if not empleado_obj:
        mensaje_error = (
            "No se encontró un legajo de empleado asociado a tu usuario. "
            "Contactá con Recursos Humanos para completar el alta antes de solicitar licencias."
        )
        return render(request, "nucleo/solicitar_licencia.html", {
            "tipos_licencia": tipos_licencia,
            "dias_por_licencia": json.dumps(dias_por_licencia),
            "vacaciones_info": vacaciones_info_list,
            "vacaciones_info_json": json.dumps(vacaciones_info_json),
            "year": year,
            "prev_available": prev_available,
            "prev_consumed": prev_consumed,
            "prev_diff": max(prev_available - prev_consumed, 0),
            "curr_available": curr_available,
            "curr_consumed": curr_consumed,
            "curr_diff": max(curr_available - curr_consumed, 0),
            "mensaje_exito": mensaje_exito,
            "mensaje_error": mensaje_error,
            "mensaje_advertencia": mensaje_advertencia,
            "feriados": feriados,
        })

    if request.method == "POST":
        id_licencia = request.POST.get("id_licencia")
        fecha_desde = request.POST.get("fecha_desde")
        fecha_hasta = request.POST.get("fecha_hasta")
        comentario = request.POST.get("comentario")
        archivo = request.FILES.get("archivo")
        try:
            tipo_lic = Tipo_licencia.objects.get(pk=id_licencia)
        except Exception:
            tipo_lic = None
        try:
            estado = Estado_lic_vac.objects.get(estado__iexact="En espera")
        except Exception:
            estado = None

        archivo_url = None
        if archivo:
            carpeta = os.path.join("media", "licencias")
            os.makedirs(carpeta, exist_ok=True)
            archivo_url = f"licencias/{archivo.name}"
            ruta_archivo = os.path.join("media", archivo_url)
            with open(ruta_archivo, "wb+") as destination:
                for chunk in archivo.chunks():
                    destination.write(chunk)

        from datetime import datetime
        try:
            fecha_desde_dt = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
            fecha_hasta_dt = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
        except Exception:
            mensaje_error = "Fechas inválidas."
            return render(request, "nucleo/solicitar_licencia.html", {
                "tipos_licencia": tipos_licencia,
                "dias_por_licencia": json.dumps(dias_por_licencia),
                "vacaciones_info": vacaciones_info_list,
                "vacaciones_info_json": json.dumps(vacaciones_info_json),
                "year": year,
                "mensaje_error": mensaje_error,
                "prev_diff": max(prev_available - prev_consumed, 0),
                "curr_diff": max(curr_available - curr_consumed, 0),
                "mensaje_advertencia": mensaje_advertencia,
                "feriados": feriados,
            })

        feriados_qs = Feriado.objects.all()
        feriados_fechas = set(f.fecha for f in feriados_qs)
        # Lista legible de feriados en el rango
        feriados_en_rango = [f.strftime("%d/%m/%Y") for f in sorted(feriados_fechas) if fecha_desde_dt <= f <= fecha_hasta_dt]
        if feriados_en_rango:
            # Si TODAS las fechas solicitadas son feriados => por defecto se rechaza,
            # excepto para 'licencia libre' (dias = NULL) donde se permite y sólo se advierte.
            from datetime import timedelta
            total_days = (fecha_hasta_dt - fecha_desde_dt).days + 1
            # Construir conjunto de días solicitados
            dias_solicitados_set = set(fecha_desde_dt + timedelta(days=i) for i in range(total_days))
            es_licencia_libre = bool(tipo_lic) and (getattr(tipo_lic, 'dias', None) is None)
            if dias_solicitados_set.issubset(feriados_fechas):
                if es_licencia_libre:
                    aviso = f"Está solicitando una licencia libre en día(s) feriado(s): {', '.join(feriados_en_rango)}. Se permite igualmente."
                    if mensaje_advertencia:
                        mensaje_advertencia += "<br>" + aviso
                    else:
                        mensaje_advertencia = aviso
                else:
                    mensaje_error = f"No es posible solicitar licencia: las fechas indicadas son feriados ({', '.join(feriados_en_rango)})."
            else:
                # Mezcla de días hábiles y feriados: sólo advertir
                aviso = f"Atención: Las fechas seleccionadas incluyen feriados: {', '.join(feriados_en_rango)}."
                if mensaje_advertencia:
                    mensaje_advertencia += "<br>" + aviso
                else:
                    mensaje_advertencia = aviso

        colisiones = []
        licencias_colision = Solicitud_licencia.objects.filter(
            idempleado=empleado_obj,
            fecha_desde__lte=fecha_hasta_dt,
            fecha_hasta__gte=fecha_desde_dt,
            id_estado__estado__in=["En espera", "Aceptada"]
        )
        vacaciones_colision = Solicitud_vacaciones.objects.filter(
            idempleado=empleado_obj,
            fecha_desde__lte=fecha_hasta_dt,
            fecha_hasta__gte=fecha_desde_dt,
            id_estado__estado__in=["En espera", "Aceptada"]
        )
        for l in licencias_colision:
            colisiones.append(f"Licencia: {l.fecha_desde.strftime('%d/%m/%Y')} - {l.fecha_hasta.strftime('%d/%m/%Y')}")
        for v in vacaciones_colision:
            colisiones.append(f"Vacaciones: {v.fecha_desde.strftime('%d/%m/%Y')} - {v.fecha_hasta.strftime('%d/%m/%Y')}")
        if colisiones:
            mensaje_error = "Colisión con licencias/vacaciones ya solicitadas en las siguientes fechas: " + "; ".join(colisiones)

        # Detectar colisiones con solicitudes ACEPTADAS de OTROS empleados -> mostrar advertencia
        try:
            from django.db.models import Q
            # Buscar licencias ACEPTADAS/APROBADAS de OTROS empleados que solapen
            other_lic_aprobada = Solicitud_licencia.objects.filter(~Q(idempleado=empleado_obj)).filter(
                Q(id_estado__estado__iexact='Aceptada') | Q(id_estado__estado__iexact='Aprobada')
            ).filter(fecha_desde__lte=fecha_hasta_dt, fecha_hasta__gte=fecha_desde_dt)
            # Buscar vacaciones de OTROS empleados que solapen (incluir En espera/Aceptada/Aprobada)
            other_vac_aprobada = Solicitud_vacaciones.objects.filter(~Q(idempleado=empleado_obj)).filter(
                id_estado__estado__in=['En espera', 'Aceptada', 'Aprobada']
            ).filter(fecha_desde__lte=fecha_hasta_dt, fecha_hasta__gte=fecha_desde_dt)

            lic_exists = other_lic_aprobada.exists()
            vac_exists = other_vac_aprobada.exists()
            if lic_exists or vac_exists:
                tipos = []
                if lic_exists:
                    tipos.append('licencia')
                if vac_exists:
                    tipos.append('vacaciones')
                if len(tipos) == 1:
                    aviso = f"En el periodo solicitado otro empleado tambien solicito {tipos[0]}"
                else:
                    aviso = "En el periodo solicitado otro empleado tambien solicito " + ' y '.join(tipos)
                if mensaje_advertencia:
                    mensaje_advertencia += "<br>" + aviso
                else:
                    mensaje_advertencia = aviso
        except Exception:
            # no bloquear ni detener el flujo por problemas al comprobar colisiones de otros empleados
            pass

        dias_solicitados = (fecha_hasta_dt - fecha_desde_dt).days + 1
        dias_permitidos = tipo_lic.dias if tipo_lic else None
        if dias_permitidos and dias_solicitados > dias_permitidos:
            mensaje_error = f"No puede solicitar más de {dias_permitidos} días para esta licencia. Ha solicitado {dias_solicitados} días."

        # Comprobar plan de trabajo ANTES de crear la solicitud: impedir solicitudes que sean
        # exclusivamente en días no laborables para el empleado. Esto aplica a cualquier tipo
        # de licencia (vacaciones u otras) y debe bloquear la creación en lugar de validar
        # después de haber creado el registro.
        try:
            from nucleo.models import Plan_trabajo
            planes_qs = Plan_trabajo.objects.filter(idempleado=empleado_obj) if empleado_obj else Plan_trabajo.objects.none()
            if planes_qs.count() > 1:
                mensaje_error = "Error: El empleado tiene más de un plan de trabajo registrado. Contacte al administrador para corregir la duplicidad."
                return render(request, "nucleo/solicitar_licencia.html", {
                    "tipos_licencia": tipos_licencia,
                    "dias_por_licencia": json.dumps(dias_por_licencia),
                    "vacaciones_info": vacaciones_info_list,
                    "vacaciones_info_json": json.dumps(vacaciones_info_json),
                    "year": year,
                    "mensaje_error": mensaje_error,
                    "prev_diff": max(prev_available - prev_consumed, 0),
                    "curr_diff": max(curr_available - curr_consumed, 0),
                    "mensaje_advertencia": mensaje_advertencia,
                    "feriados": feriados,
                })
            plan = planes_qs.first() if planes_qs.exists() else None
            if plan:
                from datetime import timedelta
                total_days = dias_solicitados
                dias_no_laborales = 0
                dias_laborables = 0
                # Validar solo el primer día seleccionado
                import logging
                d = fecha_desde_dt
                weekday = d.weekday()  # 0=lunes .. 6=domingo
                works = None
                if weekday == 0:
                    works = bool(plan.lunes)
                elif weekday == 1:
                    works = bool(plan.martes)
                elif weekday == 2:
                    works = bool(plan.miercoles)
                elif weekday == 3:
                    works = bool(plan.jueves)
                elif weekday == 4:
                    works = bool(plan.viernes)
                elif weekday == 5:
                    works = bool(plan.sabado)
                elif weekday == 6:
                    works = bool(plan.domingo)
                nombre_dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                nombre_dia = nombre_dias[weekday]
                # logging.debug(f"[DEBUG] fecha_desde: {fecha_desde}, fecha_desde_dt: {fecha_desde_dt}, weekday: {weekday}, nombre_dia: {nombre_dia}, works: {works}, empleado: {getattr(empleado_obj, 'idempleado_id', None)}")
                # Validación especial: licencia de 1 día en día no laborable o feriado
                primer_dia_feriado = fecha_desde_dt in set(f.fecha for f in Feriado.objects.all())
                es_licencia_libre = bool(tipo_lic) and (getattr(tipo_lic, 'dias', None) is None)
                if dias_solicitados == 1:
                    if not works:
                        if es_licencia_libre:
                            fecha_str = fecha_desde_dt.strftime('%d/%m/%Y')
                            aviso = f"El {fecha_str} es un día no laborable para usted, pero se permite la licencia libre de un día."
                            if mensaje_advertencia:
                                mensaje_advertencia += "<br>" + aviso
                            else:
                                mensaje_advertencia = aviso
                        else:
                            fecha_str = fecha_desde_dt.strftime('%d/%m/%Y')
                            mensaje_error = f"No se hizo la solicitud por ser el {fecha_str} un día no laborable para usted y la licencia ser de 1 solo día."
                            return render(request, "nucleo/solicitar_licencia.html", {
                                "tipos_licencia": tipos_licencia,
                                "dias_por_licencia": json.dumps(dias_por_licencia),
                                "vacaciones_info": vacaciones_info_list,
                                "vacaciones_info_json": json.dumps(vacaciones_info_json),
                                "year": year,
                                "mensaje_error": mensaje_error,
                                "prev_diff": max(prev_available - prev_consumed, 0),
                                "curr_diff": max(curr_available - curr_consumed, 0),
                                "mensaje_advertencia": mensaje_advertencia,
                                "feriados": feriados,
                            })
                    elif primer_dia_feriado:
                        if es_licencia_libre:
                            fecha_str = fecha_desde_dt.strftime('%d/%m/%Y')
                            aviso = f"El {fecha_str} es feriado; la licencia libre de un día se permite igualmente."
                            if mensaje_advertencia:
                                mensaje_advertencia += "<br>" + aviso
                            else:
                                mensaje_advertencia = aviso
                        else:
                            fecha_str = fecha_desde_dt.strftime('%d/%m/%Y')
                            mensaje_error = f"No se hizo la solicitud por ser el {fecha_str} día feriado y la licencia ser de 1 solo día."
                            return render(request, "nucleo/solicitar_licencia.html", {
                                "tipos_licencia": tipos_licencia,
                                "dias_por_licencia": json.dumps(dias_por_licencia),
                                "vacaciones_info": vacaciones_info_list,
                                "vacaciones_info_json": json.dumps(vacaciones_info_json),
                                "year": year,
                                "mensaje_error": mensaje_error,
                                "prev_diff": max(prev_available - prev_consumed, 0),
                                "curr_diff": max(curr_available - curr_consumed, 0),
                                "mensaje_advertencia": mensaje_advertencia,
                                "feriados": feriados,
                            })
                es_licencia_libre = bool(tipo_lic) and (getattr(tipo_lic, 'dias', None) is None)
                # Verificar si el primer día es feriado
                primer_dia_feriado = fecha_desde_dt in set(f.fecha for f in Feriado.objects.all())
                nombre_dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                nombre_dia = nombre_dias[weekday]
                if tipo_lic and tipo_lic.descripcion.lower() == "vacaciones":
                    if not works:
                        mensaje_error = f"El día seleccionado es un {nombre_dia}, que no es laborable para este empleado. Por favor, elija un día laborable como inicio de las vacaciones."
                    elif primer_dia_feriado:
                        mensaje_error = f"El día seleccionado es un {nombre_dia}, que es feriado. Por favor, elija un día laborable y no feriado como inicio de las vacaciones."
                # Nota: comprobación por rango removida. Mantener sólo las validaciones
                # que bloquean solicitudes en caso de primer día no laborable o feriado.
                # (El usuario prefirió no mostrar un aviso por días no laborables dentro
                # del rango, pero sí conservar la validación de primer día y feriados.)
                es_licencia_libre = bool(tipo_lic) and (getattr(tipo_lic, 'dias', None) is None)
                if tipo_lic and tipo_lic.descripcion.lower() == "vacaciones":
                    # Validación simplificada: solo mostrar mensaje genérico si no es laborable o es feriado
                    primer_dia_feriado = fecha_desde_dt in set(f.fecha for f in Feriado.objects.all())
                    nombre_dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
                    nombre_dia = nombre_dias[weekday]
                    if not works:
                        mensaje_error = f"El día seleccionado es un {nombre_dia}, que no es laborable para este empleado. Por favor, elija un día laborable como inicio de las vacaciones."
                    elif primer_dia_feriado:
                        mensaje_error = f"El día seleccionado es un {nombre_dia}, que es feriado. Por favor, elija un día laborable y no feriado como inicio de las vacaciones."
                else:
                    pass
        except Exception:
            # Silenciar si no podemos comprobar plan
            pass

        if mensaje_error:
            return render(request, "nucleo/solicitar_licencia.html", {
                "tipos_licencia": tipos_licencia,
                "dias_por_licencia": json.dumps(dias_por_licencia),
                "vacaciones_info": vacaciones_info_list,
                "vacaciones_info_json": json.dumps(vacaciones_info_json),
                "year": year,
                "mensaje_error": mensaje_error,
                "prev_diff": max(prev_available - prev_consumed, 0),
                "curr_diff": max(curr_available - curr_consumed, 0),
                "mensaje_advertencia": mensaje_advertencia,
                "feriados": feriados,
            })

        if tipo_lic and tipo_lic.descripcion.lower() == "vacaciones":
            Solicitud_vacaciones.objects.create(
                idempleado=empleado_obj,
                fecha_desde=fecha_desde_dt,
                fecha_hasta=fecha_hasta_dt,
                id_estado=estado,
                comentario=comentario or "",
            )
        else:
            Solicitud_licencia.objects.create(
                idempleado=empleado_obj,
                id_licencia=tipo_lic,
                fecha_desde=fecha_desde_dt,
                fecha_hasta=fecha_hasta_dt,
                comentario=comentario or "",
                texto_gestor="",
                archivo=archivo_url,
                id_estado=estado,
            )
               # Construir mensaje de éxito detallado
        tipo_nombre = tipo_lic.descripcion if tipo_lic else "Licencia"
        fecha_desde_str = fecha_desde_dt.strftime("%d/%m/%Y")
        fecha_hasta_str = fecha_hasta_dt.strftime("%d/%m/%Y")
        mensaje_exito = f"Solicitud de licencia por {tipo_nombre} desde el {fecha_desde_str} al {fecha_hasta_str} enviada para su aprobación."
        if tipo_lic and tipo_lic.descripcion.strip().lower() == "vacaciones":
            if fecha_desde_dt.month < 10:
                advertencia_vac = "Está solicitando vacaciones fuera del período recomendado (octubre-abril). Preferiblemente no se debe hacer, pero la solicitud fue enviada igualmente."
                if mensaje_advertencia:
                    mensaje_advertencia += "<br>" + advertencia_vac
                else:
                    mensaje_advertencia = advertencia_vac

            # (Plan de trabajo validado anteriormente) No repetir aquí.

    return render(request, "nucleo/solicitar_licencia.html", {
        "tipos_licencia": tipos_licencia,
        "dias_por_licencia": json.dumps(dias_por_licencia),
        "vacaciones_info": vacaciones_info_list,
        "vacaciones_info_json": json.dumps(vacaciones_info_json),
    "year": year,
    "prev_available": prev_available,
    "prev_consumed": prev_consumed,
    "prev_diff": max(prev_available - prev_consumed, 0),
    "curr_available": curr_available,
    "curr_consumed": curr_consumed,
    "curr_diff": max(curr_available - curr_consumed, 0),
        "mensaje_exito": mensaje_exito,
        "mensaje_error": mensaje_error,
        "mensaje_advertencia": mensaje_advertencia,
        "feriados": feriados,
    })

@login_required
def consultar_licencia(request):
    from datetime import datetime
    
    empleado_obj = get_object_or_404(Empleado, pk=request.user.id)
    licencias = list(Solicitud_licencia.objects.filter(idempleado=empleado_obj).select_related('id_licencia', 'id_estado'))
    vacaciones = list(Solicitud_vacaciones.objects.filter(idempleado=empleado_obj).select_related('id_estado'))
    
    # Obtener tipos de licencia para el filtro
    tipos_licencia = Tipo_licencia.objects.all().order_by('descripcion')
    
    # Unificar ambas listas y calcular días solicitados
    solicitudes = []
    for s in licencias:
        s.tipo = getattr(s.id_licencia, 'descripcion', 'Licencia')
        s.dias_solicitados = (s.fecha_hasta - s.fecha_desde).days + 1
        s.fecha_solicitud = s.fecha_sqllc
        solicitudes.append(s)
    for v in vacaciones:
        v.tipo = 'Vacaciones'
        v.dias_solicitados = (v.fecha_hasta - v.fecha_desde).days + 1
        v.fecha_solicitud = v.fecha_sol_vac
        solicitudes.append(v)
    
    # Aplicar filtros si existen
    filtros_activos = {}
    
    # Filtro por tipo de licencia
    tipo_licencia_filtro = request.GET.get('tipo_licencia')
    if tipo_licencia_filtro:
        if tipo_licencia_filtro == 'vacaciones':
            solicitudes = [s for s in solicitudes if s.tipo.lower() == 'vacaciones']
            filtros_activos['tipo'] = 'Vacaciones'
        else:
            # Filtrar por ID de tipo de licencia específico
            try:
                tipo_id = int(tipo_licencia_filtro)
                solicitudes = [s for s in solicitudes if hasattr(s, 'id_licencia') and s.id_licencia.id_licencia == tipo_id]
                # Buscar el nombre del tipo para mostrarlo
                tipo_obj = tipos_licencia.filter(id_licencia=tipo_id).first()
                if tipo_obj:
                    filtros_activos['tipo'] = tipo_obj.descripcion
            except (ValueError, AttributeError):
                pass  # Ignorar valores inválidos
    
    # Filtro por fecha (tipo_fecha es obligatorio si se envía fecha_desde)
    tipo_fecha = request.GET.get('tipo_fecha')
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')
    es_rango = request.GET.get('rango_fecha') == 'on'
    if tipo_fecha and fecha_desde_str:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            if es_rango and fecha_hasta_str:
                fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
            else:
                fecha_hasta = fecha_desde

            solicitudes_filtradas = []
            for s in solicitudes:
                fecha_comparar = None
                # New unified option 'desde_hasta' means we filter by overlap
                # between the requested [fecha_desde, fecha_hasta] and the
                # solicitud's [fecha_desde, fecha_hasta]. Otherwise keep
                # the original behavior when filtering by solicitud date.
                if tipo_fecha == 'solicitud':
                    fecha_comparar = s.fecha_solicitud
                    if fecha_comparar and fecha_desde <= fecha_comparar <= fecha_hasta:
                        solicitudes_filtradas.append(s)
                elif tipo_fecha == 'desde_hasta':
                    # Check interval overlap: (start1 <= end2) and (start2 <= end1)
                    s_inicio = getattr(s, 'fecha_desde', None)
                    s_fin = getattr(s, 'fecha_hasta', None)
                    if s_inicio and s_fin and not (s_fin < fecha_desde or s_inicio > fecha_hasta):
                        solicitudes_filtradas.append(s)

            solicitudes = solicitudes_filtradas
            # For display, normalize the type label when using desde_hasta
            display_tipo = 'Desde/Hasta' if tipo_fecha == 'desde_hasta' else tipo_fecha
            filtros_activos['fecha'] = {'tipo': display_tipo, 'desde': fecha_desde_str, 'hasta': fecha_hasta_str if es_rango else None}
        except ValueError:
            pass  # Ignorar fechas inválidas
    
    # Filtro por tipo (vacaciones) - mantener compatibilidad con filtro anterior
    if request.GET.get('filtro_tipo') == 'vacaciones':
        solicitudes = [s for s in solicitudes if s.tipo.lower() == 'vacaciones']
        filtros_activos['tipo'] = 'vacaciones'
    
    # Ordenar por fecha desde descendente
    solicitudes.sort(key=lambda x: x.fecha_desde, reverse=True)
    
    estados_disponibles = []
    
    return render(request, "nucleo/consultar_licencia.html", {
        "solicitudes": solicitudes,
        "tipos_licencia": tipos_licencia,
        "estados_disponibles": estados_disponibles,
        "filtros_activos": filtros_activos,
        "filtros_get": request.GET,  # Para mantener valores en el form
    })

def _build_redirect_with_filters_from_post(request, message, message_type='success'):
    """Helper simple para construir redirect con filtros desde POST"""
    from django.urls import reverse
    from urllib.parse import urlencode
    
    # Extraer filtros de los campos hidden del POST
    filter_params = {}
    
    if request.POST.get('filter_anio'):
        filter_params['anio'] = request.POST.get('filter_anio')
    if request.POST.get('filter_empleado'):
        filter_params['empleado'] = request.POST.get('filter_empleado')
    if request.POST.get('filter_tipo'):
        filter_params['tipo'] = request.POST.get('filter_tipo')
    if request.POST.get('filter_estado'):
        filter_params['estado'] = request.POST.get('filter_estado')
    if request.POST.get('filter_page'):
        filter_params['page'] = request.POST.get('filter_page')
    if request.POST.get('filter_fecha_desde'):
        filter_params['fecha_desde'] = request.POST.get('filter_fecha_desde')
    if request.POST.get('filter_fecha_hasta'):
        filter_params['fecha_hasta'] = request.POST.get('filter_fecha_hasta')
    if request.POST.get('filter_fecha_rango'):
        filter_params['fecha_rango'] = request.POST.get('filter_fecha_rango')
    
    # Agregar mensaje según el tipo
    if message:
        if message_type == 'error':
            filter_params['msg_error'] = message
        else:
            filter_params['msg_exito'] = message
    
    # Construir URL final
    base_url = reverse('nucleo:gestion_reporte_licencias')
    if filter_params:
        return f"{base_url}?{urlencode(filter_params)}"
    else:
        if message:
            param_name = 'msg_error' if message_type == 'error' else 'msg_exito'
            return f"{base_url}?{param_name}={message.replace(' ', '+')}"
        return base_url

@login_required
def gestion_reporte_licencias(request):
    import logging
    logger = logging.getLogger("django")
    try:
        logger.warning(f"[VIEW ENTER] method={request.method} GET_keys={list(request.GET.keys())} GET_items={{ {', '.join([f'{k}={request.GET.get(k)!r}' for k in request.GET.keys()])} }} session_msg={request.session.get('msg_exito', None)}")
    except Exception:
        pass
    mensaje_exito = None
    mensaje_error = None
    mensaje_unico = None
    # For tests: if an action requires forcing a message into the final render,
    # set `force_show_message` in the POST branch and it will be appended here.
    force_show_message = None
    mensajes_exito = []
    mensajes_error = []
    mensajes_advertencia = []

# (Eliminado código complejo de autoaprobación)

    if request.method == "POST":
        from django.contrib import messages

        try:
            logger.info(
                "[DEBUG POST] user=%s POST_keys=%s POST_items={%s}",
                getattr(request.user, "username", None),
                list(request.POST.keys()),
                ", ".join(f"{k}={request.POST.get(k)!r}" for k in request.POST.keys()),
            )
        except Exception:
            pass

        solicitud_id = request.POST.get("solicitud_id")
        tipo_solicitud = (request.POST.get("tipo_solicitud") or "licencia").lower()
        accion = (request.POST.get("accion") or "comentario").lower()
        comentario = request.POST.get("motivo_rechazo", "").strip()

        if not solicitud_id:
            mensaje = "Solicitud inválida."
            messages.error(request, mensaje)
            return redirect(_build_redirect_with_filters_from_post(request, mensaje, message_type="error"))

        if tipo_solicitud == "vacacion":
            solicitud = Solicitud_vacaciones.objects.filter(pk=solicitud_id).select_related("idempleado", "id_estado").first()
        else:
            solicitud = (
                Solicitud_licencia.objects.filter(pk=solicitud_id)
                .select_related("idempleado", "id_estado", "id_licencia")
                .first()
            )

        logger.debug(
            "[PROCESAR] solicitud_id=%s tipo=%s accion=%s existe=%s",
            solicitud_id,
            tipo_solicitud,
            accion,
            bool(solicitud),
        )

        resultado = procesar_accion_solicitud(
            solicitud,
            accion,
            request.user,
            comentario=comentario,
            enviar_notificacion=True,
        )

        if not resultado.success:
            mensaje_error = resultado.error or "No se pudo procesar la solicitud."
            messages.error(request, mensaje_error)
            return redirect(_build_redirect_with_filters_from_post(request, mensaje_error, message_type="error"))

        for advertencia in resultado.warnings:
            messages.warning(request, f"Advertencia: {advertencia}")

        if resultado.message:
            messages.success(request, resultado.message)

        if accion == "aprobar":
            redirect_message = "Solicitud aprobada correctamente"
        elif accion == "rechazar":
            redirect_message = resultado.message or "Solicitud rechazada correctamente"
        else:
            redirect_message = resultado.message or "Comentario guardado correctamente"

        return redirect(_build_redirect_with_filters_from_post(request, redirect_message))

    # Ahora consumimos los mensajes (después de procesar POST) para mostrarlos en el template
    from django.contrib.messages import get_messages
    # Grab messages as a list so we can iterate multiple times and also
    # pass them explicitly to the template (tests use follow=True which
    # can make messages disappear if consumed). Converting to a list
    # ensures we don't lose them.
    messages_list = list(get_messages(request))
    for m in messages_list:
        try:
            tags = getattr(m, 'tags', '')
        except Exception:
            tags = ''
        if 'success' in tags or 'exito' in tags:
            mensajes_exito.append(str(m))
        elif 'error' in tags:
            mensajes_error.append(str(m))
        elif 'warning' in tags:
            mensajes_advertencia.append(str(m))
    # Soporte para mensajes por GET (desde redirects con filtros preservados)
    msg_exito = request.GET.get('msg_exito')
    if msg_exito:
        mensajes_exito.append(msg_exito)
        
    msg_error = request.GET.get('msg_error')
    if msg_error:
        mensajes_error.append(msg_error)

    # If a POST handler requested forcing a message into the render, ensure it's present
    if force_show_message and force_show_message not in mensajes_exito:
        mensajes_exito.append(force_show_message)

    # Construir un único mensaje combinando éxitos y advertencias (para evitar duplicados)
    # Nota: no sobrescribir `mensaje_unico` si ya fue establecido durante el POST
    combined_msgs = []
    # DEBUG: registrar los mensajes recogidos para facilitar el diagnóstico en tests
    try:
        logger.info(f"[DEBUG mensajes] mensajes_exito(initial)={mensajes_exito}, mensajes_error={mensajes_error}, mensajes_advertencia={mensajes_advertencia}")
    except Exception:
        pass
    if mensajes_exito:
        combined_msgs.extend(mensajes_exito)
    if mensajes_advertencia:
        combined_msgs.extend(mensajes_advertencia)
    if combined_msgs:
        # unir por coma y espacio, por ejemplo: "Solicitud aprobada correctamente, Advertencia: ..."
        # Sólo asignar si `mensaje_unico` no fue definido anteriormente (p.ej. en la rama POST)
        if not mensaje_unico:
            mensaje_unico = ", ".join(combined_msgs)

    # Fallback: si no construimos mensaje_unico pero hay mensajes_exito, tomar el primero
    if not mensaje_unico and mensajes_exito:
        try:
            mensaje_unico = mensajes_exito[0]
        except Exception:
            pass

    # If the GET contains a msg_exito param (we redirect using it), prefer it explicitly
    try:
        get_msg = request.GET.get('msg_exito')
        if get_msg:
            # Normalize plus-encoded spaces (should already be decoded by Django)
            mensaje_unico = get_msg
            # Also add to django messages so templates that inspect `messages` will render it
            try:
                from django.contrib import messages as _messages
                _messages.success(request, mensaje_unico)
                mensajes_exito.append(mensaje_unico)
            except Exception:
                # If messages framework unavailable for some reason, still keep mensaje_unico
                pass
    except Exception:
        pass

    # Also support session-based transient message set by POST handlers
    try:
        sess_msg = request.session.pop('msg_exito', None)
        if sess_msg:
            mensajes_exito.append(sess_msg)
            try:
                from django.contrib import messages as _messages2
                _messages2.success(request, sess_msg)
            except Exception:
                pass
            # If no mensaje_unico yet, use the session message
            if not mensaje_unico:
                mensaje_unico = sess_msg
    except Exception:
        pass

    # Filtros GET
    anio = request.GET.get('anio') if 'anio' in request.GET else None
    empleado_filtro = request.GET.get('empleado') if 'empleado' in request.GET else None
    empleado_display = None
    if empleado_filtro:
        if empleado_filtro.isdigit():
            empleado_obj = Empleado.objects.filter(idempleado=empleado_filtro).first()
            if empleado_obj:
                empleado_display = f"{empleado_obj.apellido}, {empleado_obj.nombres}".strip(', ')
            else:
                empleado_display = empleado_filtro
        else:
            empleado_display = empleado_filtro
    tipo_id = request.GET.get('tipo') if 'tipo' in request.GET else None
    estado = request.GET.get('estado') if 'estado' in request.GET else None
    # Fecha simple / rango
    fecha_desde_str = request.GET.get('fecha_desde') if 'fecha_desde' in request.GET else None
    fecha_hasta_str = request.GET.get('fecha_hasta') if 'fecha_hasta' in request.GET else None
    fecha_rango = request.GET.get('fecha_rango') if 'fecha_rango' in request.GET else None

    solicitudes = Solicitud_licencia.objects.select_related('idempleado', 'id_licencia', 'id_estado')
    vacaciones = Solicitud_vacaciones.objects.select_related('idempleado', 'id_estado')
    # Aplica filtros a ambas
    if anio:
        solicitudes = solicitudes.filter(fecha_desde__year=anio)
        vacaciones = vacaciones.filter(fecha_desde__year=anio)
    if tipo_id:
        solicitudes = solicitudes.filter(id_licencia__id_licencia=tipo_id)
        # Vacaciones solo si el tipo es "Vacaciones"
        tipo_vacaciones = Tipo_licencia.objects.filter(descripcion__iexact="Vacaciones").first()
        if tipo_vacaciones and str(tipo_vacaciones.id_licencia) == str(tipo_id):
            pass  # mostrar vacaciones
        else:
            vacaciones = vacaciones.none()
    if estado:
        solicitudes = solicitudes.filter(id_estado__estado__iexact=estado)
        vacaciones = vacaciones.filter(id_estado__estado__iexact=estado)
    if empleado_filtro:
        if empleado_filtro.isdigit():
            solicitudes = solicitudes.filter(idempleado__idempleado=empleado_filtro)
            vacaciones = vacaciones.filter(idempleado__idempleado=empleado_filtro)
        else:
            solicitudes = solicitudes.filter(
                models.Q(idempleado__nombres__icontains=empleado_filtro) |
                models.Q(idempleado__apellido__icontains=empleado_filtro)
            )
            vacaciones = vacaciones.filter(
                models.Q(idempleado__nombres__icontains=empleado_filtro) |
                models.Q(idempleado__apellido__icontains=empleado_filtro)
            )

    # (fecha filter intentionally handled below so it applies regardless of empleado filter)

    # Aplicar filtro por fecha (contención dentro del rango) - debe aplicarse
    # independientemente de si se filtró por empleado u otros campos.
    if fecha_desde_str:
        try:
            from datetime import datetime as _dt
            fecha_desde = _dt.strptime(fecha_desde_str, '%Y-%m-%d').date()
            # Si el usuario definió un rango explícito (checkbox), aplicamos
            # contención: la solicitud completa debe estar dentro del rango.
            if fecha_rango and fecha_hasta_str:
                fecha_hasta = _dt.strptime(fecha_hasta_str, '%Y-%m-%d').date()
                # Contención: fecha_desde >= filtro_desde AND fecha_hasta <= filtro_hasta
                solicitudes = solicitudes.filter(fecha_desde__gte=fecha_desde, fecha_hasta__lte=fecha_hasta)
                vacaciones = vacaciones.filter(fecha_desde__gte=fecha_desde, fecha_hasta__lte=fecha_hasta)
            else:
                # Single-date semantics: devolver solicitudes cuya ventana contenga
                # la fecha seleccionada. Es decir: fecha_desde <= fecha_sel <= fecha_hasta
                solicitudes = solicitudes.filter(fecha_desde__lte=fecha_desde, fecha_hasta__gte=fecha_desde)
                vacaciones = vacaciones.filter(fecha_desde__lte=fecha_desde, fecha_hasta__gte=fecha_desde)
        except Exception:
            # Si la fecha no es válida, ignorar el filtro
            pass

    # Unifica ambas listas
    solicitudes_list = list(solicitudes)
    for v in vacaciones:
        v.id_licencia = Tipo_licencia.objects.filter(descripcion__iexact="Vacaciones").first()
        v.archivo = None
        v.comentario = getattr(v, "comentario", "")
        v.dias = (v.fecha_hasta - v.fecha_desde).days + 1
        # Añadir idempleado_id para mostrar en la tabla
        v.idempleado_id = getattr(v.idempleado, 'idempleado_id', getattr(v.idempleado, 'pk', None))
        solicitudes_list.append(v)
    # Calcula los días para licencias
    for s in solicitudes_list:
        if not hasattr(s, "dias"):
            s.dias = (s.fecha_hasta - s.fecha_desde).days + 1
        # Añadir idempleado_id para mostrar en la tabla
        s.idempleado_id = getattr(s.idempleado, 'idempleado_id', getattr(s.idempleado, 'pk', None))

    # Ordena por fecha desde descendente
    solicitudes_list.sort(key=lambda x: x.fecha_desde, reverse=True)

    # Paginación
    page_number = request.GET.get('page')
    paginator = Paginator(solicitudes_list, 12)
    page_obj = paginator.get_page(page_number)

    # Para los combos
    empleados = Empleado.objects.all()
    tipos = Tipo_licencia.objects.all()
    estados = Estado_lic_vac.objects.all().order_by('estado')
    anios = Solicitud_licencia.objects.dates('fecha_desde', 'year')

    colisiones_por_solicitud = {}

    for s in page_obj:
        colisiones_otros = []
        licencias_otros = Solicitud_licencia.objects.filter(
            fecha_desde__lte=s.fecha_hasta,
            fecha_hasta__gte=s.fecha_desde,
            id_estado__estado__in=["En espera", "Aceptada"]
        ).exclude(idempleado=s.idempleado)
        vacaciones_otros = Solicitud_vacaciones.objects.filter(
            fecha_desde__lte=s.fecha_hasta,
            fecha_hasta__gte=s.fecha_desde,
            id_estado__estado__in=["En espera", "Aceptada"]
        ).exclude(idempleado=s.idempleado)
        for l in licencias_otros:
            colisiones_otros.append(f"{l.idempleado.nombres} {l.idempleado.apellido}: {l.fecha_desde.strftime('%d/%m/%Y')} - {l.fecha_hasta.strftime('%d/%m/%Y')}")
        for v in vacaciones_otros:
            colisiones_otros.append(f"{v.idempleado.nombres} {v.idempleado.apellido}: {v.fecha_desde.strftime('%d/%m/%Y')} - {v.fecha_hasta.strftime('%d/%m/%Y')}")
        if colisiones_otros:
            colisiones_por_solicitud[s.pk] = colisiones_otros

    try:
        logger.info(f"[VIEW DEBUG] mensaje_unico={mensaje_unico}, mensajes_exito={mensajes_exito}, mensajes_error={mensajes_error}, mensajes_advertencia={mensajes_advertencia}, messages_list_len={len(messages_list) if 'messages_list' in locals() else 0}")
    except Exception:
        pass

    # Preparar respuesta
    response = render(request, "nucleo/gestion_reporte_licencias.html", {
        "solicitudes": page_obj,
        "solicitudes_completas": solicitudes_list,
        "empleados": empleados,
        "tipos": tipos,
        "estados": estados,
        "anios": anios,
        "filtros": {
            "anio": anio,
            "empleado_id": empleado_filtro,
            "empleado_display": empleado_display,
            "tipo_id": tipo_id,
            "estado": estado,
            "fecha_desde": fecha_desde_str,
            "fecha_hasta": fecha_hasta_str,
            "fecha_rango": fecha_rango,
        },
        "page_obj": page_obj,
        "mensajes_exito": mensajes_exito,
        "mensajes_error": mensajes_error,
        "mensajes_advertencia": mensajes_advertencia,
        "mensaje_unico": mensaje_unico,
        "forced_msg": force_show_message,
        "messages": messages_list if 'messages_list' in locals() else [],
        "colisiones_por_solicitud": colisiones_por_solicitud,
    })
    
# (Eliminado código de limpieza de sesión autoaprobación)
    
    return response

@login_required
def gestionar_solicitudes(request):
    # Solo admin puede ver todas las solicitudes
    es_admin = request.user.is_superuser or request.user.has_perm('nucleo.ver_todas_las_solicitudes')
    empleado_obj = None
    if not es_admin:
        empleado_obj = get_object_or_404(Empleado, pk=request.user.id)

    solicitudes = Solicitud_licencia.objects.select_related('idempleado', 'id_licencia', 'id_estado')
    vacaciones = Solicitud_vacaciones.objects.select_related('idempleado', 'id_estado')

    if not es_admin:
        solicitudes = solicitudes.filter(idempleado=empleado_obj)
        vacaciones = vacaciones.filter(idempleado=empleado_obj)
    # Lectura de filtros GET
    anio = request.GET.get('anio') if 'anio' in request.GET else None
    empleado_filtro = request.GET.get('empleado') if 'empleado' in request.GET else None
    tipo_id = request.GET.get('tipo') if 'tipo' in request.GET else None
    estado = request.GET.get('estado') if 'estado' in request.GET else None

    # Manejo de acciones por POST (aprobar/rechazar desde la lista)
    if request.method == "POST":
        solicitud_id = request.POST.get('solicitud_id')
        accion = request.POST.get('accion')
        texto_gestor = request.POST.get('texto_gestor', '').strip()
        usuario_actual = request.user
        try:
            # Buscar en solicitudes de licencia
            solicitud = Solicitud_licencia.objects.filter(pk=solicitud_id).first()
            if solicitud:
                if accion == 'aprobar':
                    if usuario_actual.id == solicitud.idempleado.id:
                        mensaje_error = "No puedes aprobar tus propias solicitudes, debe hacerlo otro gestor."
                    else:
                        solicitud.id_estado = Estado_lic_vac.objects.get(estado__iexact='Aceptada')
                        solicitud.save()
                        mensaje_exito = 'Solicitud aprobada correctamente.'
                elif accion == 'rechazar':
                    solicitud.id_estado = Estado_lic_vac.objects.get(estado__iexact='Rechazada')
                    solicitud.texto_gestor = texto_gestor
                    solicitud.save()
                    mensaje_exito = 'Solicitud rechazada correctamente.'
            else:
                # Buscar en vacaciones
                solicitud = Solicitud_vacaciones.objects.filter(pk=solicitud_id).first()
                if not solicitud:
                    mensaje_error = 'No se encontró la solicitud.'
                else:
                    if accion == 'aprobar':
                        if usuario_actual.id == solicitud.idempleado.id:
                            mensaje_error = "No puedes aprobar tus propias solicitudes, debe hacerlo otro gestor."
                        else:
                            solicitud.id_estado = Estado_lic_vac.objects.get(estado__iexact='Aceptada')
                            solicitud.save()
                            Vacaciones_otorgadas.objects.create(
                                idempleado=solicitud.idempleado,
                                inicio_consumo=solicitud.fecha_desde,
                                fin_consumo=solicitud.fecha_hasta,
                                dias_disponibles=(solicitud.fecha_hasta - solicitud.fecha_desde).days + 1,
                                dias_consumidos=(solicitud.fecha_hasta - solicitud.fecha_desde).days + 1,
                            )
                            mensaje_exito = 'Solicitud aprobada correctamente.'
                    elif accion == 'rechazar':
                        solicitud.id_estado = Estado_lic_vac.objects.get(estado__iexact='Rechazada')
                        solicitud.save()
                        mensaje_exito = 'Solicitud rechazada correctamente.'
        except Exception as e:
            mensaje_error = f'Error al procesar la solicitud: {e}'

    # Aplica filtros GET a las querysets
    if anio:
        solicitudes = solicitudes.filter(fecha_desde__year=anio)
        vacaciones = vacaciones.filter(fecha_desde__year=anio)
    if tipo_id:
        solicitudes = solicitudes.filter(id_licencia__id_licencia=tipo_id)
        tipo_vacaciones = Tipo_licencia.objects.filter(descripcion__iexact="Vacaciones").first()
        if tipo_vacaciones and str(tipo_vacaciones.id_licencia) == str(tipo_id):
            pass
        else:
            vacaciones = vacaciones.none()
    if estado:
        solicitudes = solicitudes.filter(id_estado__estado__iexact=estado)
        vacaciones = vacaciones.filter(id_estado__estado__iexact=estado)
    if empleado_filtro:
        if empleado_filtro.isdigit():
            solicitudes = solicitudes.filter(idempleado__idempleado=empleado_filtro)
            vacaciones = vacaciones.filter(idempleado__idempleado=empleado_filtro)
        else:
            solicitudes = solicitudes.filter(
                models.Q(idempleado__nombres__icontains=empleado_filtro) |
                models.Q(idempleado__apellido__icontains=empleado_filtro)
            )
            vacaciones = vacaciones.filter(
                models.Q(idempleado__nombres__icontains=empleado_filtro) |
                models.Q(idempleado__apellido__icontains=empleado_filtro)
            )

    # Unifica ambas listas
    solicitudes_list = list(solicitudes)
    for v in vacaciones:
        v.id_licencia = Tipo_licencia.objects.filter(descripcion__iexact="Vacaciones").first()
        v.archivo = None
        v.comentario = getattr(v, "comentario", "")
        v.dias = (v.fecha_hasta - v.fecha_desde).days + 1
        solicitudes_list.append(v)
    # Calcula los días para licencias
    for s in solicitudes_list:
        if not hasattr(s, "dias"):
            s.dias = (s.fecha_hasta - s.fecha_desde).days + 1

    # Ordena por fecha desde descendente
    solicitudes_list.sort(key=lambda x: x.fecha_desde, reverse=True)

    # Paginación
    page_number = request.GET.get('page')
    paginator = Paginator(solicitudes_list, 12)
    page_obj = paginator.get_page(page_number)

    # Para los combos
    empleados = Empleado.objects.all()
    tipos = Tipo_licencia.objects.all()
    estados = Estado_lic_vac.objects.all().order_by('estado')
    anios = Solicitud_licencia.objects.dates('fecha_desde', 'year')

    return render(request, "nucleo/gestion_solicitudes.html", {
        "solicitudes": page_obj,
        "empleados": empleados,
        "tipos": tipos,
        "estados": estados,
        "anios": anios,
        "filtros": {
            "anio": anio,
            "empleado_id": empleado_filtro,
            "tipo_id": tipo_id,
            "estado": estado,
        },
        "page_obj": page_obj,
        "es_admin": es_admin,
    })

@login_required
def gestionar_estado_solicitud(request):
    if request.method == "POST":
        from django.contrib import messages

        solicitud_id = request.POST.get("solicitud_id")
        accion = (request.POST.get("accion") or "comentario").lower()
        tipo_solicitud = (request.POST.get("tipo_solicitud") or "").lower()
        comentario = request.POST.get("motivo_rechazo", "").strip()

        solicitud = None
        if tipo_solicitud == "vacacion":
            solicitud = Solicitud_vacaciones.objects.filter(pk=solicitud_id).select_related("idempleado", "id_estado").first()
        else:
            solicitud = (
                Solicitud_licencia.objects.filter(pk=solicitud_id)
                .select_related("idempleado", "id_estado", "id_licencia")
                .first()
            )
            if not solicitud:
                solicitud = Solicitud_vacaciones.objects.filter(pk=solicitud_id).select_related("idempleado", "id_estado").first()
                if solicitud:
                    tipo_solicitud = "vacacion"

        if not solicitud:
            mensaje_error = "No se encontró la solicitud."
            messages.error(request, mensaje_error)
            return redirect(_build_redirect_with_filters_from_post(request, mensaje_error, message_type="error"))

        resultado = procesar_accion_solicitud(
            solicitud,
            accion,
            request.user,
            comentario=comentario,
            enviar_notificacion=True,
        )

        if not resultado.success:
            mensaje_error = resultado.error or "No se pudo procesar la solicitud."
            messages.error(request, mensaje_error)
            return redirect(_build_redirect_with_filters_from_post(request, mensaje_error, message_type="error"))

        for advertencia in resultado.warnings:
            messages.warning(request, f"Advertencia: {advertencia}")

        if resultado.message:
            messages.success(request, resultado.message)

        if accion == "aprobar":
            redirect_message = "Solicitud aprobada correctamente"
        elif accion == "rechazar":
            redirect_message = resultado.message or "Solicitud rechazada correctamente"
        else:
            redirect_message = resultado.message or "Comentario guardado correctamente"

        return redirect(_build_redirect_with_filters_from_post(request, redirect_message))
@login_required
def ver_feriados(request):
    """Vista para mostrar feriados del año seleccionado en una tabla similar a ver_empleados"""
    from datetime import date
    from django.http import JsonResponse
    
    # Obtener el año desde el parámetro GET, por defecto el año actual
    current_year = int(request.GET.get('year', date.today().year))
    
    # Filtrar feriados por el año seleccionado
    feriados = Feriado.objects.filter(fecha__year=current_year).order_by('fecha')
    
    # Si es una petición AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        feriados_data = []
        for feriado in feriados:
            feriados_data.append({
                'id_feriado': feriado.id_feriado,
                'descripcion': feriado.descripcion,
                'fecha': feriado.fecha.strftime('%d/%m/%Y')
            })
        return JsonResponse({'feriados': feriados_data})
    
    # Para peticiones normales, renderizar el template
    feriados_data = []
    for feriado in feriados:
        feriados_data.append({
            'id_feriado': feriado.id_feriado,
            'descripcion': feriado.descripcion,
            'fecha': feriado.fecha
        })

    return render(request, "nucleo/ver_feriados.html", {
        "feriados": feriados_data,
        "current_year": current_year,
    })