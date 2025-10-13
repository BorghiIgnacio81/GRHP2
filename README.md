# Gestión RRHH

Sistema de gestión de recursos humanos para administración de personal, licencias, vacaciones y más.

## Cambios recientes

### Septiembre 19, 2025
- Corregido el cálculo de días de vacaciones en el dashboard del gestor
- Ahora el gráfico de "Mis Vacaciones" muestra correctamente los días aprobados en lugar del número de solicitudes
- El gráfico "Vacaciones Anuales" ahora resta correctamente los días aprobados del total disponible

## Instrucciones para instalación local

1. Clonar el repositorio:
```bash
git clone https://github.com/BorghiIgnacio81/gestion_rrhh.git
```

2. Crear y activar entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar la base de datos en gestion_rrhh/settings.py

5. Ejecutar migraciones:
```bash
python manage.py migrate
```

6. Iniciar el servidor:
```bash
python manage.py runserver
```

## Notas importantes
- La aplicación utiliza PostgreSQL como base de datos principal
- Asegúrese de tener todas las dependencias instaladas
- Configuración de la base de datos:
  - Nombre: GRHP
  - Usuario: postgres
  - Contraseña: C05m05