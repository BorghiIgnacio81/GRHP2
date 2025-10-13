"""Simple harness: login, GET modificar form, scrape inputs, POST update, detect modal marker, extract post_data_json, POST confirm."""
from django.test import Client
from bs4 import BeautifulSoup

c = Client()
# adjust credentials if needed; try superuser
login_ok = c.login(username='admin', password='admin')
print('login_ok', login_ok)
res = c.get('/nucleo/empleados/modificar/1/')
print('GET status', res.status_code)

soup = BeautifulSoup(res.content, 'html.parser')
form = soup.find('form', {'id': 'form_modificar_empleado'}) or soup.find('form')
inputs = form.find_all(['input', 'select', 'textarea'])

payload = {}
for inp in inputs:
    name = inp.get('name')
    if not name:
        continue
    if inp.name == 'select':
        # pick selected option or first
        opt = inp.find('option', selected=True)
        if opt:
            payload[name] = opt.get('value')
        else:
            first = inp.find('option')
            payload[name] = first.get('value') if first else ''
    else:
        payload[name] = inp.get('value', '')

print('built payload keys', list(payload.keys())[:20])
# POST update
res2 = c.post('/nucleo/empleados/modificar/1/', data=payload, follow=True)
print('POST update status', res2.status_code)
print('redirects', res2.redirect_chain)
print('has modal?', 'mostrar_modal_actualizar' in res2.content.decode(errors='ignore'))

# try to find post_data_json in response
if b'post_data_json' in res2.content:
    soup2 = BeautifulSoup(res2.content, 'html.parser')
    h = soup2.find('input', {'name': 'post_data_json'})
    if h:
        post_data_json = h.get('value')
        print('found post_data_json len', len(post_data_json))
        # attempt confirm
        payload_confirm = {}
        # this is a simplification: in real flow JS would inject hidden inputs; try reuse original payload
        payload_confirm.update(payload)
        payload_confirm['post_data_json'] = post_data_json
        res3 = c.post('/nucleo/empleados/modificar/1/', data=payload_confirm, follow=True)
        print('POST confirm status', res3.status_code)
        print('has modal after confirm?', 'mostrar_modal_actualizar' in res3.content.decode(errors='ignore'))
else:
    print('no post_data_json in response')
