from django.core.management.base import BaseCommand
from django.db import transaction

from nucleo.models import Estado_empleado, Estado_lic_vac, Empleado_el, Solicitud_licencia, Solicitud_vacaciones


class Command(BaseCommand):
    help = 'Normaliza y limpia estados: mantiene solo Activo,Baja,Jubilado Activo en Estado_empleado y elimina "Licencia" y "Vacaciones"; elimina "Consumida" en Estado_lic_vac reasignando solicitudes a Aceptada.'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write('Iniciando limpieza de estados...')

            # Estado_empleado: asegurar los permitidos
            estado_activo, _ = Estado_empleado.objects.get_or_create(estado='Activo')
            estado_baja, _ = Estado_empleado.objects.get_or_create(estado='Baja')
            estado_jubilado, _ = Estado_empleado.objects.get_or_create(estado='Jubilado Activo')
            allowed_ids = {estado_activo.id_estado, estado_baja.id_estado, estado_jubilado.id_estado}

            # Reasignar empleados con estados no permitidos a Activo
            # Con el nuevo sistema, crear nuevos registros en lugar de UPDATE
            empleados_afectados = Empleado_el.objects.exclude(id_estado_id__in=allowed_ids)
            afectados = 0
            
            for empleado_el in empleados_afectados:
                # Obtener el registro más reciente del empleado
                ultimo_registro = Empleado_el.objects.filter(idempleado=empleado_el.idempleado).order_by('-fecha_el').first()
                if ultimo_registro and ultimo_registro.id_estado_id not in allowed_ids:
                    # Crear nuevo registro con estado corregido
                    from datetime import datetime
                    nuevo_registro = Empleado_el(
                        idempleado=ultimo_registro.idempleado,
                        fecha_el=datetime.now(),
                        fecha_est=ultimo_registro.fecha_est,
                        id_estado_id=estado_activo.id_estado,
                        id_puesto=ultimo_registro.id_puesto,
                        id_convenio=ultimo_registro.id_convenio,
                        alta_ant=ultimo_registro.alta_ant,
                    )
                    nuevo_registro.save()
                    afectados += 1
                    
            if afectados:
                self.stdout.write(f'Creados {afectados} nuevos registros laborales con estado Activo.')
            else:
                self.stdout.write('No se encontraron empleados con estados no permitidos.')

            # Eliminar estados no permitidos (Licencia, Vacaciones) si existen
            to_delete = Estado_empleado.objects.filter(estado__in=['Licencia','Vacaciones'])
            deleted_count = to_delete.count()
            if deleted_count:
                to_delete.delete()
                self.stdout.write(f'Eliminados {deleted_count} registros de Estado_empleado: Licencia/Vacaciones.')
            else:
                self.stdout.write('No se encontraron estados Licencia/Vacaciones para eliminar.')

            # Estado_lic_vac: reasignar solicitudes que estén en 'Consumida' a 'Aceptada'
            try:
                estado_aceptada = Estado_lic_vac.objects.get(estado__iexact='Aceptada')
            except Estado_lic_vac.DoesNotExist:
                estado_aceptada = Estado_lic_vac.objects.create(estado='Aceptada')
                self.stdout.write('Se creó estado Aceptada en Estado_lic_vac.')

            consumida_qs = Estado_lic_vac.objects.filter(estado__iexact='Consumida')
            if consumida_qs.exists():
                consumida_ids = list(consumida_qs.values_list('id_estado', flat=True))
                # Reasignar Solicitud_licencia / Solicitud_vacaciones
                sl_count = Solicitud_licencia.objects.filter(id_estado_id__in=consumida_ids).update(id_estado_id=estado_aceptada.id_estado)
                sv_count = Solicitud_vacaciones.objects.filter(id_estado_id__in=consumida_ids).update(id_estado_id=estado_aceptada.id_estado)
                # Eliminar el registro Consumida
                consumida_qs.delete()
                self.stdout.write(f'Reasignadas {sl_count} Solicitud_licencia y {sv_count} Solicitud_vacaciones de "Consumida" a "Aceptada" y eliminado el estado Consumida.')
            else:
                self.stdout.write('No se encontró estado "Consumida" en Estado_lic_vac.')

            self.stdout.write('Limpieza de estados completada.')
