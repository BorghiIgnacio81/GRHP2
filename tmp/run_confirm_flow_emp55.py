from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from nucleo.models import Log_auditoria
User = get_user_model()

c = Client()
admin = User.objects.filter(is_superuser=True).first()
if admin:
    c.force_login(admin)

url = reverse('nucleo:modificar_borrar_empleado_id', args=[55])
print('GET', url)
r = c.get(url)
print('GET status', r.status_code)
# prepare actualizar payload: toggle Lunes
from nucleo.models import Empleado, Plan_trabajo
emp = Empleado.objects.filter(idempleado_id=55).first()
if not emp:
    print('Empleado 55 no encontrado')
else:
    # prepare POST with some fields that form requires
    post = {}
    # use existing form initial values for required fields
    post['nombres'] = emp.nombres
    post['apellido'] = emp.apellido
    post['dni'] = emp.dni
    # labor forms may need these
    plan = Plan_trabajo.objects.filter(idempleado=emp).first()
    if not plan:
        post['Lunes'] = 'on'
    else:
        post['Lunes'] = 'on' if not plan.lunes else ''
    post['accion'] = 'actualizar'
    # include csrf token if present
    import re
    html = r.content.decode('utf-8')
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    if m:
        post['csrfmiddlewaretoken'] = m.group(1)
    r2 = c.post(url, post)
    print('POST actualizar status', r2.status_code)
    # Now find the confirm form and submit confirm=si
    html2 = r2.content.decode('utf-8')
    # try to extract post_data_json and cambios_json
    import json, re
    post_data_json = None
    cambios_json = None
    m = re.search(r'name="post_data_json" value=' + "'([\s\S]*?)'", html2)
    if m:
        try:
            post_data_json = json.loads(m.group(1))
        except Exception:
            post_data_json = m.group(1)
    m2 = re.search(r'name="cambios_json" value=' + "'([\s\S]*?)'", html2)
    if m2:
        try:
            cambios_json = json.loads(m2.group(1))
        except Exception:
            cambios_json = m2.group(1)
    confirm_post = {'confirmar_actualizar':'1','confirmar':'si'}
    if post_data_json:
        # post_data_json is dict
        for k,v in post_data_json.items():
            confirm_post[k] = v
    if cambios_json:
        confirm_post['cambios_json'] = json.dumps(cambios_json)
    # csrf
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html2)
    if m:
        confirm_post['csrfmiddlewaretoken'] = m.group(1)
    r3 = c.post(url, confirm_post)
    print('POST confirmar status', r3.status_code)

# Print last Log_auditoria
print('\nLast 10 Log_auditoria:')
for l in Log_auditoria.objects.order_by('-fecha_cambio')[:10]:
    print(l.id, l.nombre_tabla, l.idregistro, l.accion, l.cambio)
