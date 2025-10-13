from django.core.management.base import BaseCommand
from nucleo.views.utils import (
    actualizar_licencias_consumidas,
    actualizar_vacaciones_consumidas,
    actualizar_estados_empleados_si_corresponde,
)
from nucleo.models.licencias import eliminar_licencias_discontinuadas_sin_solicitudes

class Command(BaseCommand):
    help = "Actualiza estados de licencias, vacaciones, empleados y elimina licencias discontinuadas"

    def handle(self, *args, **kwargs):
        actualizar_licencias_consumidas()
        actualizar_vacaciones_consumidas()
        actualizar_estados_empleados_si_corresponde()
        eliminar_licencias_discontinuadas_sin_solicitudes()
        self.stdout.write(self.style.SUCCESS('Estados y licencias discontinuadas actualizados correctamente'))