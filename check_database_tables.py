#!/usr/bin/env python
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.db import connection

def check_database_tables():
    print("=== VERIFICANDO TABLAS EN LA BASE DE DATOS ===")

    with connection.cursor() as cursor:
        # Ver todas las tablas
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE 'nucleo_%'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()

        print("Tablas del app 'nucleo':")
        for table in tables:
            print(f"  - {table[0]}")

        # Ver si existe nucleo_estado_laboral
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'nucleo_estado_laboral'
            )
        """)
        exists = cursor.fetchone()[0]
        print(f"\n¿Existe nucleo_estado_laboral? {exists}")

        # Ver migraciones aplicadas
        print("\n=== MIGRACIONES APLICADAS ===")
        cursor.execute("""
            SELECT app, name, applied
            FROM django_migrations
            WHERE app = 'nucleo'
            ORDER BY applied DESC
        """)
        migrations = cursor.fetchall()
        for migration in migrations:
            print(f"  {migration[0]}: {migration[1]} - {'✅ Aplicada' if migration[2] else '❌ Pendiente'}")

if __name__ == "__main__":
    check_database_tables()
