# nucleo/forms.py

from .forms.empleados import (
    DatosPersonalesForm, EmpleadoELForm, PlanTrabajoForm, EmpleadoEOForm,
    LaboralesCombinadoForm, EmpleadoModificarForm
)
from .forms.licencias import PasswordResetUsernameForm, ConfirmacionForm

FORMS = [
    ("personales", DatosPersonalesForm),
    ("laborales", LaboralesCombinadoForm),
]