from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render

from nucleo.models import (
    Tipo_licencia,
    Solicitud_licencia,
    Solicitud_vacaciones,
    Estado_lic_vac,
)

# Feature flag: cuando es True, evita borrar tipos de licencia con solicitudes relacionadas
BLOCK_DELETE_IF_TRANSACTIONS = True


@login_required
def alta_tipo_licencia(request):
    mensaje_exito = None
    mensaje_error = None
    descripcion = ""
    dias = ""
    pago_checked = True

    if request.method == "POST":
        descripcion = request.POST.get("Descripcion", "").strip()
        dias = request.POST.get("Dias", "").strip()
        pago_checked = request.POST.get("Pago") == "on"

        if not descripcion:
            mensaje_error = "El nombre de la licencia es obligatorio."
        else:
            try:
                dias_int = int(dias) if dias != "" else None
                Tipo_licencia.objects.create(
                    descripcion=descripcion,
                    dias=dias_int,
                    pago=pago_checked,
                )
                mensaje_exito = "Licencia creada correctamente."
                descripcion = ""
                dias = ""
                pago_checked = True
            except Exception as e:
                mensaje_error = f"Error al guardar: {e}"

    context = {
        "mensaje_exito": mensaje_exito,
        "mensaje_error": mensaje_error,
        "descripcion": descripcion,
        "dias": dias,
        "pago_checked": pago_checked,
    }
    return render(request, "nucleo/alta_tipo_licencia.html", context)


@login_required
def modificar_borrar_licencia(request):
    mensaje_exito = None
    mensaje_error = None

    licencias = Tipo_licencia.objects.exclude(id_licencia=7).order_by("descripcion")
    licencia = None
    selected_id = request.POST.get("id_licencia") or request.GET.get("id_licencia")

    if selected_id:
        try:
            licencia = Tipo_licencia.objects.get(pk=selected_id)
            solicitudes_relacionadas = list(
                Solicitud_licencia.objects.filter(id_licencia=licencia)
            )
            solicitudes_aprobadas = sum(
                1
                for s in solicitudes_relacionadas
                if getattr(s.id_estado, "estado", "").strip().lower() in ("aceptada", "aprobada")
            )
        except Exception:
            licencia = None
            solicitudes_relacionadas = []
            solicitudes_aprobadas = 0
    else:
        solicitudes_relacionadas = []
        solicitudes_aprobadas = 0

    mostrar_modal_protegido = False
    mostrar_modal_confirmar_renombrar = False

    if request.method == "POST":
        post_id_lic = request.POST.get("id_licencia")

        if post_id_lic:
            try:
                licencia = Tipo_licencia.objects.get(pk=post_id_lic)
            except Exception:
                licencia = None

            solicitudes_relacionadas = (
                list(Solicitud_licencia.objects.filter(id_licencia=licencia)) if licencia else []
            )
            solicitudes_aprobadas = sum(
                1
                for s in solicitudes_relacionadas
                if getattr(s.id_estado, "estado", "").strip().lower() in ("aceptada", "aprobada")
            )

            if request.POST.get("confirmar_eliminar_todo"):
                for s in solicitudes_relacionadas:
                    s.delete()
                if licencia:
                    licencia.delete()
                mensaje_exito = "Licencia y solicitudes asociadas eliminadas."
                licencia = None
                selected_id = None
                solicitudes_relacionadas = []
            elif request.POST.get("confirmar_renombrar_si"):
                if licencia:
                    licencia.descripcion = f"{licencia.descripcion} (Discontinuada)"
                    licencia.save()
                    mensaje_exito = "Licencia marcada como discontinuada."
            elif request.POST.get("confirmar_renombrar"):
                mostrar_modal_confirmar_renombrar = True
            else:
                accion = request.POST.get("accion")
                if accion == "actualizar" and licencia:
                    descripcion = request.POST.get("Descripcion", "").strip()
                    dias = request.POST.get("Dias", "").strip()
                    pago = request.POST.get("Pago") == "on"
                    try:
                        dias_int = int(dias) if dias != "" else None
                    except Exception:
                        dias_int = None
                    licencia.descripcion = descripcion
                    licencia.dias = dias_int
                    licencia.pago = pago
                    licencia.save()
                    mensaje_exito = "Licencia actualizada correctamente."
                elif accion == "borrar" and licencia:
                    if solicitudes_relacionadas and BLOCK_DELETE_IF_TRANSACTIONS:
                        mostrar_modal_protegido = True
                    else:
                        if solicitudes_relacionadas:
                            for s in solicitudes_relacionadas:
                                s.delete()
                        if licencia:
                            licencia.delete()
                        mensaje_exito = "Licencia borrada correctamente."
                        licencia = None
                        selected_id = None

            return render(
                request,
                "nucleo/modificar_borrar_licencia.html",
                {
                    "licencias": licencias,
                    "licencia": licencia,
                    "selected_id": selected_id,
                    "mensaje_exito": mensaje_exito,
                    "mensaje_error": mensaje_error,
                    "mostrar_modal_protegido": mostrar_modal_protegido,
                    "mostrar_modal_confirmar_renombrar": mostrar_modal_confirmar_renombrar,
                    "solicitudes_relacionadas": solicitudes_relacionadas,
                    "solicitudes_aprobadas": solicitudes_aprobadas,
                },
            )

        solicitud_id = request.POST.get("solicitud_id")
        accion = request.POST.get("accion")
        motivo_rechazo = request.POST.get("motivo_rechazo", "").strip()

        try:
            usuario_actual = request.user
            solicitud = Solicitud_licencia.objects.filter(pk=solicitud_id).first()
            if solicitud:
                texto_gestor = motivo_rechazo if motivo_rechazo else ""
                accion_post = accion
                if accion_post == "aprobar" and usuario_actual.id == solicitud.idempleado.id:
                    messages.error(request, "No puedes aprobar tus propias solicitudes, debe hacerlo otro gestor.")
                elif accion_post == "aprobar":
                    estado_aceptada = Estado_lic_vac.objects.get(estado__iexact="Aceptada")
                    solicitud.id_estado = estado_aceptada
                    solicitud.save()
                    messages.success(request, "Solicitud aprobada correctamente.")
                elif accion_post == "rechazar":
                    estado_rechazada = Estado_lic_vac.objects.get(estado__iexact="Rechazada")
                    solicitud.id_estado = estado_rechazada
                    solicitud.texto_gestor = texto_gestor
                    solicitud.save()
                    messages.success(request, "Solicitud rechazada correctamente.")
                else:
                    solicitud.save()
            else:
                solicitud = Solicitud_vacaciones.objects.filter(pk=solicitud_id).first()
                if not solicitud:
                    raise Exception("No se encontró la solicitud.")
                if accion == "aprobar" and usuario_actual.id == solicitud.idempleado.id:
                    messages.error(request, "No puedes aprobar tus propias solicitudes, debe hacerlo otro gestor.")
                elif accion == "aprobar":
                    estado_aceptada = Estado_lic_vac.objects.get(estado__iexact="Aceptada")
                    solicitud.id_estado = estado_aceptada
                    solicitud.save()
                    from nucleo.models import Vacaciones_otorgadas

                    Vacaciones_otorgadas.objects.create(
                        idempleado=solicitud.idempleado,
                        inicio_consumo=solicitud.fecha_desde,
                        fin_consumo=solicitud.fecha_hasta,
                        dias_disponibles=(solicitud.fecha_hasta - solicitud.fecha_desde).days + 1,
                        dias_consumidos=(solicitud.fecha_hasta - solicitud.fecha_desde).days + 1,
                    )
                    messages.success(request, "Solicitud aprobada correctamente.")
                elif accion == "rechazar":
                    estado_rechazada = Estado_lic_vac.objects.get(estado__iexact="Rechazada")
                    solicitud.id_estado = estado_rechazada
                    solicitud.save()
                    messages.success(request, "Solicitud rechazada correctamente.")
        except Exception as e:
            messages.error(request, f"Error al procesar la solicitud: {e}")

    return render(
        request,
        "nucleo/modificar_borrar_licencia.html",
        {
            "licencias": licencias,
            "licencia": licencia,
            "selected_id": selected_id,
            "mensaje_exito": mensaje_exito,
            "mensaje_error": mensaje_error,
            "mostrar_modal_protegido": mostrar_modal_protegido,
            "mostrar_modal_confirmar_renombrar": mostrar_modal_confirmar_renombrar,
            "solicitudes_relacionadas": solicitudes_relacionadas,
            "solicitudes_aprobadas": solicitudes_aprobadas,
        },
    )


@login_required
def ver_tipo_licencia(request):
    tipos_licencia = Tipo_licencia.objects.exclude(id_licencia=7).order_by("id_licencia")

    tipos_data = []
    for tipo in tipos_licencia:
        tipos_data.append(
            {
                "id_licencia": tipo.id_licencia,
                "descripcion": tipo.descripcion,
                "dias": tipo.dias if tipo.dias is not None else "Sin límite",
                "pago": "Sí" if tipo.pago else "No",
            }
        )

    return render(
        request,
        "nucleo/ver_tipo_licencia.html",
        {
            "tipos_licencia": tipos_data,
        },
    )
