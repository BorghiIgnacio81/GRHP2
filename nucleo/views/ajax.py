from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

@login_required
def get_is_staff(request):
    user_id = request.GET.get('user_id')
    try:
        user = User.objects.get(pk=user_id)
        return JsonResponse({'is_staff': user.is_staff})
    except User.DoesNotExist:
        return JsonResponse({'is_staff': False})
