from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from nucleo.models import Empleado
from nucleo.models import Tipo_licencia, Estado_lic_vac, Solicitud_licencia, Solicitud_vacaciones
from nucleo.models import Nacionalidad, EstadoCivil, Sexo, Provincia, Localidad
from datetime import date

class LicenciasPermissionTests(TestCase):
    def setUp(self):
        # Usuarios/empleados
        self.user1 = User.objects.create_user(username='gestor1', password='pass')
        self.user1.is_staff = True
        self.user1.save()
        self.user2 = User.objects.create_user(username='gestor2', password='pass')
        self.user2.is_staff = True
        self.user2.save()

        # Empleados vinculados
        # Crear dependencias necesarias (FKs)
        self.prov = Provincia.objects.create(provincia='TestProv')
        self.localidad = Localidad.objects.create(localidad='TestLoc', provincia=self.prov)
        self.nacionalidad = Nacionalidad.objects.create(nacionalidad='Arg')
        self.estado_civil = EstadoCivil.objects.create(estado_civil='Soltero')
        self.sexo = Sexo.objects.create(sexo='M')

        self.emp1 = Empleado.objects.create(
            idempleado=self.user1,
            nombres='G1', apellido='Test', dni='111', fecha_nac='1990-01-01',
            id_nacionalidad=self.nacionalidad, id_civil=self.estado_civil,
            id_sexo=self.sexo, id_localidad=self.localidad,
            dr_personal='', telefono='', cuil='20-11111111-1'
        )
        self.emp2 = Empleado.objects.create(
            idempleado=self.user2,
            nombres='G2', apellido='Test', dni='222', fecha_nac='1990-01-01',
            id_nacionalidad=self.nacionalidad, id_civil=self.estado_civil,
            id_sexo=self.sexo, id_localidad=self.localidad,
            dr_personal='', telefono='', cuil='20-22222222-2'
        )

        # Estados y tipos
        self.estado_espera = Estado_lic_vac.objects.create(estado='En espera')
        self.estado_aceptada = Estado_lic_vac.objects.create(estado='Aceptada')
        self.estado_rechazada = Estado_lic_vac.objects.create(estado='Rechazada')
        self.tipo_vac = Tipo_licencia.objects.create(descripcion='Vacaciones', dias=30, pago=False)
        self.tipo_otra = Tipo_licencia.objects.create(descripcion='Otra', dias=5, pago=True)

        # Solicitudes
        self.solicitud_lic = Solicitud_licencia.objects.create(idempleado=self.emp1, id_licencia=self.tipo_otra, fecha_desde=date.today(), fecha_hasta=date.today(), id_estado=self.estado_espera)
        self.solicitud_vac = Solicitud_vacaciones.objects.create(idempleado=self.emp1, fecha_desde=date.today(), fecha_hasta=date.today(), id_estado=self.estado_espera, comentario='')

        self.client = Client()

    def test_auto_approval_blocked_for_license(self):
        # gestor1 (propietario) intenta aprobar su propia licencia
        self.client.login(username='gestor1', password='pass')
        resp = self.client.post(reverse('nucleo:gestion_reporte_licencias'), {
            'solicitud_id': self.solicitud_lic.pk,
            'accion': 'aprobar'
        }, follow=True)
        self.solicitud_lic.refresh_from_db()
        self.assertEqual(self.solicitud_lic.id_estado.estado, 'En espera')
        self.assertContains(resp, 'No puedes aprobar tus propias solicitudes')

    def test_other_manager_can_approve_license(self):
        # gestor2 aprueba la licencia de gestor1
        self.client.login(username='gestor2', password='pass')
        resp = self.client.post(reverse('nucleo:gestion_reporte_licencias'), {
            'solicitud_id': self.solicitud_lic.pk,
            'accion': 'aprobar'
        }, follow=True)
        self.solicitud_lic.refresh_from_db()
        self.assertEqual(self.solicitud_lic.id_estado.estado, 'Aceptada')
        self.assertContains(resp, 'Solicitud aprobada correctamente')

    def test_reject_saves_texto_gestor_for_license(self):
        # gestor2 rechaza con motivo
        self.client.login(username='gestor2', password='pass')
        motivo = 'Motivo de prueba'
        resp = self.client.post(reverse('nucleo:gestion_reporte_licencias'), {
            'solicitud_id': self.solicitud_lic.pk,
            'accion': 'rechazar',
            'motivo_rechazo': motivo,
        }, follow=True)
        self.solicitud_lic.refresh_from_db()
        self.assertEqual(self.solicitud_lic.id_estado.estado, 'Rechazada')
        self.assertEqual(self.solicitud_lic.texto_gestor, motivo)
        self.assertContains(resp, 'Solicitud rechazada correctamente')

    def test_auto_approval_blocked_for_vacation(self):
        # gestor1 intenta aprobar sus propias vacaciones
        self.client.login(username='gestor1', password='pass')
        resp = self.client.post(reverse('nucleo:gestion_reporte_licencias'), {
            'solicitud_id': self.solicitud_vac.pk,
            'accion': 'aprobar'
        }, follow=True)
        self.solicitud_vac.refresh_from_db()
        self.assertEqual(self.solicitud_vac.id_estado.estado, 'En espera')
        self.assertContains(resp, 'No puedes aprobar tus propias solicitudes')
