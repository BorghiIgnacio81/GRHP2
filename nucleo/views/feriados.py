from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from nucleo.models import Feriado, Empleado, Empleado_el, Empleado_eo
from datetime import date

@login_required
def alta_feriado(request):
    mensaje_exito = None
    mensaje_error = None
    descripcion = ""
    fecha = ""
    if request.method == "POST":
        descripcion = request.POST.get("descripcion", "").strip()
        fecha = request.POST.get("fecha", "").strip()
        if not descripcion or not fecha:
            mensaje_error = "Todos los campos son obligatorios."
        else:
            try:
                fecha_valida = date.fromisoformat(fecha)
            except ValueError:
                mensaje_error = "La fecha indicada no es válida."
            else:
                if Feriado.objects.filter(fecha=fecha_valida).exists():
                    mensaje_error = "Ya existe un feriado registrado para ese día."
                else:
                    try:
                        Feriado.objects.create(
                            descripcion=descripcion,
                            fecha=fecha_valida
                        )

                        mensaje_exito = "Feriado creado correctamente."
                        descripcion = ""
                        fecha = ""
                        # Limpiar campos después de éxito
                    except Exception as e:
                        mensaje_error = f"Error al guardar: {e}"
    return render(request, "nucleo/alta_feriado.html", {
        "mensaje_exito": mensaje_exito,
        "mensaje_error": mensaje_error,
        "today": date.today(),
        "descripcion": descripcion,
        "fecha": fecha,
    })

@login_required
def modificar_borrar_feriado(request):
    mensaje_exito = None
    mensaje_error = None

    selected_anio = request.GET.get("anio") or ""
    selected_id = request.GET.get("id_feriado") or request.POST.get("id_feriado") or ""
    feriados = Feriado.objects.all()
    if selected_anio:
        feriados = feriados.filter(fecha__year=selected_anio)
    feriados = feriados.order_by('fecha')

    feriado = None
    if selected_id:
        try:
            feriado = Feriado.objects.get(pk=selected_id)
        except Feriado.DoesNotExist:
            feriado = None
            mensaje_error = "Feriado no encontrado."

    if request.method == "POST" and feriado:
        accion = request.POST.get("accion")
        if accion == "actualizar":
            descripcion = request.POST.get("descripcion", "").strip()
            fecha = request.POST.get("fecha", "").strip()
            if not descripcion or not fecha:
                mensaje_error = "Todos los campos son obligatorios."
            else:
                # Validar formato de fecha y evitar duplicados al actualizar
                try:
                    fecha_valida = date.fromisoformat(fecha)
                except ValueError:
                    mensaje_error = "La fecha indicada no es válida."
                else:
                    # Evitar que quede la misma fecha que otro feriado existente
                    if Feriado.objects.filter(fecha=fecha_valida).exclude(pk=feriado.pk).exists():
                        mensaje_error = "Ya existe un feriado registrado para ese día."
                    else:
                        # Permitir modificar feriado incluso si la fecha es pasada.
                        feriado.descripcion = descripcion
                        feriado.fecha = fecha_valida
                        feriado.save()
                        mensaje_exito = "Feriado actualizado correctamente."
        elif accion == "borrar":
            nombre = feriado.descripcion
            feriado.delete()
            mensaje_exito = f"Feriado '{nombre}' eliminado correctamente."
            feriado = None
            selected_id = None

    anios = Feriado.objects.dates('fecha', 'year')

    return render(request, "nucleo/modificar_borrar_feriado.html", {
        "anios": anios,
        "feriados": feriados,
        "feriado": feriado,
        "selected_anio": selected_anio,
        "selected_id": selected_id,
        "mensaje_exito": mensaje_exito,
        "mensaje_error": mensaje_error,
    })


