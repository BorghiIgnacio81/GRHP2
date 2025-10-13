from nucleo.models import Empleado

def empleado_context(request):
    empleado = None
    empleado_id = None
    if request.user.is_authenticated:
        try:
            empleado = Empleado.objects.get(pk=request.user.id)
            empleado_id = empleado.pk
        except Empleado.DoesNotExist:
            empleado = None
    return {'empleado': empleado, 'empleado_id': empleado_id}