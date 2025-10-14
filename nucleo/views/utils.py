from django.views.decorators.http import require_GET
# AJAX: buscar localidades por provincia y texto
@require_GET
def buscar_localidades(request):
    provincia_id = request.GET.get('provincia_id')
    q = request.GET.get('q', '').strip()
    localidades = Localidad.objects.all()
    if provincia_id:
        localidades = localidades.filter(provincia_id=provincia_id)
    if q:
        localidades = localidades.filter(localidad__icontains=q)
    localidades = localidades.order_by('localidad')[:15]
    return JsonResponse(list(localidades.values('id', 'localidad')), safe=False)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from datetime import date
import os
import json

from nucleo.models import Localidad, Provincia, Sucursal, Empleado_el, Vacaciones_otorgadas, Solicitud_licencia, Estado_empleado
from nucleo.forms import PasswordResetUsernameForm

# AJAX: crear nueva localidad
@csrf_exempt
@require_POST
def crear_localidad(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        nombre = data.get('localidad', '').strip()
        provincia_id = data.get('provincia_id')
        if not nombre or not provincia_id:
            return JsonResponse({'success': False, 'error': 'Datos incompletos.'})
        provincia = Provincia.objects.filter(pk=provincia_id).first()
        if not provincia:
            return JsonResponse({'success': False, 'error': 'Provincia no encontrada.'})
        localidad, created = Localidad.objects.get_or_create(localidad__iexact=nombre, provincia=provincia, defaults={'localidad': nombre})
        if not created:
            return JsonResponse({'success': False, 'error': 'La localidad ya existe.'})
        return JsonResponse({'success': True, 'id': localidad.id, 'localidad': localidad.localidad})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def localidades_por_provincia(request):
    provincia_id = request.GET.get('provincia_id')
    localidades = Localidad.objects.filter(provincia_id=provincia_id).values('id', 'localidad')
    return JsonResponse(list(localidades), safe=False)

def direccion_sucursal(request):
    sucursal_id = request.GET.get('sucursal_id')
    try:
        sucursal = Sucursal.objects.get(pk=sucursal_id)
        direccion = sucursal.suc_dire
        mail = sucursal.suc_mail
    except Sucursal.DoesNotExist:
        direccion = ""
        mail = ""
    return JsonResponse({'direccion': direccion, 'mail': mail})


def password_reset_request(request):
    form = PasswordResetUsernameForm(request.POST or None)
    message = None
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data['username']
        try:
            user = User.objects.get(username=username)
            if not user.email:
                message = "No hay un email registrado para este usuario."
            else:
                # Si quieres enviar la contraseña actual (no recomendado), usa user.password (pero está hasheada)
                # Mejor: genera una nueva contraseña y envíala
                import random, string
                new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                user.set_password(new_password)
                user.save()
                send_mail(
                    subject="Recuperación de contraseña GRHP",
                    message=f"Su nueva contraseña es: {new_password}\nPor favor, cámbiela luego de ingresar.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                message = "Se ha enviado una nueva contraseña a su email."
        except User.DoesNotExist:
            message = "No existe un usuario con ese nombre."
    return render(request, "nucleo/password_reset_form.html", {"form": form, "message": message})

def calcular_antiguedad(fecha_antiguedad, fecha_hasta=None):
    if fecha_hasta is None:
        fecha_hasta = date.today()
    años = fecha_hasta.year - fecha_antiguedad.year
    meses = fecha_hasta.month - fecha_antiguedad.month
    dias = fecha_hasta.day - fecha_antiguedad.day

    if dias < 0:
        meses -= 1
        dias += (fecha_antiguedad.replace(month=fecha_antiguedad.month % 12 + 1, day=1) - fecha_antiguedad.replace(day=1)).days
    if meses < 0:
        años -= 1
        meses += 12

    partes = []
    if años > 0:
        partes.append(f"{años} año{'s' if años > 1 else ''}")
    if meses > 0:
        partes.append(f"{meses} mes{'es' if meses > 1 else ''}")
    if dias > 0 or not partes:
        partes.append(f"{dias} día{'s' if dias != 1 else ''}")

    return ", ".join(partes)

def calcular_edad(fecha_nacimiento):
    hoy = date.today()
    años = hoy.year - fecha_nacimiento.year
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        años -= 1
    return f"{años} años"

def formatear_jornada_laboral(datos_laborales):
    dias_map = [
        ('Lunes', 'lunes'),
        ('Martes', 'martes'),
        ('Miercoles', 'miércoles'),
        ('Jueves', 'jueves'),
        ('Viernes', 'viernes'),
        ('Sabado', 'sábado'),
        ('Domingo', 'domingo'),
    ]
    seleccionados = [datos_laborales.get(campo) for campo, _ in dias_map]
    nombres = [nombre for (_, nombre) in dias_map]

    grupos = []
    i = 0
    while i < 7:
        if seleccionados[i]:
            inicio = i
            while i + 1 < 7 and seleccionados[i + 1]:
                i += 1
            fin = i
            if inicio == fin:
                grupos.append(nombres[inicio])
            elif fin - inicio == 1:
                grupos.append(f"{nombres[inicio]} y {nombres[fin]}")
            else:
                grupos.append(f"de {nombres[inicio]} a {nombres[fin]}")
        i += 1

    dias_str = ", ".join(grupos)
    hora_inicio = datos_laborales['start_time'].strftime("%H:%M")
    hora_fin = datos_laborales['end_time'].strftime("%H:%M")
    return f"de {hora_inicio} a {hora_fin} {dias_str}"

# Se eliminó la función automática que cambiaba estados de empleados.
# La validación y resolución de colisiones se implementa en
# `nucleo.logic.validaciones.validar_solicitud_licencia` y debe invocarse
# desde las vistas/servicios que procesan solicitudes (aceptar/rechazar).
from nucleo.logic import validaciones

from datetime import date
from nucleo.models import Solicitud_licencia, Estado_lic_vac

def actualizar_licencias_consumidas():
    # The client requested to remove the 'Consumida' state from
    # Estado_lic_vac. Therefore we no longer change the solicitud state to
    # 'Consumida' when the end date passes. Licencias aceptadas will remain
    # as 'Aceptada' unless explicitly modified elsewhere.
    return

def actualizar_vacaciones_consumidas():
    from nucleo.models import Solicitud_vacaciones, Estado_lic_vac, Vacaciones_otorgadas
    estado_aceptada = Estado_lic_vac.objects.get(estado__iexact="Aceptada")
    hoy = date.today()
    solicitudes = Solicitud_vacaciones.objects.filter(id_estado=estado_aceptada, fecha_hasta__lte=hoy)
    for s in solicitudes:
    # Do not change the solicitud state to 'Consumida' per client request;
    # keep it as 'Aceptada' (or whatever it currently is). We still update
    # related Vacaciones_otorgadas.dias_consumidos when possible.
    # s.id_estado = estado_consumida
    # s.save()
        # Actualiza dias_consumidos en Vacaciones_otorgadas si existe
        vac_otorgada = Vacaciones_otorgadas.objects.filter(
            idempleado=s.idempleado,
            inicio_consumo=s.fecha_desde,
            fin_consumo=s.fecha_hasta
        ).first()
        if vac_otorgada:
            vac_otorgada.dias_consumidos = (s.fecha_hasta - s.fecha_desde).days + 1
            vac_otorgada.save()

