#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from nucleo.models import Estado_empleado, Empleado_el

def check_foreign_key_integrity():
    print("=== VERIFICANDO INTEGRIDAD DE LLAVES FORÁNEAS ===")

    # Ver qué estados existen
    print("\nEstados existentes en Estado_empleado:")
    estados = Estado_empleado.objects.all()
    for estado in estados:
        print(f"  ID: {estado.id_estado}, Estado: {estado.estado}")

    # Ver registros problemáticos en Empleado_el
    print("\nRegistros en Empleado_el con id_estado que no existen:")
    empleados_el = Empleado_el.objects.all()
    problematic_records = []

    for emp_el in empleados_el:
        try:
            # Intentar acceder al estado para ver si existe
            estado = emp_el.id_estado
            print(f"  Empleado {emp_el.idempleado}: Estado ID {estado.id_estado} - {estado.estado}")
        except Estado_empleado.DoesNotExist:
            print(f"  ❌ PROBLEMA: Empleado {emp_el.idempleado} tiene id_estado={emp_el.id_estado_id} que no existe")
            problematic_records.append(emp_el)

    if problematic_records:
        print(f"\n🔧 ENCONTRADOS {len(problematic_records)} REGISTROS PROBLEMÁTICOS")
        print("Estos registros necesitan ser corregidos.")

        # Mostrar opciones de corrección
        print("\nOpciones para corregir:")
        print("1. Asignar un estado válido existente")
        print("2. Crear el estado faltante")
        print("3. Eliminar los registros problemáticos")

        # Sugerir corrección automática
        if estados.exists():
            default_estado = estados.first()
            print(f"\nSugerencia: Asignar estado por defecto '{default_estado.estado}' (ID: {default_estado.id_estado})")

            respuesta = input(f"\n¿Quieres asignar el estado '{default_estado.estado}' a todos los registros problemáticos? (s/n): ")
            if respuesta.lower() == 's':
                for emp_el in problematic_records:
                    emp_el.id_estado = default_estado
                    emp_el.save()
                    print(f"  ✅ Corregido: Empleado {emp_el.idempleado} ahora tiene estado '{default_estado.estado}'")
                print("\n🎉 Todos los registros problemáticos han sido corregidos.")
            else:
                print("No se realizaron cambios.")
        else:
            print("No hay estados válidos para asignar. Necesitas crear estados primero.")
    else:
        print("\n✅ No se encontraron problemas de integridad.")

if __name__ == "__main__":
    check_foreign_key_integrity()
