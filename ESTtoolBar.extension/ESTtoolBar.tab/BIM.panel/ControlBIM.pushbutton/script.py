#! python3
# -*- coding: utf-8 -*-

"""
Control QA/QC de parámetros BIM en la vista activa.

Funciones:
- Selección de disciplina: Acero u Hormigón.
- Revisión exclusiva de elementos visibles en la vista activa.
- Validación exclusiva de parámetros compartidos de instancia.
- Clasificación de parámetros:
    OK
    VACIO
    NO ASIGNADO
    NO COMPARTIDO
- Resumen de cumplimiento.
- Aislamiento temporal de elementos observados.
- Selección de elementos observados.
- Exportación a Excel XLSX con cinco hojas:
    1. Resumen
    2. Por categoría
    3. Por parámetro
    4. Elementos observados
    5. Detalle faltantes

Compatible con Revit 2026 y pyRevit CPython3.
Autor original: Sebastián H. Sáez S.
"""

import clr
import getpass
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape, quoteattr

from pyrevit import revit, DB

from Autodesk.Revit.UI import (
    TaskDialog,
    TaskDialogResult,
    TaskDialogCommonButtons,
    TaskDialogCommandLinkId
)

from Autodesk.Revit.DB import ElementId
from System.Collections.Generic import List

clr.AddReference("System.Windows.Forms")

from System.Windows.Forms import (
    SaveFileDialog,
    DialogResult
)


# ================================================================
# EXPORTACION XLSX SEGURA MEDIANTE OPEN XML
# ================================================================
# Sin openpyxl, sin Excel Interop y sin requerir Microsoft Excel.


# ================================================================
# CONFIGURACIÓN
# ================================================================

PARAMETROS_BIM = [
    "BIM_TAG",
    "BIM_WBS",
    "BIM_COMMODITYCODE",
    "BIM_SPECIALTY",
    "BIM_STAGE",
    "BIM_NAME",
    "BIM_DESCRIPTION",
    "BIM_ADVANCECONTROL",
    "BIM_APPROVALSTATUS",
    "BIM_DIMENSION",
    "BIM_WEIGHT",
    "BIM_SECTION",
    "BIM_VOLUME",
    "BIM_GRADE",
    "BIM_MATERIAL",
    "BIM_CALCULATIONMEMORY",
    "BIM_TECHNICALSPECIFICATION",
    "BIM_FACILITIES"
]


CATEGORIAS_CONEXIONES = [
    "OST_StructConnections",
    "OST_StructConnectionAnchors",
    "OST_StructConnectionBolts",
    "OST_StructConnectionPlates"
]


CATEGORIAS_ACERO = [
    "OST_StructuralFraming",
    "OST_StructuralColumns",
    "OST_Floors",
    "OST_GenericModel",
    "OST_Stairs",
    "OST_StairsRailing"
] + CATEGORIAS_CONEXIONES


CATEGORIAS_HORMIGON = [
    "OST_StructuralFraming",
    "OST_StructuralColumns",
    "OST_StructuralFoundation",
    "OST_Floors",
    "OST_Walls",
    "OST_Ramps",
    "OST_Stairs",
    "OST_GenericModel"
] + CATEGORIAS_CONEXIONES


# ================================================================
# DOCUMENTO REVIT
# ================================================================

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView


# ================================================================
# INFORMACIÓN DEL ELEMENTO
# ================================================================

def obtener_element_id(elem):
    try:
        return str(elem.Id.Value)

    except Exception:
        try:
            return str(elem.Id.IntegerValue)

        except Exception:
            return str(elem.Id)


def obtener_categoria(elem):
    try:
        if elem.Category:
            return elem.Category.Name

    except Exception:
        pass

    return "Sin categoría"


def obtener_nombre(elem):
    try:
        return elem.Name or "Sin nombre"

    except Exception:
        return "Sin nombre"


def obtener_tipo_elemento(elem):
    try:
        type_id = elem.GetTypeId()

        if (
            type_id
            and type_id != ElementId.InvalidElementId
        ):
            return doc.GetElement(type_id)

    except Exception:
        pass

    return None


def obtener_familia(elem):
    tipo = obtener_tipo_elemento(elem)

    if tipo:
        try:
            if tipo.FamilyName:
                return tipo.FamilyName

        except Exception:
            pass

    return "Sin familia"


def obtener_tipo(elem):
    tipo = obtener_tipo_elemento(elem)

    if tipo:
        try:
            return tipo.Name or "Sin tipo"

        except Exception:
            pass

    return "Sin tipo"


# ================================================================
# LECTURA DE PARÁMETROS
# ================================================================

def obtener_valor_parametro(param):
    """
    Devuelve el valor del parámetro como texto.

    Admite:
    - String
    - Integer
    - Double
    - ElementId
    """

    if not param:
        return ""

    try:
        if not param.HasValue:
            return ""

    except Exception:
        pass

    try:
        storage_type = param.StorageType

        if storage_type == DB.StorageType.String:
            valor = param.AsString()

            if valor is not None:
                return str(valor).strip()

            return ""

        if storage_type == DB.StorageType.Integer:
            valor_formateado = param.AsValueString()

            if valor_formateado:
                return str(valor_formateado).strip()

            return str(param.AsInteger())

        if storage_type == DB.StorageType.Double:
            valor_formateado = param.AsValueString()

            if valor_formateado:
                return str(valor_formateado).strip()

            return str(param.AsDouble())

        if storage_type == DB.StorageType.ElementId:
            element_id = param.AsElementId()

            if (
                element_id
                and element_id != ElementId.InvalidElementId
            ):
                elemento_referenciado = doc.GetElement(element_id)

                if elemento_referenciado:
                    try:
                        return elemento_referenciado.Name

                    except Exception:
                        pass

                try:
                    return str(element_id.Value)

                except Exception:
                    try:
                        return str(element_id.IntegerValue)

                    except Exception:
                        return str(element_id)

    except Exception:
        pass

    try:
        valor = param.AsValueString()

        if valor:
            return str(valor).strip()

    except Exception:
        pass

    try:
        valor = param.AsString()

        if valor:
            return str(valor).strip()

    except Exception:
        pass

    return ""


def buscar_parametro_compartido_instancia(
    elem,
    nombre_parametro
):
    """
    Busca exclusivamente parámetros disponibles en la instancia.

    No revisa el tipo.

    Si existen parámetros con el mismo nombre, prioriza el que
    esté identificado como parámetro compartido.
    """

    parametros_encontrados = []

    try:
        parametros = elem.GetParameters(nombre_parametro)

        if parametros:
            parametros_encontrados.extend(
                list(parametros)
            )

    except Exception:
        pass

    if not parametros_encontrados:
        try:
            param = elem.LookupParameter(nombre_parametro)

            if param:
                parametros_encontrados.append(param)

        except Exception:
            pass

    if not parametros_encontrados:
        return None, "NO ASIGNADO"

    for param in parametros_encontrados:
        try:
            if param.IsShared:
                return param, "ENCONTRADO"

        except Exception:
            pass

    return parametros_encontrados[0], "NO COMPARTIDO"


def validar_parametro(elem, nombre_parametro):
    param, estado_busqueda = (
        buscar_parametro_compartido_instancia(
            elem,
            nombre_parametro
        )
    )

    if estado_busqueda == "NO ASIGNADO":
        return {
            "parametro": nombre_parametro,
            "estado": "NO ASIGNADO",
            "valor": ""
        }

    if estado_busqueda == "NO COMPARTIDO":
        return {
            "parametro": nombre_parametro,
            "estado": "NO COMPARTIDO",
            "valor": ""
        }

    valor = obtener_valor_parametro(param)

    if valor and valor.strip():
        return {
            "parametro": nombre_parametro,
            "estado": "OK",
            "valor": valor
        }

    return {
        "parametro": nombre_parametro,
        "estado": "VACIO",
        "valor": ""
    }


# ================================================================
# INFORMACIÓN COMPLEMENTARIA
# ================================================================

def obtener_workset(elem):
    try:
        workset = (
            doc.GetWorksetTable()
            .GetWorkset(elem.WorksetId)
        )

        if workset:
            return workset.Name

    except Exception:
        pass

    return "Sin workset"


def obtener_nivel_desde_id(level_id):
    try:
        if (
            level_id
            and level_id != ElementId.InvalidElementId
        ):
            nivel = doc.GetElement(level_id)

            if nivel:
                return nivel.Name

    except Exception:
        pass

    return ""


def obtener_nivel(elem):
    try:
        nivel = obtener_nivel_desde_id(elem.LevelId)

        if nivel:
            return nivel

    except Exception:
        pass

    built_in_params = [
        "INSTANCE_REFERENCE_LEVEL_PARAM",
        "FAMILY_LEVEL_PARAM",
        "SCHEDULE_LEVEL_PARAM",
        "LEVEL_PARAM",
        "WALL_BASE_CONSTRAINT",
        "FLOOR_PARAM_LEVEL",
        "ROOF_CONSTRAINT_LEVEL_PARAM"
    ]

    for nombre_bip in built_in_params:
        try:
            bip = getattr(
                DB.BuiltInParameter,
                nombre_bip
            )

            param = elem.get_Parameter(bip)

            if not param:
                continue

            if not param.HasValue:
                continue

            try:
                nivel = obtener_nivel_desde_id(
                    param.AsElementId()
                )

                if nivel:
                    return nivel

            except Exception:
                pass

            valor = obtener_valor_parametro(param)

            if valor:
                return valor

        except Exception:
            pass

    return "Sin nivel"


# ================================================================
# UTILIDADES
# ================================================================

def texto_seguro(valor):
    if valor is None:
        return ""

    try:
        return (
            str(valor)
            .replace("\n", " ")
            .replace("\r", " ")
            .strip()
        )

    except Exception:
        return ""


def nombre_archivo_seguro(nombre):
    resultado = str(nombre)
    caracteres_invalidos = '\\/:*?"<>|'

    for caracter in caracteres_invalidos:
        resultado = resultado.replace(
            caracter,
            "_"
        )

    return resultado


def obtener_fecha_actual():
    try:
        return datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception:
        return ""


def obtener_usuario_actual():
    try:
        return getpass.getuser()

    except Exception:
        return ""


# ================================================================
# INTERFAZ
# ================================================================

def seleccionar_disciplina():
    dialog = TaskDialog(
        "Control de parámetros BIM"
    )

    dialog.MainInstruction = (
        "Seleccione el perfil de categorías"
    )

    dialog.MainContent = (
        "Se revisarán solamente los elementos visibles en la "
        "vista activa y los parámetros compartidos de instancia."
    )

    dialog.AddCommandLink(
        TaskDialogCommandLinkId.CommandLink1,
        "Acero",
        (
            "Structural Framing, Structural Columns, Connections, "
            "Anchors, Bolts, Plates, Floors, Generic Models, "
            "Stairs y Railings."
        )
    )

    dialog.AddCommandLink(
        TaskDialogCommandLinkId.CommandLink2,
        "Hormigón",
        (
            "Structural Framing, Structural Columns, Connections, "
            "Anchors, Bolts, Plates, Structural Foundations, "
            "Floors, Walls, Ramps, Stairs y Generic Models."
        )
    )

    dialog.CommonButtons = (
        TaskDialogCommonButtons.Cancel
    )

    resultado = dialog.Show()

    if resultado == TaskDialogResult.CommandLink1:
        return "ACERO", CATEGORIAS_ACERO

    if resultado == TaskDialogResult.CommandLink2:
        return "HORMIGON", CATEGORIAS_HORMIGON

    return None, None


def preguntar_si_no(
    titulo,
    instruccion,
    contenido
):
    dialog = TaskDialog(titulo)

    dialog.MainInstruction = instruccion
    dialog.MainContent = contenido

    dialog.CommonButtons = (
        TaskDialogCommonButtons.Yes |
        TaskDialogCommonButtons.No
    )

    return (
        dialog.Show()
        == TaskDialogResult.Yes
    )


# ================================================================
# RECOLECCIÓN
# ================================================================

def recolectar_elementos(
    categorias_configuradas
):
    """
    Recupera instancias visibles en la vista activa.

    Si una categoría BuiltInCategory no está disponible en la
    versión instalada de Revit, se omite sin detener el script.
    """

    elementos_por_id = {}

    for nombre_categoria in categorias_configuradas:
        try:
            categoria = getattr(
                DB.BuiltInCategory,
                nombre_categoria
            )

        except Exception:
            continue

        try:
            collector = (
                DB.FilteredElementCollector(
                    doc,
                    view.Id
                )
                .OfCategory(categoria)
                .WhereElementIsNotElementType()
            )

            for elem in collector:
                elementos_por_id[
                    obtener_element_id(elem)
                ] = elem

        except Exception:
            pass

    return list(elementos_por_id.values())


# ================================================================
# ANÁLISIS
# ================================================================

def inicializar_resumen_parametros():
    resumen = {}

    for nombre_parametro in PARAMETROS_BIM:
        resumen[nombre_parametro] = {
            "ok": 0,
            "vacio": 0,
            "no_asignado": 0,
            "no_compartido": 0
        }

    return resumen


def analizar_elementos(elementos):
    resultados = []
    elementos_observados = []
    resumen_categorias = {}
    resumen_parametros = (
        inicializar_resumen_parametros()
    )

    campos_ok = 0
    campos_faltantes = 0

    for elem in elementos:
        categoria = obtener_categoria(elem)

        if categoria not in resumen_categorias:
            resumen_categorias[categoria] = {
                "total_elementos": 0,
                "elementos_completos": 0,
                "elementos_con_observaciones": 0,
                "campos_ok": 0,
                "campos_faltantes": 0
            }

        resumen_categorias[categoria][
            "total_elementos"
        ] += 1

        validaciones = []
        faltantes = []
        vacios = []
        no_asignados = []
        no_compartidos = []

        for nombre_parametro in PARAMETROS_BIM:
            validacion = validar_parametro(
                elem,
                nombre_parametro
            )

            validaciones.append(validacion)

            estado = validacion["estado"]

            if estado == "OK":
                campos_ok += 1

                resumen_parametros[
                    nombre_parametro
                ]["ok"] += 1

                resumen_categorias[
                    categoria
                ]["campos_ok"] += 1

            else:
                campos_faltantes += 1
                faltantes.append(nombre_parametro)

                resumen_categorias[
                    categoria
                ]["campos_faltantes"] += 1

                if estado == "VACIO":
                    vacios.append(nombre_parametro)

                    resumen_parametros[
                        nombre_parametro
                    ]["vacio"] += 1

                elif estado == "NO ASIGNADO":
                    no_asignados.append(
                        nombre_parametro
                    )

                    resumen_parametros[
                        nombre_parametro
                    ]["no_asignado"] += 1

                elif estado == "NO COMPARTIDO":
                    no_compartidos.append(
                        nombre_parametro
                    )

                    resumen_parametros[
                        nombre_parametro
                    ]["no_compartido"] += 1

        if faltantes:
            elementos_observados.append(elem)

            resumen_categorias[
                categoria
            ]["elementos_con_observaciones"] += 1

        else:
            resumen_categorias[
                categoria
            ]["elementos_completos"] += 1

        resultados.append({
            "elemento": elem,
            "validaciones": validaciones,
            "faltantes": faltantes,
            "vacios": vacios,
            "no_asignados": no_asignados,
            "no_compartidos": no_compartidos
        })

    total_campos = (
        len(elementos) *
        len(PARAMETROS_BIM)
    )

    estadisticas = {
        "total_elementos": len(elementos),

        "elementos_completos": (
            len(elementos) -
            len(elementos_observados)
        ),

        "elementos_con_observaciones": len(
            elementos_observados
        ),

        "total_campos": total_campos,
        "campos_ok": campos_ok,
        "campos_faltantes": campos_faltantes
    }

    estadisticas["porcentaje_cumplimiento"] = (
        campos_ok * 100.0 / total_campos
        if total_campos
        else 0.0
    )

    estadisticas["porcentaje_faltante"] = (
        campos_faltantes * 100.0 / total_campos
        if total_campos
        else 0.0
    )

    return (
        resultados,
        elementos_observados,
        resumen_categorias,
        resumen_parametros,
        estadisticas
    )


# ================================================================
# CALIDAD Y RESUMEN
# ================================================================

def obtener_estado_calidad(porcentaje):
    if porcentaje >= 95.0:
        return "VERDE - EXCELENTE"

    if porcentaje >= 90.0:
        return "AMARILLO - REVISAR"

    return "ROJO - CRÍTICO"


def construir_resumen(
    disciplina,
    estadisticas,
    resumen_parametros
):
    ranking = []

    for nombre, datos in resumen_parametros.items():
        total_observaciones = (
            datos["vacio"] +
            datos["no_asignado"] +
            datos["no_compartido"]
        )

        ranking.append((
            nombre,
            total_observaciones
        ))

    ranking.sort(
        key=lambda item: item[1],
        reverse=True
    )

    lineas = [
        "Disciplina: {}".format(disciplina),
        "Vista activa: {}".format(view.Name),
        "",
        "========== RESUMEN ==========",
        "",
        "Elementos revisados: {}".format(
            estadisticas["total_elementos"]
        ),
        "Elementos completos: {}".format(
            estadisticas["elementos_completos"]
        ),
        "Elementos con observaciones: {}".format(
            estadisticas[
                "elementos_con_observaciones"
            ]
        ),
        "",
        "Campos evaluados: {}".format(
            estadisticas["total_campos"]
        ),
        "Campos informados: {}".format(
            estadisticas["campos_ok"]
        ),
        "Campos faltantes: {}".format(
            estadisticas["campos_faltantes"]
        ),
        "Cumplimiento: {:.2f}%".format(
            estadisticas[
                "porcentaje_cumplimiento"
            ]
        ),
        "Estado: {}".format(
            obtener_estado_calidad(
                estadisticas[
                    "porcentaje_cumplimiento"
                ]
            )
        ),
        "",
        "Parámetros con más observaciones:"
    ]

    for nombre, total in ranking[:8]:
        lineas.append(
            "{}: {}".format(
                nombre,
                total
            )
        )

    return "\n".join(lineas)


# ================================================================
# EXCEL: SELECCIÓN DE RUTA
# ================================================================

def seleccionar_ruta_excel(disciplina):
    dialog = SaveFileDialog()

    dialog.Title = (
        "Guardar reporte de parámetros BIM"
    )

    dialog.Filter = (
        "Libro de Excel (*.xlsx)|*.xlsx"
    )

    dialog.DefaultExt = "xlsx"
    dialog.AddExtension = True

    dialog.FileName = (
        "Reporte_Parametros_BIM_{}_{}.xlsx"
        .format(
            disciplina,
            nombre_archivo_seguro(view.Name)
        )
    )

    resultado = dialog.ShowDialog()

    if resultado == DialogResult.OK:
        return dialog.FileName

    return None


# ================================================================
# XLSX OPEN XML
# ================================================================

def a_unicode(valor):
    try:
        return unicode(valor)
    except NameError:
        return str(valor)
    except Exception:
        return u""


def limpiar_texto_xml(valor):
    texto = a_unicode(valor)
    salida = []
    for caracter in texto:
        codigo = ord(caracter)
        permitido = (
            codigo in (0x09, 0x0A, 0x0D) or
            0x20 <= codigo <= 0xD7FF or
            0xE000 <= codigo <= 0xFFFD or
            0x10000 <= codigo <= 0x10FFFF
        )
        salida.append(caracter if permitido and codigo not in (0xFFFE, 0xFFFF) else u" ")
    return u"".join(salida)


def limpiar_nombre_hoja(nombre, usados):
    nombre = limpiar_texto_xml(nombre)
    for caracter in [u"[", u"]", u":", u"*", u"?", u"/", u"\\"]:
        nombre = nombre.replace(caracter, u"-")
    nombre = nombre.strip().strip(u"'") or u"Hoja"
    nombre = nombre[:31]
    base = nombre
    contador = 2
    while nombre.upper() in usados:
        sufijo = u" ({})".format(contador)
        nombre = base[:31-len(sufijo)] + sufijo
        contador += 1
    usados.add(nombre.upper())
    return nombre


def columna_excel(numero):
    texto = ""
    while numero:
        numero, resto = divmod(numero - 1, 26)
        texto = chr(65 + resto) + texto
    return texto


def celda_xml(fila, columna, valor, estilo=0):
    referencia = columna_excel(columna) + str(fila)
    estilo_txt = ' s="{}"'.format(estilo) if estilo else ""
    if isinstance(valor, bool):
        return '<c r="{}"{} t="b"><v>{}</v></c>'.format(referencia, estilo_txt, 1 if valor else 0)
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return '<c r="{}"{}><v>{}</v></c>'.format(referencia, estilo_txt, valor)
    texto = escape(limpiar_texto_xml(valor))
    return '<c r="{}"{} t="inlineStr"><is><t xml:space="preserve">{}</t></is></c>'.format(
        referencia, estilo_txt, texto)


def ancho_columna(datos, indice, minimo=12, maximo=60):
    ancho = minimo
    for fila in datos:
        if indice < len(fila):
            ancho = max(ancho, len(limpiar_texto_xml(fila[indice])) + 2)
    return min(ancho, maximo)


def hoja_xml(titulo, columnas, filas, porcentajes=None, columna_estado=None):
    porcentajes = porcentajes or []
    datos = [[titulo]] + [columnas] + filas
    cantidad_columnas = max(1, len(columnas))
    ultima_columna = columna_excel(cantidad_columnas)
    ultima_fila = max(2, len(datos))
    partes = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="2" topLeftCell="A3" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>',
        '<sheetFormatPr defaultRowHeight="15"/>', '<cols>'
    ]
    for indice in range(cantidad_columnas):
        partes.append('<col min="{0}" max="{0}" width="{1}" customWidth="1"/>'.format(
            indice + 1, ancho_columna(datos, indice)))
    partes.extend(['</cols>', '<sheetData>'])
    for indice_fila, valores in enumerate(datos, 1):
        partes.append('<row r="{}">'.format(indice_fila))
        for indice_columna, valor in enumerate(valores, 1):
            estilo = 1 if indice_fila == 1 else 2 if indice_fila == 2 else 0
            if indice_fila > 2 and valores and limpiar_texto_xml(valores[0]).upper() == 'TOTAL':
                estilo = 3
            elif indice_fila > 2 and indice_columna in porcentajes:
                estilo = 4
            if columna_estado and indice_fila > 2 and indice_columna == columna_estado:
                estado = limpiar_texto_xml(valor).upper()
                estilo = {'VACIO':5, 'NO ASIGNADO':6, 'NO COMPARTIDO':7}.get(estado, estilo)
            partes.append(celda_xml(indice_fila, indice_columna, valor, estilo))
        partes.append('</row>')
    partes.extend(['</sheetData>', '<autoFilter ref="A2:{}{}"/>'.format(ultima_columna, ultima_fila), '</worksheet>'])
    return u"".join(partes).encode('utf-8')


def estilos_xml():
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="1"><numFmt numFmtId="164" formatCode="0.00%"/></numFmts>'
        '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="14"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="8"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF4472C4"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFD9EAF7"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFE699"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFF4B084"/><bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFF9999"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="8">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="5" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="6" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="7" borderId="0" xfId="0" applyFill="1"/>'
        '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
    ).encode('utf-8')


def exportar_xlsx(ruta, hojas):
    usados = set()
    nombres = [limpiar_nombre_hoja(hoja[0], usados) for hoja in hojas]
    tipos = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    ]
    libro = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    relaciones = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for indice, nombre in enumerate(nombres, 1):
        tipos.append('<Override PartName="/xl/worksheets/sheet{}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'.format(indice))
        libro.append('<sheet name={} sheetId="{}" r:id="rId{}"/>'.format(quoteattr(nombre), indice, indice))
        relaciones.append('<Relationship Id="rId{}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{}.xml"/>'.format(indice, indice))
    tipos.append('</Types>')
    libro.append('</sheets></workbook>')
    relaciones.append('<Relationship Id="rId{}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'.format(len(hojas)+1))
    relaciones.append('</Relationships>')
    raiz = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    archivo = zipfile.ZipFile(ruta, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
    try:
        archivo.writestr('[Content_Types].xml', u''.join(tipos).encode('utf-8'))
        archivo.writestr('_rels/.rels', raiz.encode('utf-8'))
        archivo.writestr('xl/workbook.xml', u''.join(libro).encode('utf-8'))
        archivo.writestr('xl/_rels/workbook.xml.rels', u''.join(relaciones).encode('utf-8'))
        archivo.writestr('xl/styles.xml', estilos_xml())
        for indice, hoja in enumerate(hojas, 1):
            opciones = hoja[3] if len(hoja) > 3 else {}
            archivo.writestr('xl/worksheets/sheet{}.xml'.format(indice), hoja_xml(
                hoja[0], hoja[1], hoja[2], opciones.get('porcentajes', []), opciones.get('columna_estado')))
    finally:
        archivo.close()


def exportar_excel(disciplina, resultados, resumen_categorias, resumen_parametros, estadisticas):
    ruta = seleccionar_ruta_excel(disciplina)
    if not ruta:
        return
    if not ruta.lower().endswith('.xlsx'):
        ruta += '.xlsx'
    try:
        resumen = [
            ['Proyecto', texto_seguro(doc.Title)], ['Vista activa', texto_seguro(view.Name)],
            ['Disciplina', disciplina], ['Fecha', obtener_fecha_actual()], ['Usuario', obtener_usuario_actual()],
            ['Total elementos', estadisticas['total_elementos']], ['Elementos completos', estadisticas['elementos_completos']],
            ['Elementos con observaciones', estadisticas['elementos_con_observaciones']],
            ['Campos evaluados', estadisticas['total_campos']], ['Campos OK', estadisticas['campos_ok']],
            ['Campos faltantes', estadisticas['campos_faltantes']],
            ['Cumplimiento', estadisticas['porcentaje_cumplimiento']/100.0],
            ['Faltante', estadisticas['porcentaje_faltante']/100.0],
            ['Estado QA-QC', obtener_estado_calidad(estadisticas['porcentaje_cumplimiento'])]
        ]
        categorias = []
        for cat in sorted(resumen_categorias):
            datos = resumen_categorias[cat]
            total = datos['total_elementos']
            categorias.append([cat, total, datos['elementos_completos'], datos['elementos_con_observaciones'],
                               datos['campos_ok'], datos['campos_faltantes'],
                               datos['elementos_completos']/float(total) if total else 0.0])
        parametros = []
        for nombre in PARAMETROS_BIM:
            datos = resumen_parametros[nombre]
            obs = datos['vacio'] + datos['no_asignado'] + datos['no_compartido']
            total = datos['ok'] + obs
            parametros.append([nombre, datos['ok'], datos['vacio'], datos['no_asignado'], datos['no_compartido'], obs,
                               datos['ok']/float(total) if total else 0.0])
        elementos = []
        detalle = []
        for resultado in resultados:
            elem = resultado['elemento']
            base = [obtener_element_id(elem), obtener_categoria(elem), obtener_familia(elem), obtener_tipo(elem),
                    obtener_nombre(elem), obtener_workset(elem), obtener_nivel(elem)]
            if resultado['faltantes']:
                elementos.append(base + [len(resultado['faltantes']), ', '.join(resultado['vacios']),
                                          ', '.join(resultado['no_asignados']), ', '.join(resultado['no_compartidos']),
                                          ', '.join(resultado['faltantes'])])
            for validacion in resultado['validaciones']:
                if validacion['estado'] != 'OK':
                    detalle.append(base + [validacion['parametro'], validacion['estado'], validacion['valor']])
        hojas = [
            ('Resumen', ['Indicador','Valor'], resumen, {'porcentajes':[2]}),
            ('Por categoria', ['Categoria','Total','Completos','Con observaciones','Campos OK','Campos faltantes','% completos'], categorias, {'porcentajes':[7]}),
            ('Por parametro', ['Parametro','OK','Vacio','No asignado','No compartido','Total observaciones','% cumplimiento'], parametros, {'porcentajes':[7]}),
            ('Elementos observados', ['ElementId','Categoria','Familia','Tipo','Nombre','Workset','Nivel','Cantidad faltantes','Vacios','No asignados','No compartidos','Todos los faltantes'], elementos, {}),
            ('Detalle faltantes', ['ElementId','Categoria','Familia','Tipo','Nombre','Workset','Nivel','Parametro','Estado','Valor'], detalle, {'columna_estado':9})
        ]
        exportar_xlsx(ruta, hojas)
        TaskDialog.Show('Exportar Excel', 'Reporte XLSX exportado correctamente:\n\n{}'.format(ruta))
    except Exception as ex:
        TaskDialog.Show('Error al exportar Excel', 'No fue posible generar el archivo XLSX.\n\nDetalle:\n{}'.format(str(ex)))


# ================================================================
# AISLAMIENTO Y SELECCIÓN
# ================================================================

def crear_lista_ids(elementos):
    ids = List[ElementId]()

    for elem in elementos:
        ids.Add(elem.Id)

    return ids


def aislar_elementos(elementos):
    if not elementos:
        return False

    try:
        ids = crear_lista_ids(elementos)

        with revit.Transaction(
            "Aislar elementos con parámetros BIM faltantes"
        ):
            view.IsolateElementsTemporary(ids)

        try:
            uidoc.ShowElements(ids)

        except Exception:
            pass

        return True

    except Exception:
        return False


def seleccionar_elementos(elementos):
    if not elementos:
        return False

    try:
        ids = crear_lista_ids(elementos)

        uidoc.Selection.SetElementIds(ids)

        try:
            uidoc.ShowElements(ids)

        except Exception:
            pass

        return True

    except Exception:
        return False


# ================================================================
# PROCESO PRINCIPAL
# ================================================================

def main():
    disciplina, categorias = seleccionar_disciplina()

    if not disciplina:
        return

    elementos = recolectar_elementos(
        categorias
    )

    if not elementos:
        TaskDialog.Show(
            "Control BIM",
            (
                "No se encontraron elementos visibles de las "
                "categorías configuradas en la vista activa."
            )
        )

        return

    (
        resultados,
        elementos_observados,
        resumen_categorias,
        resumen_parametros,
        estadisticas
    ) = analizar_elementos(elementos)

    TaskDialog.Show(
        "Control BIM",
        construir_resumen(
            disciplina,
            estadisticas,
            resumen_parametros
        )
    )

    if elementos_observados:
        desea_aislar = preguntar_si_no(
            "Aislar elementos",
            "{} elementos tienen observaciones.".format(
                len(elementos_observados)
            ),
            (
                "¿Deseas aislarlos temporalmente en la "
                "vista activa?"
            )
        )

        if desea_aislar:
            exito = aislar_elementos(
                elementos_observados
            )

            if not exito:
                TaskDialog.Show(
                    "Aislamiento",
                    (
                        "No fue posible aislar los elementos "
                        "en la vista activa."
                    )
                )

        desea_seleccionar = preguntar_si_no(
            "Seleccionar elementos",
            (
                "¿Deseas seleccionar los elementos "
                "con observaciones?"
            ),
            (
                "La selección facilitará su revisión "
                "y corrección en Revit."
            )
        )

        if desea_seleccionar:
            exito = seleccionar_elementos(
                elementos_observados
            )

            if not exito:
                TaskDialog.Show(
                    "Selección",
                    (
                        "No fue posible seleccionar "
                        "los elementos."
                    )
                )

    desea_exportar = preguntar_si_no(
        "Exportar Excel",
        "¿Deseas exportar el reporte a Excel?",
        (
            "Se generará un archivo XLSX con hojas separadas "
            "para resumen, categorías, parámetros, elementos "
            "observados y detalle de faltantes."
        )
    )

    if desea_exportar:
        exportar_excel(
            disciplina,
            resultados,
            resumen_categorias,
            resumen_parametros,
            estadisticas
        )


# ================================================================
# EJECUCIÓN
# ================================================================

if __name__ == "__main__":
    main()