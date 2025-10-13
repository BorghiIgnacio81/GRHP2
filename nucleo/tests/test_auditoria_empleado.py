from django.test import TestCase, Client
from django.urls import reverse
from datetime import date
import json

from nucleo.models import Empleado, Empleado_eo, Sucursal, Log_auditoria, Provincia, Localidad, Nacionalidad, EstadoCivil, Sexo
from django.contrib.auth.models import User


class AuditoriaEmpleadoTest(TestCase):
    def setUp(self):
        # Crear usuario administrador para hacer requests autenticadas
        self.user = User.objects.create_user(username='tester', password='pass')
        self.user.is_staff = True
        self.user.save()
        self.client = Client()
        self.client.login(username='tester', password='pass')

        # Crear datos relacionados necesarios para Sucursal y Empleado
        self.pers_j = Sucursal._meta.get_field('id_pers_juridica').related_model.objects.create(
            pers_juridica='Empresa X', domicilio='Av Falsa 123', cond_iva='Responsable', cuit='30-12345678-9', cond_iibb='Exento'
        )
        # Crear sucursales A y B (llenar campos obligatorios)
        self.suc_a = Sucursal.objects.create(sucursal='Sucursal A', suc_dire='Calle A 1', suc_mail='a@example.com', id_pers_juridica=self.pers_j)
        self.suc_b = Sucursal.objects.create(sucursal='Sucursal B', suc_dire='Calle B 2', suc_mail='b@example.com', id_pers_juridica=self.pers_j)

        # Crear provincia/localidad y otros catálogos requeridos por Empleado
        self.prov = Provincia.objects.create(provincia='P')
        self.localidad = Localidad.objects.create(localidad='L', provincia=self.prov)
        self.nacionalidad = Nacionalidad.objects.create(nacionalidad='Arg')
        self.estadocivil = EstadoCivil.objects.create(estado_civil='Soltero')
        self.sexo = Sexo.objects.create(sexo='M')

        # Crear empleado y su registro Empleado_eo inicial (llenar campos obligatorios)
        u_emp = User.objects.create_user(username='empuser', password='ep')
        self.empleado = Empleado.objects.create(
            idempleado=u_emp,
            nombres='T',
            apellido='U',
            dni='12345678',
            fecha_nac=date(1990,1,1),
            id_nacionalidad=self.nacionalidad,
            id_civil=self.estadocivil,
            id_sexo=self.sexo,
            id_localidad=self.localidad,
            dr_personal='',
            telefono='000000000',
            cuil='20-99999999-9',
        )
        Empleado_eo.objects.create(idempleado=self.empleado, id_sucursal=self.suc_a)

    def test_cambio_sucursal_generates_log(self):
        # Prepare POST data to change sucursal (simulate form POST used by the view)
        # Empleado model uses a OneToOneField 'idempleado' as primary key (no .id attribute)
        # Use the underlying FK id field 'idempleado_id' when reversing the URL
        url = reverse('nucleo:modificar_borrar_empleado_id', kwargs={'empleado_id': self.empleado.idempleado_id})
        # Emulate the confirm/update flow: first, do the 'actualizar' action that sets session
        post_data = {
            'accion': 'actualizar',
            'nombres': self.empleado.nombres,
            'apellido': self.empleado.apellido,
            'dni': self.empleado.dni,
            'id_sucursal': str(self.suc_b.pk),
            # Plan_trabajo required fields (view expects these)
            'start_time': '09:00',
            'end_time': '17:00',
            'Lunes': 'on',
        }
        # Step 1: request to show modal (store session post_data)
        resp = self.client.post(url, data=post_data)
        self.assertIn(resp.status_code, (200, 302))

        # Now confirm the update (simulate the confirm form that posts confirmar_actualizar=1 and confirmar=si)
        confirm_data = {
            'confirmar_actualizar': '1',
            'confirmar': 'si',
            # include post_data_json so server can recover if session lost
            'post_data_json': json.dumps(post_data),
        }
        resp2 = self.client.post(url, data=confirm_data)
        self.assertIn(resp2.status_code, (200, 302))

        # Check that a Log_auditoria was created for Empleado_eo (Sucursal change)
        logs = Log_auditoria.objects.filter(nombre_tabla='Empleado_eo').order_by('-fecha_cambio')
        self.assertTrue(logs.exists(), 'No se creó Log_auditoria para Empleado_eo')
        latest = logs.first()
        # The payload should include the old and new sucursal IDs or names
        cambio = latest.cambio
        # Accept either nested minimal_changed structure or a fallback raw fields list
        self.assertTrue(isinstance(cambio, dict) or isinstance(cambio, (str, list)))
        # If dict and contains 'changed' expect id_sucursal in it
        if isinstance(cambio, dict):
            # buscar en eo_compact
            eo = cambio.get('changed') if 'changed' in cambio else cambio.get('empleado_eo') or cambio.get('eo') or cambio
            # Ensure there is some indication of id_sucursal change
            def search_dict_for_key(d, key):
                if not isinstance(d, dict):
                    return False
                if key in d:
                    return True
                for v in d.values():
                    if isinstance(v, dict) and search_dict_for_key(v, key):
                        return True
                return False
            found = search_dict_for_key(cambio, 'id_sucursal') or search_dict_for_key(cambio, 'sucursal')
            self.assertTrue(found, f"Log_auditoria payload no contiene id_sucursal/sucursal: {cambio}")
