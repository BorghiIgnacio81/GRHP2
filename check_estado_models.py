#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from nucleo.models import Estado_empleado, Estado_laboral, Empleado_el

def check_estado_models():
    print("=== VERIFICANDO MODELOS DE ESTADO ===")

    print("\nEstado_empleado:")
    estados_emp = Estado_empleado.objects.all()
    for estado in estados_emp:
        print(f"  ID: {estado.id_estado}, Estado: {estado.estado}")

    print("\nEstado_laboral:")
    estados_lab = Estado_laboral.objects.all()
    for estado in estados_lab:
        print(f"  ID: {estado.id_estado}, Estado: {estado.estado}")

    # Verificar si hay IDs superpuestos
    emp_ids = set(estados_emp.values_list('id_estado', flat=True))
    lab_ids = set(estados_lab.values_list('id_estado', flat=True))

    overlap = emp_ids & lab_ids
    if overlap:
        print(f"\n⚠️  IDs superpuestos entre Estado_empleado y Estado_laboral: {overlap}")
    else:
        print("\n✅ No hay IDs superpuestos entre los modelos de estado.")

    # Verificar si Empleado_el está referenciando IDs de Estado_laboral
    print("\nVerificando referencias de Empleado_el:")
    for emp_el in Empleado_el.objects.all():
        estado_id = emp_el.id_estado_id
        if estado_id in lab_ids and estado_id not in emp_ids:
            print(f"❌ PROBLEMA: Empleado_el {emp_el.id} referencia id_estado={estado_id} que existe en Estado_laboral pero no en Estado_empleado")
            estado_lab = Estado_laboral.objects.get(id_estado=estado_id)
            print(f"   Estado_laboral correspondiente: '{estado_lab.estado}'")

def check_database_tables():
    """Verificar directamente las tablas en la base de datos"""
    from django.db import connection
    print("\n=== VERIFICACIÓN DIRECTA DE TABLAS ===")

    with connection.cursor() as cursor:
        # Verificar tabla estado_empleado
        cursor.execute("SELECT id_estado, estado FROM nucleo_estado_empleado ORDER BY id_estado")
        estados_emp = cursor.fetchall()
        print("Tabla nucleo_estado_empleado:")
        for estado in estados_emp:
            print(f"  {estado[0]}: {estado[1]}")

        # Verificar tabla estado_laboral
        cursor.execute("SELECT id_estado, estado FROM nucleo_estado_laboral ORDER BY id_estado")
        estados_lab = cursor.fetchall()
        print("\nTabla nucleo_estado_laboral:")
        for estado in estados_lab:
            print(f"  {estado[0]}: {estado[1]}")

        # Verificar tabla empleado_el
        cursor.execute("SELECT id, id_estado FROM nucleo_empleado_el ORDER BY id")
        empleados_el = cursor.fetchall()
        print("\nTabla nucleo_empleado_el (primeros 10 registros):")
        for i, (emp_id, estado_id) in enumerate(empleados_el[:10]):
            print(f"  Registro {emp_id}: id_estado = {estado_id}")

        # Buscar referencias inválidas
        cursor.execute("""
            SELECT eel.id, eel.id_estado
            FROM nucleo_empleado_el eel
            LEFT JOIN nucleo_estado_empleado est ON eel.id_estado = est.id_estado
            WHERE est.id_estado IS NULL
        """)
        invalid_refs = cursor.fetchall()

        if invalid_refs:
            print(f"\n❌ ENCONTRADAS {len(invalid_refs)} REFERENCIAS INVÁLIDAS:")
            for row in invalid_refs:
                print(f"  Empleado_el ID {row[0]}: id_estado = {row[1]} (no existe en estado_empleado)")
        else:
            print("\n✅ No hay referencias inválidas en empleado_el.")

if __name__ == "__main__":
    check_estado_models()
    check_database_tables()
