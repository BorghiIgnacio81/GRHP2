from django.test import Client
from django.conf import settings
c = Client()
# Login as admin
from django.contrib.auth import get_user_model
User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
if admin:
    c.force_login(admin)
resp = c.get('/nucleo/modificar_borrar_empleado/55/')
print('status', resp.status_code)
html = resp.content.decode('utf-8')
print('has csrf token input:', '<input type="hidden" name="csrfmiddlewaretoken"' in html)
print('has modal-actualizar:', 'id="modal-actualizar"' in html)
start = html.find('<form method="post" id="form-actualizar"')
print('form index', start)
if start!=-1:
    snippet = html[start:start+800]
    print(snippet)
