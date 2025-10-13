# Registro de Pruebas Manuales

Este documento recopila las verificaciones funcionales realizadas durante la sesión de trabajo. Cada sección corresponde a una pantalla o flujo del sistema e indica el resultado de la prueba.

## Login
- Credenciales correctas ✅
- Credenciales incorrectas (lleva a 1 fallo) ✅
- Usuario dado de baja bloqueado ✅
- Tres errores consecutivos activa modal de bloqueo ✅
- Botón “Recuperar contraseña” redirige a `password_reset` ✅
- Ingreso con contraseña regenerada ✅
- Email de `password_reset` enviado ✅



## Sesiones
- Cerrar sesión desde dashboard con modal de confirmación ✅
- Botón “Atrás” desde dashboard muestra modal de cierre de sesión ✅


## Dashboard Empleado
- Gráficos “Mis Licencias” y “Mis Vacaciones” muestran métricas personales correctas ✅
- Gráficos se actualizan inmediatamente tras aprobar vacaciones (disponibles, consumidos, en espera) ✅

## Dashboard Gestor
- Menú y gráficos visibles para usuario `is_staff` muestran métricas esperadas ✅
- Vacaciones aprobadas y en espera se reflejan en los indicadores agregados ✅
- Gráfico "Status Licencias" muestra días acumulados por estado ✅ (retest 12/10/2025 21:52)
- Gráfico "Mis Licencias" muestra días acumulados por estado ✅ (retest 12/10/2025 21:52)
- Redirecciones al hacer clic en los cuatro gráficos llevan a la vista correspondiente ✅ (retest 12/10/2025 21:55)

## Solicitar Licencia
- Página carga con datos del empleado y días disponibles ✅
- Licencias no vacaciones muestran días disponibles correctos ✅
- Seleccionar “Vacaciones” despliega tabla de vacaciones ✅
- Tabla de vacaciones refleja correctamente los días disponibles por periodo ✅
- `fecha_hasta` se autocompleta a partir de `fecha_desde` según días pendientes ✅
- Colisión con licencias propias bloquea fechas repetidas ✅
- Colisión con día no laborable impide solicitud de un solo día ✅
- Solicitud de rango iniciando en día no laborable aceptada cuando corresponde ✅
- Solicitud misma fecha que otro empleado permite avanzar con advertencia ✅
- Licencia libre de un día (29/11–29/11) en día no laborable ✅
- Licencia libre multidiaria con comentario y adjunto ✅

## Consultar Licencia (Mis Licencias)
- Filtro por tipo de licencia devuelve los registros correspondientes ✅
- Filtro por fecha simple muestra coincidencias exactas ✅
- Filtro por rango de fechas respeta límites desde/hasta ✅
- Botón “Eliminar” cancela la licencia y actualiza la grilla ✅
- Eliminación impacta en los gráficos del dashboard (disponibles/consumidos) ✅
- Tabla de “Generar Vacaciones” refleja los días restituidos tras eliminar ✅
- Botón “Limpiar” restablece filtros y listado ✅ (retest 12/10/2025 21:10)
- Flujo completo validado con usuario empleado ✅


## Emitir Certificado
- Botón “Descargar PDF” genera el archivo correctamente ✅
- Botón “Imprimir” abre el diálogo del navegador ✅
- Vista de impresión centra el certificado en la hoja ✅ (retest CSS 12/10/2025 21:24)
- Ajuste de tamaño evita desbordes laterales en impresión ✅ (retest 12/10/2025 21:52)


## Alta de Empleado
- Paso 1 `alta_empleado_personales` completo ✅
- Paso 2 `alta_empleado_laborales` completo ✅
- Alta consecutiva (pasos 1 y 2 en la misma sesión) ✅

## Modificar/Borrar Empleado
- Búsqueda y carga de datos ✅
- Actualización “Datos personales” persiste y genera log ✅
- Actualización “Días y horario laboral” persiste y genera log ✅
- Modal de confirmación previo a guardar ✅
- Eliminación con modal de confirmación ✅
- Registro de borrado en `log_auditoria` ✅
- Cambio exclusivo de “Estado Civil” muestra solo ese campo en el modal (CUIL sin falso positivo por máscara) ✅

## Ver Empleados
- **Descripción:** Utilizar la barra de búsqueda para filtrar la grilla en vivo, incluyendo vistas con estado actual y vista ampliada.
- **Resultado:** ✅ PS — El listado se actualiza dinámicamente con los resultados devueltos por `buscar_empleados_ajax` y respeta los filtros seleccionados.
- **Acciones adicionales:**
  - ✅ PS — El botón “Editar” abre la ficha correspondiente en `modificar_borrar_empleado`.
  - ✅ PS — Checkbox “Vista ampliada” alterna correctamente la tabla.
  - ✅ PS — Checkbox “Solo estado/puesto actual” filtra la grilla según selección.
  - ✅ PS — Filtro por nombre devuelve coincidencias inmediatas.
  - ✅ PS — Exportar a Excel/PDF entrega los archivos con el conjunto filtrado.
  - ✅ PS — Filtro “Estado” devuelve solo los registros cuyo historial coincide con el estado elegido.
  - ✅ PS — Filtro “Año/Mes Fecha Estado” muestra opciones por año disponibles y filtra correctamente por año y mes.
  - ✅ PS — Botón “Limpiar filtro” restablece la grilla completa.
  - ✅ PS — Barra de búsqueda principal sigue respondiendo tras aplicar filtros.


## Gestión y Reporte de Licencias
- Aprobar licencia persiste cambios y envía email ✅ (verificado 12/10/2025 20:52)
- Rechazar licencia exige comentario, persiste estado ✅ (correo emitido con asunto/mensaje incorrecto "fallecimiento de concubino")
- Página `gestion_reporte_licencias` carga filtros y tabla ✅
- Vista `detalle_licencia` muestra comentarios y datos completos ✅
- Ver certificado adjunto desde detalle de licencia ✅
- Gestor no puede aprobar su propia solicitud (bloqueado al aprobar) ✅
- Barra de búsqueda reutiliza el componente de empleados y filtra resultados ✅
- Vacaciones aprobadas desde esta vista actualizan gráficos y tabla de solicitudes ✅
- ✅ PS — Aprobación de licencia médica confirma persistencia y envío de correo.
- ✅  PS — Aprobación de vacaciones muestra mensaje de éxito, persiste, envía correo 
- Botones de exportación a PDF y Excel generan los archivos con el dataset filtrado ✅ (retest 12/10/2025 21:55)
- Búsqueda por empleado actualiza la tabla sin desplegar dropdown de autocompletado ✅ 
- Filtros por tipo, estado y fechas refrescan la tabla dinámicamente sin recargar la página ✅ 
- Aprobación de licencia desde `detalle_licencia` persiste el estado y reenvía la notificación al empleado ✅

## Generar Vacaciones
- Botón “Generar vacaciones” crea el lote de días correctamente ✅
- Botón “Generar” abre modal de confirmación cuando el año ya fue generado ✅
- Botón “No” del modal cancela la sobrescritura y mantiene los datos existentes ✅
- Botón “Sí, sobrescribir” ejecuta la regeneración forzada y actualiza la tabla ✅
- Tabla refleja los días aprobados por empleado tras generar o aprobar ✅
- Ajustes manuales de “días consumidos” persisten ante recarga ✅
- Escenarios de antigüedad verificados manualmente:
  - ✅ Alta 11/10/2025 → 3 días otorgados (≤ 3 meses)
  - ✅ Alta 11/09/2025 → 4 días otorgados (111 días → ⌈111/30⌉)
  - ✅ Alta 11/06/2025 → 14 días otorgados (> 6 meses y < 5 años)
  - ✅ Alta 11/07/2020 → 21 días otorgados (≥ 5 años y < 10)
  - ✅ Alta 11/07/2015 → 28 días otorgados (≥ 10 años y < 20)
  - ✅ Alta 11/07/1990 → 35 días otorgados (≥ 20 años)

## Gestión de Feriados
- Alta de feriado permite fechas pasadas o del día y limpia los campos tras guardar ✅
- Filtro por año en Modificar/Borrar feriado actualiza el listado automáticamente al cambiar la selección ✅
- Modificar feriado guarda los cambios y confirma éxito ✅
- Borrar feriado elimina el registro y muestra mensaje de éxito ✅
- Listado de feriados refleja correctamente los filtros aplicados ✅
- Botón “Editar” abre el formulario del feriado seleccionado con los datos actuales ✅

## Gestión Tipo Licencias
- Alta de tipo de licencia persiste datos, muestra éxito y limpia los campos tras guardar ✅
- Modificar tipo de licencia actualiza descripción/días/pago y confirma la operación ✅
- Borrar tipo de licencia sin solicitudes relacionadas elimina el registro ✅
- Listado de tipos de licencia muestra descripción, días y estado de pago actualizados ✅

## Log Auditoría
- Creaciones se reflejan en el historial ✅
- Actualizaciones quedan registradas ✅
- Borrados aparecen en la bitácora ✅
- Botón “Exportar Excel” descarga el archivo ✅
- Botón “Exportar PDF” descarga el reporte ✅
---

> Última actualización: 12/10/2025 23:53
FATA: EN Feridados no permitir dos feriados el mismos dia
Controla en borrar empleado que no debje borrar si tiene licencias solicitadas