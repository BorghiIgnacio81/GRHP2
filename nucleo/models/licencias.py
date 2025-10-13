from django.db import models
from nucleo.models.empleados import Empleado

class Tipo_licencia(models.Model):
    id_licencia = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=100)
    # Allow null to represent 'licencia libre' (no fixed days)
    dias = models.IntegerField(null=True, blank=True)
    pago = models.BooleanField()
    def __str__(self):
        return self.descripcion

class Estado_lic_vac(models.Model):
    id_estado = models.AutoField(primary_key=True)
    estado = models.CharField(max_length=40, unique=True)
    def __str__(self):
        return self.estado

from django.db import models
from nucleo.models.empleados import Empleado


class Solicitud_licencia(models.Model):
    idsolicitudlic = models.AutoField(primary_key=True)
    fecha_sqllc = models.DateField(auto_now_add=True)
    idempleado = models.ForeignKey(
        'nucleo.Empleado', on_delete=models.PROTECT, db_column='idempleado', to_field='idempleado'
    )
    id_licencia = models.ForeignKey(
        'nucleo.Tipo_licencia', on_delete=models.PROTECT, db_column='id_licencia', to_field='id_licencia'
    )
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    id_estado = models.ForeignKey(
        'nucleo.Estado_lic_vac', on_delete=models.PROTECT, db_column='id_estado', to_field='id_estado'
    )
    comentario = models.CharField(max_length=200, blank=True, null=True)
    texto_gestor = models.CharField(max_length=200, blank=True, null=True)
    archivo = models.CharField(max_length=200, blank=True, null=True)
    def __str__(self):
        return f"Solicitud {self.idsolicitudlic} - {self.fecha_sqllc}"

class Solicitud_vacaciones(models.Model):
    idsolicitudvac = models.AutoField(primary_key=True)
    fecha_sol_vac = models.DateField(auto_now_add=True)
    idempleado = models.ForeignKey(
        'nucleo.Empleado', on_delete=models.PROTECT, db_column='idempleado', to_field='idempleado'
    )
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    id_estado = models.ForeignKey(
        'nucleo.Estado_lic_vac', on_delete=models.PROTECT, db_column='id_estado', to_field='id_estado'
    )
    comentario = models.CharField(max_length=200)
    def __str__(self):
        return f"Solicitud Vacaciones {self.idsolicitudvac}"

class Vacaciones_otorgadas(models.Model):
    id_vacaciones = models.AutoField(primary_key=True)
    idempleado = models.ForeignKey(
        Empleado, on_delete=models.PROTECT, db_column='idempleado', to_field='idempleado'
    )
    inicio_consumo = models.DateField()
    fin_consumo = models.DateField()
    dias_disponibles = models.IntegerField()
    dias_consumidos = models.IntegerField()
    def __str__(self):
        return f"Vacaciones {self.id_vacaciones} - Empleado {self.idempleado}"

class Feriado(models.Model):
    id_feriado = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=120)
    fecha = models.DateField(unique=True)
    def __str__(self):
        return f"{self.descripcion} ({self.fecha})"

def eliminar_licencias_discontinuadas_sin_solicitudes():
    from nucleo.models import Tipo_licencia, Solicitud_licencia, Estado_lic_vac
    discontinuadas = Tipo_licencia.objects.filter(descripcion__icontains="(Discontinuada)")
    for lic in discontinuadas:
        solicitudes = Solicitud_licencia.objects.filter(id_licencia=lic)
        if not solicitudes.exists():
            lic.delete()
        else:
            # Si todas las solicitudes están rechazadas o consumidas, eliminar la licencia
            estados_validos = {"rechazada", "consumida"}
            if all(s.id_estado.estado.lower() in estados_validos for s in solicitudes):
                solicitudes.delete()
                lic.delete()

