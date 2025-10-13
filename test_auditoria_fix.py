#!/usr/bin/env python
"""
Script para probar los cambios en el sistema de auditoría
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from nucleo.models import Empleado, Empleado_el, Log_auditoria
from nucleo.views.empleados import _make_json_safe

def test_foreign_key_objects():
    """Prueba que los objetos de foreign key se conviertan correctamente"""
    print("=== Probando conversión de foreign keys ===")

    empleado = Empleado.objects.filter(id_nacionalidad__isnull=False).first()
    if empleado and empleado.id_nacionalidad:
        print(f"Nacionalidad original: {empleado.id_nacionalidad}")
        safe_result = _make_json_safe(empleado.id_nacionalidad)
        print(f"_make_json_safe result: {safe_result}")
        print(f"Tipo: {type(safe_result)}")

    empleado_el = Empleado_el.objects.filter(id_estado__isnull=False).first()
    if empleado_el and empleado_el.id_estado:
        print(f"\nEstado original: {empleado_el.id_estado}")
        safe_result = _make_json_safe(empleado_el.id_estado)
        print(f"_make_json_safe result: {safe_result}")
        print(f"Tipo: {type(safe_result)}")

    if empleado_el and empleado_el.id_puesto:
        print(f"\nPuesto original: {empleado_el.id_puesto}")
        safe_result = _make_json_safe(empleado_el.id_puesto)
        print(f"_make_json_safe result: {safe_result}")
        print(f"Tipo: {type(safe_result)}")

def test_minimal_changed():
    """Prueba la función _minimal_changed con objetos"""
    from nucleo.views.empleados import _minimal_changed

    print("\n=== Probando _minimal_changed ===")

    # Simular cambio en estado
    empleado_el = Empleado_el.objects.filter(id_estado__isnull=False).first()
    if empleado_el:
        old_data = {'id_estado': None}
        new_data = {'id_estado': empleado_el.id_estado}

        result = _minimal_changed(old_data, new_data)
        print(f"_minimal_changed result: {result}")

def test_recent_logs():
    """Mostrar logs de auditoría recientes para verificar el formato"""
    print("\n=== Logs de auditoría más recientes ===")

    recent_logs = Log_auditoria.objects.order_by('-id')[:5]
    for log in recent_logs:
        print(f"ID: {log.id}, Tabla: {log.nombre_tabla}, Acción: {log.accion}")
        print(f"Cambio: {log.cambio}")
        print("---")

if __name__ == '__main__':
    test_foreign_key_objects()
    test_minimal_changed()
    test_recent_logs()
