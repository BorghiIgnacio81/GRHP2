"""Test HTTP: crea feriado + solicitud, hace login como empleado y postea a eliminar_solicitud para comprobar que no devuelve 403."""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')

def create_test_data():
    import django
    django.setup()
    from datetime import date, timedelta
    from django.contrib.auth.models import User
    from nucleo.models import Feriado, Empleado, Tipo_licencia, Estado_lic_vac, Solicitud_licencia, Provincia, Localidad, Nacionalidad, EstadoCivil, Sexo, Plan_trabajo
    import time as _ptime
    suffix = str(int(_ptime.time()))[-6:]
    feriado_fecha = date.today() + timedelta(days=7)
    Feriado.objects.filter(fecha=feriado_fecha).delete()
    fer = Feriado.objects.create(descripcion='F_delete_http', fecha=feriado_fecha)
    # empleado user
    emp_username = f'test_emp_delete_{suffix}'
    user_emp, created = User.objects.get_or_create(username=emp_username)
    if created:
        user_emp.set_password('pe')
        user_emp.save()
    prov, _ = Provincia.objects.get_or_create(provincia='P_del')
    loc, _ = Localidad.objects.get_or_create(localidad='L_del', provincia=prov)
    nac, _ = Nacionalidad.objects.get_or_create(nacionalidad='N_del')
    estc, _ = EstadoCivil.objects.get_or_create(estado_civil='Soltero')
    sex, _ = Sexo.objects.get_or_create(sexo='M')
    dni_val = '8' + suffix
    cuil_val = f'20-{suffix}-8'
    emp = Empleado.objects.filter(dni=dni_val).first()
    if not emp:
        emp = Empleado.objects.create(idempleado=user_emp, nombres='T', apellido='D', dni=dni_val, fecha_nac=date(1990,1,1), cuil=cuil_val, id_nacionalidad=nac, id_civil=estc, id_sexo=sex, id_localidad=loc)
    else:
        if getattr(emp, 'idempleado_id', None) != user_emp.id:
            emp.idempleado = user_emp
            emp.save()
    from datetime import time
    Plan_trabajo.objects.filter(idempleado=emp).delete()
    Plan_trabajo.objects.create(idempleado=emp, lunes=True, martes=True, miercoles=True, jueves=True, viernes=True, sabado=False, domingo=False, start_time=time(9,0), end_time=time(18,0))
    tipo, _ = Tipo_licencia.objects.get_or_create(descripcion='Prueba_del', defaults={'dias':1,'pago':False})
    estado_espera, _ = Estado_lic_vac.objects.get_or_create(estado='En espera')
    Solicitud_licencia.objects.filter(idempleado=emp, fecha_desde=fer.fecha, fecha_hasta=fer.fecha).delete()
    sol = Solicitud_licencia.objects.create(idempleado=emp, id_licencia=tipo, fecha_desde=fer.fecha, fecha_hasta=fer.fecha, comentario='delete http test', texto_gestor='', id_estado=estado_espera)
    return {'emp': (emp_username, 'pe'), 'sol_id': sol.pk, 'fer': fer.fecha}

if __name__ == '__main__':
    data = create_test_data()
    import requests
    session = requests.Session()
    base = 'http://127.0.0.1:8000'
    # login empleado
    login_url = base + '/login/'
    r = session.get(login_url)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf = soup.find('input', {'name':'csrfmiddlewaretoken'})['value']
    resp = session.post(login_url, data={'username': data['emp'][0], 'password': data['emp'][1], 'csrfmiddlewaretoken': csrf}, headers={'Referer': login_url})
    print('login status code:', resp.status_code)
    # ir a consultar_licencia para obtener csrf
    url = base + '/consultar_licencia/'
    r = session.get(url)
    soup = BeautifulSoup(r.text, 'html.parser')
    csrf_el = soup.find('input', {'name':'csrfmiddlewaretoken'})
    csrf = csrf_el['value'] if csrf_el else None
    print('csrf token found:', bool(csrf))
    # post eliminar
    delete_url = base + '/eliminar_solicitud/'
    data_post = {'solicitud_id': data['sol_id'], 'csrfmiddlewaretoken': csrf}
    post = session.post(delete_url, data=data_post, headers={'Referer': url})
    print('POST eliminar status:', post.status_code, '->', post.url)
    # inspeccionar DB
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')
    django.setup()
    from nucleo.models import Solicitud_licencia
    try:
        s = Solicitud_licencia.objects.get(pk=data['sol_id'])
        print('Solicitud still exists, estado:', s.id_estado.estado, 'texto_gestor=', repr(s.texto_gestor))
    except Solicitud_licencia.DoesNotExist:
        print('Solicitud fue eliminada físicamente')
