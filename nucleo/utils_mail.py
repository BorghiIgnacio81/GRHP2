
def enviar_mail_credenciales_auto(email, username, password):
    from django.core.mail import send_mail
    from django.conf import settings
    login_url = settings.SITE_URL + "/login/"
    send_mail(
        subject="Tus credenciales de acceso",
        message=f"Usuario: {username}\nContraseña: {password}\n\nAccedé al sistema desde: {login_url}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

def enviar_mail_estado_licencia(email, nombre_empleado, tipo, estado, texto_gestor=None, fecha_desde=None, fecha_hasta=None):
    from django.core.mail import send_mail
    from django.conf import settings
    import logging
    from datetime import datetime, date
    try:
        # Helper to format date with no zero-padding: D/M/YYYY
        def _fmt(d):
            try:
                if hasattr(d, 'day') and hasattr(d, 'month') and hasattr(d, 'year'):
                    return f"{d.day}/{d.month}/{d.year}"
                if isinstance(d, str):
                    # Try ISO format YYYY-MM-DD
                    try:
                        parsed = date.fromisoformat(d)
                        return f"{parsed.day}/{parsed.month}/{parsed.year}"
                    except Exception:
                        try:
                            parsed = datetime.strptime(d, '%Y-%m-%d').date()
                            return f"{parsed.day}/{parsed.month}/{parsed.year}"
                        except Exception:
                            return str(d)
                return str(d)
            except Exception:
                return str(d)

        # Build period phrase to insert into the sentence
        periodo_phrase = ''
        try:
            if fecha_desde and fecha_hasta:
                # If both dates provided and equal -> single day
                try:
                    igual = False
                    if hasattr(fecha_desde, 'year') and hasattr(fecha_hasta, 'year'):
                        igual = (fecha_desde == fecha_hasta)
                    else:
                        igual = str(fecha_desde) == str(fecha_hasta)
                    if igual:
                        periodo_phrase = f" para el {_fmt(fecha_desde)}"
                    else:
                        periodo_phrase = f" para el periodo del {_fmt(fecha_desde)} al {_fmt(fecha_hasta)}"
                except Exception:
                    periodo_phrase = f" para el periodo del {_fmt(fecha_desde)} al {_fmt(fecha_hasta)}"
            elif fecha_desde:
                periodo_phrase = f" para el {_fmt(fecha_desde)}"
        except Exception:
            periodo_phrase = ''

        if estado.lower() == 'aceptada':
            if texto_gestor:
                mensaje = f"Hola {nombre_empleado},\n\nTu solicitud de {tipo}{periodo_phrase} ha sido aprobada. Motivo del gestor: {texto_gestor}\n"
            else:
                mensaje = f"Hola {nombre_empleado},\n\nTu solicitud de {tipo}{periodo_phrase} ha sido aprobada con éxito.\n"
            mensaje += "\nSaludos."
            asunto = f"Solicitud de {tipo} aprobada"
        elif estado.lower() == 'rechazada':
            motivo = texto_gestor if texto_gestor else "Sin motivo especificado."
            mensaje = f"Hola {nombre_empleado},\n\nTu solicitud de {tipo}{periodo_phrase} ha sido rechazada. Motivo del gestor: {motivo}\n"
            mensaje += "\nSaludos."
            asunto = f"Solicitud de {tipo} rechazada"
        else:
            mensaje = f"Hola {nombre_empleado},\n\nEl estado de tu solicitud de {tipo} ha cambiado a: {estado}.\n"
            if periodo_phrase:
                # Insert period info in a separate sentence for status changes
                mensaje = f"Hola {nombre_empleado},\n\nTu solicitud de {tipo}{periodo_phrase} ha cambiado de estado a: {estado}.\n"
            asunto = f"Solicitud de {tipo} actualizada"
        logging.warning(f"Intentando enviar email a {email} con asunto '{asunto}'")
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logging.warning(f"Email enviado correctamente a {email}")
    except Exception as e:
        logging.error(f"Error al enviar email a {email}: {e}")
