"""Inspecciona solicitudes con fecha_desde dada y lista Vacaciones_otorgadas solapadas y por qué.
Uso: PYTHONPATH=/root/gestion_rrhh /root/myenv/bin/python scripts/inspect_delete_issue.py [YYYY-MM-DD]
"""
import os
import sys
from datetime import date
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_rrhh.settings')

def main():
    import django
    django.setup()
    from nucleo.models import Solicitud_licencia, Vacaciones_otorgadas
    from datetime import datetime
    arg = sys.argv[1] if len(sys.argv) > 1 else '2025-11-01'
    try:
        fecha = datetime.strptime(arg, '%Y-%m-%d').date()
    except Exception as e:
        print('Fecha inválida', e); return
    hoy = date.today()
    print('Hoy:', hoy)
    qs = Solicitud_licencia.objects.filter(fecha_desde=fecha)
    print('Solicitudes encontradas con fecha_desde=', fecha, 'count=', qs.count())
    for s in qs:
        print('--- Solicitud id:', s.pk, 'empleado_id:', getattr(s.idempleado, 'idempleado_id', None) or getattr(s.idempleado, 'pk', None))
        print('  estado:', getattr(s.id_estado,'estado',None))
        print('  rango:', s.fecha_desde, s.fecha_hasta)
        overlapping = Vacaciones_otorgadas.objects.filter(
            idempleado=s.idempleado,
            inicio_consumo__lte=s.fecha_hasta,
            fin_consumo__gte=s.fecha_desde
        )
        print('  Vacaciones_otorgadas overlapping total:', overlapping.count())
        for v in overlapping:
            in_progress = (v.inicio_consumo <= hoy <= v.fin_consumo)
            finished = (v.fin_consumo < hoy)
            consumed_gt0 = (v.dias_consumidos and v.dias_consumidos > 0)
            print('   - Vac id:', v.pk, 'inicio:', v.inicio_consumo, 'fin:', v.fin_consumo, 'dias_consumidos:', v.dias_consumidos)
            print('     in_progress:', in_progress, 'finished:', finished, 'consumed_gt0:', consumed_gt0)
    # Mostrar overlapping_consumed using same filter as view
    from django.db import models
    qs2 = Solicitud_licencia.objects.filter(fecha_desde=fecha)
    for s in qs2:
        overlapping_consumed = Vacaciones_otorgadas.objects.filter(
            idempleado=s.idempleado,
            inicio_consumo__lte=s.fecha_hasta,
            fin_consumo__gte=s.fecha_desde
        ).filter(
            models.Q(fin_consumo__lt=hoy) |
            models.Q(dias_consumidos__gt=0)
        )
        print('Solicitud', s.pk, 'overlapping_consumed count:', overlapping_consumed.count())

if __name__ == '__main__':
    main()
