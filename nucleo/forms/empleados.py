from django import forms
from datetime import date, timedelta
from ..models import Empleado, Plan_trabajo, Empleado_el, Empleado_eo, Sucursal, Estado_empleado, Convenio, Puesto, Localidad

class DatosPersonalesForm(forms.ModelForm):
    email = forms.EmailField(label="Email", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    num_hijos = forms.IntegerField(min_value=0, label="Hijos")
    id_localidad = forms.ModelChoiceField(
        queryset=Localidad.objects.all(),
        label="Localidad",
        error_messages={'required': 'Campo obligatorio'}
    )

    class Meta:
        model = Empleado
        fields = [
            'nombres', 'apellido', 'dni', 'fecha_nac', 'id_nacionalidad',
            'id_civil', 'num_hijos', 'id_sexo', 'id_localidad',
            'dr_personal', 'telefono', 'cuil', 'email'
        ]
        widgets = {
            'fecha_nac': forms.DateInput(attrs={'type': 'date'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class EmpleadoForm(forms.ModelForm):
    email = forms.EmailField(label="Email", required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    num_hijos = forms.IntegerField(min_value=0, label="Hijos")
    id_localidad = forms.ModelChoiceField(
        queryset=Localidad.objects.all(),
        label="Localidad",
        error_messages={'required': 'Campo obligatorio'}
    )

    class Meta:
        model = Empleado
        fields = [
            'nombres', 'apellido', 'dni', 'fecha_nac', 'id_nacionalidad',
            'id_civil', 'num_hijos', 'id_sexo', 'id_localidad',
            'dr_personal', 'telefono', 'cuil'
        ]
        widgets = {
            'fecha_nac': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_dni(self):
        dni = self.cleaned_data.get('dni')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI debe ser numérico.')
        return dni

    # Otros métodos de validación y lógica según tu versión local
        labels = {
            'apellido': 'Apellidos',
            'dni': 'DNI',
            'fecha_nac': 'Fecha de Nacimiento',
            'id_nacionalidad': 'Nacionalidad',
            'provincia': 'Provincia',
            'id_civil': 'Estado Civil',
            'num_hijos': 'Hijos',
            'id_sexo': 'Sexo',
            'id_localidad': 'Localidad', 
            'dr_personal': 'Dirección',
            'email': 'Email',
            'cuil' : 'CUIL',
            'telefono': 'Teléfono',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_localidad'].widget.attrs['id'] = 'id_localidad'
        data = self.data or self.initial
        provincia_id = data.get('provincia')
        id_localidad = data.get('id_localidad')
        if provincia_id:
            self.fields['id_localidad'].queryset = Localidad.objects.filter(provincia_id=provincia_id).order_by('localidad')
        elif id_localidad:
            # Si hay id_localidad pero no provincia, incluir solo esa localidad
            self.fields['id_localidad'].queryset = Localidad.objects.filter(id=id_localidad)
        else:
            self.fields['id_localidad'].queryset = Localidad.objects.none()

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '').replace('.', '')
        if not dni.isdigit() or len(dni) != 8:
            raise forms.ValidationError("El DNI debe tener exactamente 8 números.")
        return dni

    def clean_fecha_nac(self):
        fecha = self.cleaned_data.get('fecha_nac')
        hoy = date.today()
        edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
        if edad < 16:
            raise forms.ValidationError("El empleado debe ser mayor a 16 años")
        return fecha

class EmpleadoELForm(forms.ModelForm):
    class Meta:
        model = Empleado_el
        fields = [
            'id_estado', 'fecha_est', 'id_convenio', 'alta_ant', 'id_puesto'
        ]
        labels = {
            'id_estado': 'Estado',
            'fecha_est': 'Fecha Estado',
            'id_convenio': 'Convenio',
            'alta_ant': 'Antigüedad',
            'id_puesto': 'Puesto',
        }
        widgets = {
            'fecha_est': forms.DateInput(attrs={'type': 'date'}),
            'alta_ant': forms.DateInput(attrs={'type': 'date'}),
        }

class PlanTrabajoForm(forms.ModelForm):
    class Meta:
        model = Plan_trabajo
        exclude = ['idempleado']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

class EmpleadoEOForm(forms.ModelForm):
    class Meta:
        model = Empleado_eo
        fields = ['id_sucursal']

class LaboralesCombinadoForm(forms.ModelForm):
    # Quitar el sufijo de etiqueta (por defecto ':') en todos los labels de este formulario
    label_suffix = ""
    id_estado = forms.ModelChoiceField(
        queryset=Estado_empleado.objects.all(),
        label="Estado"
    )
    fecha_est = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Fecha Estado"
    )
    id_convenio = forms.ModelChoiceField(
        queryset=Convenio.objects.all(),
        label="Convenio"
    )
    id_puesto = forms.ModelChoiceField(
        queryset=Puesto.objects.all(),
        label="Puesto"
    )
    alta_ant = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Antigüedad"
    )
    id_sucursal = forms.ModelChoiceField(
        queryset=Sucursal.objects.all(),
        label="Sucursal"
    )
    # Campos de Plan_trabajo
    lunes = forms.BooleanField(required=False)
    martes = forms.BooleanField(required=False)
    miercoles = forms.BooleanField(required=False)
    jueves = forms.BooleanField(required=False)
    viernes = forms.BooleanField(required=False)
    sabado = forms.BooleanField(required=False)
    domingo = forms.BooleanField(required=False)
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'style': 'width:110px;'}),
        required=True,
        label="Horario inicio"
    )
    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'style': 'width:110px;'}),
        required=True,
        label="Horario fin"
    )

    class Meta:
        model = Empleado_el  # o el modelo principal del paso
        fields = [
            'id_estado', 'fecha_est', 'id_convenio', 'alta_ant', 'id_puesto',
            'lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo',
            'start_time', 'end_time', 'id_sucursal'
        ]
        # No es necesario definir labels aquí si ya los pusiste en los campos arriba
        # Si quieres, puedes dejar el diccionario vacío o eliminarlo
        labels = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Asegurar que no se agregue ':' al final de los labels en esta instancia
        self.label_suffix = ""
        self.fields['id_sucursal'].widget.attrs.update({'id': 'id_sucursal'})
        for field in ['id_estado', 'id_convenio', 'alta_ant', 'id_puesto', 'start_time', 'end_time', 'id_sucursal']:
            self.fields[field].required = True

class EmpleadoModificarForm(forms.ModelForm):
    # Quitar sufijo de etiqueta (por defecto ':')
    label_suffix = ""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Forzar el id correcto para el select de localidad (evita duplicar 'id_')
        self.fields['id_localidad'].widget.attrs['id'] = 'id_localidad'
        self.fields['id_localidad'].queryset = Localidad.objects.none()
        # Agregar data-inicial si hay localidad inicial
        if self.initial.get('id_localidad'):
            self.fields['id_localidad'].widget.attrs['data-inicial'] = self.initial['id_localidad']
        data = self.data or self.initial
        provincia_id = data.get('provincia')
        if provincia_id:
            self.fields['id_localidad'].queryset = Localidad.objects.filter(provincia_id=provincia_id).order_by('localidad')
    email = forms.EmailField(label="Email", required=True)
    num_hijos = forms.IntegerField(
        label="Cantidad de hijos",
        min_value=0,  # Esto fuerza el mínimo a 0
        required=True
    )
    
    class Meta:
        model = Empleado
        fields = [
            'nombres', 'apellido', 'dni', 'fecha_nac', 'id_nacionalidad',
            'id_civil', 'num_hijos', 'id_sexo', 'id_localidad',
            'dr_personal', 'telefono', 'cuil' 
        ]
        labels = {
            'nombres': 'Nombres',
            'apellido': 'Apellido',
            'dni': 'DNI',
            'fecha_nac': 'Fecha Nacimiento',
            'id_nacionalidad': 'Nacionalidad',
            'id_civil': 'Estado Civil',
            'num_hijos': 'Hijos',
            'id_sexo': 'Sexo',
            'id_localidad': 'Localidad',
            'dr_personal': 'Dirección',
            'telefono': 'Teléfono',
            'cuil': 'CUIL',
            'email': 'Email',  
        }
        widgets = {
            'fecha_nac': forms.DateInput(attrs={'type': 'date'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }