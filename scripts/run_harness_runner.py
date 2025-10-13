# Script runner para probar flujo editar->confirmar en entorno de pruebas
# Ejecutar con: python manage.py shell -c "import runpy; runpy.run_path('scripts/run_harness_runner.py', run_name='__main__')"

import re
import json
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from nucleo.models.empleados import Empleado, Log_auditoria


def main():
    c = Client()
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        admin = User.objects.create_superuser('testadmin', 'admin@example.com', 'pass')
    c.force_login(admin)

    emp = Empleado.objects.first()
    if not emp:
        print('No hay empleados en la BD para test')
        return
    emp_id = getattr(emp.idempleado, 'id', None)
    url = reverse('nucleo:modificar_borrar_empleado_id', args=[emp_id])
    print('GET', url)
    resp = c.get(url, HTTP_HOST='localhost')
    print('GET status', resp.status_code)
    body = resp.content.decode('utf-8')
    print('modal_present (baseline)', 'modal-actualizar' in body)
    print('Response length', len(body))

    # parse form: inputs, textareas, selects
    payload = {}
    input_tags = re.findall(r'<input[^>]*>', body)
    for tag in input_tags:
        name_m = re.search(r'name=\"([^\"]+)\"', tag)
        if not name_m:
            continue
        name = name_m.group(1)
        if name == 'csrfmiddlewaretoken' or name.startswith('confirmar'):
            continue
        val_m = re.search(r'value=\"([^\"]*)\"', tag)
        val = val_m.group(1) if val_m else ''
        typ_m = re.search(r'type=\"([^\"]+)\"', tag)
        typ = typ_m.group(1).lower() if typ_m else 'text'
        if typ == 'checkbox':
            if 'checked' in tag:
                payload.setdefault(name, []).append(val or 'on')
        elif typ == 'radio':
            if 'checked' in tag:
                payload[name] = val
        else:
            payload[name] = val

    for m in re.finditer(r'<textarea[^>]*name=\"([^\"]+)\"[^>]*>(.*?)</textarea>', body, re.S):
        payload[m.group(1)] = m.group(2).strip()

    for m in re.finditer(r'<select[^>]*name=\"([^\"]+)\"[^>]*>(.*?)</select>', body, re.S):
        name = m.group(1)
        opts = m.group(2)
        sel = re.search(r'<option[^>]*selected[^>]*value=\"([^\"]*)\"', opts)
        if sel:
            payload[name] = sel.group(1)
        else:
            first = re.search(r'<option[^>]*value=\"([^\"]*)\"', opts)
            payload[name] = first.group(1) if first else ''

    # ensure plan keys exist
    for d in ['Lunes','Martes','Miercoles','Jueves','Viernes','Sabado','Domingo']:
        payload.setdefault(d, '')
    payload.setdefault('start_time', '')
    payload.setdefault('end_time', '')
    payload['accion'] = 'actualizar'

    print('Prepared payload keys:', len(payload))

    resp2 = c.post(url, data=payload, HTTP_HOST='localhost')
    print('POST update status', resp2.status_code)
    body2 = resp2.content.decode('utf-8')
    modal = 'modal-actualizar' in body2
    print('modal_present after POST', modal)
    print('Response length after POST', len(body2))

    if not modal:
        print('No modal -> aborting test run (the view did not detect cambios).')
        return

    m = re.search(r'id=\"post_data_json_hidden\"[^>]*value=\"([^\"]*)\"', body2)
    post_json = m.group(1) if m else None
    print('post_data_json found:', bool(post_json))

    confirm_payload = {'confirmar_actualizar': '1', 'confirmar': 'si'}
    if post_json:
        try:
            data = json.loads(post_json)
            for k, v in data.items():
                if isinstance(v, list):
                    for item in v:
                        confirm_payload.setdefault(k, []).append(item)
                else:
                    confirm_payload[k] = v
        except Exception as e:
            print('Error parsing post_data_json', e)

    resp3 = c.post(url, data=confirm_payload, HTTP_HOST='localhost')
    print('POST confirmar status', resp3.status_code)

    # dump trace tail
    try:
        with open('/tmp/audit_trace.log','r') as f:
            tail = f.read().splitlines()[-80:]
            print('\n--- /tmp/audit_trace.log tail ---')
            for l in tail:
                print(l)
    except Exception as e:
        print('Could not read /tmp/audit_trace.log', e)

    # print last Log_auditoria
    last = Log_auditoria.objects.order_by('-id')[:10]
    print('\n--- últimos Log_auditoria ---')
    for l in last:
        print(l.id, l.nombre_tabla, l.accion, json.dumps(l.cambio) if l.cambio else l.cambio)


if __name__ == '__main__':
    main()
