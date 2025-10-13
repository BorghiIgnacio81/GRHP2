from django.db import transaction
from django.db.models import Sum, Q
from datetime import date, timedelta
from formtools.wizard.views import SessionWizardView
import json
import os
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect

from nucleo.forms import (
    DatosPersonalesForm, PlanTrabajoForm, LaboralesCombinadoForm, ConfirmacionForm,
    EmpleadoModificarForm, EmpleadoELForm
)
from nucleo.models import (
    Empleado, Estado_empleado, Convenio, Puesto, Sucursal, Localidad, Provincia,
    Empleado_el, Empleado_eo, Tipo_licencia, Solicitud_licencia, Estado_lic_vac,
    Feriado, Vacaciones_otorgadas, Plan_trabajo, Solicitud_vacaciones
)
from nucleo.views.utils import calcular_antiguedad, calcular_edad, formatear_jornada_laboral, localidades_por_provincia

FORMS = [
    ("personales", DatosPersonalesForm),
    ("laborales", LaboralesCombinadoForm),
]
TEMPLATES = {
    "personales": "nucleo/alta_empleado_personales.html",
    "laborales": "nucleo/alta_empleado_laborales.html",
}

class AltaEmpleadoWizard(SessionWizardView):
    form_list = FORMS

    def get_template_names(self):
        return [TEMPLATES[self.steps.current]]

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        if self.steps.current == "personales":
            context['provincias'] = Provincia.objects.all()
            # Persistir provincia y localidad seleccionadas
            provincia_seleccionada = None
            localidad_nombre = ''
            localidad_id = ''
            if form.is_bound:
                provincia_seleccionada = form.data.get('provincia') or form.data.get('personales-provincia')
                localidad_nombre = form.data.get('localidad') or form.data.get('personales-localidad') or ''
                localidad_id = form.data.get('personales-id_localidad') or ''
            elif form.initial:
                provincia_seleccionada = form.initial.get('provincia')
                localidad_id = form.initial.get('id_localidad')
            context['provincia_seleccionada'] = provincia_seleccionada
            context['localidad_nombre'] = localidad_nombre
            context['localidad_id'] = localidad_id
        return context

    def done(self, form_list, **kwargs):
        form_personales = self.get_cleaned_data_for_step("personales")
        form_laborales = self.get_cleaned_data_for_step("laborales")

        # Obtener is_staff del POST (checkbox)
        is_staff = False
        if self.request.POST.get('is_staff') == 'true':
            is_staff = True

        # 1. Crear usuario en auth_user
        email = form_personales['email']
        nombres = form_personales['nombres']
        apellido = form_personales['apellido']
        dni = form_personales['dni']

        username_base = f"{nombres}{apellido}".replace(" ", "").lower()
        username = username_base
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{username_base}{i}"
            i += 1
        password = f"{str(dni)[:5]}{apellido[:4]}"

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=nombres,
            last_name=apellido,
            email=email
        )
        # Setear is_staff según el checkbox
        user.is_staff = is_staff
        user.save()
        # Log de creación de usuario en auth_user
        try:
            from nucleo.models import Log_auditoria
            Log_auditoria.objects.create(
                idusuario=self.request.user,
                nombre_tabla='auth_user',
                idregistro=user.id,
                accion='insert',
                cambio={
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_staff': user.is_staff
                }
            )
        except Exception:
            pass

        try:
            from nucleo.models import Log_auditoria
            with transaction.atomic():
                empleado = Empleado.objects.create(
                    idempleado=user,
                    nombres=nombres,
                    apellido=apellido,
                    dni=dni,
                    fecha_nac=form_personales['fecha_nac'],
                    id_nacionalidad=form_personales['id_nacionalidad'],
                    id_civil=form_personales['id_civil'],
                    num_hijos=form_personales['num_hijos'],
                    id_sexo=form_personales['id_sexo'],
                    id_localidad=form_personales['id_localidad'],
                    dr_personal=form_personales['dr_personal'],
                    telefono=form_personales['telefono'],
                    cuil=form_personales['cuil'],
                )
                Log_auditoria.objects.create(
                    idusuario=self.request.user,
                    nombre_tabla='Empleado',
                    idregistro=empleado.idempleado.id,
                    accion='insert',
                    cambio={
                        'nombres': empleado.nombres,
                        'apellido': empleado.apellido,
                        'dni': empleado.dni,
                        'fecha_nac': str(empleado.fecha_nac),
                        'telefono': empleado.telefono,
                        'cuil': empleado.cuil
                    }
                )

                empleado_el = Empleado_el.objects.create(
                    fecha_el=form_laborales['alta_ant'],
                    fecha_est=form_laborales['fecha_est'],
                    idempleado=empleado,
                    id_estado=form_laborales['id_estado'],
                    id_convenio=form_laborales['id_convenio'],
                    id_puesto=form_laborales['id_puesto'],
                    alta_ant=form_laborales['alta_ant']
                )
                Log_auditoria.objects.create(
                    idusuario=self.request.user,
                    nombre_tabla='Empleado_el',
                    idregistro=empleado_el.id,
                    accion='insert',
                    cambio={
                        'id_estado': empleado_el.id_estado_id,
                        'id_convenio': empleado_el.id_convenio_id,
                        'id_puesto': empleado_el.id_puesto_id,
                        'alta_ant': str(empleado_el.alta_ant)
                    }
                )

                plan_trabajo = Plan_trabajo.objects.create(
                    idempleado=empleado,
                    lunes=form_laborales.get('lunes', False),
                    martes=form_laborales.get('martes', False),
                    miercoles=form_laborales.get('miercoles', False),
                    jueves=form_laborales.get('jueves', False),
                    viernes=form_laborales.get('viernes', False),
                    sabado=form_laborales.get('sabado', False),
                    domingo=form_laborales.get('domingo', False),
                    start_time=form_laborales['start_time'],
                    end_time=form_laborales['end_time']
                )
                # Only create an insert audit log for Plan_trabajo if it contains meaningful data
                plan_has_meaningful = any([
                    plan_trabajo.lunes, plan_trabajo.martes, plan_trabajo.miercoles,
                    plan_trabajo.jueves, plan_trabajo.viernes, plan_trabajo.sabado,
                    plan_trabajo.domingo,
                ]) or (getattr(plan_trabajo, 'start_time', None) is not None) or (getattr(plan_trabajo, 'end_time', None) is not None)
                if plan_has_meaningful:
                    Log_auditoria.objects.create(
                        idusuario=self.request.user,
                        nombre_tabla='Plan_trabajo',
                        idregistro=plan_trabajo.id,
                        accion='insert',
                        cambio={
                            'idempleado': empleado.idempleado.id,
                            'nombres': empleado.nombres,
                            'apellido': empleado.apellido,
                            'dias': {
                                'lunes': plan_trabajo.lunes,
                                'martes': plan_trabajo.martes,
                                'miercoles': plan_trabajo.miercoles,
                                'jueves': plan_trabajo.jueves,
                                'viernes': plan_trabajo.viernes,
                                'sabado': plan_trabajo.sabado,
                                'domingo': plan_trabajo.domingo,
                            },
                            'start_time': str(plan_trabajo.start_time),
                            'end_time': str(plan_trabajo.end_time)
                        }
                    )

                empleado_eo = Empleado_eo.objects.create(
                    fecha_eo=form_laborales['alta_ant'],
                    idempleado=empleado,
                    id_sucursal=form_laborales['id_sucursal']
                )
                Log_auditoria.objects.create(
                    idusuario=self.request.user,
                    nombre_tabla='Empleado_eo',
                    idregistro=empleado_eo.id,
                    accion='insert',
                    cambio={
                        'idempleado': empleado.idempleado.id,
                        'nombres': empleado.nombres,
                        'apellido': empleado.apellido,
                        'id_sucursal': empleado_eo.id_sucursal_id,
                        'fecha_eo': str(empleado_eo.fecha_eo)
                    }
                )
            # Enviar mail automáticamente con las credenciales
            try:
                from nucleo.utils_mail import enviar_mail_credenciales_auto
                enviar_mail_credenciales_auto(email, username, password)
            except Exception as mail_exc:
                messages.warning(self.request, f"El empleado fue creado pero no se pudo enviar el mail: {mail_exc}")
        except Exception as e:
            messages.error(self.request, f"Error al guardar el empleado: {e}")
            return redirect('alta_empleado')

        return render(self.request, "nucleo/alta_empleado_exito.html", {
            "empleado_nombre": f"{empleado.nombres} {empleado.apellido}",
            "username": username,
            "password": password,
            "email": email,
            "idempleado": empleado.idempleado.id,
        })