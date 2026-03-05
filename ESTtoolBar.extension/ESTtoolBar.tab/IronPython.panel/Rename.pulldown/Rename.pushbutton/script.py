# -*- coding: utf-8 -*-
"""
Notas: Este script permite renombrar elementos de un modelo de Revit, 
como vistas, niveles o familias, mediante la adición de prefijos, 
buscar y reemplazar, y sufijos.
"""
__author__ = "Felipe Bonnemaison"
__min_revit_ver__ = 2022
__python_ver__ = "IronPython 2.7.9"

# IMPORTS
from Autodesk.Revit.DB import View, Level, Family, Transaction, FilteredElementCollector
from pyrevit import revit, forms
from rpw.ui.forms import FlexForm, Label, TextBox, Separator, Button

# VARIABLES
doc = __revit__.ActiveUIDocument.Document  # Documento activo.
uidoc = __revit__.ActiveUIDocument  # Interfaz activa del documento.
app = __revit__.Application  # Hace referencia a la aplicación activa de Revit.


# FUNCIONES
def seleccionar_elementos(tipo_elemento):
    """
    Selecciona los elementos del modelo de Revit.
    Si no hay elementos seleccionados, se abre una interfaz para elegirlos.
    Args:
        tipo_elemento: Clase del tipo de elemento a seleccionar (View, Level, Family, etc.).
    Returns:
        Lista de elementos seleccionados.
    """
    sel_el_ids = uidoc.Selection.GetElementIds()
    sel_elem = [doc.GetElement(el_id) for el_id in sel_el_ids]

    # Filtrar por tipo de elemento
    elementos_seleccionados = [el for el in sel_elem if isinstance(el, tipo_elemento)]

    if not elementos_seleccionados:
        if tipo_elemento == View:
            # forms.select_views() # devuelve directamente una lista de vistas
            selected_views = forms.select_views()  # Interfaz muestra "NOMBRE (TIPO)" de las vistas
            if not selected_views:  # Verificar si el usuario canceló la selección
                forms.alert('No se seleccionaron vistas.', exitscript=True)
            elementos_seleccionados = selected_views  # No necesitas usar doc.GetElement aquí

        elif tipo_elemento == Level:
            selected_levels = forms.select_levels()  # Interfaz muestra solo "NOMBRE" de los niveles
            if not selected_levels:  # Verificar si el usuario canceló la selección
                forms.alert('No se seleccionaron niveles.', exitscript=True)
            elementos_seleccionados = [doc.GetElement(level.Id) for level in selected_levels]

        elif tipo_elemento == Family:
            # Recoger todas las familias cargables del documento
            coleccion_familias = FilteredElementCollector(doc).OfClass(Family).ToElements()
            # Crear una lista con los nombres de las familias cargables y sus tipos
            opciones_familias = {
                fam.Id.IntegerValue: "{} ({})".format(fam.Name, fam.FamilyCategory.Name if fam.FamilyCategory else "Sin categoría")
                for fam in coleccion_familias
            }
            # Mostrar una interfaz para seleccionar las familias
            seleccionados = forms.SelectFromList.show(
                opciones_familias.values(),
                title="Seleccione las familias que desea renombrar",
                multiselect=True
            )  # Interfaz muestra "NOMBRE (TIPO)" de las familias
            if not seleccionados:
                forms.alert('No se seleccionaron familias.', exitscript=True)
            # Filtrar las familias seleccionadas
            elementos_seleccionados = [
                fam for fam in coleccion_familias
                if "{} ({})".format(fam.Name, fam.FamilyCategory.Name if fam.FamilyCategory else "Sin categoría") in seleccionados
            ]

    if not elementos_seleccionados:
        forms.alert('No se seleccionaron elementos.', exitscript=True)

    return elementos_seleccionados


def mostrar_interfaz_usuario_renombrar():
    """
    Muestra una interfaz al usuario para ingresar los valores de prefijo, buscar y reemplazar, y sufijo.
    Returns:
        dict: Diccionario con los valores ingresados por el usuario.
    """
    components = [
        Label('Prefijo:'), TextBox('prefijo'),
        Label('Buscar:'), TextBox('buscar'),
        Label('Reemplazar:'), TextBox('reemplazar'),
        Label('Sufijo:'), TextBox('sufijo'),
        Separator(), Button('Aceptar')
    ]

    form = FlexForm('Renombrar Elementos', components)
    form.show()

    user_inputs = form.values
    if not user_inputs:
        forms.alert("No se ingresaron datos.", exitscript=True)
        
    # Validación de caracteres inválidos
    caracteres_invalidos = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for campo, valor in user_inputs.items():
        if any(char in valor for char in caracteres_invalidos):
            forms.alert("El valor ingresado en '{}' contiene caracteres inválidos: {}".format(campo, caracteres_invalidos), exitscript=True)    

    return user_inputs

def renombrar_elementos(elementos, user_inputs):
    """
    Renombra los elementos utilizando prefijos, buscar y reemplazar, y sufijos.
    Args:
        elementos: Lista de elementos seleccionados.
        user_inputs: Diccionario con los valores ingresados por el usuario (prefijo, buscar, reemplazar, sufijo).
    """
    prefix = user_inputs['prefijo']
    find = user_inputs['buscar']
    replace = user_inputs['reemplazar']
    sufix = user_inputs['sufijo']

    t = Transaction(doc, "Renombrar Elementos")
    t.Start()

    for elemento in elementos:
        old_name = elemento.Name

        # Aplicar prefijo, buscar y reemplazar, y sufijo
        new_name = old_name
        if find and replace:
            new_name = new_name.replace(find, replace)  # Buscar y reemplazar
        new_name = prefix + new_name + sufix  # Aplicar prefijo y sufijo

        for i in range(20):  # Máximo 20 intentos para evitar conflictos de nombres
            try:
                elemento.Name = new_name
                print('{} -> {}'.format(old_name, new_name))
                break
            except Exception as e:
                print("Error al renombrar elemento: {}".format(e))
                new_name = '{}_{}'.format(new_name.split('_')[0], i + 1)  # Agregar un sufijo numérico
        else:
            print("Error: No se pudo asignar un nombre único para el elemento '{}' después de 20 intentos.".format(old_name))

    t.Commit()


# MAIN
def main():
    try:
        # Código principal del script
        tipo_opciones = {
            "Vistas": View,
            "Niveles": Level,
            "Familias Cargables": Family
        }

        tipo_seleccionado = forms.CommandSwitchWindow.show(
            tipo_opciones.keys(),
            message="¿Qué tipo de elementos desea renombrar?"
        )

        if not tipo_seleccionado:
            forms.alert("No se seleccionó ninguna opción de tipo de elemento.", exitscript=True)

        tipo_elemento = tipo_opciones[tipo_seleccionado]

        # Seleccionar elementos
        elementos_seleccionados = seleccionar_elementos(tipo_elemento)

        # Mostrar interfaz al usuario para ingresar prefijo, buscar/reemplazar y sufijo
        user_inputs = mostrar_interfaz_usuario_renombrar()

        # Renombrar elementos
        print(":alien_monster: Inicio del proceso de renombrado... :alien_monster:")
        renombrar_elementos(elementos_seleccionados, user_inputs)
        print(":sign_of_the_horns: ¡Renombrado completado! :sign_of_the_horns:")
        print("Total de elementos procesados: {}".format(len(elementos_seleccionados)))

    except Exception as e:
        forms.alert("Se produjo un error: {}".format(str(e)), title="Error crítico", exitscript=True)


if __name__ == '__main__':
    main()