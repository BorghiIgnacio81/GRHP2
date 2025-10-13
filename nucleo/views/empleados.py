from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
import csv
import json
import sys
import traceback
from django.views.decorators.csrf import csrf_protect
from datetime import date, datetime, timedelta
import re
# MODELOS Y FORMULARIOS
from nucleo.models import Empleado, Empleado_el, Empleado_eo, Plan_trabajo, Sucursal, Provincia, Estado_empleado, Log_auditoria, Nacionalidad, EstadoCivil, Sexo, Localidad
from nucleo.forms import EmpleadoModificarForm, EmpleadoELForm
from django.contrib.auth.models import User
# LOGGER
import logging
logger = logging.getLogger(__name__)

def _crear_nuevo_registro_empleado_el(empleado, form_laboral, request=None, registro_anterior=None):
    """
    Crea un nuevo registro en Empleado_el (INSERT) en lugar de actualizar el existente.
    Esto mantiene el historial completo de cambios laborales.
    """
    # Crear nueva instancia sin ID para forzar INSERT
    nuevo_empleado_el = Empleado_el(
        idempleado=empleado,
        fecha_el=datetime.now(),  # Timestamp del registro
    )
    
    # Copiar todos los datos del formulario al nuevo registro
    for field_name, field_value in form_laboral.cleaned_data.items():
        if hasattr(nuevo_empleado_el, field_name):
            # Manejar campos relacionados (ForeignKey) correctamente
            if field_name in ['id_estado', 'id_convenio', 'id_puesto'] and field_value:
                setattr(nuevo_empleado_el, field_name + '_id', field_value.pk if hasattr(field_value, 'pk') else field_value)
            elif field_name not in ['id_estado', 'id_convenio', 'id_puesto']:
                setattr(nuevo_empleado_el, field_name, field_value)
    
    # Manejar campos ForeignKey específicamente para evitar problemas de NULL
    if 'id_estado' in form_laboral.cleaned_data and form_laboral.cleaned_data['id_estado']:
        nuevo_empleado_el.id_estado = form_laboral.cleaned_data['id_estado']
    if 'id_convenio' in form_laboral.cleaned_data and form_laboral.cleaned_data['id_convenio']:
        nuevo_empleado_el.id_convenio = form_laboral.cleaned_data['id_convenio']
    if 'id_puesto' in form_laboral.cleaned_data and form_laboral.cleaned_data['id_puesto']:
        nuevo_empleado_el.id_puesto = form_laboral.cleaned_data['id_puesto']
    
    # Asegurar que fecha_el sea el timestamp actual
    nuevo_empleado_el.fecha_el = datetime.now()
    
    # Guardar el nuevo registro
    nuevo_empleado_el.save()
    
    logger.info(f"Nuevo registro Empleado_el creado para empleado {empleado.idempleado_id} con fecha_el {nuevo_empleado_el.fecha_el}")
    
    # Crear log de auditoría mostrando solo los cambios
    if request and registro_anterior:
        try:
            cambios_laborales = []
            
            # Mapeo de nombres de campos para mostrar en español
            field_labels = {
                'id_estado': 'Estado',
                'id_puesto': 'Puesto', 
                'id_convenio': 'Convenio',
                'fecha_est': 'Fecha Estado',
                'alta_ant': 'Fecha Alta Anterior',
                'sueldo_basico': 'Sueldo Básico'
            }
            
            # Comparar cada campo del formulario
            for field_name in form_laboral.cleaned_data.keys():
                old_value = getattr(registro_anterior, field_name, None)
                new_value = getattr(nuevo_empleado_el, field_name, None)
                
                # Formatear valores para comparación
                if field_name in ['id_estado', 'id_convenio', 'id_puesto']:
                    old_display = str(old_value) if old_value else ''
                    new_display = str(new_value) if new_value else ''
                elif field_name in ['fecha_est', 'alta_ant']:
                    old_display = old_value.strftime('%d/%m/%Y') if old_value else ''
                    new_display = new_value.strftime('%d/%m/%Y') if new_value else ''
                else:
                    old_display = str(old_value) if old_value is not None else ''
                    new_display = str(new_value) if new_value is not None else ''
                
                # Si hay cambio, agregarlo a la lista
                if old_display != new_display:
                    field_label = field_labels.get(field_name, field_name)
                    cambios_laborales.append(f"{field_label}: {old_display} → {new_display}")
            
            # Solo crear log si hay cambios
            if cambios_laborales:
                # Agregar información del empleado
                try:
                    user = User.objects.filter(id=empleado.idempleado_id).first()
                    target_username = user.username if user else f"empleado_{empleado.idempleado_id}"
                except Exception:
                    target_username = f"empleado_{empleado.idempleado_id}"
                
                # Crear el mensaje de cambios en formato texto
                mensaje_cambios = "\n".join(cambios_laborales)
                
                # Crear log de auditoría con formato correcto
                _create_log_if_new(request, 'Empleado_el', nuevo_empleado_el.id, 'update', mensaje_cambios)
                logger.info(f"Log de auditoría creado para cambios en Empleado_el ID {nuevo_empleado_el.id}")
            
        except Exception as e:
            logger.exception(f"Error creando log de auditoría para Empleado_el: {e}")
    
    return nuevo_empleado_el


def _crear_nuevo_registro_empleado_el_directo(empleado, post_data, request=None, registro_anterior=None):
    """
    Crea un nuevo registro en Empleado_el usando directamente los datos de POST,
    sin validación de formulario. Usado como fallback cuando el formulario no valida.
    """
    from nucleo.models import Estado_empleado, Puesto, Convenio
    
    # Crear nueva instancia sin ID para forzar INSERT
    nuevo_empleado_el = Empleado_el(
        idempleado=empleado,
        fecha_el=datetime.now(),
    )
    
    # Mapear campos del POST a los campos del modelo
    try:
        # Estado
        if 'id_estado' in post_data and post_data['id_estado']:
            estado_id = int(post_data['id_estado'])
            nuevo_empleado_el.id_estado_id = estado_id
        
        # Puesto  
        if 'id_puesto' in post_data and post_data['id_puesto']:
            puesto_id = int(post_data['id_puesto'])
            nuevo_empleado_el.id_puesto_id = puesto_id
            
        # Convenio
        if 'id_convenio' in post_data and post_data['id_convenio']:
            convenio_id = int(post_data['id_convenio'])
            nuevo_empleado_el.id_convenio_id = convenio_id
            
        # Fecha Estado
        if 'fecha_est' in post_data and post_data['fecha_est']:
            from datetime import datetime
            try:
                fecha_est = datetime.strptime(post_data['fecha_est'], '%Y-%m-%d').date()
                nuevo_empleado_el.fecha_est = fecha_est
            except ValueError:
                # Si el formato no es correcto, mantener el valor anterior
                if registro_anterior and hasattr(registro_anterior, 'fecha_est'):
                    nuevo_empleado_el.fecha_est = registro_anterior.fecha_est
                    
        # Fecha Alta Anterior
        if 'alta_ant' in post_data and post_data['alta_ant']:
            try:
                alta_ant = datetime.strptime(post_data['alta_ant'], '%Y-%m-%d').date()
                nuevo_empleado_el.alta_ant = alta_ant
            except ValueError:
                if registro_anterior and hasattr(registro_anterior, 'alta_ant'):
                    nuevo_empleado_el.alta_ant = registro_anterior.alta_ant
                    
        # Sueldo Básico
        if 'sueldo_basico' in post_data and post_data['sueldo_basico']:
            try:
                sueldo = float(post_data['sueldo_basico'])
                nuevo_empleado_el.sueldo_basico = sueldo
            except ValueError:
                if registro_anterior and hasattr(registro_anterior, 'sueldo_basico'):
                    nuevo_empleado_el.sueldo_basico = registro_anterior.sueldo_basico
                    
    except Exception as e:
        logger.exception(f"Error procesando campos en _crear_nuevo_registro_empleado_el_directo: {e}")
    
    # Guardar el nuevo registro
    nuevo_empleado_el.save()
    
    logger.info(f"Nuevo registro Empleado_el creado directamente para empleado {empleado.idempleado_id} con fecha_el {nuevo_empleado_el.fecha_el}")
    
    # Crear log de auditoría mostrando solo los cambios
    if request and registro_anterior:
        try:
            cambios_laborales = []
            
            # Mapeo de nombres de campos para mostrar en español
            field_labels = {
                'id_estado': 'Estado',
                'id_puesto': 'Puesto', 
                'id_convenio': 'Convenio',
                'fecha_est': 'Fecha Estado',
                'alta_ant': 'Fecha Alta Anterior',
                'sueldo_basico': 'Sueldo Básico'
            }
            
            # Comparar cada campo directamente
            campos_a_comparar = ['id_estado', 'id_puesto', 'id_convenio', 'fecha_est', 'alta_ant', 'sueldo_basico']
            
            for field_name in campos_a_comparar:
                old_value = getattr(registro_anterior, field_name, None)
                new_value = getattr(nuevo_empleado_el, field_name, None)
                
                # Formatear valores para comparación
                if field_name in ['id_estado', 'id_convenio', 'id_puesto']:
                    old_display = str(old_value) if old_value else ''
                    new_display = str(new_value) if new_value else ''
                elif field_name in ['fecha_est', 'alta_ant']:
                    old_display = old_value.strftime('%d/%m/%Y') if old_value else ''
                    new_display = new_value.strftime('%d/%m/%Y') if new_value else ''
                else:
                    old_display = str(old_value) if old_value is not None else ''
                    new_display = str(new_value) if new_value is not None else ''
                
                # Si hay cambio, agregarlo a la lista
                if old_display != new_display:
                    field_label = field_labels.get(field_name, field_name)
                    cambios_laborales.append(f"{field_label}: {old_display} → {new_display}")
            
            # Solo crear log si hay cambios
            if cambios_laborales:
                # Crear el mensaje de cambios en formato texto
                mensaje_cambios = "\n".join(cambios_laborales)
                
                # Crear log de auditoría con formato correcto
                _create_log_if_new(request, 'Empleado_el', nuevo_empleado_el.id, 'update', mensaje_cambios)
                logger.info(f"Log de auditoría creado para cambios directos en Empleado_el ID {nuevo_empleado_el.id}")
            
        except Exception as e:
            logger.exception(f"Error creando log de auditoría para Empleado_el directo: {e}")
    
    return nuevo_empleado_el


# Feature flag: when True, prevent deleting an Empleado if there are
# transactional records (licencias/vacaciones). Keep this as a single
# variable so the behaviour is easily reversible.
BLOCK_DELETE_IF_TRANSACTIONS = True

def _make_json_safe(obj):
    """Recursively convert common Python/Django objects into JSON-safe types.
    - dict/list/tuple are traversed
    - date/datetime -> ISO string
    - Django model instances -> their PK if present, else str(obj)
    - other non-serializable objects -> str(obj)
    """
    from datetime import datetime, date
    # quick primitives
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        result = {str(k): _make_json_safe(v) for k, v in obj.items()}
        return result
    if isinstance(obj, (list, tuple, set)):
        result = [_make_json_safe(v) for v in obj]
        return result
    # Django model instances - use string representation instead of PK for better readability
    if hasattr(obj, '_meta'):  # Django model instance
        try:
            return str(obj)
        except Exception:
            # Fallback to PK if str() fails
            pk = getattr(obj, 'pk', None) or getattr(obj, 'id', None)
            if pk is not None:
                return pk
            return f"<model:{type(obj).__name__}>"
    # fallback to converting to string
    try:
        result = str(obj)
        return result
    except Exception:
        result = f"<unserializable: {type(obj).__name__}>"
        return result

def _generar_cuil(dni, sexo):
    """Genera CUIL basado en DNI y sexo.
    Hombres: 20 + DNI + dígito verificador
    Mujeres: 27 + DNI + dígito verificador
    """
    try:
        # Limpiar DNI de caracteres no numéricos
        dni_limpio = ''.join(ch for ch in str(dni) if ch.isdigit())
        if len(dni_limpio) != 8:
            return None
            
        # Determinar prefijo según sexo
        if sexo and hasattr(sexo, 'sexo'):
            sexo_str = sexo.sexo.lower()
            if 'femenino' in sexo_str or 'mujer' in sexo_str:
                prefijo = '27'
            elif 'masculino' in sexo_str or 'hombre' in sexo_str:
                prefijo = '20'
            else:
                prefijo = '20'  # default
        else:
            prefijo = '20'  # default
            
        # Crear base del CUIL
        base = prefijo + dni_limpio
        
        # Calcular dígito verificador
        multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
        suma = 0
        for i, digito in enumerate(base):
            suma += int(digito) * multiplicadores[i]
        
        resto = suma % 11
        if resto == 0:
            verificador = 0
        else:
            verificador = 11 - resto
            
        return base + str(verificador)
        
    except Exception:
        return None

def _mask_cuil(cuil):
    """Formatea un CUIL numérico como 'PP-XX.XXX.XXX-C'. Si no es válido, devuelve el valor original como str."""
    try:
        digits = re.sub(r"\D", '', str(cuil or ''))
        if len(digits) != 11:
            return str(cuil or '')
        pref = digits[:2]
        dni = digits[2:10]
        ver = digits[10:]
        dni_mask = f"{dni[:2]}.{dni[2:5]}.{dni[5:]}"
        return f"{pref}-{dni_mask}-{ver}"
    except Exception:
        return str(cuil or '')

def _minimal_changed(old, new):
    """Return a minimal dict with only fields that changed between old and new.
    Format: {'id': <id if present>, 'changed': {field: {'old': val, 'new': val}, ...}}
    Both old and new are expected to be dict-like. Values are passed through _make_json_safe.
    """
    if not isinstance(old, dict):
        old = {} if old is None else dict(old)
    if not isinstance(new, dict):
        new = {} if new is None else dict(new)
    def _norm_key_val(k, v):
        try:
            if k in ('dni', 'cuil'):
                return re.sub(r"\D", '', str(v or ''))
        except Exception:
            pass
        return _make_json_safe(v)

    def is_empty(val):
        return val in (None, '', 0, [], {})

    changed = {}
    keys = set(list(old.keys()) + list(new.keys()))
    for k in keys:
        try:
            old_val = old.get(k)
            new_val = new.get(k)
        except Exception:
            old_val = None
            new_val = None
        # Normalizar ciertos campos
        if k in ('dni', 'cuil'):
            norm_old = _norm_key_val(k, old_val)
            norm_new = _norm_key_val(k, new_val)
            if norm_old != norm_new and not (is_empty(norm_old) and is_empty(norm_new)):
                changed[k] = {'old': _make_json_safe(old_val), 'new': _make_json_safe(new_val)}
        else:
            safe_old = _make_json_safe(old_val)
            safe_new = _make_json_safe(new_val)
            # Solo registrar si ambos no son None/vacío y son diferentes
            if safe_old != safe_new and not (is_empty(safe_old) and is_empty(safe_new)):
                changed[k] = {'old': safe_old, 'new': safe_new}
    id_val = new.get('idempleado') or new.get('id') or old.get('idempleado') or old.get('id')
    return {'id': _make_json_safe(id_val), 'changed': changed}

def _create_log_if_new(request, nombre_tabla, idregistro, accion, cambio):
    """Create a Log_auditoria unless the most recent identical entry exists.
    This reduces duplicate/noise audit rows where the payload is identical.
    Returns the created Log_auditoria or None if skipped/failed.
    """
    try:
        safe = _make_json_safe(cambio)
        dump = json.dumps(safe, default=str, sort_keys=True)
        last = Log_auditoria.objects.filter(nombre_tabla=nombre_tabla, idregistro=idregistro, accion=accion).order_by('-id').first()
        if last is not None:
            try:
                last_dump = json.dumps(_make_json_safe(last.cambio), default=str, sort_keys=True)
            except Exception:
                last_dump = None
            if last_dump == dump:
                return None
        log_entry = Log_auditoria.objects.create(
            idusuario=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
            nombre_tabla=nombre_tabla,
            idregistro=idregistro,
            accion=accion,
            cambio=safe,
        )
        return log_entry
    except Exception as e:
        logger.exception('Failed creating unique Log_auditoria')
        return None

def _is_plan_only_entry_text(text):
    if not text or not isinstance(text, str):
        return False
    s = text.lower()
    days = ('lunes','martes','miercoles','jueves','viernes','sabado','domingo')
    if any(d in s for d in days):
        return True
    if 'horario' in s or 'horario inicio' in s or 'horario fin' in s or 'horario salida' in s or 'horario entrada' in s:
        return True
    return False


def _is_laboral_change_text(text):
    """Detecta si un cambio es específicamente de datos laborales (Empleado_el)"""
    if not text or not isinstance(text, str):
        return False
    s = text.lower()
    # Palabras clave que indican cambios laborales
    laboral_keywords = ['estado:', 'puesto:', 'convenio:', 'fecha estado:', 'fecha alta anterior:', 'sueldo básico:', 'antigüedad:']
    if any(keyword in s for keyword in laboral_keywords):
        return True
    return False


def _is_mask_only_change(text):
    # Detect changes that only differ by formatting (points/hyphens) for DNI/CUIL
    if not text or not isinstance(text, str):
        return False
    low = text.lower()
    if 'dni' in low or 'cuil' in low:
        # try to extract the two sides around the arrow → or ->
        m = re.search(r':\s*([^\u2192\-]+)[\u2192\-]+\s*(.+)$', text)
        if not m:
            # try a simpler split on →
            parts = re.split(r'→|-\>', text)
            if len(parts) >= 2:
                left = parts[0]
                right = parts[-1]
            else:
                return False
        else:
            left = m.group(1)
            right = m.group(2)
        a = re.sub(r'\D', '', left or '')
        b = re.sub(r'\D', '', right or '')
        return (a != '' and a == b)
    return False

def _is_sucursal_change_text(text):
    # Detect textual entries that represent only Sucursal changes
    if not text or not isinstance(text, str):
        return False
    low = text.lower()
    return 'sucursal' in low





@login_required
def modificar_borrar_empleado(request, empleado_id=None):
    # Limpiar datos de sesión al recargar la página (GET)
    if request.method == 'GET':
        request.session.pop('post_data', None)
        request.session.pop('cambios_actualizar', None)
        request.session.pop('cambios_laboral', None)
    empleado = None
    empleado_el_obj = None
    plan = None
    sucursal_obj = None
    # Flag that indicates the UI should show the "delete blocked" modal because
    # the empleado has transactional records (licencias/vacaciones). Compute on
    # GET so the template shows the blocked modal immediately without a POST.
    deletion_blocked = False

    # Initialize laboral changes list early to avoid UnboundLocalError when this
    # function contains later assignments to the same name (Python treats it as
    # local at compile time). Keep a small trace for auditing.
    cambios_laboral = []
    # Defensive: if some older in-memory code path references this name before
    # our initialization (observed in some deployments), ensure it exists.
    try:
        _ = cambios_laboral
    except Exception:
        cambios_laboral = []
    try:
        with open('/tmp/audit_trace.log', 'a') as _f:
            _f.write('INIT: cambios_laboral initialized at function start\n')
    except Exception:
        pass

    user = None
    is_staff_val = False
    if empleado_id:
        empleado = get_object_or_404(Empleado, pk=empleado_id)
        empleado_el_obj = Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el', '-id').first()
        plan = Plan_trabajo.objects.filter(idempleado=empleado).first()
        empleado_eo_obj = Empleado_eo.objects.filter(idempleado=empleado).first()
        sucursal_obj = empleado_eo_obj.id_sucursal if empleado_eo_obj else None

        user = User.objects.filter(id=empleado.idempleado_id).first()
        is_staff_val = user.is_staff if user else False
        initial = {'email': user.email if user else ''}
        # Si no existen registros laborales o plan de trabajo, crear instancias vacías para poblar el formulario
        if not empleado_el_obj and empleado:
            empleado_el_obj = Empleado_el(idempleado=empleado)
        if not plan and empleado:
            plan = Plan_trabajo(idempleado=empleado)
        form = EmpleadoModificarForm(instance=empleado, initial=initial)
        # Asegura que la localidad actual esté en el queryset
        if empleado.id_localidad:
            form.fields['id_localidad'].queryset = Localidad.objects.filter(
                provincia_id=empleado.id_localidad.provincia_id
            ) | Localidad.objects.filter(pk=empleado.id_localidad.pk)
    else:
        form = EmpleadoModificarForm()
        empleado_el_obj = None
        plan = None

    form_laboral = EmpleadoELForm(instance=empleado_el_obj)
    cambios = []
    cambios_laboral = []
    mostrar_modal_actualizar = False
    dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']

    if request.method == 'POST':
        # Calcular cambios reales entre el estado actual y el nuevo
        if empleado:
            # CAPTURAR VALORES ORIGINALES ANTES DE CUALQUIER PROCESAMIENTO
            original_empleado_data = {}
            for field in EmpleadoModificarForm.base_fields:
                original_empleado_data[field] = getattr(empleado, field, '')
            original_laboral_data = {}
            if empleado_el_obj:
                for field in EmpleadoELForm.base_fields:
                    original_laboral_data[field] = getattr(empleado_el_obj, field, '')
            original_user_email = user.email if user else ''
            
            # Guardar valores originales antes de normalizar
            original_dni = request.POST.get('dni', '').strip()
            original_cuil = request.POST.get('cuil', '').strip()

            # Limpiar máscara antes de comparar y guardar
            post_data = request.POST.copy()
            if 'dni' in post_data:
                post_data['dni'] = re.sub(r'\D', '', post_data['dni'])
            if 'cuil' in post_data:
                post_data['cuil'] = re.sub(r'\D', '', post_data['cuil'])

            # Evitar detectar cambios en CUIL cuando solo varía la máscara
            norm_cuil_db = re.sub(r'\D', '', str(original_empleado_data.get('cuil', '') or ''))
            norm_cuil_post = re.sub(r'\D', '', str(post_data.get('cuil', '') or ''))
            norm_dni_db = re.sub(r'\D', '', str(original_empleado_data.get('dni', '') or ''))
            norm_dni_post = re.sub(r'\D', '', str(post_data.get('dni', '') or ''))
            dni_changed = norm_dni_db != norm_dni_post
            sexo_changed = str(post_data.get('id_sexo') or '') != str(getattr(empleado, 'id_sexo_id', '') or '')
            nacionalidad_changed = str(post_data.get('id_nacionalidad') or '') != str(getattr(empleado, 'id_nacionalidad_id', '') or '')
            if (
                norm_cuil_db
                and norm_cuil_post
                and norm_cuil_db != norm_cuil_post
                and not (dni_changed or sexo_changed or nacionalidad_changed)
            ):
                post_data['cuil'] = norm_cuil_db
            form_post = EmpleadoModificarForm(post_data, instance=empleado)
            if form_post.is_valid():
                # use module-level logger (avoid local assignment that breaks scope)
                # Solo mostrar cambios numéricos para DNI y CUIL
                for field in form_post.changed_data:
                    # Usar valores originales en lugar de la instancia modificada
                    old_val = original_empleado_data.get(field)
                    new_val = form_post.cleaned_data.get(field, None)
                    if field == 'dni':
                        norm_old = re.sub(r'\D', '', str(old_val or ''))
                        norm_new = re.sub(r'\D', '', str(new_val or ''))
                        if norm_old != norm_new:
                            cambio_dni = f"DNI: '{str(old_val or '')}' → '{original_dni}'"
                            cambios.append(cambio_dni)
                    elif field == 'cuil':
                        norm_old = re.sub(r'\D', '', str(old_val or ''))
                        norm_new = re.sub(r'\D', '', str(new_val or ''))
                        if norm_old != norm_new:
                            cambio_cuil = f"CUIL: '{str(old_val or '')}' → '{original_cuil}'"
                            cambios.append(cambio_cuil)
                    else:
                        if str(old_val) != str(new_val):
                            cambio_other = f"{field.capitalize()}: '{old_val}' → '{new_val}'"
                            cambios.append(cambio_other)
            
            # Detectar cambios en el plan de trabajo (días de la semana)
            if plan:
                dias_mapping = {
                    'Lunes': 'lunes', 'Martes': 'martes', 'Miercoles': 'miercoles',
                    'Jueves': 'jueves', 'Viernes': 'viernes', 'Sabado': 'sabado', 'Domingo': 'domingo'
                }
                for dia_post, dia_model in dias_mapping.items():
                    valor_actual = getattr(plan, dia_model, False)
                    valor_nuevo = request.POST.get(dia_post) == 'on'
                    if valor_actual != valor_nuevo:
                        cambio_dia = f"{dia_post}: {'Sí' if valor_actual else 'No'} → {'Sí' if valor_nuevo else 'No'}"
                        cambios.append(cambio_dia)
                
                # Detectar cambios en horario
                start_time_actual = plan.start_time.strftime('%H:%M') if plan.start_time else ''
                end_time_actual = plan.end_time.strftime('%H:%M') if plan.end_time else ''
                start_time_nuevo = request.POST.get('start_time', '')
                end_time_nuevo = request.POST.get('end_time', '')
                if start_time_actual != start_time_nuevo:
                    cambio_horario = f"Horario inicio: '{start_time_actual}' → '{start_time_nuevo}'"
                    cambios.append(cambio_horario)
                if end_time_actual != end_time_nuevo:
                    cambio_horario = f"Horario fin: '{end_time_actual}' → '{end_time_nuevo}'"
                    cambios.append(cambio_horario)
            
            # Si no hay cambios, no mostrar el modal
            if cambios:
                mostrar_modal_actualizar = True
            else:
                mostrar_modal_actualizar = False
            # Limpiar variables de sesión y cambios al inicio del POST
            request.session.pop('post_data', None)
            request.session.pop('cambios_actualizar', None)
            request.session.pop('cambios_laboral', None)
            # Botón NO del modal de borrar
            if request.POST.get('confirmar_borrado') == '1' and request.POST.get('confirmar') == 'no':
                # Limpiar cambios y estado and return to the same view.
                # Previously this returned redirect('nucleo:modificar_borrar_empleado')
                # which in some deployments raised an exception (NoReverseMatch
                # or similar) and produced a 500. Catch and log any exception
                # to a temporary file for diagnosis and fall back to a safe
                # redirect back to the request.path.
                mostrar_modal_actualizar = False
                cambios = []
                cambios_laboral = []
                try:
                    # Try the namespaced reverse with the empleado_id if present
                    if empleado_id:
                        return redirect('nucleo:modificar_borrar_empleado', empleado_id=empleado_id)
                    return redirect('nucleo:modificar_borrar_empleado')
                except Exception as _e:
                    # Write diagnostic information to a temp file for later inspection
                    try:
                        with open('/tmp/empleado_delete_error.log', 'a') as _f:
                            _f.write('=== empleado NO-REDIRECT EXCEPTION ===\n')
                            try:
                                _f.write('exception: ' + str(_e) + '\n')
                            except Exception:
                                _f.write('exception: <unserializable>\n')
                            try:
                                _f.write(traceback.format_exc() + '\n')
                            except Exception:
                                _f.write('traceback: <failed to format>\n')
                            try:
                                _f.write('POST_KEYS: ' + json.dumps(list(request.POST.keys())) + '\n')
                            except Exception:
                                _f.write('POST_KEYS: <failed to dump>\n')
                            try:
                                _f.write('REQUEST_PATH: ' + str(request.path) + '\n')
                            except Exception:
                                _f.write('REQUEST_PATH: <failed to stringify>\n')
                            _f.write('======================================\n')
                    except Exception:
                        logger.exception('Failed writing empleado_delete_error.log')
                    # Fallback: redirect back to the same URL to avoid a 500
                    try:
                        return redirect(request.path)
                    except Exception:
                        # As a last-ditch fallback, redirect to the main empleados list
                        try:
                            return redirect('nucleo:modificar_borrar_empleado')
                        except Exception:
                            # If everything fails, return a minimal HttpResponse
                            return HttpResponse(status=302)

            # Botón SI del modal de borrar
            if request.POST.get('confirmar_borrado') == '1' and request.POST.get('confirmar') == 'si':
                # Confirmación del modal de actualizar
                if request.POST.get('confirmar_actualizar') == '1' and request.POST.get('confirmar') == 'si':
                    # Si la petición es AJAX, procesar y devolver solo JSON
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        # Limpiar máscara antes de guardar
                        post_data_save = request.POST.copy()
                        if 'dni' in post_data_save:
                            post_data_save['dni'] = re.sub(r'\D', '', post_data_save['dni'])
                        if 'cuil' in post_data_save:
                            post_data_save['cuil'] = re.sub(r'\D', '', post_data_save['cuil'])

                        norm_cuil_db = re.sub(r'\D', '', str(original_empleado_data.get('cuil', '') or ''))
                        norm_cuil_post = re.sub(r'\D', '', str(post_data_save.get('cuil', '') or ''))
                        norm_dni_db = re.sub(r'\D', '', str(original_empleado_data.get('dni', '') or ''))
                        norm_dni_post = re.sub(r'\D', '', str(post_data_save.get('dni', '') or ''))
                        dni_changed = norm_dni_db != norm_dni_post
                        sexo_changed = str(post_data_save.get('id_sexo') or '') != str(getattr(empleado, 'id_sexo_id', '') or '')
                        nacionalidad_changed = str(post_data_save.get('id_nacionalidad') or '') != str(getattr(empleado, 'id_nacionalidad_id', '') or '')
                        if (
                            norm_cuil_db
                            and norm_cuil_post
                            and norm_cuil_db != norm_cuil_post
                            and not (dni_changed or sexo_changed or nacionalidad_changed)
                        ):
                            post_data_save['cuil'] = norm_cuil_db
                        form = EmpleadoModificarForm(post_data_save, instance=empleado)
                        form_laboral = EmpleadoELForm(post_data_save, instance=empleado_el_obj)
                        logger.info(f"DEBUG: Form valid: {form.is_valid()}, Form_laboral valid: {form_laboral.is_valid()}")
                        if not form.is_valid():
                            logger.error(f"DEBUG: Form errors: {form.errors}")
                        if not form_laboral.is_valid():
                            logger.error(f"DEBUG: Form_laboral errors: {form_laboral.errors}")
                        if form.is_valid() and form_laboral.is_valid():
                            logger.info(f"DEBUG: About to save forms for empleado {empleado.idempleado_id}")
                            form.save()
                            _crear_nuevo_registro_empleado_el(empleado, form_laboral, request, empleado_el_obj)
                            logger.info(f"DEBUG: Forms saved successfully for empleado {empleado.idempleado_id}")
                            # Recargar datos actualizados del empleado
                            empleado_actualizado = Empleado.objects.get(pk=empleado.pk)
                            form = EmpleadoModificarForm(instance=empleado_actualizado)
                            form_laboral = EmpleadoELForm(instance=Empleado_el.objects.filter(idempleado=empleado_actualizado).order_by('-fecha_el', '-id').first())
                            return JsonResponse({'success': True})
                        else:
                            errors = {}
                            errors.update(form.errors)
                            errors.update(form_laboral.errors)
                            logger.error(f"DEBUG: Validation failed with errors: {errors}")
                            return JsonResponse({'success': False, 'error': str(errors)})
                    try:
                        with open('/tmp/audit_trace.log', 'a') as _f:
                            _f.write('ENTER_CONFIRM_BLOCK_EARLY\n')
                    except Exception:
                        pass

                    # prefer session-stored post_data, fallback to embedded JSON or request.POST
                    post_data = request.session.pop('post_data', None)
                    cambios = request.session.pop('cambios_actualizar', [])
                    cambios_laboral = request.session.pop('cambios_laboral', []) if 'cambios_laboral' in request.session else []

                    try:
                        raw = request.POST.get('post_data_json')
                        if raw:
                            post_data = json.loads(raw)
                            logger.debug('Recovered post_data from POST payload (early handler)')
                    except Exception:
                        logger.exception('Failed to recover post_data from POST payload (early handler)')

                    if not post_data and request.POST:
                        post_data = request.POST
                        logger.debug('Using request.POST as post_data fallback (early handler)')

                    # Ensure post_data has normalized numeric fields (strip mask characters)
                    try:
                        if post_data is not None:
                            # make a mutable copy if it's a QueryDict or similar
                            try:
                                post_data = post_data.copy()
                            except Exception:
                                pass
                            if 'dni' in post_data:
                                post_data['dni'] = re.sub(r'\D', '', str(post_data.get('dni') or ''))
                            if 'cuil' in post_data:
                                post_data['cuil'] = re.sub(r'\D', '', str(post_data.get('cuil') or ''))

                            norm_cuil_db = re.sub(r'\D', '', str(original_empleado_data.get('cuil', '') or ''))
                            norm_cuil_post = re.sub(r'\D', '', str(post_data.get('cuil', '') or ''))
                            norm_dni_db = re.sub(r'\D', '', str(original_empleado_data.get('dni', '') or ''))
                            norm_dni_post = re.sub(r'\D', '', str(post_data.get('dni', '') or ''))
                            dni_changed = norm_dni_db != norm_dni_post
                            sexo_changed = str(post_data.get('id_sexo') or '') != str(getattr(empleado, 'id_sexo_id', '') or '')
                            nacionalidad_changed = str(post_data.get('id_nacionalidad') or '') != str(getattr(empleado, 'id_nacionalidad_id', '') or '')
                            if (
                                norm_cuil_db
                                and norm_cuil_post
                                and norm_cuil_db != norm_cuil_post
                                and not (dni_changed or sexo_changed or nacionalidad_changed)
                            ):
                                post_data['cuil'] = norm_cuil_db
                    except Exception:
                        logger.exception('Normalization of post_data failed')

                    try:
                        raw_c = request.POST.get('cambios_json')
                        if raw_c:
                            cambios = json.loads(raw_c)
                            # Filter out mask-only changes (DNI/CUIL formatting differences) sent by client
                            try:
                                cambios_filtrados = []
                                for c in cambios:
                                    is_mask_only = _is_mask_only_change(c)
                                    if not is_mask_only:
                                        cambios_filtrados.append(c)
                                cambios = cambios_filtrados
                            except Exception:
                                logger.exception('Filtering mask-only cambios failed')
                            logger.debug('Recovered cambios_actualizar from POST payload (early handler)')
                    except Exception:
                        logger.exception('Failed to recover cambios_json from POST payload (early handler)')

                    try:
                        raw_cl = request.POST.get('cambios_laboral_json')
                        if raw_cl:
                            cambios_laboral = json.loads(raw_cl)
                            logger.debug('Recovered cambios_laboral from POST payload (early handler)')
                    except Exception:
                        logger.exception('Failed to recover cambios_laboral_json from POST payload (early handler)')

                    try:
                        import json as _json
                        with open('/tmp/audit_trace.log', 'a') as _f:
                            _f.write('SESSION_KEYS:' + _json.dumps(list(request.session.keys())) + '\n')
                            if post_data is not None:
                                try:
                                    _f.write('POST_DATA_KEYS:' + _json.dumps(list(post_data.keys())) + '\n')
                                except Exception:
                                    _f.write('POST_DATA_KEYS:unserializable\n')
                                try:
                                    _f.write('POST_DATA:' + _json.dumps(post_data, default=str) + '\n')
                                except Exception:
                                    _f.write('POST_DATA:UNSERIALIZABLE\n')
                            else:
                                _f.write('POST_DATA:None\n')
                            _f.write('CAMBIOS:' + _json.dumps(cambios or []) + '\n')
                            _f.write('CAMBIOS_LABORAL:' + _json.dumps(cambios_laboral or []) + '\n')
                    except Exception:
                        pass

                    if post_data:
                        form = EmpleadoModificarForm(post_data, instance=empleado)
                        form_laboral = EmpleadoELForm(post_data, instance=empleado_el_obj)

                        if form.is_valid() and form_laboral.is_valid():
                            # capture snapshots BEFORE saving so we can build compact diffs
                            try:
                                old_empleado_snapshot = {
                                    'idempleado': getattr(empleado, 'idempleado_id', None),
                                    'nombres': getattr(empleado, 'nombres', ''),
                                    'apellido': getattr(empleado, 'apellido', ''),
                                    'dni': getattr(empleado, 'dni', ''),
                                    'telefono': getattr(empleado, 'telefono', ''),
                                    'cuil': getattr(empleado, 'cuil', ''),
                                    'num_hijos': getattr(empleado, 'num_hijos', None),
                                    'dr_personal': getattr(empleado, 'dr_personal', ''),
                                    'fecha_nac': empleado.fecha_nac.isoformat() if getattr(empleado, 'fecha_nac', None) else None,
                                    'id_localidad': getattr(empleado, 'id_localidad', None),
                                    # provincia derivada desde localidad
                                    'id_provincia': getattr(getattr(empleado, 'id_localidad', None), 'provincia', None) if getattr(empleado, 'id_localidad', None) else None,
                                    'id_nacionalidad': empleado.id_nacionalidad if hasattr(empleado, 'id_nacionalidad') and empleado.id_nacionalidad else None,
                                    'id_civil': empleado.id_civil if hasattr(empleado, 'id_civil') and empleado.id_civil else None,
                                    'id_sexo': empleado.id_sexo if hasattr(empleado, 'id_sexo') and empleado.id_sexo else None,
                                }
                                old_user = None
                                user = User.objects.filter(id=empleado.idempleado_id).first()
                                if user:
                                    old_user = {'id': user.id, 'username': user.username, 'email': user.email, 'is_staff': user.is_staff}
                                old_empleado_el = None
                                if empleado_el_obj:
                                    old_empleado_el = {}
                                    for f in EmpleadoELForm.base_fields:
                                        old_empleado_el[f] = getattr(empleado_el_obj, f, '')
                                old_empleado_eo = None
                                try:
                                    empleado_eo_before = Empleado_eo.objects.filter(idempleado=empleado).first()
                                    if empleado_eo_before:
                                        old_empleado_eo = {
                                            'id': getattr(empleado_eo_before, 'id', None),
                                            # Usar id_sucursal_id (campo directo) para consistencia
                                            'id_sucursal': getattr(empleado_eo_before, 'id_sucursal_id', None),
                                            'fecha_eo': empleado_eo_before.fecha_eo.strftime('%Y-%m-%d') if getattr(empleado_eo_before, 'fecha_eo', None) else None,
                                        }
                                except Exception:
                                    old_empleado_eo = None

                                old_plan = None
                                if plan:
                                    old_plan = {}
                                    for dia in dias:
                                        old_plan[dia] = getattr(plan, dia, False)
                                    old_plan['start_time'] = plan.start_time.strftime('%H:%M') if getattr(plan, 'start_time', None) else ''
                                    old_plan['end_time'] = plan.end_time.strftime('%H:%M') if getattr(plan, 'end_time', None) else ''
                            except Exception:
                                old_empleado_snapshot = None
                                old_user = None
                                old_empleado_el = None
                                old_plan = None

                            empleado_actualizado = form.save(commit=False)
                            
                            # Si cambió DNI o Sexo, regenerar CUIL
                            if ('dni' in form.changed_data) or ('id_sexo' in form.changed_data):
                                nuevo_cuil = _generar_cuil(empleado_actualizado.dni, empleado_actualizado.id_sexo)
                                if nuevo_cuil:
                                    empleado_actualizado.cuil = nuevo_cuil
                            
                            empleado_actualizado.save()
                            user = User.objects.filter(id=empleado.idempleado_id).first()
                            if user:
                                if 'email' in form.cleaned_data:
                                    user.email = form.cleaned_data['email']
                                user.first_name = form.cleaned_data.get('nombres', user.first_name)
                                user.last_name = form.cleaned_data.get('apellido', user.last_name)
                                is_staff_val = post_data.get('is_staff', 'false')
                                user.is_staff = (is_staff_val == 'true')
                                user.save()
                            logger.info(f"DEBUG: About to save form_laboral in main flow for empleado {empleado.idempleado_id}")
                            _crear_nuevo_registro_empleado_el(empleado, form_laboral, request, empleado_el_obj)
                            logger.info(f"DEBUG: form_laboral saved successfully in main flow for empleado {empleado.idempleado_id}")
                            if plan:
                                for dia in dias:
                                    setattr(plan, dia, post_data.get(dia.capitalize()) == 'on')
                                start_val = post_data.get('start_time')
                                end_val = post_data.get('end_time')
                                try:
                                    from datetime import datetime as _dt
                                    if start_val:
                                        try:
                                            plan.start_time = _dt.strptime(start_val, '%H:%M').time()
                                        except Exception:
                                            pass
                                    if end_val:
                                        try:
                                            plan.end_time = _dt.strptime(end_val, '%H:%M').time()
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                plan.save()
                            if empleado:
                                empleado_eo = Empleado_eo.objects.filter(idempleado=empleado).first()
                                nuevo_sucursal = post_data.get('id_sucursal')
                                if nuevo_sucursal:
                                    try:
                                        nuevo_sucursal_id = int(str(nuevo_sucursal))
                                    except Exception:
                                        nuevo_sucursal_id = None
                                    if empleado_eo:
                                        old_id = getattr(empleado_eo.id_sucursal, 'id', None) if getattr(empleado_eo, 'id_sucursal', None) else None
                                        if nuevo_sucursal_id and old_id != nuevo_sucursal_id:
                                            empleado_eo.id_sucursal_id = nuevo_sucursal_id
                                            empleado_eo.save()
                                            # Logging diferido: se realizará con snapshots más abajo
                                    else:
                                        # Si no existe Empleado_eo, crearlo y registrar log como update (old=None)
                                        if nuevo_sucursal_id:
                                            empleado_eo = Empleado_eo.objects.create(
                                                idempleado=empleado,
                                                id_sucursal_id=nuevo_sucursal_id,
                                            )
                                            # Logging diferido mediante snapshot más abajo

                            # --- Auditoría: crear registro de update con snapshot old/new ---
                            try:
                                # construir snapshot nuevo
                                new_empleado_snapshot = {
                                    'idempleado': getattr(empleado_actualizado, 'idempleado_id', None),
                                    'nombres': getattr(empleado_actualizado, 'nombres', ''),
                                    'apellido': getattr(empleado_actualizado, 'apellido', ''),
                                    'dni': getattr(empleado_actualizado, 'dni', ''),
                                    'telefono': getattr(empleado_actualizado, 'telefono', ''),
                                    'cuil': getattr(empleado_actualizado, 'cuil', ''),
                                    'num_hijos': getattr(empleado_actualizado, 'num_hijos', None),
                                    'dr_personal': getattr(empleado_actualizado, 'dr_personal', ''),
                                    'fecha_nac': empleado_actualizado.fecha_nac.isoformat() if getattr(empleado_actualizado, 'fecha_nac', None) else None,
                                    'id_localidad': getattr(empleado_actualizado, 'id_localidad', None),
                                    'id_provincia': getattr(getattr(empleado_actualizado, 'id_localidad', None), 'provincia', None) if getattr(empleado_actualizado, 'id_localidad', None) else None,
                                    'id_nacionalidad': getattr(empleado_actualizado, 'id_nacionalidad', None),
                                    'id_civil': getattr(empleado_actualizado, 'id_civil', None),
                                    'id_sexo': getattr(empleado_actualizado, 'id_sexo', None),
                                }
                                new_user = None
                                if user:
                                    new_user = {'id': user.id, 'username': user.username, 'email': user.email, 'is_staff': user.is_staff}
                                new_empleado_el = None
                                empleado_el_latest = Empleado_el.objects.filter(idempleado=empleado_actualizado).order_by('-fecha_el', '-id').first()
                                if empleado_el_latest:
                                    new_empleado_el = {}
                                    for f in EmpleadoELForm.base_fields:
                                        new_empleado_el[f] = getattr(empleado_el_latest, f, '')

                                cambio = {
                                    'empleado': _minimal_changed(old_empleado_snapshot or {}, new_empleado_snapshot or {}),
                                    'empleado_el': _minimal_changed(old_empleado_el or {}, new_empleado_el or {}),
                                    'fields_changed': cambios if isinstance(cambios, list) else []
                                }

                                empleado_compact = _minimal_changed(old_empleado_snapshot or {}, new_empleado_snapshot or {})
                                if empleado_compact.get('changed'):
                                    _create_log_if_new(request, 'Empleado', getattr(empleado_actualizado, 'idempleado_id', None), 'update', empleado_compact)
                                else:
                                    if cambios:
                                        meaningful = [c for c in cambios if not (_is_plan_only_entry_text(c) or _is_mask_only_change(c) or _is_sucursal_change_text(c))]
                                        if meaningful:
                                            target_username = None
                                            try:
                                                usr = User.objects.filter(id=empleado_actualizado.idempleado_id).first()
                                                if usr:
                                                    target_username = usr.username
                                            except Exception:
                                                target_username = None
                                            fallback_payload = {'fields_changed': meaningful, 'target_username': target_username}
                                            _create_log_if_new(request, 'Empleado', getattr(empleado_actualizado, 'idempleado_id', None), 'update', fallback_payload)

                                # Log de auth_user si cambió email o Gestor
                                try:
                                    if old_user or new_user:
                                        user_compact = _minimal_changed(old_user or {}, new_user or {})
                                        if user_compact.get('changed') and user:
                                            _create_log_if_new(request, 'auth_user', getattr(user, 'id', None), 'update', user_compact)
                                except Exception:
                                    logger.exception('Auth user audit log failed')

                                if empleado_el_latest:
                                    new_empleado_el_compact = {}
                                    for f in EmpleadoELForm.base_fields:
                                        value = getattr(empleado_el_latest, f, None)
                                        # For foreign key fields, get the related object instead of just the ID
                                        if value is not None and hasattr(EmpleadoELForm.base_fields[f], 'queryset'):
                                            new_empleado_el_compact[f] = value  # Keep the object for _make_json_safe to handle
                                        else:
                                            new_empleado_el_compact[f] = value
                                    empleado_el_compact = _minimal_changed(old_empleado_el or {}, new_empleado_el_compact)
                                    if empleado_el_compact.get('changed'):
                                        _create_log_if_new(request, 'Empleado_el', getattr(empleado_el_latest, 'id', None), 'update', empleado_el_compact)
                                    else:
                                        laboral_nonplan = [c for c in (cambios_laboral or []) if not _is_plan_only_entry_text(c)]
                                        if (old_empleado_el or empleado_el_latest) and laboral_nonplan:
                                            laboral_meaningful = [c for c in laboral_nonplan if not _is_mask_only_change(c)]
                                            if laboral_meaningful:
                                                target_username = None
                                                try:
                                                    usr = User.objects.filter(id=empleado_actualizado.idempleado_id).first()
                                                    if usr:
                                                        target_username = usr.username
                                                except Exception:
                                                    target_username = None
                                                fallback_el = {'fields_changed': laboral_meaningful, 'target_username': target_username}
                                                _create_log_if_new(request, 'Empleado_el', getattr(empleado_el_latest, 'id', None) if empleado_el_latest else None, 'update', fallback_el)

                                if plan:
                                    new_plan = {}
                                    for dia in dias:
                                        new_plan[dia] = getattr(plan, dia, False)
                                    ps = getattr(plan, 'start_time', None)
                                    pe = getattr(plan, 'end_time', None)
                                    new_plan['start_time'] = ps.strftime('%H:%M') if hasattr(ps, 'strftime') else (str(ps) if ps is not None else '')
                                    new_plan['end_time'] = pe.strftime('%H:%M') if hasattr(pe, 'strftime') else (str(pe) if pe is not None else '')
                                    plan_compact = _minimal_changed(old_plan or {}, new_plan or {})
                                    if plan_compact.get('changed'):
                                        _create_log_if_new(request, 'Plan_trabajo', getattr(plan, 'id', None), 'update', plan_compact)
                                # Empleado_eo logging (Sucursal) for this confirm path
                                try:
                                    empleado_eo_after = Empleado_eo.objects.filter(idempleado=empleado_actualizado).first()
                                    if empleado_eo_after or old_empleado_eo:
                                        new_empleado_eo = None
                                        if empleado_eo_after:
                                            new_empleado_eo = {
                                                'id': getattr(empleado_eo_after, 'id', None),
                                                'id_sucursal': empleado_eo_after.id_sucursal.id if getattr(empleado_eo_after, 'id_sucursal', None) else None,
                                                'fecha_eo': empleado_eo_after.fecha_eo.strftime('%Y-%m-%d') if getattr(empleado_eo_after, 'fecha_eo', None) else None,
                                            }
                                        eo_compact = _minimal_changed(old_empleado_eo or {}, new_empleado_eo or {})
                                        if eo_compact.get('changed'):
                                            _create_log_if_new(request, 'Empleado_eo', getattr(empleado_eo_after, 'id', None) if empleado_eo_after else None, 'update', eo_compact)
                                except Exception:
                                    logger.exception('Log_auditoria CREATE failed (Empleado_eo update-confirm legacy path)')
                            except Exception as e:
                                logger.exception('Log_auditoria CREATE failed (update-confirm): %s', e)

                            # DEBUG: Verificar si llegamos aquí
                            print(f"=== DEBUG: Llegamos al punto de mensaje ===")
                            print(f"Usuario: {request.user.pk}, Empleado: {empleado.idempleado_id}")
                            print(f"POST data: {dict(request.POST)}")
                            
                            # Verificar si es auto-modificación de datos laborales
                            # Detectar si hay campos laborales en el POST
                            campos_laborales = ['id_estado', 'id_puesto', 'id_convenio', 'fecha_est', 'alta_ant']
                            hay_cambios_laborales = any(campo in request.POST for campo in campos_laborales)
                            print(f"¿Hay cambios laborales?: {hay_cambios_laborales}")
                            
                            if request.user.pk == empleado.idempleado_id and hay_cambios_laborales:
                                print("=== MOSTRANDO MENSAJE DE WARNING ===")
                                messages.warning(request, "No puede modificar sus propios datos laborales")
                            else:
                                print("=== MOSTRANDO MENSAJE DE SUCCESS ===")
                                messages.success(request, f"Empleado {empleado.nombres} {empleado.apellido} actualizado correctamente")
                            # Recargar datos actualizados del empleado en lugar de limpiar todo
                            empleado_actualizado = Empleado.objects.get(pk=empleado.pk)
                            empleado_el_actualizado = Empleado_el.objects.filter(idempleado=empleado_actualizado).order_by('-fecha_el', '-id').first()
                            plan_actualizado = Plan_trabajo.objects.filter(idempleado=empleado_actualizado).first()
                            empleado_eo_actualizado = Empleado_eo.objects.filter(idempleado=empleado_actualizado).first()
                            sucursal_obj = empleado_eo_actualizado.id_sucursal if empleado_eo_actualizado else None
                            
                            # Recrear formularios con datos actualizados
                            user_actualizado = User.objects.filter(id=empleado_actualizado.idempleado_id).first()
                            initial = {'email': user_actualizado.email if user_actualizado else ''}
                            form = EmpleadoModificarForm(instance=empleado_actualizado, initial=initial)
                            if empleado_actualizado.id_localidad:
                                form.fields['id_localidad'].queryset = Localidad.objects.filter(
                                    provincia_id=empleado_actualizado.id_localidad.provincia_id
                                ) | Localidad.objects.filter(pk=empleado_actualizado.id_localidad.pk)
                            
                            form_laboral = EmpleadoELForm(instance=empleado_el_actualizado)
                            plan = plan_actualizado
                            empleado = empleado_actualizado
                            provincia_actual = empleado.id_localidad.provincia if empleado.id_localidad else None
                            
                            # Limpiar solo el estado del modal
                            mostrar_modal_actualizar = False
                            cambios = []
                            cambios_laboral = []
                            return render(request, 'nucleo/modificar_borrar_empleado.html', {
                                'form': form,
                                'form_laboral': form_laboral,
                                'plan': plan,
                                'sucursales': Sucursal.objects.all(),
                                'sucursal': sucursal_obj,
                                'empleado': empleado,
                                'is_staff_val': is_staff_val,
                                'mostrar_modal_actualizar': mostrar_modal_actualizar,
                                'cambios': cambios,
                                'provincias': provincias,
                                'provincia_actual': provincia_actual,
                            })
                        else:
                            return render(request, 'nucleo/modificar_borrar_empleado.html', {
                                'form': form,
                                'form_laboral': form_laboral,
                                'plan': plan,
                                'sucursales': Sucursal.objects.all(),
                                'sucursal': sucursal_obj,
                                'empleado': empleado,
                                'is_staff_val': is_staff_val,
                                'mostrar_modal_actualizar': False,
                                'cambios': cambios,
                                'provincias': Provincia.objects.all(),
                                'provincia_actual': provincia_actual,
                            })
                        

    form_laboral = EmpleadoELForm(instance=empleado_el_obj)
    cambios = []
    mostrar_modal_actualizar = False
    dias = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']

    if request.method == 'POST':
        logger.debug("POST recibido")
        # Botón NO del modal de borrar
        if request.POST.get('confirmar_borrado') == '1' and request.POST.get('confirmar') == 'no':
            logger.debug("Botón NO del modal de borrar")
            return redirect('nucleo:modificar_borrar_empleado')

        # Botón SI del modal de borrar
        if request.POST.get('confirmar_borrado') == '1' and request.POST.get('confirmar') == 'si':
            logger.debug("Botón SI del modal de borrar")
            from django.db import transaction
            from nucleo.models.licencias import Solicitud_licencia, Solicitud_vacaciones, Vacaciones_otorgadas
            if empleado:
                # If the feature flag is enabled, check for transactional records
                deletion_blocked = False
                if BLOCK_DELETE_IF_TRANSACTIONS:
                    try:
                        has_lic = Solicitud_licencia.objects.filter(idempleado=empleado).exists()
                    except Exception:
                        has_lic = False
                    try:
                        has_vac = Solicitud_vacaciones.objects.filter(idempleado=empleado).exists()
                    except Exception:
                        has_vac = False
                    if has_lic or has_vac:
                        deletion_blocked = True

                if deletion_blocked:
                    # Do not perform delete. Render the page with a flag that
                    # causes the template to show the blocked-delete modal.
                    provincias = Provincia.objects.all()
                    provincia_actual = empleado.id_localidad.provincia if empleado and empleado.id_localidad else None
                    return render(request, 'nucleo/modificar_borrar_empleado.html', {
                        'form': EmpleadoModificarForm(instance=empleado),
                        'form_laboral': EmpleadoELForm(instance=Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el', '-id').first()),
                        'plan': Plan_trabajo.objects.filter(idempleado=empleado).first(),
                        'sucursales': Sucursal.objects.all(),
                        'sucursal': sucursal_obj,
                        'empleado': empleado,
                        'mostrar_modal_actualizar': False,
                        'cambios': [],
                        'provincias': provincias,
                        'provincia_actual': provincia_actual,
                        'deletion_blocked': True,
                    })

                try:
                    # Tomar snapshots de dependencias antes de eliminar
                    try:
                        plan_qs = list(Plan_trabajo.objects.filter(idempleado=empleado))
                    except Exception:
                        plan_qs = []
                    try:
                        el_qs = list(Empleado_el.objects.filter(idempleado=empleado))
                    except Exception:
                        el_qs = []
                    try:
                        eo_qs = list(Empleado_eo.objects.filter(idempleado=empleado))
                    except Exception:
                        eo_qs = []

                    # Snapshot del empleado
                    nombre = f"{empleado.nombres} {empleado.apellido}"
                    snapshot = {
                        'idempleado': getattr(empleado, 'idempleado_id', None),
                        'nombres': empleado.nombres,
                        'apellido': empleado.apellido,
                        'dni': empleado.dni,
                        'telefono': empleado.telefono,
                        'cuil': empleado.cuil,
                        'id_localidad': empleado.id_localidad_id if getattr(empleado, 'id_localidad', None) else None,
                    }
                    user = User.objects.filter(id=empleado.idempleado_id).first()

                    # Eliminar dependencias (dentro de transacción)
                    with transaction.atomic():
                        try:
                            Solicitud_licencia.objects.filter(idempleado=empleado).delete()
                            Solicitud_vacaciones.objects.filter(idempleado=empleado).delete()
                            Vacaciones_otorgadas.objects.filter(idempleado=empleado).delete()
                            Plan_trabajo.objects.filter(idempleado=empleado).delete()
                            Empleado_el.objects.filter(idempleado=empleado).delete()
                            Empleado_eo.objects.filter(idempleado=empleado).delete()
                        except Exception:
                            logger.exception('Error deleting dependencies for empleado id=%s', getattr(empleado, 'idempleado_id', None))

                    # Crear logs de auditoría para cada registro eliminado (más robusto y con deduplicación)
                    try:
                        from nucleo.models import Log_auditoria

                        seen_logs = set()
                        def _create_log_unique(nombre_tabla, idregistro, accion, cambio):
                            """Create a Log_auditoria once per (tabla, idregistro, accion)."""
                            key = (str(nombre_tabla), str(idregistro), str(accion))
                            if key in seen_logs:
                                logger.debug('Duplicate audit key found for %s id=%s accion=%s — attempting to update existing log', nombre_tabla, idregistro, accion)
                                # Try to find an existing Log_auditoria in DB and add target_username if missing
                                try:
                                    existing = Log_auditoria.objects.filter(nombre_tabla=nombre_tabla, idregistro=idregistro, accion=accion).order_by('-fecha_cambio').first()
                                    if existing:
                                        try:
                                            parsed = None
                                            if isinstance(existing.cambio, str):
                                                try:
                                                    parsed = json.loads(existing.cambio)
                                                except Exception:
                                                    parsed = None
                                            else:
                                                parsed = existing.cambio

                                            updated = False
                                            if isinstance(parsed, dict):
                                                if not parsed.get('target_username') and user and getattr(user, 'username', None):
                                                    parsed = dict(parsed)
                                                    parsed['target_username'] = user.username
                                                    existing.cambio = _make_json_safe(parsed)
                                                    existing.save()
                                                    updated = True
                                            else:
                                                # convert raw cambio into structured payload including target_username
                                                if user and getattr(user, 'username', None):
                                                    new_payload = {'raw': parsed, 'target_username': user.username}
                                                    existing.cambio = _make_json_safe(new_payload)
                                                    existing.save()
                                                    updated = True

                                            if updated:
                                                logger.debug('Updated existing Log_auditoria id=%s with target_username', existing.id)
                                            return existing
                                        except Exception:
                                            logger.exception('Failed updating existing Log_auditoria for duplicate key')
                                            return None
                                    else:
                                        logger.debug('No existing Log_auditoria found for duplicate key; skipping create')
                                        return None
                                except Exception:
                                    logger.exception('Error while searching/updating existing Log_auditoria for duplicate key')
                                    return None
                            seen_logs.add(key)
                            try:
                                # If cambio is a dict and doesn't already include target_username,
                                # try to attach the username of the empleado being deleted (if available)
                                try:
                                    if isinstance(cambio, dict) and 'target_username' not in cambio:
                                        # `user` variable is in outer scope and refers to User linked to empleado
                                        if 'user' in locals() or 'user' in globals() or True:
                                            try:
                                                # prefer the user object captured earlier in the function
                                                if user and getattr(user, 'username', None):
                                                    cambio = dict(cambio)
                                                    cambio['target_username'] = user.username
                                            except Exception:
                                                pass
                                except Exception:
                                    pass

                                return Log_auditoria.objects.create(
                                    idusuario=request.user if hasattr(request, 'user') and request.user.is_authenticated else None,
                                    nombre_tabla=nombre_tabla,
                                    idregistro=idregistro,
                                    accion=accion,
                                    cambio=_make_json_safe(cambio)
                                )
                            except Exception:
                                logger.exception('Failed to create Log_auditoria for %s id=%s', nombre_tabla, idregistro)
                                return None

                        # Tomar snapshots de otras relaciones que también se borraron
                        try:
                            lic_qs = list(Solicitud_licencia.objects.filter(idempleado=empleado))
                        except Exception:
                            lic_qs = []
                        try:
                            vac_qs = list(Solicitud_vacaciones.objects.filter(idempleado=empleado))
                        except Exception:
                            vac_qs = []
                        try:
                            vac_otorgadas_qs = list(Vacaciones_otorgadas.objects.filter(idempleado=empleado))
                        except Exception:
                            vac_otorgadas_qs = []

                        # Plan_trabajo
                        for p in plan_qs:
                            try:
                                ps = getattr(p, 'start_time', None)
                                pe = getattr(p, 'end_time', None)
                                p_snap = {
                                    'id': getattr(p, 'pk', getattr(p, 'id', None)),
                                    'idempleado': getattr(p, 'idempleado_id', getattr(p, 'idempleado', None)),
                                    'dias': {d: getattr(p, d, False) for d in ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']},
                                    'start_time': ps.strftime('%H:%M') if ps is not None and hasattr(ps, 'strftime') else (str(ps) if ps is not None else None),
                                    'end_time': pe.strftime('%H:%M') if pe is not None and hasattr(pe, 'strftime') else (str(pe) if pe is not None else None),
                                    # include target username if available
                                    'target_username': getattr(user, 'username', None) if 'user' in locals() or 'user' in globals() else None,
                                }
                                _create_log_unique('Plan_trabajo', getattr(p, 'pk', getattr(p, 'id', None)), 'delete', p_snap)
                            except Exception:
                                logger.exception('Error preparing Plan_trabajo audit snapshot for id=%s', getattr(p, 'pk', getattr(p, 'id', None)))

                        # Empleado_el
                        for el in el_qs:
                            try:
                                alta = getattr(el, 'alta_ant', None)
                                fecha_est = getattr(el, 'fecha_est', None)
                                el_snap = {
                                    'id': getattr(el, 'pk', getattr(el, 'id', None)),
                                    'idempleado': getattr(el, 'idempleado_id', getattr(el, 'idempleado', None)),
                                    'id_estado': getattr(getattr(el, 'id_estado', None), 'pk', None),
                                    'id_puesto': getattr(getattr(el, 'id_puesto', None), 'pk', None),
                                    'id_convenio': getattr(getattr(el, 'id_convenio', None), 'pk', None),
                                    'alta_ant': alta.strftime('%Y-%m-%d') if alta is not None and hasattr(alta, 'strftime') else (str(alta) if alta is not None else None),
                                    'fecha_est': fecha_est.strftime('%Y-%m-%d') if fecha_est is not None and hasattr(fecha_est, 'strftime') else (str(fecha_est) if fecha_est is not None else None),
                                    'target_username': getattr(user, 'username', None) if 'user' in locals() or 'user' in globals() else None,
                                }
                                _create_log_unique('Empleado_el', getattr(el, 'pk', getattr(el, 'id', None)), 'delete', el_snap)
                            except Exception:
                                logger.exception('Error preparing Empleado_el audit snapshot for id=%s', getattr(el, 'pk', getattr(el, 'id', None)))

                        # Empleado_eo
                        for eo in eo_qs:
                            try:
                                fecha_eo = getattr(eo, 'fecha_eo', None)
                                eo_snap = {
                                    'id': getattr(eo, 'pk', getattr(eo, 'id', None)),
                                    'idempleado': getattr(eo, 'idempleado_id', getattr(eo, 'idempleado', None)),
                                    'id_sucursal': getattr(getattr(eo, 'id_sucursal', None), 'pk', None),
                                    'fecha_eo': fecha_eo.strftime('%Y-%m-%d') if fecha_eo is not None and hasattr(fecha_eo, 'strftime') else (str(fecha_eo) if fecha_eo is not None else None),
                                    'target_username': getattr(user, 'username', None) if 'user' in locals() or 'user' in globals() else None,
                                }
                                _create_log_unique('Empleado_eo', getattr(eo, 'pk', getattr(eo, 'id', None)), 'delete', eo_snap)
                            except Exception:
                                logger.exception('Error preparing Empleado_eo audit snapshot for id=%s', getattr(eo, 'pk', getattr(eo, 'id', None)))

                        # Solicitudes / Vacaciones
                        for lic in lic_qs:
                            try:
                                lic_snap = {
                                    'id': getattr(lic, 'id', None),
                                    'idempleado': getattr(lic, 'idempleado_id', getattr(lic, 'idempleado', None)),
                                    'tipo': getattr(lic, 'tipo', None) if hasattr(lic, 'tipo') else None,
                                    'target_username': getattr(user, 'username', None) if 'user' in locals() or 'user' in globals() else None,
                                }
                                _create_log_unique('Solicitud_licencia', getattr(lic, 'id', None), 'delete', lic_snap)
                            except Exception:
                                logger.exception('Error preparing Solicitud_licencia audit snapshot for id=%s', getattr(lic, 'id', None))

                        for vac in vac_qs:
                            try:
                                vac_snap = {
                                    'id': getattr(vac, 'id', None),
                                    'idempleado': getattr(vac, 'idempleado_id', getattr(vac, 'idempleado', None)),
                                }
                                # include target username when possible
                                vac_snap['target_username'] = getattr(user, 'username', None) if 'user' in locals() or 'user' in globals() else None
                                _create_log_unique('Solicitud_vacaciones', getattr(vac, 'id', None), 'delete', vac_snap)
                            except Exception:
                                logger.exception('Error preparing Solicitud_vacaciones audit snapshot for id=%s', getattr(vac, 'id', None))

                        for v in vac_otorgadas_qs:
                            try:
                                v_snap = {
                                    'id': getattr(v, 'id', None),
                                    'idempleado': getattr(v, 'idempleado_id', getattr(v, 'idempleado', None)),
                                    'dias_otorgados': getattr(v, 'dias_otorgados', None) if hasattr(v, 'dias_otorgados') else None,
                                }
                                v_snap['target_username'] = getattr(user, 'username', None) if 'user' in locals() or 'user' in globals() else None
                                _create_log_unique('Vacaciones_otorgadas', getattr(v, 'id', None), 'delete', v_snap)
                            except Exception:
                                logger.exception('Error preparing Vacaciones_otorgadas audit snapshot for id=%s', getattr(v, 'id', None))

                        # Empleado (registro principal)
                        try:
                            # ensure snapshot contains target username
                            if isinstance(snapshot, dict) and 'target_username' not in snapshot:
                                snapshot = dict(snapshot)
                                snapshot['target_username'] = getattr(user, 'username', None) if user else None
                            _create_log_unique('Empleado', getattr(empleado, 'idempleado_id', None), 'delete', snapshot)
                        except Exception:
                            logger.exception('Error creating Empleado delete audit for id=%s', getattr(empleado, 'idempleado_id', None))

                        # auth_user
                        if user:
                            try:
                                _create_log_unique('auth_user', user.id, 'delete', {'username': user.username, 'email': user.email})
                            except Exception:
                                logger.exception('Error creating auth_user delete audit for id=%s', getattr(user, 'id', None))
                    except Exception as e:
                        logger.exception('Log_auditoria CREATE failed (delete): %s', e)

                    # Finalmente eliminar empleado y user (fuera del bloque que ya borró dependencias)
                    try:
                        empleado.delete()
                    except Exception as e:
                        messages.error(request, f"Error al eliminar empleado: {e}")
                        logger.exception(f"Error al eliminar empleado: {e}")
                    if user:
                        try:
                            user.delete()
                        except Exception as e:
                            messages.error(request, f"Error al eliminar usuario: {e}")
                            logger.exception(f"Error al eliminar usuario: {e}")
                    messages.success(request, f"Empleado {nombre} eliminado")
                except Exception as e:
                    messages.error(request, f"Error al eliminar empleado: {e}")
            # Limpiar formularios y recargar la página vacía
            form = EmpleadoModificarForm()
            form_laboral = EmpleadoELForm()
            plan = None
            sucursal_obj = None
            empleado = None
            mostrar_modal_actualizar = False
            provincias = Provincia.objects.all()
            provincia_actual = None
            return render(request, 'nucleo/modificar_borrar_empleado.html', {
                'form': form,
                'form_laboral': form_laboral,
                'plan': plan,
                'sucursales': Sucursal.objects.all(),
                'sucursal': sucursal_obj,
                'empleado': empleado,
                'mostrar_modal_actualizar': mostrar_modal_actualizar,
                'cambios': [],
                'provincias': provincias,
                'provincia_actual': provincia_actual,
            })

        # --- BLOQUE DE ACTUALIZAR ---
        if request.POST.get('accion') == 'actualizar':
            logger.debug("Botón ACTUALIZAR")
            # Usar los valores originales capturados al principio del POST
            original_data = original_empleado_data.copy()
            if user:
                original_data['email'] = original_user_email

            original_laboral = original_laboral_data.copy() if empleado_el_obj else {}

            form = EmpleadoModificarForm(request.POST, instance=empleado)
            form_laboral = EmpleadoELForm(request.POST, instance=empleado_el_obj)
            cambios = []
            cambios_main = []
            cambios_laboral = []

            if form.is_valid() and form_laboral.is_valid():
                logger.debug("Form válido, revisando cambios...")
                # Track changes separately for the main empleado form and the laboral form
                for field in form.fields:
                    old = original_data.get(field, '')
                    new = form.cleaned_data[field]

                    # Special handling for DNI and CUIL to avoid formatting-only changes
                    if field in ['dni', 'cuil']:
                        # Normalize both values for comparison
                        old_norm = re.sub(r'\D', '', str(old or ''))
                        new_norm = re.sub(r'\D', '', str(new or ''))
                        if old_norm != new_norm:
                            # Left side must be true old DB value; right side from POST or computed
                            if field == 'cuil':
                                old_display = _mask_cuil(old)
                                new_display = request.POST.get('cuil', new)
                            else:  # dni
                                old_display = str(old)
                                new_display = request.POST.get('dni', new)
                            text = f"{field.upper()}: '{old_display}' → '{new_display}'"
                            cambios.append(text)
                            cambios_main.append(text)
                    elif str(old) != str(new):
                        text = f"{form.fields[field].label or field}: '{old}' → '{new}'"
                        cambios.append(text)
                        cambios_main.append(text)
                        # Si cambia la localidad, agregar también la Provincia derivada
                        if field == 'id_localidad':
                            try:
                                old_prov = getattr(old, 'provincia', None) if old else None
                                new_prov = getattr(new, 'provincia', None) if new else None
                                prov_text = f"Provincia: '{old_prov}' → '{new_prov}'"
                                cambios.append(prov_text)
                                cambios_main.append(prov_text)
                            except Exception:
                                pass
            
            # Detectar cambios laborales SIEMPRE, independientemente de la validación del formulario
            if form_laboral.is_valid():
                # Si el formulario es válido, usar cleaned_data
                for field in form_laboral.fields:
                    old = original_laboral.get(field, '')
                    new = form_laboral.cleaned_data[field]
                    logger.debug("Laboral Campo: %s | Viejo: %s | Nuevo: %s", field, old, new)
                    if str(old) != str(new):
                        text = f"{form_laboral.fields[field].label or field}: '{old}' → '{new}'"
                        cambios.append(text)
                        cambios_laboral.append(text)
            else:
                # Si el formulario no es válido, comparar directamente con POST data
                logger.debug("Form_laboral NO válido, comparando con POST data directamente")
                for field in form_laboral.fields:
                    old = original_laboral.get(field, '')
                    new_raw = request.POST.get(field, '')
                    
                    # Convertir valores para comparación
                    if field in ['id_estado', 'id_puesto', 'id_convenio'] and new_raw:
                        try:
                            # Para campos ForeignKey, convertir a objeto para comparar
                            if field == 'id_estado':
                                from nucleo.models import Estado_empleado
                                new = Estado_empleado.objects.get(pk=int(new_raw))
                            elif field == 'id_puesto':
                                from nucleo.models import Puesto
                                new = Puesto.objects.get(pk=int(new_raw))
                            elif field == 'id_convenio':
                                from nucleo.models import Convenio
                                new = Convenio.objects.get(pk=int(new_raw))
                        except:
                            new = new_raw
                    else:
                        new = new_raw
                    
                    logger.debug("Laboral Campo (POST): %s | Viejo: %s | Nuevo: %s", field, old, new)
                    if str(old) != str(new):
                        text = f"{form_laboral.fields[field].label or field}: '{old}' → '{new}'"
                        cambios.append(text)
                        cambios_laboral.append(text)

            # Detectar cambio en is_staff (Gestor) - solo si form principal es válido
            if form.is_valid():
                is_staff_post = request.POST.get('is_staff', 'false') == 'true'
                is_staff_original = user.is_staff if user else False
                if is_staff_post != is_staff_original:
                    if is_staff_post:
                        cambios.append("Ahora es Gestor")
                    else:
                        cambios.append("Dejó de ser Gestor")

            # Días y horarios (laboral changes) - SIEMPRE verificar
            for dia in dias:
                nuevo_valor = True if request.POST.get(dia.capitalize()) == 'on' else False
                if plan and getattr(plan, dia, False) != nuevo_valor:
                    text = f"{dia.capitalize()}: {'Sí' if getattr(plan, dia, False) else 'No'} → {'Sí' if nuevo_valor else 'No'}"
                    cambios.append(text)
                    cambios_laboral.append(text)
            nuevo_start = request.POST.get('start_time') or ''
            nuevo_end = request.POST.get('end_time') or ''
            if plan and plan.start_time and plan.start_time.strftime('%H:%M') != nuevo_start:
                text = f"Horario inicio: {plan.start_time.strftime('%H:%M')} → {nuevo_start}"
                cambios.append(text)
                cambios_laboral.append(text)
            if plan and plan.end_time and plan.end_time.strftime('%H:%M') != nuevo_end:
                text = f"Horario fin: {plan.end_time.strftime('%H:%M')} → {nuevo_end}"
                cambios.append(text)
                cambios_laboral.append(text)
            
            # Sucursal (laboral) - SIEMPRE verificar
            nuevo_sucursal = request.POST.get('id_sucursal')
            
            # Obtener sucursal actual más confiable - buscar directamente en Empleado_eo
            sucursal_actual_obj = None
            try:
                empleado_eo_actual = Empleado_eo.objects.filter(idempleado=empleado).first()
                if empleado_eo_actual and empleado_eo_actual.id_sucursal:
                    sucursal_actual_obj = empleado_eo_actual.id_sucursal
            except Exception:
                # Fallback al sucursal_obj original
                sucursal_actual_obj = sucursal_obj
            
            old_sucursal = sucursal_actual_obj.pk if sucursal_actual_obj else None
            if str(old_sucursal) != str(nuevo_sucursal):
                try:
                    nueva_sucursal_obj = Sucursal.objects.get(pk=nuevo_sucursal) if nuevo_sucursal else None
                    text = f"Sucursal: {sucursal_actual_obj} → {nueva_sucursal_obj}"
                    cambios.append(text)
                    cambios_laboral.append(text)
                except Sucursal.DoesNotExist:
                    text = f"Sucursal: {sucursal_actual_obj} → (sin sucursal)"
                    cambios.append(text)
                    cambios_laboral.append(text)

            # Verificar si hay errores de validación 
            if not (form.is_valid() and form_laboral.is_valid()):
                logger.debug("Form NO válido")
                logger.debug("Errores form: %s", form.errors)
                logger.debug("Errores form_laboral: %s", form_laboral.errors)

            if not cambios:
                mostrar_modal_actualizar = False
                messages.info(request, "No hay nada que actualizar.")
            else:
                mostrar_modal_actualizar = True
                # Store both main-only and laboral-only change lists so confirmation processing can
                # decide which fallback audit logs to create. 'cambios' keeps the combined display.
                # store both main and laboral lists and the combined display list
                request.session['cambios_actualizar'] = cambios_main
                request.session['cambios_laboral'] = cambios_laboral
                request.session['cambios_combined'] = cambios
                # Guardar una copia serializable de los datos POST en sesión
                try:
                    request.session['post_data'] = request.POST.dict()
                    try:
                        # ensure session is saved to backend immediately
                        request.session.save()
                    except Exception:
                        pass
                    # dump to /tmp for debugging session persistence
                    try:
                        with open('/tmp/audit_debug_post_saved.json', 'w') as f:
                            json.dump(request.session['post_data'], f, default=str)
                    except Exception:
                        pass
                except Exception:
                    # Fallback: convertir manualmente
                    request.session['post_data'] = {k: request.POST.getlist(k) if len(request.POST.getlist(k))>1 else request.POST.get(k) for k in request.POST.keys()}
                    try:
                        request.session.save()
                    except Exception:
                        pass
                    try:
                        with open('/tmp/audit_debug_post_saved.json', 'w') as f:
                            json.dump(request.session['post_data'], f, default=str)
                    except Exception:
                        pass
                return render(request, 'nucleo/modificar_borrar_empleado.html', {
                    'form': form,
                    'form_laboral': form_laboral,
                    'plan': plan,
                    'sucursales': Sucursal.objects.all(),
                    'sucursal': sucursal_obj,
                    'empleado': empleado,
                    'mostrar_modal_actualizar': True,
                    'cambios': cambios,
                    'post_data_json': json.dumps(request.session.get('post_data', {}), default=str),
                    'post_data': request.session.get('post_data', {}),
                    # list-valued fields that should be rendered as multiple hidden inputs
                    'post_data_list_keys': [k for k,v in (request.session.get('post_data', {}) or {}).items() if isinstance(v, list)],
                    'cambios_json': json.dumps(cambios, default=str),
                    'cambios_laboral_json': json.dumps(cambios_laboral, default=str),
                })

        # Confirmación del modal de actualizar
    if request.POST.get('confirmar_actualizar') == '1' and request.POST.get('confirmar') == 'si':
            post_data = request.session.pop('post_data', None)
            # fallback: if session lost, try to read serialized json payload included in the confirm form
            if not post_data:
                try:
                    raw = request.POST.get('post_data_json')
                    if raw:
                        post_data = json.loads(raw)
                    else:
                        pass
                except Exception as e:
                    pass
            # final fallback: if we still don't have post_data, use request.POST (the hidden inputs we rendered)
            if not post_data and request.POST:
                post_data = request.POST
            # popped post_data kept in memory for processing
            # retrieve both the main and laboral change lists (and combined display list)
            cambios_main = request.session.pop('cambios_actualizar', [])
            cambios_laboral = request.session.pop('cambios_laboral', [])
            cambios = request.session.pop('cambios_combined', [])
            try:
                with open('/tmp/audit_trace.log', 'a') as _f:
                    _f.write('AT_CONFIRM_POPPED_SESSION:' + json.dumps({
                        'cambios_main': cambios_main,
                        'cambios_laboral': cambios_laboral,
                        'cambios_combined': cambios
                    }, default=str) + '\n')
            except Exception:
                pass
            # If session lost these, try to recover from POST payload (embedded hidden inputs)
            if not cambios_main:
                try:
                    raw_c = request.POST.get('cambios_json')
                    if raw_c:
                        cambios_main = json.loads(raw_c)
                    else:
                        pass
                except Exception as e:
                    pass
            if not cambios_laboral:
                try:
                    raw_cl = request.POST.get('cambios_laboral_json')
                    if raw_cl:
                        cambios_laboral = json.loads(raw_cl)
                    else:
                        pass
                except Exception as e:
                    pass
            if not cambios:
                try:
                    raw_c = request.POST.get('cambios_json')
                    if raw_c:
                        cambios = json.loads(raw_c)
                    else:
                        pass
                except Exception as e:
                    pass

            # Procesar confirmación de actualización
            # Incluso si los lists de cambios se perdieron (p.ej. sesión), proceder a persistir
            try:
                with open('/tmp/audit_trace.log', 'a') as _f:
                    _f.write('CONFIRM_NO_DIFF_GUARD: main=' + str(bool(cambios_main)) + ' lab=' + str(bool(cambios_laboral)) + '\n')
            except Exception:
                pass

            # Si hay cambios, proceder a actualizar
            try:
                # prefer session-stored post_data, fallback to embedded JSON or request.POST
                post_data = request.session.pop('post_data', None)
                cambios = request.session.pop('cambios_actualizar', [])
                cambios_laboral = request.session.pop('cambios_laboral', []) if 'cambios_laboral' in request.session else []

                try:
                    raw = request.POST.get('post_data_json')
                    if raw:
                        post_data = json.loads(raw)
                        logger.debug('Recovered post_data from POST payload (confirm handler)')
                except Exception:
                    logger.exception('Failed to recover post_data from POST payload (confirm handler)')

                if not post_data and request.POST:
                    post_data = request.POST
                    logger.debug('Using request.POST as post_data fallback (confirm handler)')

                # Ensure post_data has normalized numeric fields (strip mask characters)
                try:
                    if post_data is not None:
                        # make a mutable copy if it's a QueryDict or similar
                        try:
                            post_data = post_data.copy()
                        except Exception:
                            pass
                        if 'dni' in post_data:
                            post_data['dni'] = re.sub(r'\D', '', str(post_data.get('dni') or ''))
                        if 'cuil' in post_data:
                            post_data['cuil'] = re.sub(r'\D', '', str(post_data.get('cuil') or ''))
                except Exception:
                    logger.exception('Normalization of post_data failed')

                # Preparar snapshots previos
                old_empleado_snapshot = None
                old_user = None
                old_empleado_el = None
                old_empleado_eo = None
                old_plan = None
                try:
                    if empleado:
                        old_empleado_snapshot = {
                            'idempleado': getattr(empleado, 'idempleado_id', None),
                            'nombres': getattr(empleado, 'nombres', ''),
                            'apellido': getattr(empleado, 'apellido', ''),
                            'dni': getattr(empleado, 'dni', ''),
                            'telefono': getattr(empleado, 'telefono', ''),
                            'cuil': getattr(empleado, 'cuil', ''),
                            'fecha_nac': empleado.fecha_nac.isoformat() if getattr(empleado, 'fecha_nac', None) else None,
                            'id_localidad': getattr(empleado, 'id_localidad', None),
                            'id_nacionalidad': empleado.id_nacionalidad if hasattr(empleado, 'id_nacionalidad') and empleado.id_nacionalidad else None,
                            'id_civil': empleado.id_civil if hasattr(empleado, 'id_civil') and empleado.id_civil else None,
                            'id_sexo': empleado.id_sexo if hasattr(empleado, 'id_sexo') and empleado.id_sexo else None,
                        }
                        usr = User.objects.filter(id=empleado.idempleado_id).first()
                        if usr:
                            old_user = {'id': usr.id, 'username': usr.username, 'email': usr.email, 'is_staff': usr.is_staff}
                    if empleado_el_obj:
                        old_empleado_el = {}
                        for f in EmpleadoELForm.base_fields:
                            old_empleado_el[f] = getattr(empleado_el_obj, f, '')
                    try:
                        empleado_eo_before = Empleado_eo.objects.filter(idempleado=empleado).first()
                        if empleado_eo_before:
                            old_empleado_eo = {
                                'id': getattr(empleado_eo_before, 'id', None),
                                # Usar id_sucursal_id (campo directo) para consistencia con el new_empleado_eo
                                'id_sucursal': getattr(empleado_eo_before, 'id_sucursal_id', None),
                                'fecha_eo': empleado_eo_before.fecha_eo.strftime('%Y-%m-%d') if getattr(empleado_eo_before, 'fecha_eo', None) else None,
                            }
                    except Exception:
                        old_empleado_eo = None
                    if plan:
                        old_plan = {}
                        for dia in dias:
                            old_plan[dia] = getattr(plan, dia, False)
                        old_plan['start_time'] = plan.start_time.strftime('%H:%M') if getattr(plan, 'start_time', None) else ''
                        old_plan['end_time'] = plan.end_time.strftime('%H:%M') if getattr(plan, 'end_time', None) else ''
                except Exception:
                    pass

                # Procesar cambios en el registro principal de Empleado (siempre que el form sea válido)
                try:
                    form = EmpleadoModificarForm(post_data, instance=empleado)
                    if form.is_valid():
                        # Snapshot ANTES de guardar (agregamos num_hijos y dr_personal)
                        try:
                            old_empleado_snapshot = {
                                'idempleado': getattr(empleado, 'idempleado_id', None),
                                'nombres': getattr(empleado, 'nombres', ''),
                                'apellido': getattr(empleado, 'apellido', ''),
                                'dni': getattr(empleado, 'dni', ''),
                                'telefono': getattr(empleado, 'telefono', ''),
                                'cuil': getattr(empleado, 'cuil', ''),
                                'fecha_nac': empleado.fecha_nac.isoformat() if getattr(empleado, 'fecha_nac', None) else None,
                                'id_localidad': getattr(empleado, 'id_localidad', None),  # Keep object for _make_json_safe
                                'id_nacionalidad': empleado.id_nacionalidad if hasattr(empleado, 'id_nacionalidad') and empleado.id_nacionalidad else None,
                                'id_civil': empleado.id_civil if hasattr(empleado, 'id_civil') and empleado.id_civil else None,
                                'id_sexo': empleado.id_sexo if hasattr(empleado, 'id_sexo') and empleado.id_sexo else None,
                                'num_hijos': getattr(empleado, 'num_hijos', None),
                                'dr_personal': getattr(empleado, 'dr_personal', ''),
                            }
                            user = User.objects.filter(id=empleado.idempleado_id).first()
                        except Exception:
                            old_empleado_snapshot = None
                            user = User.objects.filter(id=empleado.idempleado_id).first()

                        empleado_actualizado = form.save(commit=False)
                        # Si cambió DNI o Sexo, regenerar CUIL
                        if ('dni' in form.changed_data) or ('id_sexo' in form.changed_data):
                            nuevo_cuil = _generar_cuil(empleado_actualizado.dni, empleado_actualizado.id_sexo)
                            if nuevo_cuil:
                                empleado_actualizado.cuil = nuevo_cuil

        					# Guardar Empleado
                        empleado_actualizado.save()
                        # Actualizar usuario relacionado (email, nombre, gestor)
                        user = User.objects.filter(id=empleado.idempleado_id).first()
                        if user:
                            if 'email' in form.cleaned_data:
                                user.email = form.cleaned_data['email']
                            user.first_name = form.cleaned_data.get('nombres', user.first_name)
                            user.last_name = form.cleaned_data.get('apellido', user.last_name)
                            is_staff_val = post_data.get('is_staff', 'false')
                            user.is_staff = (is_staff_val == 'true')
                            user.save()

                        # Auditoría Empleado
                        try:
                            new_empleado_snapshot = {
                                'idempleado': getattr(empleado_actualizado, 'idempleado_id', None),
                                'nombres': getattr(empleado_actualizado, 'nombres', ''),
                                'apellido': getattr(empleado_actualizado, 'apellido', ''),
                                'dni': getattr(empleado_actualizado, 'dni', ''),
                                'telefono': getattr(empleado_actualizado, 'telefono', ''),
                                'cuil': getattr(empleado_actualizado, 'cuil', ''),
                                'fecha_nac': empleado_actualizado.fecha_nac.isoformat() if getattr(empleado_actualizado, 'fecha_nac', None) else None,
                                'id_localidad': getattr(empleado_actualizado, 'id_localidad', None),
                                'id_nacionalidad': getattr(empleado_actualizado, 'id_nacionalidad', None),
                                'id_civil': getattr(empleado_actualizado, 'id_civil', None),
                                'id_sexo': getattr(empleado_actualizado, 'id_sexo', None),
                                'num_hijos': getattr(empleado_actualizado, 'num_hijos', None),
                                'dr_personal': getattr(empleado_actualizado, 'dr_personal', ''),
                            }

                            empleado_compact = _minimal_changed(old_empleado_snapshot or {}, new_empleado_snapshot or {})
                            if empleado_compact.get('changed'):
                                _create_log_if_new(request, 'Empleado', getattr(empleado_actualizado, 'idempleado_id', None), 'update', empleado_compact)
                            else:
                                # Fallback: usar lista de cambios detectada en la pantalla si existe
                                if cambios_main:
                                    meaningful = [c for c in cambios_main if not (
                                        _is_plan_only_entry_text(c) or 
                                        _is_mask_only_change(c) or 
                                        _is_sucursal_change_text(c) or
                                        _is_laboral_change_text(c)  # Excluir cambios laborales
                                    )]
                                    if meaningful:
                                        target_username = None
                                        try:
                                            usr = User.objects.filter(id=empleado_actualizado.idempleado_id).first()
                                            if usr:
                                                target_username = usr.username
                                        except Exception:
                                            target_username = None
                                        fallback_payload = {'fields_changed': meaningful, 'target_username': target_username}
                                        _create_log_if_new(request, 'Empleado', getattr(empleado_actualizado, 'idempleado_id', None), 'update', fallback_payload)
                        except Exception:
                            logger.exception('Log_auditoria CREATE failed (empleado confirm)')
                except Exception as e:
                    logger.exception('Error updating Empleado on confirm: %s', e)

                # Procesar SIEMPRE cambios laborales (Empleado_el, Plan_trabajo, Sucursal)
                from django.db import transaction
                try:
                    with transaction.atomic():
                        # Usar cambios_combined para determinar si hay cambios que procesar
                        # cambios_combined contiene todos los cambios detectados (main + laboral)
                        hay_cambios_para_procesar = bool(cambios) or bool(cambios_main) or bool(cambios_laboral)
                        
                        logger.info(f"DEBUG: hay_cambios_para_procesar={hay_cambios_para_procesar}, cambios={len(cambios)}, cambios_main={len(cambios_main)}, cambios_laboral={len(cambios_laboral)}")
                        
                        if hay_cambios_para_procesar:  # Si hay cambios detectados en la primera pasada
                            # Guardar Empleado_el usando los datos que ya fueron validados
                            form_laboral = EmpleadoELForm(post_data, instance=empleado_el_obj)
                            logger.info(f"DEBUG: In transaction block, form_laboral.is_valid(): {form_laboral.is_valid()}")
                            if not form_laboral.is_valid():
                                logger.error(f"DEBUG: form_laboral errors in transaction: {form_laboral.errors}")
                                # Intentar crear el registro aunque el formulario no sea válido
                                # usando directamente los datos de post_data
                                try:
                                    logger.info(f"DEBUG: Attempting to save despite validation errors for empleado {empleado.idempleado_id}")
                                    _crear_nuevo_registro_empleado_el_directo(empleado, post_data, request, empleado_el_obj)
                                    logger.info(f"DEBUG: Direct save successful for empleado {empleado.idempleado_id}")
                                except Exception as e:
                                    logger.exception(f"DEBUG: Direct save failed: {e}")
                            else:
                                logger.info(f"DEBUG: About to save form_laboral in transaction for empleado {empleado.idempleado_id}")
                                _crear_nuevo_registro_empleado_el(empleado, form_laboral, request, empleado_el_obj)
                                logger.info(f"DEBUG: form_laboral saved successfully in transaction for empleado {empleado.idempleado_id}")
                        else:
                            logger.info(f"DEBUG: No laboral changes detected, skipping Empleado_el save for empleado {empleado.idempleado_id}")

                        # Actualizar Plan_trabajo (días y horarios)
                        if plan:
                            try:
                                for dia in dias:
                                    setattr(plan, dia, post_data.get(dia.capitalize()) == 'on')
                                start_val = post_data.get('start_time')
                                end_val = post_data.get('end_time')
                                from datetime import datetime as _dt
                                plan.start_time = _dt.strptime(start_val, '%H:%M').time() if (start_val or '').strip() else None
                                plan.end_time = _dt.strptime(end_val, '%H:%M').time() if (end_val or '').strip() else None
                                plan.save()
                            except Exception:
                                logger.exception('Error updating Plan_trabajo in confirm handler')

                        # Actualizar Sucursal (Empleado_eo)
                        try:
                            if empleado:
                                empleado_eo = Empleado_eo.objects.filter(idempleado=empleado).first()
                                nuevo_sucursal = post_data.get('id_sucursal')
                                if nuevo_sucursal:
                                    try:
                                        nuevo_sucursal_id = int(str(nuevo_sucursal))
                                    except Exception:
                                        nuevo_sucursal_id = None
                                    if empleado_eo:
                                        old_id = getattr(empleado_eo.id_sucursal, 'id', None) if getattr(empleado_eo, 'id_sucursal', None) else None
                                        if nuevo_sucursal_id and old_id != nuevo_sucursal_id:
                                            empleado_eo.id_sucursal_id = nuevo_sucursal_id
                                            empleado_eo.save()
                                            # Logging diferido mediante snapshot más abajo
                                    else:
                                        if nuevo_sucursal_id:
                                            empleado_eo = Empleado_eo.objects.create(
                                                idempleado=empleado,
                                                id_sucursal_id=nuevo_sucursal_id,
                                            )
                                            # Logging diferido mediante snapshot más abajo
                        except Exception:
                            logger.exception('Error updating Empleado_eo (Sucursal) in confirm handler')

                        # Traza aplicada
                        try:
                            with open('/tmp/audit_trace.log', 'a') as _f:
                                _f.write('APPLIED_LABORAL_UPDATE: ' + json.dumps({
                                    'empleado_id': getattr(empleado, 'idempleado_id', None),
                                    'sucursal_id': post_data.get('id_sucursal'),
                                    'dias': {d: bool(post_data.get(d.capitalize()) == 'on') for d in dias},
                                    'start_time': post_data.get('start_time'),
                                    'end_time': post_data.get('end_time')
                                }, default=str) + '\n')
                        except Exception:
                            pass
                except Exception:
                    logger.exception('Error processing laboral updates in confirm handler')

                # Logging laboral/plan
                try:
                    # Empleado_el logging
                    empleado_el_latest = Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el', '-id').first()
                    if empleado_el_latest:
                        new_empleado_el_compact = {}
                        for f in EmpleadoELForm.base_fields:
                            value = getattr(empleado_el_latest, f, None)
                            new_empleado_el_compact[f] = value
                        empleado_el_compact = _minimal_changed(old_empleado_el or {}, new_empleado_el_compact)
                        if empleado_el_compact.get('changed'):
                            _create_log_if_new(request, 'Empleado_el', getattr(empleado_el_latest, 'id', None), 'update', empleado_el_compact)

                    # Empleado_eo (Sucursal) logging
                    try:
                        empleado_eo_after = Empleado_eo.objects.filter(idempleado=empleado).first()
                        new_empleado_eo = None
                        if empleado_eo_after:
                            new_empleado_eo = {
                                'id': getattr(empleado_eo_after, 'id', None),
                                # En este modelo, la PK de Sucursal es 'id_sucursal'; usar el campo relacional _id
                                'id_sucursal': getattr(empleado_eo_after, 'id_sucursal_id', None),
                                'fecha_eo': empleado_eo_after.fecha_eo.strftime('%Y-%m-%d') if getattr(empleado_eo_after, 'fecha_eo', None) else None,
                            }
                        if old_empleado_eo or new_empleado_eo:
                            eo_compact = _minimal_changed(old_empleado_eo or {}, new_empleado_eo or {})
                            if eo_compact.get('changed'):
                                _create_log_if_new(
                                    request,
                                    'Empleado_eo',
                                    getattr(empleado_eo_after, 'id', None) if empleado_eo_after else None,
                                    'update',
                                    eo_compact,
                                )
                    except Exception:
                        logger.exception('Log_auditoria CREATE failed (Empleado_eo update-confirm)')

                    # Plan_trabajo logging
                    if plan:
                        new_plan = {}
                        for dia in dias:
                            new_plan[dia] = getattr(plan, dia, False)
                        ps = getattr(plan, 'start_time', None)
                        pe = getattr(plan, 'end_time', None)
                        new_plan['start_time'] = ps.strftime('%H:%M') if hasattr(ps, 'strftime') else (str(ps) if ps is not None else '')
                        new_plan['end_time'] = pe.strftime('%H:%M') if hasattr(pe, 'strftime') else (str(pe) if pe is not None else '')
                        plan_compact = _minimal_changed(old_plan or {}, new_plan or {})
                        if plan_compact.get('changed'):
                            _create_log_if_new(request, 'Plan_trabajo', getattr(plan, 'id', None), 'update', plan_compact)
                except Exception:
                    logger.exception('Log_auditoria CREATE failed (laboral/plan confirm)')
            except Exception as e:
                print(f"Error en bloque try (1201): {e}")

            # Tras aplicar cambios, recargar y renderizar con datos actualizados
            try:
                empleado_actualizado = Empleado.objects.get(pk=empleado.pk) if empleado else None
                empleado_el_actualizado = Empleado_el.objects.filter(idempleado=empleado_actualizado).order_by('-fecha_el', '-id').first() if empleado_actualizado else None
                plan_actualizado = Plan_trabajo.objects.filter(idempleado=empleado_actualizado).first() if empleado_actualizado else None
                empleado_eo_actualizado = Empleado_eo.objects.filter(idempleado=empleado_actualizado).first() if empleado_actualizado else None
                sucursal_actualizada = empleado_eo_actualizado.id_sucursal if empleado_eo_actualizado else None

                user_actualizado = User.objects.filter(id=empleado_actualizado.idempleado_id).first() if empleado_actualizado else None
                initial = {'email': user_actualizado.email if user_actualizado else ''}
                form = EmpleadoModificarForm(instance=empleado_actualizado, initial=initial) if empleado_actualizado else EmpleadoModificarForm()
                if empleado_actualizado and empleado_actualizado.id_localidad:
                    form.fields['id_localidad'].queryset = Localidad.objects.filter(
                        provincia_id=empleado_actualizado.id_localidad.provincia_id
                    ) | Localidad.objects.filter(pk=empleado_actualizado.id_localidad.pk)
                form_laboral = EmpleadoELForm(instance=empleado_el_actualizado)
                provincia_actual = empleado_actualizado.id_localidad.provincia if (empleado_actualizado and empleado_actualizado.id_localidad) else None
                return render(request, 'nucleo/modificar_borrar_empleado.html', {
                    'form': form,
                    'form_laboral': form_laboral,
                    'plan': plan_actualizado,
                    'sucursales': Sucursal.objects.all(),
                    'sucursal': sucursal_actualizada,
                    'empleado': empleado_actualizado,
                    'is_staff_val': (user_actualizado.is_staff if user_actualizado else False),
                    'mostrar_modal_actualizar': False,
                    'cambios': [],
                    'provincias': Provincia.objects.all(),
                    'provincia_actual': provincia_actual,
                })
            except Exception:
                pass

    # Return final render for GET requests or when no specific action is taken
    provincia_actual = None
    if empleado and empleado.id_localidad:
        provincia_actual = empleado.id_localidad.provincia
    return render(request, 'nucleo/modificar_borrar_empleado.html', {
        'form': form,
        'form_laboral': form_laboral,
        'plan': plan,
        'sucursales': Sucursal.objects.all(),
        'sucursal': sucursal_obj,
        'empleado': empleado,
    'is_staff_val': is_staff_val,
        'mostrar_modal_actualizar': mostrar_modal_actualizar,
        'cambios': cambios,
        'provincias': Provincia.objects.all(),
        'provincia_actual': provincia_actual,
        'deletion_blocked': deletion_blocked,
    })


@login_required
def ver_empleados(request):
    q = request.GET.get('q', '')
    vista_ampliada = request.GET.get('vista_ampliada') == '1'
    solo_estado_actual = request.GET.get('solo_estado_actual') == '1'
    empleados_qs = Empleado.objects.exclude(idempleado_id=1)
    if q:
        empleados_qs = empleados_qs.filter(nombres__icontains=q) | empleados_qs.filter(apellido__icontains=q)
    empleados = []
    
    for emp in empleados_qs:
        # Datos básicos del empleado que no cambian
        base_data = {
            'idempleado_id': emp.idempleado.id,
            'nombres': emp.nombres,
            'apellido': emp.apellido,
            'dni': emp.dni,
            'fecha_nac': emp.fecha_nac,
            'id_nacionalidad': emp.id_nacionalidad.id if emp.id_nacionalidad else '',
            'nacionalidad_nombre': emp.id_nacionalidad.nacionalidad if emp.id_nacionalidad else '',
            'id_civil': emp.id_civil.id if emp.id_civil else '',
            'civil_nombre': emp.id_civil.estado_civil if emp.id_civil else '',
            'id_sexo': emp.id_sexo.id if emp.id_sexo else '',
            'sexo_nombre': emp.id_sexo.sexo if emp.id_sexo else '',
            'id_localidad': emp.id_localidad.id if emp.id_localidad else '',
            'localidad_nombre': emp.id_localidad.localidad if emp.id_localidad else '',
            'dr_personal': emp.dr_personal,
            'email': emp.idempleado.email if getattr(emp, 'idempleado', None) else '',
        }
        
        # Obtener registro laboral actual de la base de datos
        el_actual = Empleado_el.objects.filter(idempleado=emp).order_by('-fecha_el', '-id').first()
        
        if solo_estado_actual:
            # Solo mostrar el registro actual
            if el_actual:
                data = base_data.copy()
                data.update({
                    'estado': el_actual.id_estado.estado if el_actual.id_estado else '',
                    'fecha_estado': el_actual.fecha_est if el_actual.fecha_est else el_actual.fecha_el,
                    'puesto': el_actual.id_puesto.tipo_puesto if el_actual.id_puesto else '',
                    'id_puesto': el_actual.id_puesto.id_puesto if el_actual.id_puesto else '',
                    'is_historical': False,
                    'fecha_el': el_actual.fecha_el,
                })
                
                if vista_ampliada:
                    eo = Empleado_eo.objects.filter(idempleado=emp).order_by('-fecha_eo').first()
                    plan = Plan_trabajo.objects.filter(idempleado=emp).first()
                    suc = eo.id_sucursal if eo else None
                    pers_jur = suc.id_pers_juridica if suc else None
                    data.update({
                        'num_hijos': emp.num_hijos,
                        'telefono': emp.telefono,
                        'cuil': emp.cuil,
                        'convenio': el_actual.id_convenio.tipo_convenio if el_actual.id_convenio else '',
                        'puesto': el_actual.id_puesto.tipo_puesto if el_actual.id_puesto else '',
                        'fecha_antiguedad': el_actual.alta_ant if el_actual.alta_ant else '',
                        'sucursal': suc.sucursal if suc else '',
                        'suc_dire': suc.suc_dire if suc else '',
                        'pers_juridica': pers_jur.pers_juridica if pers_jur else '',
                        'domicilio_pers_juridica': pers_jur.domicilio if pers_jur else '',
                        'cond_iva': pers_jur.cond_iva if pers_jur else '',
                        'cuit': pers_jur.cuit if pers_jur else '',
                        'cond_iibb': pers_jur.cond_iibb if pers_jur else '',
                    })
                
                empleados.append(data)
            else:
                # Si no hay registro laboral, crear una fila básica
                empleados.append(base_data.copy())
        else:
            # Mostrar historial completo (actual + histórico)
            registros_mostrados = []
            
            # 1. Agregar registro actual de la BD
            if el_actual:
                data = base_data.copy()
                data.update({
                    'estado': el_actual.id_estado.estado if el_actual.id_estado else '',
                    'fecha_estado': el_actual.fecha_est if el_actual.fecha_est else el_actual.fecha_el,
                    'puesto': el_actual.id_puesto.tipo_puesto if el_actual.id_puesto else '',
                    'id_puesto': el_actual.id_puesto.id_puesto if el_actual.id_puesto else '',
                    'is_historical': False,
                    'fecha_el': el_actual.fecha_el,
                })
                
                if vista_ampliada:
                    eo = Empleado_eo.objects.filter(idempleado=emp).order_by('-fecha_eo').first()
                    plan = Plan_trabajo.objects.filter(idempleado=emp).first()
                    suc = eo.id_sucursal if eo else None
                    pers_jur = suc.id_pers_juridica if suc else None
                    data.update({
                        'num_hijos': emp.num_hijos,
                        'telefono': emp.telefono,
                        'cuil': emp.cuil,
                        'convenio': el_actual.id_convenio.tipo_convenio if el_actual.id_convenio else '',
                        'puesto': el_actual.id_puesto.tipo_puesto if el_actual.id_puesto else '',
                        'fecha_antiguedad': el_actual.alta_ant if el_actual.alta_ant else '',
                        'sucursal': suc.sucursal if suc else '',
                        'suc_dire': suc.suc_dire if suc else '',
                        'pers_juridica': pers_jur.pers_juridica if pers_jur else '',
                        'domicilio_pers_juridica': pers_jur.domicilio if pers_jur else '',
                        'cond_iva': pers_jur.cond_iva if pers_jur else '',
                        'cuit': pers_jur.cuit if pers_jur else '',
                        'cond_iibb': pers_jur.cond_iibb if pers_jur else '',
                    })
                
                registros_mostrados.append(data)
            
            
            # 2. Agregar registros históricos de la base de datos
            registros_historicos = Empleado_el.objects.filter(idempleado=emp).order_by('-fecha_el', '-id')
            for el_historico in registros_historicos[1:]:  # Omitir el primero (ya agregado como actual)
                data_hist = base_data.copy()
                data_hist.update({
                    'estado': el_historico.id_estado.estado if el_historico.id_estado else '',
                    'fecha_estado': el_historico.fecha_est,
                    'puesto': el_historico.id_puesto.tipo_puesto if el_historico.id_puesto else '',
                    'is_historical': True,
                    'fecha_el': el_historico.fecha_el,
                    'id_estado': el_historico.id_estado_id if el_historico.id_estado else '',
                    'id_puesto': el_historico.id_puesto_id if el_historico.id_puesto else '',
                })
                
                if vista_ampliada:
                    # Para registros históricos, usar datos de empleado actual para campos no laborales
                    eo = Empleado_eo.objects.filter(idempleado=emp).order_by('-fecha_eo').first()
                    suc = eo.id_sucursal if eo else None
                    pers_jur = suc.id_pers_juridica if suc else None
                    data_hist.update({
                        'num_hijos': emp.num_hijos,
                        'telefono': emp.telefono,
                        'cuil': emp.cuil,
                        'convenio': el_historico.id_convenio.tipo_convenio if el_historico.id_convenio else '',
                        'puesto': el_historico.id_puesto.tipo_puesto if el_historico.id_puesto else '',
                        'fecha_antiguedad': el_historico.alta_ant or el_historico.fecha_el,
                        'sucursal': suc.sucursal if suc else '',
                        'suc_dire': suc.suc_dire if suc else '',
                        'pers_juridica': pers_jur.pers_juridica if pers_jur else '',
                        'domicilio_pers_juridica': pers_jur.domicilio if pers_jur else '',
                        'cond_iva': pers_jur.cond_iva if pers_jur else '',
                        'cuit': pers_jur.cuit if pers_jur else '',
                        'cond_iibb': pers_jur.cond_iibb if pers_jur else '',
                    })
                
                registros_mostrados.append(data_hist)
            
            
            # Si no hay registros, crear uno básico
            if not registros_mostrados:
                registros_mostrados.append(base_data.copy())
            
            empleados.extend(registros_mostrados)

    return render(request, "nucleo/ver_empleados.html", {
        "empleados": empleados,
        "vista_ampliada": vista_ampliada,
        "solo_estado_actual": solo_estado_actual,
        "nacionalidades": list(Nacionalidad.objects.values('id', 'nacionalidad')),
        "estados_civil": list(EstadoCivil.objects.values('id', 'estado_civil')),
        "sexos": list(Sexo.objects.values('id', 'sexo')),
        "localidades": list(Localidad.objects.values('id', 'localidad', 'provincia_id')),
        "provincias": list(Provincia.objects.values('id', 'provincia')),
        "estados_empleado": list(Estado_empleado.objects.values('id_estado', 'estado')),
        "years_fecha_estado": sorted(
            {
                *[d.year for d in Empleado_el.objects.filter(fecha_el__isnull=False).dates('fecha_el', 'year', order='DESC')],
                *[d.year for d in Empleado_el.objects.filter(fecha_est__isnull=False).dates('fecha_est', 'year', order='DESC')],
            },
            reverse=True
        ),
    })


@login_required
def emitir_certificado(request, empleado_id):
    empleado = get_object_or_404(Empleado, pk=empleado_id)
    empleado_eo = Empleado_eo.objects.filter(idempleado=empleado).order_by('-fecha_eo').first()
    sucursal = empleado_eo.id_sucursal.sucursal if empleado_eo and getattr(empleado_eo, 'id_sucursal', None) else "Sin sucursal"
    # Resolve puesto: prefer empleado_eo.id_puesto.tipo_puesto, fallback to empleado_el.id_puesto.tipo_puesto, else default
    puesto = "Responsable de farmacia"
    try:
        if empleado_eo and getattr(empleado_eo, 'id_puesto', None):
            puesto = getattr(empleado_eo.id_puesto, 'tipo_puesto', puesto) or puesto
    except Exception:
        pass
    try:
        empleado_el = Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el', '-id').first()
        if (not puesto or puesto == "Responsable de farmacia") and empleado_el and getattr(empleado_el, 'id_puesto', None):
            puesto = getattr(empleado_el.id_puesto, 'tipo_puesto', puesto) or puesto
    except Exception:
        pass
    
    # Obtener el registro laboral (Empleado_el) más reciente para este empleado
    empleado_el = Empleado_el.objects.filter(idempleado=empleado).order_by('-fecha_el', '-id').first()
    fecha_ingreso = empleado_el.fecha_est if empleado_el and empleado_el.fecha_est else None

    fecha_emision = date.today()

    # Formato de fecha en español
    meses = [
        '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
    ]
    fecha_emision_larga = f"{fecha_emision.day} de {meses[fecha_emision.month]} del año {fecha_emision.year}"
    # Extraer el convenio legible desde el registro laboral más reciente (Empleado_el)
    try:
        convenio_val = ''
        if empleado_el and getattr(empleado_el, 'id_convenio', None):
            # id_convenio es una FK a Convenio; preferir el campo tipo_convenio
            convenio_val = getattr(empleado_el.id_convenio, 'tipo_convenio', '') or str(empleado_el.id_convenio)
    except Exception:
        convenio_val = ''

    return render(request, "nucleo/emitir_certificado.html", {
        "empleado": empleado,
        "empresa": f"Farmacia Gómez de Galarze, {sucursal}",
        "puesto": puesto,
        "fecha_ingreso": fecha_ingreso,
        "fecha_emision": fecha_emision,
        "fecha_emision_larga": fecha_emision_larga,
        "fecha_ant": fecha_ingreso.strftime('%d/%m/%Y') if fecha_ingreso else "No disponible",
        "convenio": convenio_val,
    })


@login_required
def buscar_empleados_ajax(request):
    q = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', '').strip()
    vista_ampliada = request.GET.get('vista_ampliada') == '1'
    solo_estado_actual = request.GET.get('solo_estado_actual') == '1'
    empleados = Empleado.objects.exclude(idempleado_id=1)

    # Generic filter params (driven by the front-end controls)
    edad_desde = request.GET.get('edad_desde')
    edad_hasta = request.GET.get('edad_hasta')
    nacionalidad_id = request.GET.get('nacionalidad_id')
    estado_civil_id = request.GET.get('estado_civil_id')
    sexo_id = request.GET.get('sexo_id')
    provincia_id = request.GET.get('provincia_id')
    localidad_id = request.GET.get('localidad_id')
    estado_emp_id = request.GET.get('estado_emp_id')
    estado_filter_id = None
    year_filter_raw = request.GET.get('year_fecha_estado')
    month_filter_raw = request.GET.get('mes_fecha_estado')
    year_filter_int = None
    month_filter_int = None
    fecha_estado_filter = None

    try:
        year_filter_int = int(year_filter_raw) if year_filter_raw else None
    except (TypeError, ValueError):
        year_filter_int = None
    try:
        month_filter_int = int(month_filter_raw) if month_filter_raw else None
    except (TypeError, ValueError):
        month_filter_int = None

    # Age filtering: convert ages into fecha_nac range
    try:
        today = date.today()
        if edad_desde:
            y = int(edad_desde)
            cutoff = date(today.year - y, today.month, today.day)
            empleados = empleados.filter(fecha_nac__lte=cutoff)
        if edad_hasta:
            y = int(edad_hasta)
            cutoff = date(today.year - y, today.month, today.day)
            empleados = empleados.filter(fecha_nac__gte=cutoff)
    except Exception:
        # ignore malformed age values
        pass

    if nacionalidad_id:
        try:
            empleados = empleados.filter(id_nacionalidad__id=int(nacionalidad_id))
        except Exception:
            pass
    if estado_civil_id:
        try:
            empleados = empleados.filter(id_civil__id=int(estado_civil_id))
        except Exception:
            pass
    if sexo_id:
        try:
            empleados = empleados.filter(id_sexo__id=int(sexo_id))
        except Exception:
            pass
    if provincia_id:
        try:
            empleados = empleados.filter(id_localidad__provincia__id=int(provincia_id))
        except Exception:
            pass
    if localidad_id:
        try:
            empleados = empleados.filter(id_localidad__id=int(localidad_id))
        except Exception:
            pass

    # Filter by empleado_el.estado (current laboral estado) if requested
    if estado_emp_id:
        try:
            estado_filter_id = int(estado_emp_id)
            empleados = empleados.filter(
                empleado_el__in=Empleado_el.objects.filter(id_estado_id=estado_filter_id)
            ).distinct()
        except Exception:
            estado_filter_id = None

    if filtro == 'year_fecha_estado' and (year_filter_int is not None or month_filter_int is not None):
        q_est = Q()
        q_el = Q()
        if year_filter_int is not None:
            q_est &= Q(fecha_est__year=year_filter_int)
            q_el &= Q(fecha_el__year=year_filter_int)
        if month_filter_int is not None:
            q_est &= Q(fecha_est__month=month_filter_int)
            q_el &= Q(fecha_el__month=month_filter_int)

        fecha_q = Q()
        if q_est.children:
            fecha_q |= q_est
        if q_el.children:
            fecha_q |= q_el

        if fecha_q.children:
            matching_registros = Empleado_el.objects.filter(fecha_q)
            empleados = empleados.filter(empleado_el__in=matching_registros).distinct()
            fecha_estado_filter = {
                'year': year_filter_int,
                'month': month_filter_int,
            }

    # Generic text/id search (still applied whether filtro used or not)
    if q:
        if q.isdigit():
            empleados = empleados.filter(
                Q(pk=int(q)) |
                Q(nombres__icontains=q) |
                Q(apellido__icontains=q)
            )
        else:
            empleados = empleados.filter(
                Q(nombres__icontains=q) |
                Q(apellido__icontains=q)
            )
    
    force_actual_only = solo_estado_actual

    resultados = []
    for emp in empleados[:15]:  # Limitamos a 15 empleados base para evitar demasiados resultados
        # Datos básicos del empleado que no cambian
        empleado_usuario = getattr(emp, 'idempleado', None)
        base_data = {
            'id': emp.pk,
            'idempleado_id': empleado_usuario.id if empleado_usuario else '',
            'nombres': emp.nombres,
            'apellido': emp.apellido,
            'dni': emp.dni,
            'fecha_nac': emp.fecha_nac.strftime('%Y-%m-%d') if emp.fecha_nac else '',
            'id_nacionalidad': emp.id_nacionalidad.id if emp.id_nacionalidad else '',
            'nacionalidad_nombre': emp.id_nacionalidad.nacionalidad if emp.id_nacionalidad else '',
            'id_civil': emp.id_civil.id if emp.id_civil else '',
            'civil_nombre': emp.id_civil.estado_civil if emp.id_civil else '',
            'id_sexo': emp.id_sexo.id if emp.id_sexo else '',
            'sexo_nombre': emp.id_sexo.sexo if emp.id_sexo else '',
            'id_localidad': emp.id_localidad.id if emp.id_localidad else '',
            'localidad_nombre': emp.id_localidad.localidad if emp.id_localidad else '',
            'dr_personal': emp.dr_personal,
            'email': empleado_usuario.email if empleado_usuario else '',
        }
        
        registros_laborales = list(Empleado_el.objects.filter(idempleado=emp).order_by('-fecha_el', '-id'))
        el_actual = registros_laborales[0] if registros_laborales else None

        def matches_estado(el_obj):
            if estado_filter_id is None:
                return True
            return getattr(el_obj, 'id_estado_id', None) == estado_filter_id

        def matches_fecha(el_obj):
            if not fecha_estado_filter:
                return True
            year_required = fecha_estado_filter.get('year')
            month_required = fecha_estado_filter.get('month')
            if year_required is None and month_required is None:
                return True

            def match_date(dt):
                if not dt:
                    return False
                if year_required is not None and dt.year != year_required:
                    return False
                if month_required is not None and dt.month != month_required:
                    return False
                return True

            fecha_candidates = [getattr(el_obj, 'fecha_est', None), getattr(el_obj, 'fecha_el', None)]
            return any(match_date(dt) for dt in fecha_candidates if dt)

        def build_row(el, is_historical):
            data = base_data.copy()
            if el:
                data.update({
                    'estado': el.id_estado.estado if el.id_estado else '',
                    'fecha_estado': el.fecha_est.strftime('%Y-%m-%d') if el.fecha_est else (el.fecha_el.strftime('%Y-%m-%d') if el.fecha_el else ''),
                    'puesto': el.id_puesto.tipo_puesto if el.id_puesto else '',
                    'id_puesto': el.id_puesto.id_puesto if el.id_puesto else '',
                    'is_historical': is_historical,
                    'fecha_el': el.fecha_el.strftime('%Y-%m-%d') if el.fecha_el else '',
                })

                if vista_ampliada:
                    eo = Empleado_eo.objects.filter(idempleado=emp).order_by('-fecha_eo').first()
                    suc = eo.id_sucursal if eo else None
                    pers_jur = suc.id_pers_juridica if suc else None
                    fecha_ant = ''
                    if el.alta_ant:
                        fecha_ant = el.alta_ant.strftime('%Y-%m-%d')
                    elif is_historical and el.fecha_el:
                        fecha_ant = el.fecha_el.strftime('%Y-%m-%d')
                    data.update({
                        'num_hijos': emp.num_hijos,
                        'telefono': emp.telefono,
                        'cuil': emp.cuil,
                        'convenio': el.id_convenio.tipo_convenio if el.id_convenio else '',
                        'puesto': el.id_puesto.tipo_puesto if el.id_puesto else '',
                        'fecha_antiguedad': fecha_ant,
                        'sucursal': suc.sucursal if suc else '',
                        'suc_dire': suc.suc_dire if suc else '',
                        'pers_juridica': pers_jur.pers_juridica if pers_jur else '',
                        'domicilio_pers_juridica': pers_jur.domicilio if pers_jur else '',
                        'cond_iva': pers_jur.cond_iva if pers_jur else '',
                        'cuit': pers_jur.cuit if pers_jur else '',
                        'cond_iibb': pers_jur.cond_iibb if pers_jur else '',
                    })
            else:
                data.update({
                    'estado': '',
                    'fecha_estado': '',
                    'puesto': '',
                    'id_puesto': '',
                    'is_historical': False,
                    'fecha_el': '',
                })
            return data

        if force_actual_only:
            if not el_actual:
                resultados.append(build_row(None, False))
                continue
            if not matches_estado(el_actual):
                continue
            if not matches_fecha(el_actual):
                continue
            resultados.append(build_row(el_actual, False))
            continue

        registros_iter = registros_laborales
        if estado_filter_id is not None or fecha_estado_filter:
            registros_iter = [el for el in registros_laborales if matches_estado(el) and matches_fecha(el)]
            registros_iter.sort(key=lambda el: (0 if el_actual and el.pk == el_actual.pk else 1, el.fecha_el or date.min))

        if not registros_iter:
            if estado_filter_id is None:
                resultados.append(build_row(None, False))
            continue

        for el in registros_iter:
            is_historical = bool(el_actual and el.pk != el_actual.pk)
            resultados.append(build_row(el, is_historical))
    
    return JsonResponse({'empleados': resultados})


@login_required
def ver_log_auditoria(request):
    """Vista para mostrar el log de auditoría"""
    # Obtener parámetros de ordenación
    log_order = request.GET.get('log_order', 'fecha_cambio')
    log_dir = request.GET.get('log_dir', 'desc')
    
    # Validar campo de ordenación
    valid_order_fields = {
        'fecha_cambio': 'fecha_cambio',
        'usuario': 'idusuario__username',
        'tabla': 'nombre_tabla',
        'accion': 'accion',
        'id': 'id'
    }
    
    order_field = valid_order_fields.get(log_order, 'fecha_cambio')
    
    # Aplicar dirección de ordenación
    if log_dir == 'asc':
        order_by = order_field
    else:
        order_by = f'-{order_field}'
    
    # Obtener todos los logs de auditoría con ordenación
    logs = Log_auditoria.objects.all().order_by(order_by)
    
    # Filtros opcionales
    tabla = request.GET.get('tabla', '')
    usuario = request.GET.get('usuario', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    rango_fecha = request.GET.get('rango_fecha', '')  # checkbox: present when checked
    
    if tabla:
        logs = logs.filter(nombre_tabla__icontains=tabla)
    if usuario:
        # If usuario looks like an integer, also allow filtering by id
        try:
            u_id = int(usuario)
        except Exception:
            u_id = None
        if u_id is not None:
            # use imported Q from django.db.models
            logs = logs.filter(Q(idusuario__id=u_id) | Q(idusuario__username__icontains=usuario))
        else:
            logs = logs.filter(idusuario__username__icontains=usuario)

    if fecha_desde:
        if rango_fecha:
            # rango activo: use >=
            logs = logs.filter(fecha_cambio__date__gte=fecha_desde)
        else:
            # single date: match exact day
            logs = logs.filter(fecha_cambio__date=fecha_desde)
    if fecha_hasta and rango_fecha:
        # only apply fecha_hasta when rango is enabled
        logs = logs.filter(fecha_cambio__date__lte=fecha_hasta)
    
    # Paginación - incrementar a 50 registros para mostrar más datos
    paginator = Paginator(logs, 50)  # 50 registros por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'logs': page_obj,
        'filtros': {
            'tabla': tabla,
            'usuario': usuario,
            'rango_fecha': bool(rango_fecha),
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
        },
        'log_order': log_order,
        'log_dir': log_dir,
        'total_logs': logs.count()  # Total de registros para mostrar información
    }
    
    return render(request, 'nucleo/log_auditoria.html', context)


@login_required
def exportar_empleados_excel(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="empleados.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Nombre', 'Apellido', 'DNI'])
    for emp in Empleado.objects.exclude(idempleado_id=1):
        writer.writerow([emp.idempleado, emp.nombres, emp.apellido, emp.dni])
    return response
