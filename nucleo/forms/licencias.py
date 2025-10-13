from django import forms

class PasswordResetUsernameForm(forms.Form):
    username = forms.CharField(label="Ingrese su usuario", required=True)

class ConfirmacionForm(forms.Form):
    pass 

