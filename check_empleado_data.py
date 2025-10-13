#!/usr/bin/env python
import os
import sys
import django
import re

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from nucleo.models import Empleado
from django.contrib.auth.models import User

def check_empleado_data():
    print("=== VERIFICANDO DATOS DEL EMPLEADO ===")

    # Buscar empleados con apellido Borghi
    empleados = Empleado.objects.filter(apellido='Borghi')
    for emp in empleados:
        print(f'Empleado: {emp.nombres} {emp.apellido}')
        print(f'DNI en BD: "{emp.dni}"')
        print(f'CUIL en BD: "{emp.cuil}"')

        # Simular normalización
        dni_norm = re.sub(r'[^0-9]', '', str(emp.dni or ''))
        cuil_norm = re.sub(r'[^0-9]', '', str(emp.cuil or ''))
        print(f'DNI normalizado: "{dni_norm}"')
        print(f'CUIL normalizado: "{cuil_norm}"')

        # Simular valores del formulario
        dni_form = "33.213.232"
        cuil_form = "20-33.213.232-7"

        dni_form_norm = re.sub(r'[^0-9]', '', dni_form)
        cuil_form_norm = re.sub(r'[^0-9]', '', cuil_form)

        print(f'Formulario DNI: "{dni_form}" -> normalizado: "{dni_form_norm}"')
        print(f'Formulario CUIL: "{cuil_form}" -> normalizado: "{cuil_form_norm}"')

        # Comparar
        dni_equal = dni_norm == dni_form_norm
        cuil_equal = cuil_norm == cuil_form_norm

        print(f'DNI igual: {dni_equal}')
        print(f'CUIL igual: {cuil_equal}')
        print('---')

if __name__ == "__main__":
    check_empleado_data()
