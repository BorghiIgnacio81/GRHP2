# Forzar cambio de estado laboral y ejecutar flujo editar->confirmar
import json
import re
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from nucleo.models.empleados import Empleado, Empleado_el, Log_auditoria
from nucleo.models.empleados import Estado_empleado


def main():
    c = Client()
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        admin = User.objects.create_superuser('testadmin', 'admin@example.com', 'pass')
    c.force_login(admin)

    emp = Empleado.objects.first()
    if not emp:
        print('No hay empleados')
        return
    emp_id = getattr(emp.idempleado, 'id', None)
    empleado_el = Empleado_el.objects.filter(idempleado=emp).order_by('-fecha_el').first()
    if not empleado_el:
        print('No hay Empleado_el para este empleado')
        return
    current_estado = getattr(empleado_el.id_estado, 'pk', None)
    alt_estado = Estado_empleado.objects.exclude(pk=current_estado).first()
    if not alt_estado:
        print('No hay otro Estado_empleado para cambiar')
        return
    print('Forzando cambio de estado:', current_estado, '->', alt_estado.pk)

    url = reverse('nucleo:modificar_borrar_empleado_id', args=[emp_id])
    resp = c.get(url, HTTP_HOST='localhost')
    body = resp.content.decode('utf-8')

    # Build payload similar to run_harness_runner but override id_estado
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

    # override id_estado to alt_estado.pk
    payload['id_estado'] = str(alt_estado.pk)
    payload.setdefault('Lunes','')
    payload.setdefault('Martes','')
    payload.setdefault('Miercoles','')
    payload.setdefault('Jueves','')
    payload.setdefault('Viernes','')
    payload.setdefault('Sabado','')
    payload.setdefault('Domingo','')
    payload.setdefault('start_time','')
    payload.setdefault('end_time','')
    payload['accion'] = 'actualizar'

    print('POST update, campos:', len(payload))
    resp2 = c.post(url, data=payload, HTTP_HOST='localhost')
    print('POST update status', resp2.status_code)
    body2 = resp2.content.decode('utf-8')
    print('modal_present after POST', 'modal-actualizar' in body2)
    if 'modal-actualizar' not in body2:
        print('Modal no presente, abortando')
        return
    m = re.search(r'id=\"post_data_json_hidden\"[^>]*value=\"([^\"]*)\"', body2)
    post_json = m.group(1) if m else None
    print('post_data_json found:', bool(post_json))

    confirm_payload = {'confirmar_actualizar': '1', 'confirmar': 'si'}
    if post_json:
        data = json.loads(post_json)
        for k, v in data.items():
            if isinstance(v, list):
                for item in v:
                    confirm_payload.setdefault(k, []).append(item)
            else:
                confirm_payload[k] = v
    else:
        # as fallback include id_estado
        confirm_payload['id_estado'] = str(alt_estado.pk)

    resp3 = c.post(url, data=confirm_payload, HTTP_HOST='localhost')
    print('POST confirmar status', resp3.status_code)

    try:
        with open('/tmp/audit_trace.log','r') as f:
            tail = f.read().splitlines()[-80:]
            print('\n--- /tmp/audit_trace.log tail ---')
            for l in tail:
                print(l)
    except Exception as e:
        print('No se pudo leer /tmp/audit_trace.log', e)

    last = Log_auditoria.objects.order_by('-id')[:10]
    print('\n--- últimos Log_auditoria ---')
    for l in last:
        print(l.id, l.nombre_tabla, l.accion, json.dumps(l.cambio) if l.cambio else l.cambio)


if __name__ == '__main__':
    main()
