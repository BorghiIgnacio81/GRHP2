import os
import sys
from datetime import date

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
import django
django.setup()

from django.template.loader import render_to_string
from nucleo.models import Empleado, Empleado_el, Empleado_eo

emp = Empleado.objects.exclude(idempleado_id=1).first()
if not emp:
    print('No empleados found')
    sys.exit(0)

# Reproduce la resolución de sucursal/puesto similar a la vista
empleado_eo = Empleado_eo.objects.filter(idempleado=emp).order_by('-fecha_eo').first()
sucursal = empleado_eo.id_sucursal.sucursal if empleado_eo and getattr(empleado_eo, 'id_sucursal', None) else 'Sin sucursal'
puesto = 'Responsable de farmacia'
try:
    if empleado_eo and getattr(empleado_eo, 'id_puesto', None):
        puesto = getattr(empleado_eo.id_puesto, 'tipo_puesto', puesto) or puesto
except Exception:
    pass

empleado_el = Empleado_el.objects.filter(idempleado=emp).order_by('-fecha_el').first()
try:
    if (not puesto or puesto == 'Responsable de farmacia') and empleado_el and getattr(empleado_el, 'id_puesto', None):
        puesto = getattr(empleado_el.id_puesto, 'tipo_puesto', puesto) or puesto
except Exception:
    pass

fecha_ingreso = empleado_el.fecha_est if empleado_el and empleado_el.fecha_est else None
fecha_emision = date.today()
meses = [
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
]
fecha_emision_larga = f"{fecha_emision.day} de {meses[fecha_emision.month]} del año {fecha_emision.year}"

convenio_val = ''
try:
    if empleado_el and getattr(empleado_el, 'id_convenio', None):
        convenio_val = getattr(empleado_el.id_convenio, 'tipo_convenio', '') or str(empleado_el.id_convenio)
except Exception:
    convenio_val = ''

ctx = {
    'empleado': emp,
    'empresa': f'Farmacia G\u00f3mez de Galarze, {sucursal}',
    'puesto': puesto,
    'fecha_ingreso': fecha_ingreso,
    'fecha_emision': fecha_emision,
    'fecha_emision_larga': fecha_emision_larga,
    'fecha_ant': fecha_ingreso.strftime('%d/%m/%Y') if fecha_ingreso else 'No disponible',
    'convenio': convenio_val,
}

output = render_to_string('nucleo/emitir_certificado.html', ctx)
print(output)
