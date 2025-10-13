"""Script de prueba: crear feriado + solicitud de 1 día + simular aprobación de gestor.
Imprime estado final y texto_gestor.
Se ejecuta desde el repo con el venv: /root/myenv/bin/python manage.py shell o como script.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
django.setup()

from datetime import date, timedelta
from django.contrib.auth.models import User
from nucleo.models import Feriado, Empleado, Tipo_licencia, Estado_lic_vac, Solicitud_licencia, Plan_trabajo
from nucleo.logic.validaciones import validar_solicitud_licencia, ValidacionError

# Crear/obtener datos de prueba
feriado_fecha = date.today() + timedelta(days=5)
Feriado.objects.filter(fecha=feriado_fecha).delete()
fer = Feriado.objects.create(descripcion='F_test', fecha=feriado_fecha)
print('Feriado creado:', fer.fecha)

# Usuario empleado de prueba
user, created = User.objects.get_or_create(username='test_emp')
if created:
    user.set_password('p')
    user.save()
# crear datos relacionados obligatorios
from nucleo.models import Provincia, Localidad, Nacionalidad, EstadoCivil, Sexo
prov, _ = Provincia.objects.get_or_create(provincia='P_test')
loc, _ = Localidad.objects.get_or_create(localidad='L_test', provincia=prov)
nac, _ = Nacionalidad.objects.get_or_create(nacionalidad='Arg_test')
estc, _ = EstadoCivil.objects.get_or_create(estado_civil='Soltero')
sex, _ = Sexo.objects.get_or_create(sexo='M')

emp_defaults = {
    'nombres': 'T', 'apellido': 'U', 'dni': '99999998', 'fecha_nac': date(1990,1,1),
    'cuil': '20-11111111-1', 'id_nacionalidad': nac, 'id_civil': estc, 'id_sexo': sex, 'id_localidad': loc
}
emp, _ = Empleado.objects.get_or_create(idempleado=user, defaults=emp_defaults)

# Plan de trabajo: trabaja lunes-viernes
Plan_trabajo.objects.filter(idempleado=emp).delete()
from datetime import time
Plan_trabajo.objects.create(idempleado=emp, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True, sabado=False, domingo=False, start_time=time(9,0), end_time=time(18,0))

# Tipo licencia 1 dia
tipo, _ = Tipo_licencia.objects.get_or_create(descripcion='Prueba_test', defaults={'dias':1,'pago':False})

# Estado pendiente
estado_en_espera, _ = Estado_lic_vac.objects.get_or_create(estado='En espera')
estado_aceptada, _ = Estado_lic_vac.objects.get_or_create(estado='Aceptada')
estado_rechazada, _ = Estado_lic_vac.objects.get_or_create(estado='Rechazada')

# Crear solicitud de 1 dia en feriado
Solicitud_licencia.objects.filter(idempleado=emp, fecha_desde=feriado_fecha, fecha_hasta=feriado_fecha).delete()
sol = Solicitud_licencia.objects.create(idempleado=emp, id_licencia=tipo, fecha_desde=feriado_fecha, fecha_hasta=feriado_fecha, comentario='test', texto_gestor='', id_estado=estado_en_espera)
print('Solicitud creada id:', sol.pk)

# Simular aprobación por gestor: llamar a validar_solicitud_licencia
try:
    ok, warnings = validar_solicitud_licencia(sol)
except ValidacionError as e:
    print('Validación rechazó la solicitud:', e)
    # marcar como rechazada
    sol.id_estado = estado_rechazada
    sol.texto_gestor = str(e)
    sol.save()
else:
    if warnings:
        sol.texto_gestor = '\n'.join(warnings)
    sol.id_estado = estado_aceptada
    sol.save()
    print('Solicitud aceptada con advertencias:' if warnings else 'Solicitud aceptada sin advertencias')
    if warnings:
        print('Advertencias:', warnings)

# Mostrar estado final
sol.refresh_from_db()
print('Estado final:', sol.id_estado.estado)
print('texto_gestor:', repr(sol.texto_gestor))
