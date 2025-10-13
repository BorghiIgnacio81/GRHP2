"""Simula login como gestor y borra una solicitud vía /eliminar_solicitud/ para validar mensajes en gestion_reporte_licencias."""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','gestion_rrhh.settings')
import django
django.setup()
from datetime import date, timedelta
from django.contrib.auth.models import User
from nucleo.models import Empleado, Tipo_licencia, Estado_lic_vac, Solicitud_licencia, Provincia, Localidad, Nacionalidad, EstadoCivil, Sexo, Plan_trabajo

# preparar datos
suffix = 'gest_del'
feriado_fecha = date.today() + timedelta(days=10)

# crear gestor y empleado
gest_user, _ = User.objects.get_or_create(username='test_gestor_delete')
# Ensure password and staff flag are set so HTTP login works in tests
gest_user.set_password('pg')
gest_user.is_staff = True
gest_user.save()

emp_user, _ = User.objects.get_or_create(username='test_emp_gest_del')
if not emp_user.has_usable_password(): emp_user.set_password('pe'); emp_user.save()
prov, _ = Provincia.objects.get_or_create(provincia='P_gest_del')
loc, _ = Localidad.objects.get_or_create(localidad='L_gest_del', provincia=prov)
nac, _ = Nacionalidad.objects.get_or_create(nacionalidad='N_gest_del')
estc, _ = EstadoCivil.objects.get_or_create(estado_civil='Soltero')
sex, _ = Sexo.objects.get_or_create(sexo='M')

emp = Empleado.objects.filter(dni='99'+suffix).first()
if not emp:
    emp = Empleado.objects.create(idempleado=emp_user, nombres='T', apellido='G', dni='99'+suffix, fecha_nac=date(1990,1,1), cuil='20-99-'+suffix, id_nacionalidad=nac, id_civil=estc, id_sexo=sex, id_localidad=loc)
Plan_trabajo.objects.filter(idempleado=emp).delete()
from datetime import time
Plan_trabajo.objects.create(idempleado=emp, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True, sabado=False, domingo=False, start_time=time(9,0), end_time=time(18,0))

tipo, _ = Tipo_licencia.objects.get_or_create(descripcion='Prueba_gest_del', defaults={'dias':1,'pago':False})
estado_espera, _ = Estado_lic_vac.objects.get_or_create(estado='En espera')

# crear solicitud
Solicitud_licencia.objects.filter(idempleado=emp, fecha_desde=feriado_fecha).delete()
sol = Solicitud_licencia.objects.create(idempleado=emp, id_licencia=tipo, fecha_desde=feriado_fecha, fecha_hasta=feriado_fecha, comentario='test gestor delete', texto_gestor='', id_estado=estado_espera)
print('Solicitud creada id', sol.pk)

# ahora HTTP
import requests
session = requests.Session()
base='http://127.0.0.1:8000'
login_url = base + '/login/'
r = session.get(login_url)
from bs4 import BeautifulSoup
soup = BeautifulSoup(r.text,'html.parser')
csrf = soup.find('input', {'name':'csrfmiddlewaretoken'})['value']
resp = session.post(login_url, data={'username':'test_gestor_delete','password':'pg','csrfmiddlewaretoken':csrf}, headers={'Referer': login_url})
print('login', resp.status_code)
# ir a gestion para obtener csrf
gestion_url = base + '/gestion_reporte_licencias/'
r = session.get(gestion_url)
soup = BeautifulSoup(r.text,'html.parser')
csrf = soup.find('input', {'name':'csrfmiddlewaretoken'})['value']
# enviar eliminar via eliminar_solicitud (como el formulario del template lo hace)
post = session.post(base + '/eliminar_solicitud/', data={'solicitud_id': sol.pk, 'csrfmiddlewaretoken': csrf}, headers={'Referer': gestion_url})
print('POST eliminar status', post.status_code, '->', post.url)
print('Response redirected to gestion?:', 'gestion_reporte_licencias' in post.url)

# comprobar DB
try:
    s = Solicitud_licencia.objects.get(pk=sol.pk)
    print('Solicitud sigue existiendo, estado:', s.id_estado.estado)
except Solicitud_licencia.DoesNotExist:
    print('Solicitud eliminada físicamente')
