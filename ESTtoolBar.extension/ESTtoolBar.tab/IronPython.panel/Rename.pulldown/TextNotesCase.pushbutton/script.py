# -*- coding: utf-8 -*-
"""
Notas: Esta rutina permitirá renombrar las notas de texto seleccionadas en el modelo de Revit.
Permite modificar los nombres mediante mayúsculas, minúsculas, Sentence Case o Title Case.
"""
__author__ = "Sebastián Sáez S."
__min_revit_ver__ = 2022
__python_ver__ = "IronPython 2.7.9"

import clr
import sys

# Referencias necesarias para Revit API
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
from Autodesk.Revit.UI.Selection import *

# Para compatibilidad con IronPython 2.7
try:
    import re
except ImportError:
    # Implementación básica si re no está disponible
    class SimpleRegex:
        @staticmethod
        def split(pattern, text):
            # Implementación simple para dividir por puntos
            result = []
            current = ""
            for char in text:
                if char in '.!?':
                    if current:
                        result.append(current)
                        current = ""
                    result.append(char)
                else:
                    current += char
            if current:
                result.append(current)
            return result
    re = SimpleRegex()

# Variables de entorno de Revit - Compatible con diferentes versiones
try:
    doc = __revit__.ActiveUIDocument.Document
    uidoc = __revit__.ActiveUIDocument
except:
    # Para uso directo en macro de Revit
    try:
        doc = CommandData.Application.ActiveUIDocument.Document
        uidoc = CommandData.Application.ActiveUIDocument
    except:
        # Último intento
        app = Application()
        uidoc = app.ActiveUIDocument
        doc = uidoc.Document

def title_case(text):
    """
    Convierte texto a formato de título (primera letra de cada palabra en mayúscula)
    Compatible con IronPython 2.7
    """
    if not text:
        return text
    
    # Método compatible con IronPython
    words = text.split()
    title_words = []
    
    for word in words:
        if word:
            # Capitalizar primera letra de cada palabra
            if len(word) == 1:
                title_words.append(word.upper())
            else:
                title_words.append(word[0].upper() + word[1:].lower())
        else:
            title_words.append(word)
    
    return ' '.join(title_words)
    """
    Convierte texto a formato de oración (primera letra mayúscula, resto minúscula)
    Compatible con IronPython 2.7
    """
    if not text:
        return text
    
    # Convertir todo a minúsculas primero
    text = text.lower()
    
    # Método compatible con IronPython para capitalizar oraciones
    try:
        # Intentar usar re si está disponible
        sentences = re.split(r'([.!?]+\s*)', text)
        result = []
        
        for i, sentence in enumerate(sentences):
            if i % 2 == 0 and sentence.strip():  # Partes de texto (no puntuación)
                # Capitalizar primera letra de la oración
                sentence = sentence.lstrip()
                if sentence:
                    sentence = sentence[0].upper() + sentence[1:]
            result.append(sentence)
        
        return ''.join(result)
    except:
        # Método alternativo más simple para IronPython
        if not text:
            return text
        
        # Capitalizar después de punto, exclamación o interrogación
        result = list(text)
        capitalize_next = True
        
        for i, char in enumerate(result):
            if capitalize_next and char.isalpha():
                result[i] = char.upper()
                capitalize_next = False
            elif char in '.!?':
                capitalize_next = True
        
        return ''.join(result)

def change_text_case(element, case_type):
    """
    Cambia el caso del texto en un elemento
    case_type: 'upper', 'lower', 'sentence', 'title'
    """
    try:
        # Para elementos de texto (TextNote) - Soporte mejorado
        if isinstance(element, TextNote):
            original_text = element.Text
            if not original_text or original_text.strip() == "":
                return False
                
            if case_type == 'upper':
                new_text = original_text.upper()
            elif case_type == 'lower':
                new_text = original_text.lower()
            elif case_type == 'sentence':
                new_text = sentence_case(original_text)
            elif case_type == 'title':
                new_text = title_case(original_text)
            
            # Verificar si el texto realmente cambió
            if new_text != original_text:
                element.Text = new_text
                return True
            return False
            
        # Para dimensiones con texto personalizado
        elif hasattr(element, 'NumberOfSegments'):
            changed = False
            for i in range(element.NumberOfSegments):
                segment = element.get_Segment(i)
                if segment.Suffix or segment.Prefix:
                    if segment.Suffix:
                        if case_type == 'upper':
                            segment.Suffix = segment.Suffix.upper()
                        elif case_type == 'lower':
                            segment.Suffix = segment.Suffix.lower()
                        elif case_type == 'sentence':
                            segment.Suffix = sentence_case(segment.Suffix)
                        changed = True
                    
                    if segment.Prefix:
                        if case_type == 'upper':
                            segment.Prefix = segment.Prefix.upper()
                        elif case_type == 'lower':
                            segment.Prefix = segment.Prefix.lower()
                        elif case_type == 'sentence':
                            segment.Prefix = sentence_case(segment.Prefix)
                        changed = True
            return changed
        
        # Para etiquetas (tags) y otros elementos con parámetros de texto
        else:
            # Buscar parámetros de texto comunes
            text_params = ['Text', 'Mark', 'Comments', 'Type Comments']
            changed = False
            
            for param_name in text_params:
                param = element.LookupParameter(param_name)
                if param and not param.IsReadOnly and param.StorageType == StorageType.String:
                    original_text = param.AsString()
                    if original_text:
                        if case_type == 'upper':
                            new_text = original_text.upper()
                        elif case_type == 'lower':
                            new_text = original_text.lower()
                        elif case_type == 'sentence':
                            new_text = sentence_case(original_text)
                        elif case_type == 'title':
                            new_text = title_case(original_text)
                        
                        param.Set(new_text)
                        changed = True
            
            return changed
            
    except Exception as e:
        print("Error procesando elemento " + str(element.Id) + ": " + str(e))
        return False

def get_text_elements():
    """
    Obtiene los elementos de texto seleccionados o permite seleccionarlos
    """
    # Verificar si hay elementos seleccionados
    selected_ids = uidoc.Selection.GetElementIds()
    
    if selected_ids:
        elements = [doc.GetElement(id) for id in selected_ids]
        # Filtrar solo elementos que contienen texto
        text_elements = []
        for elem in elements:
            if isinstance(elem, TextNote):
                # Verificar que la nota de texto tiene contenido
                if elem.Text and elem.Text.strip():
                    text_elements.append(elem)
            elif (hasattr(elem, 'NumberOfSegments') or
                  any(elem.LookupParameter(param) for param in ['Text', 'Mark', 'Comments'] 
                      if elem.LookupParameter(param) and elem.LookupParameter(param).StorageType == StorageType.String)):
                text_elements.append(elem)
        
        if text_elements:
            return text_elements
        else:
            TaskDialog.Show("Aviso", "Los elementos seleccionados no contienen texto editable.\n\nAsegúrate de seleccionar:\n• Notas de texto\n• Dimensiones con texto personalizado\n• Etiquetas con texto")
            return None
    
    # Si no hay selección, permitir seleccionar
    try:
        TaskDialog.Show("Instrucción", "Selecciona los elementos de texto que deseas modificar.")
        
        # Crear filtro para elementos de texto - Mejorado para TextNote
        class TextElementFilter(ISelectionFilter):
            def AllowElement(self, element):
                # Priorizar TextNote
                if isinstance(element, TextNote):
                    return True
                # Otros elementos de texto
                return (hasattr(element, 'NumberOfSegments') or
                       any(element.LookupParameter(param) for param in ['Text', 'Mark', 'Comments'] 
                           if element.LookupParameter(param) and element.LookupParameter(param).StorageType == StorageType.String))
            
            def AllowReference(self, reference, point):
                return False
        
        # Seleccionar elementos
        selected_refs = uidoc.Selection.PickObjects(ObjectType.Element, 
                                                   TextElementFilter(), 
                                                   "Selecciona notas de texto y otros elementos de texto")
        
        elements = [doc.GetElement(ref.ElementId) for ref in selected_refs]
        
        # Filtrar elementos vacíos o sin texto válido
        valid_elements = []
        for elem in elements:
            if isinstance(elem, TextNote):
                if elem.Text and elem.Text.strip():
                    valid_elements.append(elem)
            else:
                valid_elements.append(elem)
        
        return valid_elements if valid_elements else None
        
    except Exception:
        # Usuario canceló la selección
        return None

def main():
    """
    Función principal del script
    """
    # Obtener elementos de texto
    text_elements = get_text_elements()
    
    if not text_elements:
        return
    
    # Mostrar diálogo para seleccionar el tipo de caso
    dialog = TaskDialog("Cambiar Caso de Texto")
    dialog.MainInstruction = "Selecciona el tipo de formato para el texto:"
    
    # Contar tipos de elementos
    text_notes = 0
    other_elements = 0
    for elem in text_elements:
        if isinstance(elem, TextNote):
            text_notes += 1
        else:
            other_elements += 1
    
    content_lines = []
    if text_notes > 0:
        content_lines.append("• " + str(text_notes) + " nota(s) de texto")
    if other_elements > 0:
        content_lines.append("• " + str(other_elements) + " otro(s) elemento(s) de texto")
    
    dialog.MainContent = "Se modificarán:\n" + "\n".join(content_lines)
    
    # Agregar botones para cada tipo de caso
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink1, 
                         "MAYÚSCULAS", 
                         "Convertir todo el texto a mayúsculas")
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink2, 
                         "minúsculas", 
                         "Convertir todo el texto a minúsculas")
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink3, 
                         "Formato de oración", 
                         "Primera letra mayúscula, resto minúsculas")
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink4, 
                         "Formato de Título", 
                         "Primera letra de cada palabra en mayúscula")
    
    dialog.CommonButtons = TaskDialogCommonButtons.Cancel
    dialog.DefaultButton = TaskDialogResult.Cancel
    
    result = dialog.Show()
    
    # Determinar el tipo de caso según la selección
    case_type = None
    if result == TaskDialogResult.CommandLink1:
        case_type = 'upper'
    elif result == TaskDialogResult.CommandLink2:
        case_type = 'lower'
    elif result == TaskDialogResult.CommandLink3:
        case_type = 'sentence'
    elif result == TaskDialogResult.CommandLink4:
        case_type = 'title'
    else:
        return  # Usuario canceló
    
    # Iniciar transacción
    with Transaction(doc, "Cambiar Caso de Texto") as trans:
        trans.Start()
        
        success_count = 0
        error_count = 0
        
        for element in text_elements:
            try:
                if change_text_case(element, case_type):
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                # Compatible con IronPython - usar str() explícitamente
                print("Error con elemento " + str(element.Id) + ": " + str(e))
        
        trans.Commit()
        
        # Mostrar resultado
        message = "Operación completada:\n"
        message += "• " + str(success_count) + " elemento(s) modificado(s) exitosamente\n"
        if error_count > 0:
            message += "• " + str(error_count) + " elemento(s) no se pudieron modificar"
        
        TaskDialog.Show("Resultado", message)

# Ejecutar el script
if __name__ == "__main__":
    main()