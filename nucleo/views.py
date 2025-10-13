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





