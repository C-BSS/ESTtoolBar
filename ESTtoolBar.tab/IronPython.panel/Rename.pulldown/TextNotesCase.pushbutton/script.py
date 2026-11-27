#! python3
# -*- coding: utf-8 -*-
"""
Cambiar el formato de texto en elementos de Revit:
- Notas de texto (TextNote)
- Dimensiones con prefijo/sufijo
- Etiquetas y otros elementos con parámetros de texto

Opciones: MAYÚSCULAS, minúsculas, Sentence Case, Title Case
Compatible con Revit 2026 + pyRevit (Python 3)
"""

from pyrevit import revit, DB
from Autodesk.Revit.UI import TaskDialog, TaskDialogCommandLinkId, TaskDialogResult, TaskDialogCommonButtons
from Autodesk.Revit.UI.Selection import ObjectType   # <-- Import correcto

doc = revit.doc
uidoc = revit.uidoc


# --- Funciones de formato ---
def title_case(text):
    return ' '.join([w.capitalize() for w in text.split()])


def sentence_case(text):
    text = text.strip().lower()
    if not text:
        return text
    result = []
    capitalize_next = True
    for ch in text:
        if capitalize_next and ch.isalpha():
            result.append(ch.upper())
            capitalize_next = False
        else:
            result.append(ch)
        if ch in ".!?":
            capitalize_next = True
    return ''.join(result)


def apply_case(text, case_type):
    if case_type == 'upper':
        return text.upper()
    elif case_type == 'lower':
        return text.lower()
    elif case_type == 'sentence':
        return sentence_case(text)
    elif case_type == 'title':
        return title_case(text)
    return text


# --- Función principal de cambio ---
def change_text_case(element, case_type):
    try:
        if isinstance(element, DB.TextNote):
            original_text = element.Text
            if not original_text.strip():
                return False
            new_text = apply_case(original_text, case_type)
            if new_text != original_text:
                element.Text = new_text
                return True
            return False

        elif hasattr(element, 'NumberOfSegments'):
            changed = False
            for i in range(element.NumberOfSegments):
                seg = element.get_Segment(i)
                if seg.Suffix:
                    seg.Suffix = apply_case(seg.Suffix, case_type)
                    changed = True
                if seg.Prefix:
                    seg.Prefix = apply_case(seg.Prefix, case_type)
                    changed = True
            return changed

        else:
            text_params = ['Text', 'Mark', 'Comments', 'Type Comments']
            changed = False
            for pname in text_params:
                param = element.LookupParameter(pname)
                if param and not param.IsReadOnly and param.StorageType == DB.StorageType.String:
                    original_text = param.AsString()
                    if original_text:
                        new_text = apply_case(original_text, case_type)
                        if new_text != original_text:
                            param.Set(new_text)
                            changed = True
            return changed

    except Exception as e:
        print("Error procesando elemento " + str(element.Id) + ": " + str(e))
        return False


# --- Flujo principal ---
def main():
    selection_ids = uidoc.Selection.GetElementIds()

    if selection_ids:
        elements = [doc.GetElement(id) for id in selection_ids]
    else:
        TaskDialog.Show("Instrucción", "Selecciona los elementos de texto que deseas modificar.")
        picked_refs = uidoc.Selection.PickObjects(ObjectType.Element, "Selecciona elementos de texto")
        elements = [doc.GetElement(ref.ElementId) for ref in picked_refs]

        # Filtrar solo los que tengan texto válido
        valid_elements = []
        for elem in elements:
            if isinstance(elem, DB.TextNote):
                if elem.Text and elem.Text.strip():
                    valid_elements.append(elem)
            elif hasattr(elem, 'NumberOfSegments'):
                valid_elements.append(elem)
            else:
                for pname in ['Text', 'Mark', 'Comments', 'Type Comments']:
                    p = elem.LookupParameter(pname)
                    if p and p.StorageType == DB.StorageType.String:
                        valid_elements.append(elem)
                        break
        elements = valid_elements

    if not elements:
        TaskDialog.Show("Aviso", "No se seleccionaron elementos de texto válidos.")
        return

    # Diálogo para elegir formato
    dialog = TaskDialog("Cambiar Caso de Texto")
    dialog.MainInstruction = "Selecciona el formato de texto:"
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink1, "MAYÚSCULAS")
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink2, "minúsculas")
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink3, "Formato de oración")
    dialog.AddCommandLink(TaskDialogCommandLinkId.CommandLink4, "Formato de Título")
    dialog.CommonButtons = TaskDialogCommonButtons.Cancel
    result = dialog.Show()

    mapping = {
        TaskDialogResult.CommandLink1: "upper",
        TaskDialogResult.CommandLink2: "lower",
        TaskDialogResult.CommandLink3: "sentence",
        TaskDialogResult.CommandLink4: "title"
    }
    case_type = mapping.get(result)
    if not case_type:
        return

    success_count = 0
    t = DB.Transaction(doc, "Cambiar Caso de Texto")
    t.Start()
    for elem in elements:
        if change_text_case(elem, case_type):
            success_count += 1
    t.Commit()

    TaskDialog.Show("Resultado", "Se modificaron " + str(success_count) + " elementos.")


if __name__ == "__main__":
    main()
