"""Diagnosticar por qué la vista considera 'No hay nada que actualizar'.
Construye payload similar al del harness y ejecuta la lógica de diff usada en la vista.
"""
import re
import json
from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse
from nucleo.models import Empleado, Plan_trabajo, Empleado_el, Empleado_eo
from nucleo.forms import EmpleadoModificarForm, EmpleadoELForm


def debug(employee_id=None):
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        admin = User.objects.create_superuser('dbg_admin', 'dbg@example.com', 'pass')
    emp = Empleado.objects.first() if not employee_id else Empleado.objects.filter(idempleado__id=employee_id).first()
    if not emp:
        print('No hay empleado')
        return
    empleado = emp
    user = None
    from django.contrib.auth.models import User as AuthUser
    user = AuthUser.objects.filter(id=empleado.idempleado_id).first()
    empleado_el_obj = Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el').first()
    plan = Plan_trabajo.objects.filter(idempleado=empleado).first()

    # original_data
    original_data = {}
    for field in EmpleadoModificarForm.base_fields:
        original_data[field] = getattr(empleado, field, '')
    if user:
        original_data['email'] = user.email
    original_laboral = {}
    for field in EmpleadoELForm.base_fields:
        original_laboral[field] = getattr(empleado_el_obj, field, '')

    print('Original nombres, telefono:', original_data.get('nombres'), original_data.get('telefono'))

    # Construct payload similar to what harness sent
    payload = {}
    payload['nombres'] = 'TestCambio'
    payload['telefono'] = '000000000'
    # include other required fields from original to avoid validation errors
    for f, v in original_data.items():
        if f not in payload:
            payload[f] = v
    # ensure laboral fields if present
    for f, v in original_laboral.items():
        payload[f] = v

    # emulate detection logic from view
    cambios = []
    def _strip_digits(v):
        import re
        try:
            return re.sub(r"\D", "", str(v or ""))
        except Exception:
            return str(v or "")

    form = EmpleadoModificarForm(payload, instance=empleado)
    form_laboral = EmpleadoELForm(payload, instance=empleado_el_obj)
    print('Form valid?', form.is_valid(), 'Form laboral valid?', form_laboral.is_valid())
    if form.is_valid() and form_laboral.is_valid():
        for field in form.fields:
            old = original_data.get(field, '')
            new = form.cleaned_data[field]
            if field in ('dni','cuil'):
                if _strip_digits(old) != _strip_digits(new):
                    cambios.append(f"{form.fields[field].label or field}: '{old}' → '{new}'")
            else:
                if str(old) != str(new):
                    cambios.append(f"{form.fields[field].label or field}: '{old}' → '{new}'")
        for field in form_laboral.fields:
            old = original_laboral.get(field, '')
            new = form_laboral.cleaned_data[field]
            if str(old) != str(new):
                cambios.append(f"{form_laboral.fields[field].label or field}: '{old}' → '{new}'")
    else:
        print('Form errors:', form.errors, form_laboral.errors)
    print('Detected cambios:', cambios)

if __name__ == '__main__':
    debug()
