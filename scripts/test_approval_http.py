"""Script de prueba HTTP: crea feriado + solicitud + simula login como gestor y POSTs a las vistas de aprobación.
Requiere que gunicorn esté corriendo en 0.0.0.0:8000 (el script lo asume en localhost:8000).
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
# No necesitamos django.setup() porque usaremos HTTP; solo lo usamos para inspeccionar DB al final

def create_test_data():
    import django
    django.setup()
    from datetime import date, timedelta, time
    from django.contrib.auth.models import User
    from nucleo.models import Feriado, Empleado, Tipo_licencia, Estado_lic_vac, Solicitud_licencia, Plan_trabajo, Provincia, Localidad, Nacionalidad, EstadoCivil, Sexo
    # usar sufijo único para evitar colisiones con ejecuciones previas
    import time as _ptime
    suffix = str(int(_ptime.time()))[-6:]

    feriado_fecha = date.today() + timedelta(days=7)
    Feriado.objects.filter(fecha=feriado_fecha).delete()
    fer = Feriado.objects.create(descripcion='F_http', fecha=feriado_fecha)
    print('Feriado creado:', fer.fecha)

    # crear gestor
    gestor_username = f'test_gestor_{suffix}'
    gestor, created = User.objects.get_or_create(username=gestor_username)
    if created:
        gestor.set_password('pg')
        gestor.is_staff = True
        gestor.save()

    # empleado
    emp_username = f'test_emp_http_{suffix}'
    user_emp, created = User.objects.get_or_create(username=emp_username)
    if created:
        user_emp.set_password('pe')
        user_emp.save()
    prov, _ = Provincia.objects.get_or_create(provincia='P_http')
    loc, _ = Localidad.objects.get_or_create(localidad='L_http', provincia=prov)
    nac, _ = Nacionalidad.objects.get_or_create(nacionalidad='N_http')
    estc, _ = EstadoCivil.objects.get_or_create(estado_civil='Soltero')
    sex, _ = Sexo.objects.get_or_create(sexo='M')
    # generar dni y cuil únicos para este run
    dni_val = '9' + suffix
    cuil_val = f'20-{suffix}-9'
    emp = Empleado.objects.filter(dni=dni_val).first()
    if not emp:
        emp = Empleado.objects.create(idempleado=user_emp, nombres='T', apellido='U', dni=dni_val, fecha_nac=date(1990,1,1), cuil=cuil_val, id_nacionalidad=nac, id_civil=estc, id_sexo=sex, id_localidad=loc)
    else:
        if getattr(emp, 'idempleado_id', None) != user_emp.id:
            emp.idempleado = user_emp
            emp.save()
    Plan_trabajo.objects.filter(idempleado=emp).delete()
    Plan_trabajo.objects.create(idempleado=emp, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True, sabado=False, domingo=False, start_time=time(9,0), end_time=time(18,0))

    tipo, _ = Tipo_licencia.objects.get_or_create(descripcion='Prueba_http', defaults={'dias':1,'pago':False})
    estado_espera, _ = Estado_lic_vac.objects.get_or_create(estado='En espera')

    Solicitud_licencia.objects.filter(idempleado=emp, fecha_desde=fer.fecha, fecha_hasta=fer.fecha).delete()
    sol = Solicitud_licencia.objects.create(idempleado=emp, id_licencia=tipo, fecha_desde=fer.fecha, fecha_hasta=fer.fecha, comentario='http test', texto_gestor='', id_estado=estado_espera)
    print('Solicitud creada id:', sol.pk)
    return {'gestor': ('test_gestor','pg'), 'emp': ('test_emp_http','pe'), 'sol_id': sol.pk, 'fer': fer.fecha}


if __name__ == '__main__':
    # crear datos
    data = create_test_data()
    import requests
    session = requests.Session()
    base = 'http://127.0.0.1:8000'

    # login gestor
    login_url = base + '/login/'
    # obtener csrf
    r = session.get(login_url)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name':'csrfmiddlewaretoken'})['value']
    resp = session.post(login_url, data={'username': data['gestor'][0], 'password': data['gestor'][1], 'csrfmiddlewaretoken': csrf}, headers={'Referer': login_url})
    print('login status code:', resp.status_code)

    # probar detalle_licencia approve
    detalle_url = base + f"/detalle_licencia/{data['sol_id']}/"
    r = session.get(detalle_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name':'csrfmiddlewaretoken'})['value']
    post = session.post(detalle_url, data={'accion':'aprobar', 'texto_gestor':'', 'csrfmiddlewaretoken': csrf}, headers={'Referer': detalle_url})
    print('POST detalle status:', post.status_code, '->', post.url)

    # consultar DB para ver estado final
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
    django.setup()
    from nucleo.models import Solicitud_licencia
    s = Solicitud_licencia.objects.get(pk=data['sol_id'])
    print('After detalle approve: estado=', s.id_estado.estado, 'texto_gestor=', repr(s.texto_gestor))

    # ahora probar gestion_reporte_licencias approve
    # crear otra solicitud
    from datetime import date
    django.setup()
    from nucleo.models import Solicitud_licencia, Estado_lic_vac
    emp = Solicitud_licencia.objects.get(pk=data['sol_id']).idempleado
    tipo = Solicitud_licencia.objects.get(pk=data['sol_id']).id_licencia
    estado_espera = Estado_lic_vac.objects.get(estado='En espera')
    newsol = Solicitud_licencia.objects.create(idempleado=emp, id_licencia=tipo, fecha_desde=data['fer'], fecha_hasta=data['fer'], comentario='http test 2', texto_gestor='', id_estado=estado_espera)
    print('Nueva solicitud id:', newsol.pk)

    gestion_url = base + '/gestion_reporte_licencias/'
    r = session.get(gestion_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name':'csrfmiddlewaretoken'})['value']
    post = session.post(gestion_url, data={'solicitud_id': newsol.pk, 'accion':'aprobar', 'motivo_rechazo':'', 'csrfmiddlewaretoken': csrf}, headers={'Referer': gestion_url})
    print('POST gestion status:', post.status_code, '->', post.url)

    s2 = Solicitud_licencia.objects.get(pk=newsol.pk)
    print('After gestion approve: estado=', s2.id_estado.estado, 'texto_gestor=', repr(s2.texto_gestor))
