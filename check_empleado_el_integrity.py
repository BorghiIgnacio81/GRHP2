#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from nucleo.models import Estado_empleado, Empleado_el, Empleado

def check_problematic_empleado_el():
    print("=== BUSCANDO REGISTROS PROBLEMÁTICOS EN EMPLEADO_EL ===")

    # Obtener todos los IDs de estado que existen
    existing_state_ids = set(Estado_empleado.objects.values_list('id_estado', flat=True))
    print(f"Estados existentes: {sorted(existing_state_ids)}")

    # Buscar registros problemáticos
    problematic_records = []
    all_records = Empleado_el.objects.all()

    print(f"\nVerificando {all_records.count()} registros en Empleado_el...")

    for emp_el in all_records:
        if emp_el.id_estado_id not in existing_state_ids:
            problematic_records.append(emp_el)
            print(f"❌ PROBLEMA: Empleado {emp_el.idempleado} tiene id_estado={emp_el.id_estado_id} (no existe)")

    if problematic_records:
        print(f"\n🔧 ENCONTRADOS {len(problematic_records)} REGISTROS PROBLEMÁTICOS")

        # Mostrar detalles
        for emp_el in problematic_records:
            try:
                empleado = emp_el.idempleado
                print(f"  - Empleado: {empleado.apellido}, {empleado.nombres} (ID: {empleado.idempleado_id})")
                print(f"    Estado problemático: {emp_el.id_estado_id}")
                print(f"    Fecha EL: {emp_el.fecha_el}")
            except Exception as e:
                print(f"  - Error obteniendo detalles: {e}")

        # Ofrecer corrección
        if existing_state_ids:
            default_state = Estado_empleado.objects.filter(id_estado__in=existing_state_ids).first()
            if default_state:
                print(f"\n💡 Sugerencia: Asignar estado por defecto '{default_state.estado}' (ID: {default_state.id_estado})")

                respuesta = input(f"\n¿Quieres corregir estos registros asignándoles el estado '{default_state.estado}'? (s/n): ")
                if respuesta.lower() == 's':
                    for emp_el in problematic_records:
                        emp_el.id_estado = default_state
                        emp_el.save()
                        print(f"  ✅ Corregido: Empleado {emp_el.idempleado} ahora tiene estado '{default_state.estado}'")
                    print("\n🎉 Todos los registros problemáticos han sido corregidos.")
                else:
                    print("No se realizaron cambios.")
    else:
        print("\n✅ No se encontraron registros problemáticos en Empleado_el.")

def check_raw_sql():
    """Verificar directamente en la base de datos"""
    from django.db import connection
    print("\n=== VERIFICACIÓN DIRECTA EN BASE DE DATOS ===")

    with connection.cursor() as cursor:
        # Verificar estados existentes
        cursor.execute("SELECT id_estado, estado FROM nucleo_estado_empleado ORDER BY id_estado")
        estados = cursor.fetchall()
        print("Estados en nucleo_estado_empleado:")
        for estado in estados:
            print(f"  {estado[0]}: {estado[1]}")

        # Verificar referencias problemáticas
        cursor.execute("""
            SELECT eel.id, eel.idempleado_id, eel.id_estado_id, e.nombres, e.apellido
            FROM nucleo_empleado_el eel
            LEFT JOIN nucleo_estado_empleado est ON eel.id_estado_id = est.id_estado
            LEFT JOIN nucleo_empleado e ON eel.idempleado_id = e.idempleado_id
            WHERE est.id_estado IS NULL
        """)
        problematic = cursor.fetchall()

        if problematic:
            print(f"\n❌ ENCONTRADAS {len(problematic)} REFERENCIAS PROBLEMÁTICAS:")
            for row in problematic:
                emp_id, estado_id, nombres, apellido = row[1], row[2], row[3], row[4]
                print(f"  Empleado {apellido}, {nombres} (ID: {emp_id}) - Estado inválido: {estado_id}")
        else:
            print("\n✅ No hay referencias problemáticas en la base de datos.")

if __name__ == "__main__":
    check_problematic_empleado_el()
    check_raw_sql()
