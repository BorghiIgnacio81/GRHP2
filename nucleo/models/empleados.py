from django.db import models
from django.contrib.auth.models import User

class Nacionalidad(models.Model):
    nacionalidad = models.CharField(max_length=40, unique=True)
    def __str__(self): return self.nacionalidad

class EstadoCivil(models.Model):
    estado_civil = models.CharField(max_length=40, unique=True)
    def __str__(self): return self.estado_civil

class Sexo(models.Model):
    sexo = models.CharField(max_length=20, unique=True)
    def __str__(self): return self.sexo

class Provincia(models.Model):
    provincia = models.CharField(max_length=100)
    def __str__(self): return self.provincia

class Localidad(models.Model):
    localidad = models.CharField(max_length=100)
    provincia = models.ForeignKey(Provincia, on_delete=models.PROTECT, db_column='provincia_id')
    def __str__(self): return self.localidad

class Pers_juridica(models.Model):
    id_pers_juridica = models.AutoField(primary_key=True)
    pers_juridica = models.CharField(max_length=50, unique=True)
    domicilio = models.CharField(max_length=120)
    cond_iva = models.CharField(max_length=45)
    cuit = models.CharField(max_length=15)
    cond_iibb = models.CharField(max_length=45)
    def __str__(self): return self.pers_juridica

class Sucursal(models.Model):
    id_sucursal = models.AutoField(primary_key=True)
    sucursal = models.CharField(max_length=30)
    suc_dire = models.CharField(max_length=120)
    suc_mail = models.CharField(max_length=50)
    id_pers_juridica = models.ForeignKey(
        Pers_juridica, on_delete=models.PROTECT, db_column='id_pers_juridica',
        to_field='id_pers_juridica'
    )
    def __str__(self): return f"{self.sucursal}"

class Empleado(models.Model):
    idempleado = models.OneToOneField(
        User, on_delete=models.CASCADE, primary_key=True, db_column='Idempleado', to_field='id'
    )
    fecha_e = models.DateField(auto_now_add=True)
    nombres = models.CharField(max_length=40)
    apellido = models.CharField(max_length=40)
    dni = models.CharField(max_length=15, unique=True)
    fecha_nac = models.DateField()
    id_nacionalidad = models.ForeignKey(
        Nacionalidad, on_delete=models.PROTECT, db_column='id_nacionalidad'
    )
    id_civil = models.ForeignKey(
        EstadoCivil, on_delete=models.PROTECT, db_column='id_civil'
    )
    num_hijos = models.IntegerField(default=0)
    id_sexo = models.ForeignKey(
        Sexo, on_delete=models.PROTECT, db_column='id_sexo'
    )
    id_localidad = models.ForeignKey(
        Localidad, on_delete=models.PROTECT, db_column='id_localidad'
    )
    dr_personal = models.CharField(max_length=40)
    telefono = models.CharField(max_length=20)
    cuil = models.CharField(max_length=15, unique=True)
    def __str__(self):
        return f"{self.apellido}, {self.nombres} ({self.dni})"

    # Otros métodos y propiedades según tu versión local

class Empleado_eo(models.Model):
    fecha_eo = models.DateField(auto_now_add=True)
    idempleado = models.ForeignKey(
        Empleado, on_delete=models.CASCADE, db_column='idempleado',
        to_field='idempleado'
    )
    id_sucursal = models.ForeignKey(
        Sucursal, on_delete=models.CASCADE, db_column='id_sucursal',
        to_field='id_sucursal'
    )
    class Meta:
        unique_together = ('fecha_eo', 'idempleado')
    def __str__(self):
        return f"Empleado {self.idempleado} EO el {self.fecha_eo} en Suc {self.id_sucursal}"

class Convenio(models.Model):
    id_convenio = models.AutoField(primary_key=True)
    tipo_convenio = models.CharField(max_length=100)
    def __str__(self): return self.tipo_convenio

class Puesto(models.Model):
    id_puesto = models.AutoField(primary_key=True)
    tipo_puesto = models.CharField(max_length=60)
    def __str__(self): return self.tipo_puesto

class Plan_trabajo(models.Model):
    idempleado = models.ForeignKey(
        Empleado, on_delete=models.CASCADE, db_column='idempleado',
        to_field='idempleado'
    )
    lunes = models.BooleanField(default=False)
    martes = models.BooleanField(default=False)
    miercoles = models.BooleanField(default=False)
    jueves = models.BooleanField(default=False)
    viernes = models.BooleanField(default=False)
    sabado = models.BooleanField(default=False)
    domingo = models.BooleanField(default=False)
    start_time = models.TimeField()
    end_time = models.TimeField()
    def __str__(self):
        return f"Plan {self.idempleado} {self.start_time}-{self.end_time}"

class Log_auditoria(models.Model):
    idusuario = models.ForeignKey(
        User, on_delete=models.CASCADE, db_column='idusuario'
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    nombre_tabla = models.CharField(max_length=100)
    idregistro = models.IntegerField()
    accion = models.CharField(max_length=40)
    cambio = models.JSONField()
    def __str__(self):
        return f"Log {self.id} - {self.nombre_tabla} - {self.accion}"

class Estado_empleado(models.Model):
    id_estado = models.AutoField(primary_key=True)
    estado = models.CharField(max_length=40, unique=True)
    def __str__(self):
        return self.estado

class Empleado_el(models.Model):
    fecha_el = models.DateField(auto_now_add=True)
    fecha_est = models.DateField(null=True, blank=True)  # Nuevo campo para la fecha de estado laboral
    idempleado = models.ForeignKey(
        Empleado, on_delete=models.CASCADE, db_column='idempleado', to_field='idempleado'
    )
    id_estado = models.ForeignKey(
        Estado_empleado, on_delete=models.PROTECT, db_column='id_estado', to_field='id_estado'
    )
    id_convenio = models.ForeignKey(
        Convenio, on_delete=models.PROTECT, db_column='id_convenio', to_field='id_convenio'
    )
    id_puesto = models.ForeignKey(
        Puesto, on_delete=models.PROTECT, db_column='id_puesto', to_field='id_puesto'
    )
    alta_ant = models.DateField()
    def __str__(self):
        return f"Empleado_EL {self.idempleado} - Estado: {self.id_estado}, Convenio: {self.id_convenio}, Puesto: {self.id_puesto}"

class Estado_laboral(models.Model):
    id_estado = models.AutoField(primary_key=True)
    estado = models.CharField(max_length=40, unique=True)
    def __str__(self):
        return self.estado