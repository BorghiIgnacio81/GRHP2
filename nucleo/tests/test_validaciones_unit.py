from django.test import TestCase
from datetime import date, timedelta, time
from django.contrib.auth.models import User

from nucleo.models import Empleado, Plan_trabajo, Feriado, Tipo_licencia, Estado_lic_vac, Solicitud_licencia, Provincia, Localidad, Nacionalidad, EstadoCivil, Sexo
from nucleo.logic.validaciones import validar_solicitud_licencia, ValidacionError


class ValidacionesUnitTest(TestCase):
    def setUp(self):
        provincia = Provincia.objects.create(provincia='P')
        localidad = Localidad.objects.create(localidad='L', provincia=provincia)
        nacionalidad = Nacionalidad.objects.create(nacionalidad='Arg')
        estadocivil = EstadoCivil.objects.create(estado_civil='Soltero')
        sexo = Sexo.objects.create(sexo='M')

        user = User.objects.create_user(username='u_test', password='p')
        empleado = Empleado.objects.create(
            idempleado=user, nombres='T', apellido='U', dni='99999999', fecha_nac=date(1990,1,1),
            id_nacionalidad=nacionalidad, id_civil=estadocivil, id_sexo=sexo, id_localidad=localidad,
            dr_personal='', telefono='', cuil='20-12345678-9'
        )
        self.empleado = empleado

        Plan_trabajo.objects.create(idempleado=empleado, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True, sabado=False, domingo=False, start_time=time(9,0), end_time=time(18,0))
        Estado_lic_vac.objects.create(estado='Aceptada')
        Estado_lic_vac.objects.create(estado='Pendiente')
        Tipo_licencia.objects.create(descripcion='Prueba', dias=1, pago=False)

    def test_rechaza_si_todo_feriado(self):
        feriado_dia = date.today() + timedelta(days=2)
        Feriado.objects.create(descripcion='F', fecha=feriado_dia)
        lic = Solicitud_licencia(idempleado=self.empleado, fecha_desde=feriado_dia, fecha_hasta=feriado_dia, id_estado=Estado_lic_vac.objects.get(estado='Pendiente'), id_licencia=Tipo_licencia.objects.first())
        with self.assertRaises(ValidacionError) as cm:
            validar_solicitud_licencia(lic)
        self.assertIn('es feriado', str(cm.exception))

    def test_warn_si_parcial_feriado(self):
        d1 = date.today() + timedelta(days=2)
        d2 = d1 + timedelta(days=1)
        Feriado.objects.create(descripcion='F', fecha=d1)
        lic = Solicitud_licencia(idempleado=self.empleado, fecha_desde=d1, fecha_hasta=d2, id_estado=Estado_lic_vac.objects.get(estado='Aceptada'), id_licencia=Tipo_licencia.objects.first())
        ok, warnings = validar_solicitud_licencia(lic)
        self.assertTrue(ok)
        self.assertIn('es feriado', warnings)

    def test_rechaza_si_no_laboral_total(self):
        user2 = User.objects.create_user(username='u2', password='p')
        nacionalidad = Nacionalidad.objects.first()
        estadocivil = EstadoCivil.objects.first()
        sexo = Sexo.objects.first()
        localidad = Localidad.objects.first()
        emp2 = Empleado.objects.create(idempleado=user2, nombres='A', apellido='B', dni='11111111', fecha_nac=date(1990,1,1), id_nacionalidad=nacionalidad, id_civil=estadocivil, id_sexo=sexo, id_localidad=localidad, dr_personal='', telefono='', cuil='20-87654321-9')
        Plan_trabajo.objects.create(idempleado=emp2, lunes=False, martes=False, miercoles=False, jueves=False, viernes=False, sabado=False, domingo=False, start_time=time(9,0), end_time=time(18,0))
        d1 = date.today() + timedelta(days=3)
        lic = Solicitud_licencia(idempleado=emp2, fecha_desde=d1, fecha_hasta=d1, id_estado=Estado_lic_vac.objects.get(estado='Pendiente'), id_licencia=Tipo_licencia.objects.first())
        with self.assertRaises(ValidacionError):
            validar_solicitud_licencia(lic)

    def test_rechaza_solapamiento_licencia(self):
        d1 = date.today() + timedelta(days=4)
        d2 = d1 + timedelta(days=1)
        estado_acept = Estado_lic_vac.objects.get(estado='Aceptada')
        tipo = Tipo_licencia.objects.first()
        s1 = Solicitud_licencia.objects.create(idempleado=self.empleado, fecha_desde=d1, fecha_hasta=d2, id_estado=estado_acept, id_licencia=tipo)
        s2 = Solicitud_licencia(idempleado=self.empleado, fecha_desde=d1, fecha_hasta=d1, id_estado=Estado_lic_vac.objects.get(estado='Pendiente'), id_licencia=tipo)
        with self.assertRaises(ValidacionError):
            validar_solicitud_licencia(s2)
