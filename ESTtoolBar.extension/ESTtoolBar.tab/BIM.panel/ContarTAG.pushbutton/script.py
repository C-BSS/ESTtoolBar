#! python3
# -*- coding: utf-8 -*-
"""
Resumen BIM_TAG en vista activa:
- Revisa sólo categorías estructurales relevantes
- Incluye framing, columns, foundations y structural connections
- Cuenta elementos con y sin valor en parámetro BIM_TAG
- Muestra resumen general en formato tabla
- Muestra resumen por categoría en formato tabla
- Incluye semáforo de calidad BIM
- Permite aislar temporalmente elementos sin BIM_TAG
- Permite seleccionar automáticamente elementos sin BIM_TAG
- Permite exportar listado de elementos sin BIM_TAG a CSV
- CSV incluye fecha, usuario, ranking por categoría, BIM_TAG, Workset y Nivel

Compatible con Revit 2026 + pyRevit CPython3
by Sebastián H. Sáez S.
"""

import clr
import csv
import os
import getpass
from datetime import datetime

from pyrevit import revit, DB

from Autodesk.Revit.UI import (
    TaskDialog,
    TaskDialogResult,
    TaskDialogCommonButtons
)

from Autodesk.Revit.DB import ElementId

from System.Collections.Generic import List

clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import SaveFileDialog, DialogResult


# ================================================================
# CONFIGURACION
# ================================================================

PARAM_BIM_TAG = "BIM_TAG"


# ================================================================
# DOCUMENTO
# ================================================================

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView


# ================================================================
# FUNCIONES AUXILIARES
# ================================================================

def obtener_element_id(elem):

    try:
        return str(elem.Id.IntegerValue)
    except:
        try:
            return str(elem.Id.Value)
        except:
            return str(elem.Id)


def obtener_categoria(elem):

    try:
        if elem.Category:
            return elem.Category.Name
    except:
        pass

    return "Sin categoria"


def obtener_nombre(elem):

    try:
        return elem.Name
    except:
        return "Sin nombre"


def obtener_tipo_elemento(elem):

    try:
        type_id = elem.GetTypeId()

        if type_id and type_id != ElementId.InvalidElementId:
            tipo = doc.GetElement(type_id)

            if tipo:
                return tipo

    except:
        pass

    return None


def obtener_familia(elem):

    try:
        tipo = obtener_tipo_elemento(elem)

        if tipo:

            try:
                return tipo.FamilyName
            except:
                pass

            try:
                param = tipo.LookupParameter("Family Name")

                if param and param.HasValue:
                    valor = param.AsString()

                    if valor:
                        return valor
            except:
                pass

    except:
        pass

    return "Sin familia"


def obtener_tipo(elem):

    try:
        tipo = obtener_tipo_elemento(elem)

        if tipo:
            return tipo.Name

    except:
        pass

    return "Sin tipo"


def obtener_valor_parametro_texto(param):

    if not param:
        return ""

    try:
        valor = param.AsString()

        if valor:
            return valor
    except:
        pass

    try:
        valor = param.AsValueString()

        if valor:
            return valor
    except:
        pass

    return ""


def obtener_bim_tag(elem):

    try:
        param = elem.LookupParameter(PARAM_BIM_TAG)

        if param and param.HasValue:

            valor = obtener_valor_parametro_texto(param)

            if valor:
                return valor

    except:
        pass

    return ""


def tiene_bim_tag(elem):

    valor = obtener_bim_tag(elem)

    if valor and valor.strip() != "":
        return True

    return False


def obtener_workset(elem):

    try:
        workset_id = elem.WorksetId

        if workset_id:
            workset = doc.GetWorksetTable().GetWorkset(workset_id)

            if workset:
                return workset.Name

    except:
        pass

    return "Sin workset"


def obtener_nivel_desde_element_id(level_id):

    try:
        if level_id and level_id != ElementId.InvalidElementId:

            nivel = doc.GetElement(level_id)

            if nivel:
                return nivel.Name

    except:
        pass

    return ""


def obtener_nivel(elem):

    # 1. Intentar propiedad LevelId
    try:
        nivel = obtener_nivel_desde_element_id(elem.LevelId)

        if nivel:
            return nivel
    except:
        pass

    # 2. Intentar parámetros comunes de nivel
    parametros_nivel = [
        "Level",
        "Reference Level",
        "Base Level",
        "Top Level",
        "Schedule Level"
    ]

    for nombre_param in parametros_nivel:

        try:
            param = elem.LookupParameter(nombre_param)

            if param and param.HasValue:

                try:
                    level_id = param.AsElementId()
                    nivel = obtener_nivel_desde_element_id(level_id)

                    if nivel:
                        return nivel
                except:
                    pass

                try:
                    valor = obtener_valor_parametro_texto(param)

                    if valor:
                        return valor
                except:
                    pass

        except:
            pass

    # 3. Intentar BuiltInParameters habituales
    built_in_params = [
        "INSTANCE_REFERENCE_LEVEL_PARAM",
        "FAMILY_LEVEL_PARAM",
        "SCHEDULE_LEVEL_PARAM",
        "LEVEL_PARAM",
        "WALL_BASE_CONSTRAINT",
        "FLOOR_PARAM_LEVEL",
        "ROOF_CONSTRAINT_LEVEL_PARAM"
    ]

    for bip_name in built_in_params:

        try:
            bip = getattr(DB.BuiltInParameter, bip_name)
            param = elem.get_Parameter(bip)

            if param and param.HasValue:

                try:
                    level_id = param.AsElementId()
                    nivel = obtener_nivel_desde_element_id(level_id)

                    if nivel:
                        return nivel
                except:
                    pass

                try:
                    valor = obtener_valor_parametro_texto(param)

                    if valor:
                        return valor
                except:
                    pass

        except:
            pass

    return "Sin nivel"


def obtener_estado_calidad(pct_with):

    try:
        if pct_with >= 95.0:
            return "VERDE - EXCELENTE"

        if pct_with >= 90.0:
            return "AMARILLO - REVISAR"

        return "ROJO - CRITICO"

    except:
        return "SIN ESTADO"


def obtener_recomendacion_calidad(pct_with):

    try:
        if pct_with >= 95.0:
            return "Modelo con muy buen cumplimiento BIM_TAG."

        if pct_with >= 90.0:
            return "Modelo aceptable, pero se recomienda revisar elementos pendientes."

        return "Modelo requiere revision prioritaria de BIM_TAG."

    except:
        return "No fue posible evaluar el estado de calidad."


def preguntar_si_no(titulo, instruccion, contenido):

    dialog = TaskDialog(titulo)

    dialog.MainInstruction = instruccion
    dialog.MainContent = contenido

    dialog.CommonButtons = (
        TaskDialogCommonButtons.Yes |
        TaskDialogCommonButtons.No
    )

    resultado = dialog.Show()

    return resultado == TaskDialogResult.Yes


def texto_seguro(valor):

    try:
        if valor is None:
            return ""

        texto = str(valor)
        texto = texto.replace("\n", " ")
        texto = texto.replace("\r", " ")

        return texto

    except:
        return ""


def nombre_archivo_seguro(nombre):

    caracteres_invalidos = '\\/:*?"<>|'

    resultado = str(nombre)

    for c in caracteres_invalidos:
        resultado = resultado.replace(c, "_")

    return resultado


def obtener_fecha_actual():

    try:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ""


def obtener_usuario_actual():

    try:
        return getpass.getuser()
    except:
        return ""


# ================================================================
# EXPORTAR CSV
# ================================================================

def seleccionar_ruta_csv():

    dialog = SaveFileDialog()

    dialog.Title = "Guardar listado de elementos sin BIM_TAG"
    dialog.Filter = "Archivo CSV (*.csv)|*.csv"
    dialog.DefaultExt = "csv"
    dialog.AddExtension = True

    nombre_base = "Elementos_sin_BIM_TAG_{}".format(
        nombre_archivo_seguro(view.Name)
    )

    dialog.FileName = nombre_base + ".csv"

    resultado = dialog.ShowDialog()

    if resultado == DialogResult.OK:
        return dialog.FileName

    return None


def exportar_csv(
    elementos_sin_tag,
    total_count,
    with_tag,
    without_tag,
    pct_with,
    pct_without,
    resumen_categorias
):

    ruta = seleccionar_ruta_csv()

    if not ruta:

        TaskDialog.Show(
            "Exportar CSV",
            "Exportacion cancelada por el usuario."
        )

        return

    estado_calidad = obtener_estado_calidad(pct_with)
    recomendacion_calidad = obtener_recomendacion_calidad(pct_with)

    try:

        with open(ruta, "w", newline="", encoding="utf-8-sig") as csvfile:

            writer = csv.writer(
                csvfile,
                delimiter=";",
                lineterminator="\n"
            )

            # ----------------------------------------------------
            # DATOS GENERALES
            # ----------------------------------------------------

            writer.writerow(["Reporte BIM_TAG"])
            writer.writerow(["Proyecto", texto_seguro(doc.Title)])
            writer.writerow(["Vista activa", texto_seguro(view.Name)])
            writer.writerow(["Fecha ejecucion", obtener_fecha_actual()])
            writer.writerow(["Usuario", obtener_usuario_actual()])
            writer.writerow(["Parametro revisado", PARAM_BIM_TAG])
            writer.writerow(["Estado calidad", estado_calidad])
            writer.writerow(["Recomendacion", recomendacion_calidad])
            writer.writerow([])

            # ----------------------------------------------------
            # RESUMEN ESTADISTICO
            # ----------------------------------------------------

            writer.writerow(["Resumen estadistico"])
            writer.writerow(["Indicador", "Valor"])

            writer.writerow([
                "Total elementos revisados",
                total_count
            ])

            writer.writerow([
                "Elementos con BIM_TAG",
                with_tag
            ])

            writer.writerow([
                "Elementos sin BIM_TAG",
                without_tag
            ])

            writer.writerow([
                "Porcentaje cumplimiento BIM_TAG",
                "{:.2f}%".format(pct_with)
            ])

            writer.writerow([
                "Porcentaje faltante BIM_TAG",
                "{:.2f}%".format(pct_without)
            ])

            writer.writerow([
                "Semaforo calidad",
                estado_calidad
            ])

            writer.writerow([
                "Recomendacion calidad",
                recomendacion_calidad
            ])

            writer.writerow([])

            # ----------------------------------------------------
            # RESUMEN GENERAL
            # ----------------------------------------------------

            writer.writerow(["Resumen general"])
            writer.writerow(["Concepto", "Cantidad", "Porcentaje"])

            writer.writerow([
                "Total Elementos",
                total_count,
                "{:.2f}%".format(100.0 if total_count > 0 else 0.0)
            ])

            writer.writerow([
                "Con BIM_TAG",
                with_tag,
                "{:.2f}%".format(pct_with)
            ])

            writer.writerow([
                "Sin BIM_TAG",
                without_tag,
                "{:.2f}%".format(pct_without)
            ])

            writer.writerow([])

            # ----------------------------------------------------
            # RESUMEN POR CATEGORIA
            # ----------------------------------------------------

            writer.writerow(["Resumen por categoria"])
            writer.writerow([
                "Categoria",
                "Total",
                "OK",
                "Falta",
                "% OK",
                "% Falta"
            ])

            ranking_categorias = []

            for cat in sorted(resumen_categorias.keys()):

                datos = resumen_categorias[cat]

                total_cat = datos["total"]
                con_tag_cat = datos["con_tag"]
                sin_tag_cat = datos["sin_tag"]

                pct_ok_cat = (
                    con_tag_cat * 100.0 / total_cat
                    if total_cat > 0 else 0.0
                )

                pct_falta_cat = (
                    sin_tag_cat * 100.0 / total_cat
                    if total_cat > 0 else 0.0
                )

                ranking_categorias.append([
                    cat,
                    total_cat,
                    con_tag_cat,
                    sin_tag_cat,
                    pct_ok_cat,
                    pct_falta_cat
                ])

                writer.writerow([
                    texto_seguro(cat),
                    total_cat,
                    con_tag_cat,
                    sin_tag_cat,
                    "{:.2f}%".format(pct_ok_cat),
                    "{:.2f}%".format(pct_falta_cat)
                ])

            writer.writerow([])

            # ----------------------------------------------------
            # RANKING DE CATEGORIAS
            # ----------------------------------------------------

            writer.writerow(["Ranking categorias con mayor cantidad de BIM_TAG faltantes"])
            writer.writerow([
                "Categoria",
                "Total",
                "Sin BIM_TAG",
                "% Falta"
            ])

            ranking_ordenado = sorted(
                ranking_categorias,
                key=lambda x: x[3],
                reverse=True
            )

            for item in ranking_ordenado:

                writer.writerow([
                    texto_seguro(item[0]),
                    item[1],
                    item[3],
                    "{:.2f}%".format(item[5])
                ])

            writer.writerow([])

            # ----------------------------------------------------
            # LISTADO DE ELEMENTOS SIN BIM_TAG
            # ----------------------------------------------------

            writer.writerow(["Listado de elementos sin BIM_TAG"])
            writer.writerow([
                "ElementId",
                "Categoria",
                "Familia",
                "Tipo",
                "Nombre",
                "Workset",
                "Nivel",
                "BIM_TAG"
            ])

            for elem in elementos_sin_tag:

                writer.writerow([
                    obtener_element_id(elem),
                    texto_seguro(obtener_categoria(elem)),
                    texto_seguro(obtener_familia(elem)),
                    texto_seguro(obtener_tipo(elem)),
                    texto_seguro(obtener_nombre(elem)),
                    texto_seguro(obtener_workset(elem)),
                    texto_seguro(obtener_nivel(elem)),
                    texto_seguro(obtener_bim_tag(elem))
                ])

        TaskDialog.Show(
            "Exportar CSV",
            "Listado exportado correctamente:\n\n{}".format(ruta)
        )

    except Exception as ex:

        TaskDialog.Show(
            "Error al exportar CSV",
            str(ex)
        )


# ================================================================
# AISLAMIENTO TEMPORAL
# ================================================================

def aislar_elementos(elementos):

    ids = List[ElementId]()

    for elem in elementos:
        ids.Add(elem.Id)

    with revit.Transaction(
        "Aislar elementos sin BIM_TAG"
    ):

        view.IsolateElementsTemporary(ids)

    try:
        uidoc.ShowElements(ids)
    except:
        pass


# ================================================================
# SELECCION AUTOMATICA
# ================================================================

def seleccionar_elementos(elementos):

    try:
        ids = List[ElementId]()

        for elem in elementos:
            ids.Add(elem.Id)

        uidoc.Selection.SetElementIds(ids)

        try:
            uidoc.ShowElements(ids)
        except:
            pass

        return True

    except:
        return False


# ================================================================
# RESUMEN EN FORMATO TABLA
# ================================================================

def construir_resumen_general(
    total_count,
    with_tag,
    without_tag,
    pct_with,
    pct_without,
    resumen_categorias
):

    estado_calidad = obtener_estado_calidad(pct_with)
    recomendacion = obtener_recomendacion_calidad(pct_with)

    lineas = []

    lineas.append(
        "Vista activa: {}".format(
            view.Name
        )
    )

    lineas.append("")
    lineas.append("========== SEMAFORO DE CALIDAD ==========")
    lineas.append("")
    lineas.append("Estado QAQC: {}".format(estado_calidad))
    lineas.append("Cumplimiento BIM_TAG: {:.2f}%".format(pct_with))
    lineas.append("Recomendacion: {}".format(recomendacion))

    lineas.append("")
    lineas.append("========== RESUMEN GENERAL ==========")
    lineas.append("")

    lineas.append(
        "{:<30} {:>10} {:>10}".format(
            "Concepto",
            "Cantidad",
            "%"
        )
    )

    lineas.append("-" * 55)

    lineas.append(
        "{:<30} {:>10} {:>9.2f}".format(
            "Total Elementos",
            total_count,
            100.00 if total_count > 0 else 0.00
        )
    )

    lineas.append(
        "{:<30} {:>10} {:>9.2f}".format(
            "Con BIM_TAG",
            with_tag,
            pct_with
        )
    )

    lineas.append(
        "{:<30} {:>10} {:>9.2f}".format(
            "Sin BIM_TAG",
            without_tag,
            pct_without
        )
    )

    lineas.append("")
    lineas.append("======= RESUMEN POR CATEGORIA =======")
    lineas.append("")

    lineas.append(
        "{:<35} {:>8} {:>8} {:>8} {:>9} {:>9}".format(
            "Categoria",
            "Total",
            "OK",
            "Falta",
            "% OK",
            "% Falta"
        )
    )

    lineas.append("-" * 85)

    for cat in sorted(resumen_categorias.keys()):

        datos = resumen_categorias[cat]

        total_cat = datos["total"]
        con_tag_cat = datos["con_tag"]
        sin_tag_cat = datos["sin_tag"]

        pct_ok_cat = (
            con_tag_cat * 100.0 / total_cat
            if total_cat > 0 else 0.0
        )

        pct_falta_cat = (
            sin_tag_cat * 100.0 / total_cat
            if total_cat > 0 else 0.0
        )

        lineas.append(
            "{:<35} {:>8} {:>8} {:>8} {:>8.2f}% {:>8.2f}%".format(
                cat[:35],
                total_cat,
                con_tag_cat,
                sin_tag_cat,
                pct_ok_cat,
                pct_falta_cat
            )
        )

    return "\n".join(lineas)


# ================================================================
# RECOLECCION DE ELEMENTOS ESTRUCTURALES
# SOLO VISTA ACTIVA
# ================================================================

def recolectar_elementos_estructurales():

    nombres_categorias = [
        "OST_StructuralFraming",
        "OST_StructuralColumns",
        "OST_StructuralFoundation",
        "OST_StructConnections"
    ]

    categorias = []

    for nombre_cat in nombres_categorias:

        try:
            categorias.append(
                getattr(DB.BuiltInCategory, nombre_cat)
            )
        except:
            pass

    elementos = []

    for cat in categorias:

        try:

            collector = (
                DB.FilteredElementCollector(doc, view.Id)
                .OfCategory(cat)
                .WhereElementIsNotElementType()
            )

            elementos.extend(list(collector))

        except:
            pass

    return elementos


# ================================================================
# PROCESO PRINCIPAL
# ================================================================

def main():

    elementos = recolectar_elementos_estructurales()

    total_count = 0
    with_tag = 0
    without_tag = 0

    elementos_sin_tag = []

    resumen_categorias = {}

    for elem in elementos:

        total_count += 1

        categoria = obtener_categoria(elem)

        if categoria not in resumen_categorias:

            resumen_categorias[categoria] = {
                "total": 0,
                "con_tag": 0,
                "sin_tag": 0
            }

        resumen_categorias[categoria]["total"] += 1

        if tiene_bim_tag(elem):

            with_tag += 1
            resumen_categorias[categoria]["con_tag"] += 1

        else:

            without_tag += 1
            resumen_categorias[categoria]["sin_tag"] += 1
            elementos_sin_tag.append(elem)

    pct_with = (
        with_tag * 100.0 / total_count
        if total_count > 0 else 0.0
    )

    pct_without = (
        without_tag * 100.0 / total_count
        if total_count > 0 else 0.0
    )

    resumen = construir_resumen_general(
        total_count,
        with_tag,
        without_tag,
        pct_with,
        pct_without,
        resumen_categorias
    )

    TaskDialog.Show(
        "Resumen BIM_TAG",
        resumen
    )

    # ------------------------------------------------------------
    # SI NO HAY ELEMENTOS EN LAS CATEGORIAS REVISADAS
    # ------------------------------------------------------------

    if total_count == 0:

        TaskDialog.Show(
            "BIM_TAG",
            "No se encontraron elementos estructurales visibles en la vista activa."
        )

        return

    # ------------------------------------------------------------
    # SI NO HAY ELEMENTOS SIN TAG
    # ------------------------------------------------------------

    if len(elementos_sin_tag) == 0:

        TaskDialog.Show(
            "BIM_TAG",
            "Todos los elementos estructurales visibles poseen BIM_TAG."
        )

        return

    # ------------------------------------------------------------
    # PREGUNTAR SI DESEA AISLAR
    # ------------------------------------------------------------

    desea_aislar = preguntar_si_no(
        "Aislar elementos",
        "{} elementos estructurales no poseen BIM_TAG.".format(
            len(elementos_sin_tag)
        ),
        "Deseas aislar temporalmente estos elementos en la vista activa?"
    )

    if desea_aislar:

        aislar_elementos(elementos_sin_tag)

        TaskDialog.Show(
            "Aislamiento Temporal",
            "{} elementos sin BIM_TAG han sido aislados temporalmente en la vista activa.".format(
                len(elementos_sin_tag)
            )
        )

    # ------------------------------------------------------------
    # PREGUNTAR SI DESEA SELECCIONAR ELEMENTOS
    # ------------------------------------------------------------

    desea_seleccionar = preguntar_si_no(
        "Seleccionar elementos",
        "Deseas seleccionar los elementos sin BIM_TAG?",
        (
            "Los elementos quedaran seleccionados en Revit para facilitar "
            "su revision, modificacion o creacion de filtros/selection sets."
        )
    )

    if desea_seleccionar:

        exito = seleccionar_elementos(
            elementos_sin_tag
        )

        if exito:

            TaskDialog.Show(
                "Seleccion completada",
                "{} elementos sin BIM_TAG fueron seleccionados.".format(
                    len(elementos_sin_tag)
                )
            )

        else:

            TaskDialog.Show(
                "Seleccion",
                "No fue posible seleccionar los elementos sin BIM_TAG."
            )

    # ------------------------------------------------------------
    # PREGUNTAR SI DESEA EXPORTAR CSV
    # ------------------------------------------------------------

    desea_exportar_csv = preguntar_si_no(
        "Exportar CSV",
        "Deseas exportar el listado de elementos sin BIM_TAG a CSV?",
        (
            "El archivo CSV incluira fecha, usuario, semaforo de calidad, "
            "resumen estadistico, resumen por categoria, ranking por faltantes, "
            "workset, nivel y listado completo de elementos sin BIM_TAG."
        )
    )

    if desea_exportar_csv:

        exportar_csv(
            elementos_sin_tag,
            total_count,
            with_tag,
            without_tag,
            pct_with,
            pct_without,
            resumen_categorias
        )


if __name__ == "__main__":
    main()