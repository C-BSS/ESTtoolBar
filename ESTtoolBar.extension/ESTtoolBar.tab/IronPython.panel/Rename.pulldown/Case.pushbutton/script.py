# -*- coding: utf-8 -*-
"""
Notas: Esta rutina permitirá renombrar las vistas o niveles seleccionadas en el modelo de Revit.
Permite modificar los nombres mediante mayúsculas, minúsculas, Sentence Case o Title Case.
"""
__author__ = "Felipe Bonnemaison"
__min_revit_ver__ = 2022
__python_ver__ = "IronPython 2.7.9"

# IMPORTS
from Autodesk.Revit.DB import View, Level, Family, Transaction, FilteredElementCollector
from pyrevit import revit, forms
from pyrevit.forms import SelectFromList

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
            selected_views = forms.select_views()
            if selected_views is None:  # Verificar si el usuario canceló la selección
                forms.alert('No se seleccionaron vistas.', exitscript=True)
            elementos_seleccionados = [doc.GetElement(el_id) for el_id in selected_views]
        
        elif tipo_elemento == Level:
            selected_levels = forms.select_levels()
            if selected_levels is None:  # Verificar si el usuario canceló la selección
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


def sentence_case(string):
    """
    Convierte un texto al formato 'Sentence Case'.
    Args:
        string (str): Texto original.
    Returns:
        str: Texto con la primera letra en mayúscula y el resto en minúsculas.
    """
    if not isinstance(string, str):
        raise ValueError("La entrada debe ser una cadena de texto.")
    if not string:
        return string  # Manejar cadenas vacías o None
    return string[0].upper() + string[1:].lower()  # Capitaliza la primera letra y convierte el resto a minúsculas.


def title_case(string):
    """
    Convierte un texto al formato 'Title Case'.
    Args:
        string: Texto original.
    Returns:
        Texto con la primera letra de cada palabra en mayúscula.
    """
    return string.title()  # Capitaliza la primera letra de cada palabra.


def renombrar_elementos(elementos, conversion_func):
    """
    Renombra los elementos según la función de conversión proporcionada.
    Args:
        elementos: Lista de elementos seleccionados.
        conversion_func: Función que define cómo se modifican los nombres (e.g., str.upper, str.lower).
    """
    t = Transaction(doc, "Renombrar Elementos")
    t.Start()

    for elemento in elementos:
        old_name = elemento.Name
        new_name = conversion_func(old_name)  # Aplicar la conversión

        for i in range(20):  # Máximo 20 intentos para evitar conflictos de nombres
            try:
                elemento.Name = new_name
                print('{} -> {}'.format(old_name, new_name))
                break
            except Exception as e:
                print("Error al renombrar elemento: {}".format(e))
                new_name = "{}_{}".format(new_name.split('_')[0], i + 1)  # Agregar un sufijo numérico
        else:
            print("Error: No se pudo asignar un nombre único para el elemento '{}' después de 20 intentos.".format(old_name))

    t.Commit()


def mostrar_interfaz_usuario():
    """
    Muestra la interfaz al usuario para elegir qué tipo de elementos desea modificar
    (Vistas, Niveles o Familias) y el formato de renombrado (Mayúsculas, Minúsculas, Sentence Case, Title Case).
    Returns:
        tipo_elemento: Tipo de elemento seleccionado (View, Level o Family).
        conversion_func: Función de conversión seleccionada (e.g., str.upper, str.lower, sentence_case, title_case).
    """
    tipo_opciones = {
        "Vistas": View,
        "Niveles": Level,
        "Familias Cargables": Family  # Agregar soporte para familias
    }
    
    tipo_seleccionado = forms.CommandSwitchWindow.show(
        tipo_opciones.keys(),
        message="¿Qué tipo de elementos desea renombrar?"
    )

    if not tipo_seleccionado:
        forms.alert("No se seleccionó ninguna opción de tipo de elemento.", exitscript=True)
    
    tipo_elemento = tipo_opciones[tipo_seleccionado]

    formato_opciones = {
        "UPPER CASE": str.upper,
        "lower case": str.lower,
        "Sentence case": sentence_case,
        "Title Case": title_case
    }

    formato_seleccionado = forms.CommandSwitchWindow.show(
        formato_opciones.keys(),
        message="Seleccione cómo desea modificar los nombres de los elementos:"
    )

    if not formato_seleccionado:
        forms.alert("No se seleccionó ninguna opción de formato.", exitscript=True)

    conversion_func = formato_opciones[formato_seleccionado]

    return tipo_elemento, conversion_func


# MAIN
def main():
    """
    Función principal que ejecuta el script.
    Organiza el flujo de trabajo: selección de elementos, interfaz de usuario y renombrado.
    """
    # Mostrar interfaz al usuario
    tipo_elemento, conversion_func = mostrar_interfaz_usuario()

    # Seleccionar elementos
    elementos_seleccionados = seleccionar_elementos(tipo_elemento)

    # Renombrar elementos
    print(":alien_monster: Inicio del proceso de renombrado... :alien_monster:")
    renombrar_elementos(elementos_seleccionados, conversion_func)
    print(":sign_of_the_horns: ¡Renombrado completado! :sign_of_the_horns:")
    print("Total de elementos procesados: {}".format(len(elementos_seleccionados)))


# Ejecutar el script
if __name__ == '__main__':
    main()