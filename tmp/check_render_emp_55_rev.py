from django.test import Client
from django.urls import reverse
from django.conf import settings
c = Client()
from django.contrib.auth import get_user_model
User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
if admin:
    c.force_login(admin)
url = reverse('nucleo:modificar_borrar_empleado_id', args=[55])
print('url', url)
resp = c.get(url)
print('status', resp.status_code)
html = resp.content.decode('utf-8')
print('has csrf token input:', '<input type="hidden" name="csrfmiddlewaretoken"' in html)
print('has modal-actualizar:', 'id="modal-actualizar"' in html)
start = html.find('<form method="post" id="form-actualizar"')
print('form index', start)
if start!=-1:
    snippet = html[start:start+800]
    print(snippet)
