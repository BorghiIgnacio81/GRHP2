# Temporary harness to test editar->confirmar flow
import re, json
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from nucleo.models import Empleado, Log_auditoria


def run_one():
    c = Client()
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        admin = User.objects.create_superuser('testadmin', 'admin@example.com', 'pass')
    c.force_login(admin)

    emp = Empleado.objects.first()
    if not emp:
        print('No hay empleados en DB para testear')
        return
    employee_id = emp.idempleado.id
    url = reverse('nucleo:modificar_borrar_empleado_id', args=[employee_id])
    print('GET', url)
    resp = c.get(url)
    print('GET status', resp.status_code)
    html = resp.content.decode('utf-8')
    # build payload from inputs/selects
    payload = {}
    # inputs
    for tag in re.findall(r'<input[^>]*>', html):
        nm = re.search(r'name\s*=\s*"([^"]+)"', tag)
        if not nm: continue
        name = nm.group(1)
        if name == 'csrfmiddlewaretoken' or name.startswith('confirmar'): continue
        # skip modal hidden placeholders
        val_m = re.search(r'value\s*=\s*"([^"]*)"', tag)
        val = val_m.group(1) if val_m else ''
        typ_m = re.search(r'type\s*=\s*"([^"]+)"', tag)
        typ = typ_m.group(1).lower() if typ_m else 'text'
        if typ == 'checkbox':
            if 'checked' in tag:
                payload.setdefault(name, []).append(val or 'on')
        elif typ == 'radio':
            if 'checked' in tag:
                payload[name] = val
        else:
            payload[name] = val
    # textareas
    for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', html, re.S):
        payload[m.group(1)] = m.group(2).strip()
    # selects
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        name = m.group(1)
        opts = m.group(2)
        sel = re.search(r'<option[^>]*selected[^>]*value="([^"]*)"', opts)
        if sel:
            payload[name] = sel.group(1)
        else:
            first = re.search(r'<option[^>]*value="([^"]*)"', opts)
            payload[name] = first.group(1) if first else ''
    payload['accion'] = 'actualizar'
    # Force a visible change so the modal appears (in case the form had identical values)
    # Force different values for crucial fields so the server detects changes
    payload['telefono'] = '000000000'
    payload['nombres'] = 'TestCambio'
    # ensure required ModelChoice/required fields have valid ids
    # use localidad that is actually set in the form (hidden value observed in response)
    payload['id_localidad'] = payload.get('id_localidad') or '2960'
    payload['id_estado'] = payload.get('id_estado') or '1'
    payload['id_convenio'] = payload.get('id_convenio') or '1'
    payload['id_puesto'] = payload.get('id_puesto') or '4'
    payload['alta_ant'] = payload.get('alta_ant') or '2020-01-01'
    payload['id_nacionalidad'] = payload.get('id_nacionalidad') or '1'
    payload['id_civil'] = payload.get('id_civil') or '1'
    payload['id_sexo'] = payload.get('id_sexo') or '1'
    # set provincia to match localidad 2960 (CABA -> provincia id 1)
    payload['provincia'] = payload.get('provincia') or '1'
    print('POST update fields:', len(payload))
    resp2 = c.post(url, data=payload)
    print('POST update status', resp2.status_code)
    body = resp2.content.decode('utf-8')
    # save body for inspection
    try:
        with open('/tmp/resp_update.html', 'w') as f:
            f.write(body)
    except Exception:
        pass
    # detect common error markers
    form_error_present = 'mensaje-error' in body or 'error' in body.lower() or 'form.errors' in body
    print('Form error markers present?', form_error_present)
    if 'modal-actualizar' not in body:
        print('Modal no presente en respuesta; abortando. Len body:', len(body))
        return
    m = re.search(r'id="post_data_json_hidden"[^>]*value="([^"]*)"', body)
    post_json = m.group(1) if m else None
    print('post_data_json encontrado:', bool(post_json))
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
            print('Error parseando post_data_json', e)
    print('POST confirmar fields:', len(confirm_payload))
    resp3 = c.post(url, data=confirm_payload)
    print('POST confirmar status', resp3.status_code)
    try:
        with open('/tmp/audit_trace.log', 'r') as f:
            tail = f.read().splitlines()[-80:]
            print('\n--- /tmp/audit_trace.log tail ---')
            for line in tail:
                print(line)
    except Exception as e:
        print('No se pudo leer /tmp/audit_trace.log', e)
    last = Log_auditoria.objects.order_by('-id')[:10]
    print('\n--- últimos Log_auditoria ---')
    for l in last:
        print(l.id, l.nombre_tabla, l.accion, json.dumps(l.cambio) if l.cambio else l.cambio)

if __name__ == '__main__':
    run_one()
