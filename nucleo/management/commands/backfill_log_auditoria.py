from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import json, os


class Command(BaseCommand):
    help = 'Backfill Log_auditoria for insert rows: populate idempleado and nombres/apellido when possible.'

    def add_arguments(self, parser):
        parser.add_argument('--what', choices=['empleado_eo', 'plan_trabajo', 'all'], default='all')
        parser.add_argument('--limit', type=int, default=0, help='Max number of rows to process (0 = no limit)')
        parser.add_argument('--dry-run', action='store_true', dest='dry_run', default=False, help='Do not write changes, only report')
        parser.add_argument('--apply', action='store_true', dest='apply', default=False, help='Apply changes to DB')
        parser.add_argument('--backup-dir', default='backups', help='Directory to write backup file')

    def handle(self, *args, **options):
        from nucleo.models import Log_auditoria, Empleado_eo, Plan_trabajo, Empleado

        what = options['what']
        limit = options['limit']
        dry = options['dry_run']
        do_apply = options['apply']
        backup_dir = options['backup_dir']

        now = timezone.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f'log_audit_backfill_{what}_{now}.json')

        q = Log_auditoria.objects.filter(accion__in=('insert','create'))
        if what == 'empleado_eo':
            q = q.filter(nombre_tabla__iexact='Empleado_eo')
        elif what == 'plan_trabajo':
            q = q.filter(nombre_tabla__iexact='Plan_trabajo')
        else:
            q = q.filter(nombre_tabla__in=['Empleado_eo', 'Plan_trabajo'])

        q = q.order_by('id')
        total = q.count()
        self.stdout.write(f'Found {total} candidate insert logs for {what}')

        to_process = list(q)
        if limit and limit > 0:
            to_process = to_process[:limit]

        modified = []
        processed = 0

        for log in to_process:
            processed += 1
            try:
                cambio = log.cambio
                if isinstance(cambio, str):
                    try:
                        cambio = json.loads(cambio)
                    except Exception:
                        # can't parse; skip
                        continue

                if not isinstance(cambio, dict):
                    continue

                original = dict(cambio)
                changed = False

                if log.nombre_tabla and log.nombre_tabla.lower() == 'empleado_eo':
                    # try to populate idempleado
                    if not cambio.get('idempleado'):
                        # try by log.idregistro -> Empleado_eo.pk
                        try:
                            eo = None
                            if log.idregistro:
                                eo = Empleado_eo.objects.filter(pk=log.idregistro).first()
                            if not eo:
                                # try matching by fecha_eo and id_sucursal
                                fe = cambio.get('fecha_eo')
                                sid = cambio.get('id_sucursal')
                                if fe and sid:
                                    eo = Empleado_eo.objects.filter(fecha_eo=fe, id_sucursal_id=sid).first()
                            if eo and getattr(eo, 'idempleado_id', None):
                                cambio['idempleado'] = eo.idempleado_id
                                changed = True
                        except Exception:
                            pass
                    # try to populate nombres/apellido from Empleado if we now have idempleado
                    if cambio.get('idempleado') and (not cambio.get('nombres') or not cambio.get('apellido')):
                        try:
                            emp = Empleado.objects.filter(idempleado_id=cambio.get('idempleado')).first()
                            if emp:
                                cambio['nombres'] = emp.nombres
                                cambio['apellido'] = emp.apellido
                                changed = True
                        except Exception:
                            pass

                if log.nombre_tabla and log.nombre_tabla.lower() == 'plan_trabajo':
                    if not cambio.get('idempleado'):
                        try:
                            pt = None
                            if log.idregistro:
                                pt = Plan_trabajo.objects.filter(pk=log.idregistro).first()
                            # fallback: try to infer by matching start_time/end_time and dias
                            if not pt:
                                # try to match by start/end times if provided
                                st = cambio.get('start_time') or cambio.get('start_time')
                                en = cambio.get('end_time') or cambio.get('end_time')
                                if st and en:
                                    pt = Plan_trabajo.objects.filter(start_time=st, end_time=en).first()
                            if pt and getattr(pt, 'idempleado_id', None):
                                cambio['idempleado'] = pt.idempleado_id
                                changed = True
                        except Exception:
                            pass
                    if cambio.get('idempleado') and (not cambio.get('nombres') or not cambio.get('apellido')):
                        try:
                            emp = Empleado.objects.filter(idempleado_id=cambio.get('idempleado')).first()
                            if emp:
                                cambio['nombres'] = emp.nombres
                                cambio['apellido'] = emp.apellido
                                changed = True
                        except Exception:
                            pass

                if changed:
                    modified.append({'log_id': log.id, 'nombre_tabla': log.nombre_tabla, 'old': original, 'new': cambio})
                    if do_apply:
                        # write change
                        try:
                            with transaction.atomic():
                                log.cambio = cambio
                                log.save()
                        except Exception as e:
                            self.stderr.write(f'Failed saving log id={log.id}: {e}')
                # end for this log
            except Exception as e:
                self.stderr.write(f'Error processing log id={getattr(log, "id", None)}: {e}')

        # write backup
        try:
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(modified, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f'Wrote backup of {len(modified)} modified rows to {backup_path}')
        except Exception as e:
            self.stderr.write(f'Failed writing backup file: {e}')

        self.stdout.write(f'Processed {processed} rows, modified {len(modified)} rows. apply={do_apply}, dry_run={dry}')
