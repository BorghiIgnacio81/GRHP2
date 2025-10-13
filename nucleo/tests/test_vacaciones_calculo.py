import os
import unittest
from datetime import date, timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_rrhh.settings")
django.setup()

from nucleo.views.vacaciones import (
    calcular_dias_vacaciones,
    obtener_fecha_corte_generacion,
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_rrhh.settings")


class VacacionesCalculoTests(unittest.TestCase):
    def test_fecha_corte_para_generacion_es_fin_de_ciclo(self):
        year = date.today().year + 1
        self.assertEqual(
            obtener_fecha_corte_generacion(year),
            date(year, 12, 31),
        )

    def test_empleado_menor_seis_meses_recibe_redondeo_fin_de_ciclo(self):
        year = date.today().year
        alta = date(year, 9, 11)

        fecha_corte = obtener_fecha_corte_generacion(year)
        self.assertEqual((fecha_corte - alta).days, 111)

        dias_proporcionales = calcular_dias_vacaciones(alta, fecha_corte)
        self.assertEqual(dias_proporcionales, 4)
