#! python3
# -*- coding: utf-8 -*-
"""
Resumen de elementos en vista activa:
- Cuenta cuántos tienen valor en el parámetro BIM_TAG
- Muestra porcentajes
- Ventana flotante con gráfico circular
Compatible con Revit 2026 + pyRevit (Python 3)
"""

from pyrevit import revit, DB
from Autodesk.Revit.UI import TaskDialog
import clr

# Referencias .NET
clr.AddReference("System.Windows.Forms")
clr.AddReference("System.Drawing")

import System.Windows.Forms as WinForms
import System.Drawing as Drawing

doc = revit.doc
view = doc.ActiveView

# --- Contar elementos visibles ---
collector = DB.FilteredElementCollector(doc, view.Id).WhereElementIsNotElementType()

total_count = 0
with_tag = 0
without_tag = 0

for elem in collector:
    total_count += 1
    param = elem.LookupParameter("BIM_TAG")
    if param and param.HasValue and param.AsString():
        with_tag += 1
    else:
        without_tag += 1

pct_with = (with_tag * 100.0 / total_count) if total_count > 0 else 0
pct_without = (without_tag * 100.0 / total_count) if total_count > 0 else 0

# --- Mostrar resumen con TaskDialog ---
msg = "Elementos en vista: {0}\nCon BIM_TAG: {1} ({2:.2f}%)\nSin BIM_TAG: {3} ({4:.2f}%)".format(
    total_count, with_tag, pct_with, without_tag, pct_without
)
TaskDialog.Show("Resumen BIM_TAG", msg)

# --- Crear gráfico circular en WinForms ---
class PieChartForm(WinForms.Form):
    def __init__(self):
        self.Text = "Gráfico BIM_TAG"
        self.Width = 400
        self.Height = 400
        self.Paint += self.OnPaint

    def OnPaint(self, sender, e):
        g = e.Graphics
        rect = Drawing.Rectangle(50, 50, 250, 250)

        brush_with = Drawing.SolidBrush(Drawing.Color.Green)
        brush_without = Drawing.SolidBrush(Drawing.Color.Red)

        angle_with = (pct_with / 100.0) * 360.0
        angle_without = (pct_without / 100.0) * 360.0

        g.FillPie(brush_with, rect, 0, angle_with)
        g.FillPie(brush_without, rect, angle_with, angle_without)

        g.DrawString("Con BIM_TAG: {0:.2f}%".format(pct_with),
                     Drawing.Font("Arial", 10),
                     Drawing.SolidBrush(Drawing.Color.Black),
                     50, 320)
        g.DrawString("Sin BIM_TAG: {0:.2f}%".format(pct_without),
                     Drawing.Font("Arial", 10),
                     Drawing.SolidBrush(Drawing.Color.Black),
                     50, 340)

# Ejecutar ventana gráfica
form = PieChartForm()
WinForms.Application.Run(form)
