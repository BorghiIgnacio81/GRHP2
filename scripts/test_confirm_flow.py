"""Pequeño harness de prueba para el flujo editar->confirmar empleado.
Usa el cliente de pruebas de Django para: GET form, POST payload completo, obtener modal con post_data_json, POST confirm con embedded fields.
Imprime trazas y revisa Log_auditoria creación.
"""
import json
import re

from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from nucleo.models.empleados import Empleado, Log_auditoria


def run(employee_id=None):
    c = Client()
    # login como superuser si existe
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        admin = User.objects.create_superuser('testadmin', 'admin@example.com', 'pass')
    c.force_login(admin)

    if not employee_id:
        emp = Empleado.objects.first()
        if not emp:
            print('No hay empleados en DB para testear')
            return
        employee_id = emp.idempleado.id

    url = reverse('nucleo:modificar_borrar_empleado_id', args=[employee_id])
    print('GET', url)
    resp = c.get(url, HTTP_HOST='localhost')
    if resp.status_code != 200:
        print('GET falló', resp.status_code)
        return

    # parsear el form y construir payload: tomar todos inputs name y valores
    html = resp.content.decode('utf-8')
    # buscar inputs y selects básicos (esto no cubre JS-only fields)
    names = re.findall(r'name="([a-zA-Z0-9_\-]+)"(?:[^>]*value="([^"]*)")?', html)
    payload = {}
    for nm, val in names:
        # omitir csrf y botones
        if nm == 'csrfmiddlewaretoken':
            continue
        if nm.startswith('confirmar'):
            continue
        # preferir valor ya en input, si está vacío usar 'on' para checkbox heurística
        if val:
            payload[nm] = val
        else:
            # intentar detectar checkbox existencia
            if re.search(r'name="%s"[^>]*type="checkbox"' % re.escape(nm), html):
                # si marcado, dejar 'on' else nada. Para este test marcarlo cuando aparece checked
                payload[nm] = 'on' if re.search(r'name="%s"[^>]*checked' % re.escape(nm), html) else ''
            else:
                payload[nm] = ''

    payload['accion'] = 'actualizar'

    """Pequeño harness de prueba para el flujo editar->confirmar empleado.
    Usa el cliente de pruebas de Django para: GET form, POST payload completo, obtener modal con post_data_json, POST confirm con embedded fields.
    Imprime trazas y revisa Log_auditoria creación.
    """
    import json
    import re

    from django.test import Client
    from django.urls import reverse
    from django.contrib.auth.models import User
    from nucleo.models.empleados import Empleado, Log_auditoria


    def run(employee_id=None):
        c = Client()
        # login como superuser si existe
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            admin = User.objects.create_superuser('testadmin', 'admin@example.com', 'pass')
        c.force_login(admin)

        if not employee_id:
            emp = Empleado.objects.first()
            if not emp:
                print('No hay empleados en DB para testear')
                return
            employee_id = emp.idempleado.id

        url = reverse('nucleo:modificar_borrar_empleado_id', args=[employee_id])
        print('GET', url)
        resp = c.get(url, HTTP_HOST='localhost')
        if resp.status_code != 200:
            print('GET falló', resp.status_code)
            return

        html = resp.content.decode('utf-8')

        # Construir payload recogiendo inputs, textareas, selects y checkbox checked
        payload = {}

        # inputs
        input_tags = re.findall(r'<input[^>]*>', html)
        for tag in input_tags:
            name_m = re.search(r'name=\"([^\"]+)\"', tag)
            if not name_m:
                continue
            name = name_m.group(1)
            if name.startswith('confirmar'):
                continue
            if name == 'csrfmiddlewaretoken':
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

        # textareas
        for m in re.finditer(r'<textarea[^>]*name=\"([^\"]+)\"[^>]*>(.*?)</textarea>', html, re.S):
            payload[m.group(1)] = m.group(2).strip()

        # selects
        for m in re.finditer(r'<select[^>]*name=\"([^\"]+)\"[^>]*>(.*?)</select>', html, re.S):
            name = m.group(1)
            opts = m.group(2)
            sel = re.search(r'<option[^>]*selected[^>]*value=\"([^\"]*)\"', opts)
            if sel:
                payload[name] = sel.group(1)
            else:
                first = re.search(r'<option[^>]*value=\"([^\"]*)\"', opts)
                payload[name] = first.group(1) if first else ''

        payload['accion'] = 'actualizar'

        print('POST update, campos:', len(payload))
        resp2 = c.post(url, data=payload, HTTP_HOST='localhost')
        print('POST update status', resp2.status_code)
        body = resp2.content.decode('utf-8')
        if 'modal-actualizar' not in body:
            print('Modal no presente en respuesta; abortando. Long respuesta:', len(body))
            return

        # extraer post_data_json
        m = re.search(r'id=\"post_data_json_hidden\"[^>]*value=\"([^\"]*)\"', body)
        post_json = m.group(1) if m else None
        print('post_data_json encontrado:', bool(post_json))
        if not post_json:
            # intentar extraer cambios_json
            m2 = re.search(r'id=\"cambios_json_hidden\"[^>]*value=\"([^\"]*)\"', body)
            print('cambios_json presente:', bool(m2))

        # preparar confirm payload: incluir post_data_json fields como hidden inputs (decodificar JSON)
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

        print('POST confirmar, campos:', len(confirm_payload))
        resp3 = c.post(url, data=confirm_payload, HTTP_HOST='localhost')
        print('POST confirmar status', resp3.status_code)

        # mostrar últimas trazas
        try:
            with open('/tmp/audit_trace.log','r') as f:
                tail = f.read().splitlines()[-40:]
                print('\n--- /tmp/audit_trace.log tail ---')
                print('\n'.join(tail))
        except Exception as e:
            print('No se pudo leer /tmp/audit_trace.log', e)

        # comprobar Log_auditoria reciente
        last = Log_auditoria.objects.order_by('-id')[:5]
        print('\n--- últimos Log_auditoria ---')
        for l in last:
            print(l.id, l.nombre_tabla, l.accion, json.dumps(l.cambio) if l.cambio else l.cambio)


    if __name__ == '__main__':
        run()
