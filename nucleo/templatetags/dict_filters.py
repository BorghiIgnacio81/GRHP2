from django import template
import json
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.db import DatabaseError
import unicodedata

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def accion_label(value):
    """Translate action codes to Spanish labels."""
    if value is None:
        return ''
    mapping = {
        'delete': 'Borrar',
        'del': 'Borrar',
        'remove': 'Borrar',
        'update': 'Actualizar',
        'modify': 'Actualizar',
        'insert': 'Crear',
        'create': 'Crear',
    }
    return mapping.get(str(value).lower(), str(value))


@register.simple_tag
def render_cambio(log):
    """Render user-friendly HTML for the `cambio` field depending on action.

    Usage in template: {% render_cambio l %}
    """
    accion = getattr(log, 'accion', '') or ''
    cambio = getattr(log, 'cambio', None)
    usuario = getattr(log, 'idusuario', None)

    accion_l = str(accion).lower()

    def safe(s):
        return escape('' if s is None else str(s))

    def maybe_fmt_date_str(val):
        """If val looks like YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS, return DD/MM/YYYY, else return original."""
        if val is None:
            return val
        # date objects
        try:
            if hasattr(val, 'strftime'):
                return val.strftime('%d/%m/%Y')
        except Exception:
            pass
        s = str(val)
        # ISO date
        try:
            if 'T' in s:
                s2 = s.split('T', 1)[0]
                parts = s2.split('-')
                if len(parts) == 3:
                    return f"{parts[2]}/{parts[1]}/{parts[0]}"
            parts = s.split('-')
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                return f"{parts[2]}/{parts[1]}/{parts[0]}"
        except Exception:
            pass
        return s

    def find_username(obj):
        """Recursively search for a 'username' key in nested dict/list structures.
        Return first found value or None.
        """
        if obj is None:
            return None
        if isinstance(obj, dict):
            # prefer common username keys, including target_username when present
            for key in ('username', 'target_username', 'user', 'usuario', 'nombre'):
                if key in obj and obj.get(key):
                    return obj.get(key)
            for v in obj.values():
                res = find_username(v)
                if res:
                    return res
        if isinstance(obj, (list, tuple)):
            for v in obj:
                res = find_username(v)
                if res:
                    return res
        return None

    def find_fullname(obj):
        """Look for name parts in the payload and return 'Nombres Apellido' if present."""
        if obj is None:
            return None
        try:
            if isinstance(obj, dict):
                # common Spanish keys
                if 'nombres' in obj and obj.get('apellido'):
                    n = obj.get('nombres') or ''
                    a = obj.get('apellido') or ''
                    full = (n + ' ' + a).strip()
                    if full:
                        return full
                # auth user style
                if 'first_name' in obj and obj.get('last_name'):
                    n = obj.get('first_name') or ''
                    a = obj.get('last_name') or ''
                    full = (n + ' ' + a).strip()
                    if full:
                        return full
                # alternative keys
                if 'nombre' in obj and obj.get('apellido'):
                    n = obj.get('nombre') or ''
                    a = obj.get('apellido') or ''
                    full = (n + ' ' + a).strip()
                    if full:
                        return full
            # walk nested structures
            if isinstance(obj, (list, tuple)):
                for v in obj:
                    res = find_fullname(v)
                    if res:
                        return res
            if isinstance(obj, dict):
                for v in obj.values():
                    res = find_fullname(v)
                    if res:
                        return res
        except Exception:
            return None
        return None

    def find_target_name(obj, log):
        """Try to find an employee id in the payload or the log and return 'Nombres Apellido'.

        Search keys: 'idempleado', 'id', 'idregistro', 'idempleado_id'. If found, try to
        resolve Empleado by matching Empleado.idempleado_id == candidate or Empleado.pk == candidate.
        """
        # candidate id extraction
        candidate = None
        try:
            if isinstance(obj, dict):
                for key in ('idempleado', 'id', 'idregistro', 'idempleado_id'):
                    if key in obj and obj.get(key):
                        candidate = obj.get(key)
                        break
            # fallback to log.idregistro
            if not candidate and hasattr(log, 'idregistro') and log.idregistro:
                candidate = log.idregistro
            # coerce to int when possible
            if isinstance(candidate, (list, tuple)) and candidate:
                candidate = candidate[0]
            if candidate is None:
                return None
            try:
                cid = int(candidate)
            except Exception:
                return None
            # import model lazily
            try:
                from nucleo.models import Empleado
                emp = Empleado.objects.filter(idempleado_id=cid).first()
                if not emp:
                    emp = Empleado.objects.filter(pk=cid).first()
                if emp:
                    n = getattr(emp, 'nombres', '') or ''
                    a = getattr(emp, 'apellido', '') or ''
                    full = (n + ' ' + a).strip()
                    return full if full else None
            except DatabaseError:
                return None
            except Exception:
                return None
        except Exception:
            return None
        return None

    def strip_quotes(val):
        """Remove surrounding single/double quotes from strings (common when values are stored as repr)."""
        try:
            if isinstance(val, str) and len(val) >= 2:
                if (val[0] == val[-1]) and val[0] in ("'", '"'):
                    return val[1:-1]
        except Exception:
            pass
        return val

    def normalize_name(s):
        try:
            if not s:
                return ''
            s2 = str(s)
            # remove accents and non-alnum
            s2 = unicodedata.normalize('NFKD', s2).encode('ascii', 'ignore').decode('ascii')
            s2 = ''.join(ch for ch in s2 if ch.isalnum()).lower()
            return s2
        except Exception:
            return str(s).lower() if s else ''

    def find_emp_from_fields_changed(parsed):
        """Try to find an Empleado using parsed['fields_changed'] strings.

        Looks for patterns like "Apellido: 'old' → 'new'", "DNI: 'old' → 'new'", etc.
        Returns full name string or None.
        """
        try:
            if not isinstance(parsed, dict):
                return None
            fc = parsed.get('fields_changed')
            if not isinstance(fc, (list, tuple)):
                return None
            cand = None
            for item in fc:
                try:
                    s = str(item)
                    # split by arrow if present
                    if '→' in s:
                        left, right = s.split('→', 1)
                        # field part is before ':' in left
                        if ':' in left:
                            field = left.split(':', 1)[0].strip().lower()
                        else:
                            field = left.strip().lower()
                        # new value is right
                        newv = right.strip()
                    elif '->' in s:
                        left, right = s.split('->', 1)
                        if ':' in left:
                            field = left.split(':', 1)[0].strip().lower()
                        else:
                            field = left.strip().lower()
                        newv = right.strip()
                    else:
                        # not a field change with new value
                        continue
                    # strip quotes and html entities
                    newv = newv.replace("'", '').replace('"', '').replace('&#x27;', '').strip()
                    # if field indicates apellido/dni/nombres/cuil, try to find employee
                    from nucleo.models import Empleado
                    if 'apellido' in field and newv:
                        e = Empleado.objects.filter(apellido__iexact=newv).first()
                        if e:
                            return (getattr(e, 'nombres', '') or '') + ' ' + (getattr(e, 'apellido', '') or '')
                    if 'dni' in field and newv:
                        e = Empleado.objects.filter(dni__iexact=newv).first()
                        if e:
                            return (getattr(e, 'nombres', '') or '') + ' ' + (getattr(e, 'apellido', '') or '')
                    if 'cuil' in field and newv:
                        clean = newv.replace('.', '').replace('-', '').strip()
                        e = Empleado.objects.filter(cuil__icontains=clean).first()
                        if e:
                            return (getattr(e, 'nombres', '') or '') + ' ' + (getattr(e, 'apellido', '') or '')
                    if 'nombre' in field or 'nombres' in field and newv:
                        e = Empleado.objects.filter(nombres__iexact=newv).first()
                        if e:
                            return (getattr(e, 'nombres', '') or '') + ' ' + (getattr(e, 'apellido', '') or '')
                except Exception:
                    continue
        except Exception:
            return None
        return None

    html_parts = []

    # For delete: prefer target employee full name from payload/log, else prefer username
    if accion_l in ('delete', 'del', 'remove'):
        target_display = None
        try:
            parsed_cambio = None
            if isinstance(cambio, str):
                try:
                    parsed_cambio = json.loads(cambio)
                except Exception:
                    parsed_cambio = None
            else:
                parsed_cambio = cambio
            # prefer explicit fullname from payload, then resolved employee name, then username-like
            target_display = find_fullname(parsed_cambio)
            if not target_display:
                target_display = find_target_name(parsed_cambio, log)
            if not target_display:
                # fallback to any username-like value
                target_display = find_username(parsed_cambio)
        except Exception:
            target_display = None

        if not target_display:
            target_display = getattr(usuario, 'username', None) if usuario else None

        if target_display:
            html_parts.append(f"<div class=\"cambio-username\">{safe(target_display)}</div>")
        else:
            html_parts.append(f"<div class=\"cambio-raw\">{safe(cambio)}</div>")
        return mark_safe(''.join(html_parts))

    # Try to parse cambio as JSON if it's a string
    parsed = None
    if isinstance(cambio, str):
        try:
            parsed = json.loads(cambio)
        except Exception:
            parsed = None
    else:
        parsed = cambio

    # For update: prefer target employee full name from payload/log and render each changed field on its own line
    if accion_l in ('update', 'modify'):
        table_name = (getattr(log, 'nombre_tabla', '') or '').lower()

        # 1) try to resolve directly from DB when update concerns Empleado/Empleado_el
        target_display = None
        if table_name in ('empleado', 'empleado_el'):
            try:
                from nucleo.models import Empleado, Empleado_el as _EmpleadoEl
                if table_name == 'empleado_el':
                    el = _EmpleadoEl.objects.filter(pk=getattr(log, 'idregistro', None)).first()
                    if el and getattr(el, 'idempleado', None):
                        emp = getattr(el, 'idempleado')
                        tn = (getattr(emp, 'nombres', '') or '') + ' ' + (getattr(emp, 'apellido', '') or '')
                        tn = tn.strip()
                        if tn:
                            target_display = tn
                else:
                    emp = Empleado.objects.filter(pk=getattr(log, 'idregistro', None)).first()
                    if not emp and isinstance(parsed, dict):
                        cid = parsed.get('idempleado') or parsed.get('id') or parsed.get('idregistro')
                        try:
                            if cid:
                                emp = Empleado.objects.filter(idempleado_id=int(cid)).first() or Empleado.objects.filter(pk=int(cid)).first()
                        except Exception:
                            emp = None
                    if emp:
                        tn = (getattr(emp, 'nombres', '') or '') + ' ' + (getattr(emp, 'apellido', '') or '')
                        tn = tn.strip()
                        if tn:
                            target_display = tn
            except Exception:
                target_display = None

        # Special rendering for Empleado_eo (Sucursal changes): show branch names
        if table_name == 'empleado_eo':
            try:
                from nucleo.models import Empleado as _Empleado, Empleado_eo as _EmpleadoEo, Sucursal as _Sucursal
                eo_rec = _EmpleadoEo.objects.filter(pk=getattr(log, 'idregistro', None)).first()
                if not target_display and eo_rec and getattr(eo_rec, 'idempleado', None):
                    emp = getattr(eo_rec, 'idempleado')
                    tn = (getattr(emp, 'nombres', '') or '') + ' ' + (getattr(emp, 'apellido', '') or '')
                    tn = tn.strip()
                    if tn:
                        target_display = tn
                # Parse changes and format id_sucursal using names
                if isinstance(parsed, dict):
                    changed = parsed.get('changed') or {}
                    if isinstance(changed, dict) and 'id_sucursal' in changed:
                        rec = changed.get('id_sucursal') or {}
                        old_id = rec.get('old')
                        new_id = rec.get('new')
                        def _suc_name(_id):
                            if not _id:
                                return 'Sin sucursal'
                            try:
                                s = _Sucursal.objects.filter(pk=int(_id)).first()
                                return getattr(s, 'sucursal', None) or f"#{_id}"
                            except Exception:
                                return f"#{_id}"
                        if target_display:
                            html_parts.append(f"<div class=\"cambio-username\">{safe(target_display)}</div>")
                        # Render label in bold like other fields
                        html_parts.append('<div class="cambio-field">')
                        html_parts.append('<span class="cambio-field-name"><strong>Sucursal</strong>:</span>')
                        html_parts.append(f" {safe(_suc_name(old_id))} \u2192 {safe(_suc_name(new_id))}")
                        html_parts.append('</div>')
                        return mark_safe(''.join(html_parts))
            except Exception:
                pass

        # 2) fallback: payload fullname or resolved target id (do NOT show actor username)
        if not target_display:
            target_display = find_fullname(parsed) or find_target_name(parsed, log)
            if not target_display:
                cid = None
                if isinstance(parsed, dict):
                    cid = parsed.get('idempleado') or parsed.get('id') or parsed.get('idregistro')
                if not cid and hasattr(log, 'idregistro') and log.idregistro:
                    cid = getattr(log, 'idregistro')
                if cid:
                    try:
                        from nucleo.models import Empleado
                        emp = None
                        try:
                            emp = Empleado.objects.filter(idempleado_id=int(cid)).first() or Empleado.objects.filter(pk=int(cid)).first()
                        except Exception:
                            emp = None
                        if emp:
                            tn = (getattr(emp, 'nombres', '') or '') + ' ' + (getattr(emp, 'apellido', '') or '')
                            tn = tn.strip()
                            if tn:
                                target_display = tn
                        else:
                            target_display = f"Empleado #{cid}"
                    except Exception:
                        target_display = f"Registro #{cid}"

        # 3) try heuristic from fields_changed strings
        if not target_display:
            try:
                candidate = find_emp_from_fields_changed(parsed)
                if candidate:
                    target_display = candidate
            except Exception:
                pass

        # remember header for the affected employee (append later to avoid duplicates)
        header_display = None
        if target_display:
            header_display = target_display

        # If plan_trabajo update, render similarly to insert/create (idempleado, dias badges, horarios)
        if table_name == 'plan_trabajo' and isinstance(parsed, dict):
            # Accept compact diff payloads produced by _minimal_changed: {'id': ..., 'changed': {field: {'old':..,'new':..}}}
            # Normalize to a payload shape similar to insert: {'idempleado':..., 'dias': {...}, 'start_time':..., 'end_time':...}
            normalized = None
            try:
                # If parsed contains 'changed' mapping, build dias/start/end from it
                if 'changed' in parsed and isinstance(parsed.get('changed'), dict):
                    changed = parsed.get('changed') or {}
                    dias_map = {}
                    st = None
                    en = None
                    for k, v in changed.items():
                        # v may be dict {'old':..., 'new':...}
                        newv = None
                        if isinstance(v, dict):
                            newv = v.get('new')
                        else:
                            newv = v
                        lk = str(k).lower()
                        if lk in ('start_time','start','entrada'):
                            st = newv
                        elif lk in ('end_time','end','salida'):
                            en = newv
                        elif lk in ('lunes','martes','miercoles','jueves','viernes','sabado','domingo'):
                            dias_map[lk] = bool(newv)
                    normalized = {'idempleado': parsed.get('id') or parsed.get('idempleado') or parsed.get('idregistro'), 'dias': dias_map or None, 'start_time': st, 'end_time': en}
                else:
                    normalized = parsed
            except Exception:
                normalized = parsed
            # use normalized payload for downstream logic
            # preserve original 'changed' mapping if present so we can prefer its 'new' values
            if isinstance(normalized, dict) and isinstance(parsed, dict) and 'changed' in parsed and isinstance(parsed.get('changed'), dict):
                normalized = dict(normalized)
                normalized['changed'] = parsed.get('changed')
            parsed = normalized
            # For updates, we want to show only edited days and times (if present).
            # If the payload contains a compact 'changed' mapping (field -> {'old','new'}),
            # prefer its 'new' values for rendering rather than comparing against the DB
            changed_entries = None
            if isinstance(parsed, dict) and 'changed' in parsed and isinstance(parsed.get('changed'), dict):
                changed_entries = parsed.get('changed')
                # build payloads from changed_entries
                dias_payload = {}
                start_payload = None
                end_payload = None
                for k, v in changed_entries.items():
                    lk = str(k).lower()
                    newv = None
                    if isinstance(v, dict):
                        newv = v.get('new')
                    else:
                        newv = v
                    if lk in ('lunes','martes','miercoles','jueves','viernes','sabado','domingo'):
                        try:
                            dias_payload[lk] = bool(newv)
                        except Exception:
                            dias_payload[lk] = newv
                    elif lk in ('start_time','start','entrada'):
                        start_payload = newv
                    elif lk in ('end_time','end','salida'):
                        end_payload = newv
                # idempleado may be present at top-level
                idempleado_val = parsed.get('id') or parsed.get('idempleado') or parsed.get('idregistro')
            else:
                idempleado_val = parsed.get('idempleado') or None
                dias_payload = parsed.get('dias') if isinstance(parsed.get('dias'), dict) else None
                start_payload = parsed.get('start_time') or parsed.get('start') or parsed.get('entrada') or None
                end_payload = parsed.get('end_time') or parsed.get('end') or parsed.get('salida') or None

            try:
                from nucleo.models import Plan_trabajo
                pt = Plan_trabajo.objects.filter(pk=getattr(log, 'idregistro', None)).first()
            except Exception:
                pt = None

            # Try to resolve employee fullname
            emp_name = None
            if pt and getattr(pt, 'idempleado', None):
                emp = getattr(pt, 'idempleado')
                emp_name = ((getattr(emp, 'nombres', '') or '') + ' ' + (getattr(emp, 'apellido', '') or '')).strip()
            if not emp_name:
                # try payload
                emp_name = find_fullname(parsed) or find_target_name(parsed, log)
            # prefer emp_name for header when available
            if emp_name:
                header_display = emp_name

            # if we have a header_display, render it at top so Plan_trabajo logs show the employee
            if header_display:
                html_parts.append(f"<div class=\"cambio-target\" style=\"background:#eef6ff;padding:6px;border-radius:4px;margin-bottom:6px\"><strong>{safe(header_display)}</strong></div>")

            # Determine edited days: if we have a 'changed' mapping, use its 'new' values directly;
            # otherwise, try to detect changes by comparing payload against DB.
            edited_days = {}
            if isinstance(dias_payload, dict):
                if changed_entries is not None:
                    for k, v in dias_payload.items():
                        try:
                            edited_days[k] = bool(v)
                        except Exception:
                            edited_days[k] = v
                else:
                    for k, v in dias_payload.items():
                        try:
                            before = getattr(pt, k) if pt and hasattr(pt, k) else None
                        except Exception:
                            before = None
                        # consider change if before is not same truthiness as v
                        try:
                            if bool(before) != bool(v):
                                edited_days[k] = bool(v)
                        except Exception:
                            if str(before) != str(v):
                                edited_days[k] = v

            # render edited days only
            if edited_days:
                parts = []
                order = ['lunes','martes','miercoles','jueves','viernes','sabado','domingo']
                for d in order:
                    if d in edited_days:
                        boolean = bool(edited_days[d])
                        color = 'background: #d4edda; color: #155724; padding:2px 6px; border-radius:4px;' if boolean else 'background: #f8d7da; color: #721c24; padding:2px 6px; border-radius:4px;'
                        parts.append(f"{d}: <span style=\"{color}\">{str(boolean)}</span>")
                dias_html = ', '.join(parts)
                html_parts.append('<div class="cambio-field">')
                html_parts.append(f"<span class=\"cambio-field-name\"><strong>Dias editados</strong>:</span> <span class=\"cambio-new\">{mark_safe(dias_html)}</span>")
                html_parts.append('</div>')

            # horarios: show when payload included them; if we have changed_entries prefer its 'new' values
            if start_payload:
                if changed_entries is not None:
                    # start_payload already taken from changed_entries
                    html_parts.append('<div class="cambio-field">')
                    html_parts.append(f"<span class=\"cambio-field-name\"><strong>Horario entrada</strong>:</span> {safe(strip_quotes(start_payload))}")
                    html_parts.append('</div>')
                else:
                    before_start = getattr(pt, 'start_time', None) if pt else None
                    if str(before_start) != str(start_payload):
                        html_parts.append('<div class="cambio-field">')
                        html_parts.append(f"<span class=\"cambio-field-name\"><strong>Horario entrada</strong>:</span> {safe(strip_quotes(start_payload))}")
                        html_parts.append('</div>')
            if end_payload:
                if changed_entries is not None:
                    html_parts.append('<div class="cambio-field">')
                    html_parts.append(f"<span class=\"cambio-field-name\"><strong>Horario salida</strong>:</span> {safe(strip_quotes(end_payload))}")
                    html_parts.append('</div>')
                else:
                    before_end = getattr(pt, 'end_time', None) if pt else None
                    if str(before_end) != str(end_payload):
                        html_parts.append('<div class="cambio-field">')
                        html_parts.append(f"<span class=\"cambio-field-name\"><strong>Horario salida</strong>:</span> {safe(strip_quotes(end_payload))}")
                        html_parts.append('</div>')

            return mark_safe(''.join(html_parts))

        # Generic update rendering follows: build a table-scoped list of field changes
        field_changes = []
        table_name = (getattr(log, 'nombre_tabla', '') or '').lower()

        def parse_fields_changed_list(items):
            out = []
            for item in items:
                try:
                    s = str(item)
                    # split arrow
                    if '→' in s:
                        left, right = s.split('→', 1)
                    elif '->' in s:
                        left, right = s.split('->', 1)
                    else:
                        left = s
                        right = ''
                    # extract field name before ':' if present
                    if ':' in left:
                        field = left.split(':', 1)[0].strip()
                        old = left.split(':', 1)[1].strip()
                    else:
                        field = left.strip()
                        old = ''
                    new = right.strip()
                    old = strip_quotes(old.replace('&#x27;', '').strip())
                    new = strip_quotes(new.replace('&#x27;', '').strip())
                    out.append({'field': field or '', 'old': old, 'new': new})
                except Exception:
                    continue
            return out

        # Case A: human-readable list under 'fields_changed'
        if isinstance(parsed, dict) and 'fields_changed' in parsed and isinstance(parsed['fields_changed'], (list, tuple)):
            field_changes = parse_fields_changed_list(parsed['fields_changed'])
        else:
            # Case B: parsed may contain a sub-dict for the table (key equal to table_name)
            parsed_sub = None
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    try:
                        if isinstance(k, str) and k.lower() == table_name:
                            parsed_sub = v
                            break
                    except Exception:
                        continue
                if parsed_sub is None:
                    # no explicit table sub-dict; assume parsed itself describes the fields for this table
                    parsed_sub = parsed

            # Normalize parsed_sub into field_changes
            if isinstance(parsed_sub, dict):
                # prefer 'changed' mapping when present
                if 'changed' in parsed_sub and isinstance(parsed_sub['changed'], dict):
                    for fname, fvals in parsed_sub['changed'].items():
                        old = ''
                        new = ''
                        if isinstance(fvals, dict):
                            old = fvals.get('old') or fvals.get('before') or ''
                            new = fvals.get('new') or fvals.get('after') or ''
                        else:
                            new = fvals
                        field_changes.append({'field': fname, 'old': strip_quotes(maybe_fmt_date_str(old)), 'new': strip_quotes(maybe_fmt_date_str(new))})
                else:
                    for fname, vals in parsed_sub.items():
                        # skip nested tables keys
                        if isinstance(fname, str) and fname.lower() != table_name:
                            # if this key looks like another table (contains uppercase or '_'), skip it
                            # but still allow standard field names
                            pass
                        old = ''
                        new = ''
                        if isinstance(vals, (list, tuple)):
                            if len(vals) >= 1:
                                old = vals[0]
                            if len(vals) >= 2:
                                new = vals[1]
                        elif isinstance(vals, dict):
                            old = vals.get('old') or vals.get('before') or vals.get('viejo') or ''
                            new = vals.get('new') or vals.get('after') or vals.get('nuevo') or ''
                        else:
                            new = vals
                        field_changes.append({'field': fname, 'old': strip_quotes(maybe_fmt_date_str(old)), 'new': strip_quotes(maybe_fmt_date_str(new))})

        # Append header (if any) and then render only the table-scoped fields
        if header_display:
            html_parts.append(f"<div class=\"cambio-target\" style=\"background:#eef6ff;padding:6px;border-radius:4px;margin-bottom:6px\"><strong>{safe(header_display)}</strong></div>")

        # Filter field_changes to include only fields that belong to this table's model when possible
        try:
            model_field_norms = set()
            if table_name in ('empleado', 'empleado_el'):
                from nucleo import models as _models
                if table_name == 'empleado':
                    m = getattr(_models, 'Empleado', None)
                else:
                    m = getattr(_models, 'Empleado_el', None)
                if m is not None:
                    for f in m._meta.get_fields():
                        try:
                            fname = getattr(f, 'name', '') or ''
                            vname = str(getattr(f, 'verbose_name', '') or '')
                            if fname:
                                model_field_norms.add(normalize_name(fname))
                            if vname:
                                model_field_norms.add(normalize_name(vname))
                        except Exception:
                            continue
            # Allow derived provincia field for Empleado logs
            if table_name == 'empleado':
                model_field_norms.add('idprovincia')
                # Add friendly-label synonyms so fallback 'fields_changed' labels pass filtering
                # Normalize removing accents / non-alnum to match our normalization
                synonyms = [
                    'nombre', 'apellido', 'dni', 'cuil', 'fechanacimiento',
                    'nacionalidad', 'estadocivil', 'cantidaddehijos', 'sexo',
                    'provincia', 'localidad', 'direccion', 'telefono'
                ]
                for s in synonyms:
                    model_field_norms.add(s)
        except Exception:
            model_field_norms = set()

        if field_changes:
            arrow_html = '<span class="cambio-arrow" style="background:#d4edda;color:#155724;padding:2px 6px;border-radius:4px;margin:0 6px;">→</span>'
            # helper to map labels by table/field
            def friendly_label(tn, fname):
                fl = str(fname)
                low = fl.lower()
                if tn == 'auth_user':
                    if low == 'is_staff':
                        return 'Gestor'
                    if low == 'email':
                        return 'Email'
                    return fl
                if tn == 'empleado_el':
                    if low == 'alta_ant':
                        return 'Antiguedad reconocida'
                    if low == 'fecha_est':
                        return 'Fecha Estado'
                    if low in ('id_estado','estado'):
                        return 'Estado'
                    if low in ('id_puesto','puesto'):
                        return 'Puesto'
                    if low in ('id_convenio','convenio'):
                        return 'Convenio'
                    return fl
                if tn == 'empleado':
                    mapping = {
                        'nombres': 'Nombre',
                        'apellido': 'Apellido',
                        'dni': 'DNI',
                        'cuil': 'CUIL',
                        'fecha_nac': 'Fecha Nacimiento',
                        'id_nacionalidad': 'Nacionalidad',
                        'id_civil': 'Estado Civil',
                        'num_hijos': 'Cantidad de Hijos',
                        'id_sexo': 'Sexo',
                        'id_provincia': 'Provincia',
                        'id_localidad': 'Localidad',
                        'dr_personal': 'Dirección',
                        'telefono': 'Teléfono',
                    }
                    return mapping.get(low, fl)
                return fl

            for ch in field_changes:
                fname = ch.get('field') or ''
                # filter by model fields when we have norms
                try:
                    if model_field_norms:
                        if normalize_name(fname) not in model_field_norms:
                            # skip fields that don't match model fields
                            continue
                except Exception:
                    pass
                # map to friendlier labels per table
                label = friendly_label(table_name, fname)
                old = ch.get('old') or ''
                new = ch.get('new') or ''
                # Skip lines where old and new are equal (can happen in fallback 'fields_changed')
                try:
                    if str(old).strip() == str(new).strip():
                        continue
                except Exception:
                    pass
                # Special formatting for auth_user Gestor boolean
                if table_name == 'auth_user' and str(fname).lower() == 'is_staff':
                    def yn(v):
                        s = str(v).strip().lower()
                        return 'sí' if s in ('1','true','t','yes','y','si','on') else 'no'
                    old = yn(old)
                    new = yn(new)
                html_parts.append('<div class="cambio-field">')
                html_parts.append(f"<span class=\"cambio-field-name\"><strong>{safe(label)}</strong>:</span>")
                html_parts.append(f" {safe(old)} {arrow_html} {safe(new)}")
                html_parts.append('</div>')
            return mark_safe(''.join(html_parts))

        # Fallback: if we couldn't parse field changes, show raw cleaned
        html_parts.append(f"<div class=\"cambio-raw\">{safe(cambio)}</div>")
        return mark_safe(''.join(html_parts))

    # For insert/create: list fields and values
    if accion_l in ('insert', 'create'):
        # Special cases for certain tables
        table_name = (getattr(log, 'nombre_tabla', '') or '').lower()
        # Helper: format date YYYY-MM-DD -> DD/MM/YYYY
        def fmt_date(d):
            if not d:
                return ''
            try:
                # accept date objects or strings
                if hasattr(d, 'strftime'):
                    return d.strftime('%d/%m/%Y')
                s = str(d)
                parts = s.split('-')
                if len(parts) >= 3:
                    return f"{parts[2]}/{parts[1]}/{parts[0]}"
            except Exception:
                return str(d)
            return str(d)

        if isinstance(parsed, dict) and table_name == 'empleado_eo':
            # Show: idempleado, fecha_eo (dd/mm/yyyy), sucursal (lookup)
            idempleado_val = parsed.get('idempleado') or None
            fecha_eo_val = parsed.get('fecha_eo') or parsed.get('fecha') or None
            suc_id = parsed.get('id_sucursal') or parsed.get('idSucursal') or parsed.get('sucursal') or None
            # try to resolve missing pieces from DB using log.idregistro
            if not idempleado_val or not suc_id:
                try:
                    from nucleo.models import Empleado_eo, Sucursal
                    eo = Empleado_eo.objects.filter(pk=getattr(log, 'idregistro', None)).first()
                    if eo:
                        if not idempleado_val:
                            idempleado_val = getattr(eo, 'idempleado_id', None)
                        if not fecha_eo_val:
                            fecha_eo_val = getattr(eo, 'fecha_eo', None)
                        if not suc_id:
                            suc_id = getattr(eo, 'id_sucursal_id', None)
                except Exception:
                    pass

            sucursal_name = None
            if suc_id:
                try:
                    from nucleo.models import Sucursal
                    suc = Sucursal.objects.filter(pk=suc_id).first()
                    if suc:
                        sucursal_name = getattr(suc, 'sucursal', None)
                except Exception:
                    sucursal_name = None

            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">idempleado:</span> <span class=\"cambio-new\">{safe(idempleado_val)}</span>")
            html_parts.append('</div>')
            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">fecha_eo:</span> <span class=\"cambio-new\">{safe(fmt_date(fecha_eo_val))}</span>")
            html_parts.append('</div>')
            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\"><strong>Sucursal</strong>:</span> <span class=\"cambio-new\">{safe(sucursal_name or suc_id)}</span>")
            html_parts.append('</div>')
            return mark_safe(''.join(html_parts))

        if isinstance(parsed, dict) and table_name == 'plan_trabajo':
            # Show: idempleado, dias: lunes: True,.. with colored badges, horario entrada(start_time), horario salida(end_time)
            idempleado_val = parsed.get('idempleado') or None
            dias = parsed.get('dias') if isinstance(parsed.get('dias'), dict) else None
            start = parsed.get('start_time') or parsed.get('start') or parsed.get('entrada') or None
            end = parsed.get('end_time') or parsed.get('end') or parsed.get('salida') or None

            # attempt to resolve from DB if missing
            if not idempleado_val or not dias:
                try:
                    from nucleo.models import Plan_trabajo
                    pt = Plan_trabajo.objects.filter(pk=getattr(log, 'idregistro', None)).first()
                    if pt:
                        if not idempleado_val:
                            idempleado_val = getattr(pt, 'idempleado_id', None)
                        if not dias:
                            dias = {
                                'lunes': pt.lunes,
                                'martes': pt.martes,
                                'miercoles': pt.miercoles,
                                'jueves': pt.jueves,
                                'viernes': pt.viernes,
                                'sabado': pt.sabado,
                                'domingo': pt.domingo,
                            }
                        if not start:
                            start = getattr(pt, 'start_time', None)
                        if not end:
                            end = getattr(pt, 'end_time', None)
                except Exception:
                    pass

            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">idempleado:</span> <span class=\"cambio-new\">{safe(idempleado_val)}</span>")
            html_parts.append('</div>')

            # format dias inline
            if isinstance(dias, dict):
                parts = []
                order = ['lunes','martes','miercoles','jueves','viernes','sabado','domingo']
                for d in order:
                    val = dias.get(d)
                    # display True/False with colored background
                    try:
                        boolean = bool(val)
                    except Exception:
                        boolean = False
                    color = 'background: #d4edda; color: #155724; padding:2px 6px; border-radius:4px;' if boolean else 'background: #f8d7da; color: #721c24; padding:2px 6px; border-radius:4px;'
                    parts.append(f"{d}: <span style=\"{color}\">{str(boolean)}</span>")
                dias_html = ', '.join(parts)
                html_parts.append('<div class="cambio-field">')
                # don't double-escape: dias_html already contains safe inline spans
                html_parts.append(f"<span class=\"cambio-field-name\">dias:</span> <span class=\"cambio-new\">{mark_safe(dias_html)}</span>")
                html_parts.append('</div>')

            # horarios
            if start:
                html_parts.append('<div class="cambio-field">')
                html_parts.append(f"<span class=\"cambio-field-name\">horario entrada:</span> <span class=\"cambio-new\">{safe(start)}</span>")
                html_parts.append('</div>')
            if end:
                html_parts.append('<div class="cambio-field">')
                html_parts.append(f"<span class=\"cambio-field-name\">horario salida:</span> <span class=\"cambio-new\">{safe(end)}</span>")
                html_parts.append('</div>')
            return mark_safe(''.join(html_parts))

        if isinstance(parsed, dict) and table_name in ('empleado_el', 'empleado_el'.lower()):
            # Show: idempleado, alta_ant (dd/mm/yyyy), estado (lookup Estado_empleado), puesto (lookup Puesto), convenio (lookup Convenio)
            idempleado_val = parsed.get('idempleado') or parsed.get('id_empleado') or None
            alta_ant_val = parsed.get('alta_ant') or parsed.get('alta_antiguedad') or parsed.get('alta') or None
            id_estado = parsed.get('id_estado') or parsed.get('estado') or None
            id_puesto = parsed.get('id_puesto') or parsed.get('puesto') or None
            id_convenio = parsed.get('id_convenio') or parsed.get('convenio') or None

            # try to resolve missing pieces from DB using log.idregistro
            try:
                from nucleo.models import Empleado_el, Estado_empleado, Puesto, Convenio
                el = Empleado_el.objects.filter(pk=getattr(log, 'idregistro', None)).first()
                if el:
                    if not idempleado_val:
                        idempleado_val = getattr(el, 'idempleado_id', None)
                    if not alta_ant_val:
                        alta_ant_val = getattr(el, 'alta_ant', None)
                    if not id_estado:
                        id_estado = getattr(el, 'id_estado_id', None)
                    if not id_puesto:
                        id_puesto = getattr(el, 'id_puesto_id', None)
                    if not id_convenio:
                        id_convenio = getattr(el, 'id_convenio_id', None)
            except Exception:
                pass

            estado_name = None
            try:
                from nucleo.models import Estado_empleado as _Estado, Puesto as _Puesto, Convenio as _Convenio
                if id_estado:
                    st = _Estado.objects.filter(pk=id_estado).first()
                    if st:
                        estado_name = getattr(st, 'estado', None)
                puesto_name = None
                if id_puesto:
                    p = _Puesto.objects.filter(pk=id_puesto).first()
                    if p:
                        puesto_name = getattr(p, 'tipo_puesto', None)
                convenio_name = None
                if id_convenio:
                    c = _Convenio.objects.filter(pk=id_convenio).first()
                    if c:
                        convenio_name = getattr(c, 'tipo_convenio', None)
            except Exception:
                estado_name = estado_name if 'estado_name' in locals() else None
                puesto_name = puesto_name if 'puesto_name' in locals() else None
                convenio_name = convenio_name if 'convenio_name' in locals() else None

            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">idempleado:</span> <span class=\"cambio-new\">{safe(idempleado_val)}</span>")
            html_parts.append('</div>')

            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">alta_ant:</span> <span class=\"cambio-new\">{safe(fmt_date(alta_ant_val))}</span>")
            html_parts.append('</div>')

            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">estado:</span> <span class=\"cambio-new\">{safe(estado_name or id_estado)}</span>")
            html_parts.append('</div>')

            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">puesto:</span> <span class=\"cambio-new\">{safe(puesto_name or id_puesto)}</span>")
            html_parts.append('</div>')

            html_parts.append('<div class="cambio-field">')
            html_parts.append(f"<span class=\"cambio-field-name\">convenio:</span> <span class=\"cambio-new\">{safe(convenio_name or id_convenio)}</span>")
            html_parts.append('</div>')
            return mark_safe(''.join(html_parts))

        if isinstance(parsed, dict) and table_name == 'empleado':
            # Show empleado fields but ensure date fields are formatted dd/mm/yyyy
            for field, val in parsed.items():
                display_val = val
                # format date-like fields using fmt_date
                try:
                    display_val = fmt_date(val)
                except Exception:
                    display_val = maybe_fmt_date_str(val)
                html_parts.append('<div class="cambio-field">')
                html_parts.append(f"<span class=\"cambio-field-name\">{safe(field)}:</span> <span class=\"cambio-new\">{safe(display_val)}</span>")
                html_parts.append('</div>')
            return mark_safe(''.join(html_parts))

        # generic fallback for other inserts
        if isinstance(parsed, dict):
            for field, val in parsed.items():
                # show field: value
                html_parts.append('<div class="cambio-field">')
                display_val = maybe_fmt_date_str(val)
                html_parts.append(f"<span class=\"cambio-field-name\">{safe(field)}:</span> <span class=\"cambio-new\">{safe(display_val)}</span>")
                html_parts.append('</div>')
        else:
            html_parts.append(f"<div class=\"cambio-raw\">{safe(cambio)}</div>")

        return mark_safe(''.join(html_parts))

    # Default fallback: show raw but escaped and without braces/quotes
    if cambio is None:
        return ''
    # attempt to stringify and strip braces/quotes
    text = str(cambio)
    # remove surrounding braces and quotes
    text = text.strip()
    if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
        try:
            parsed2 = json.loads(text)
            if isinstance(parsed2, dict):
                for k, v in parsed2.items():
                    html_parts.append(f"<div class=\"cambio-field\"><span class=\"cambio-field-name\">{safe(k)}:</span> <span class=\"cambio-new\">{safe(v)}</span></div>")
                return mark_safe(''.join(html_parts))
        except Exception:
            pass

    return mark_safe(f"<div class=\"cambio-raw\">{escape(text)}</div>")