# RebarTool — Configurador de Armaduras para Revit

Herramienta Python para pyRevit que permite colocar armaduras de refuerzo
(barras horizontales, verticales y estribos) en elementos de hormigón
estructural, respetando recubrimientos y definiendo todos los parámetros
desde una interfaz gráfica WPF integrada en Revit.

---

## Requisitos

| Requisito          | Versión mínima |
|--------------------|----------------|
| Autodesk Revit     | 2020           |
| pyRevit            | 4.8+           |
| Python (IronPython)| 2.7 (incluido en pyRevit) |

---

## Instalación

### Opción A — pyRevit Extension (recomendado)

1. Crea la carpeta de extensión:
   ```
   %APPDATA%\pyRevit\Extensions\RebarTool.extension\
   ```
2. Dentro, crea:
   ```
   RebarTool.extension\
   └── RebarTool.tab\
       └── Armado.panel\
           └── RebarTool.pushbutton\
               ├── RebarConfigurator.py   ← script principal
               ├── bundle.yaml
               └── icon.png               ← (opcional)
   ```
3. Abre Revit, ve a **pyRevit → Settings → Custom Extensions** y agrega
   la ruta de la carpeta `.extension`.
4. Haz clic en **Reload** — aparecerá un botón "RebarTool" en la cinta.

### Opción B — Ejecución directa (desarrollo)

Desde la consola de pyRevit (`pyRevit → Developer Tools → IronPython Console`):

```python
import sys
sys.path.append(r"C:\ruta\a\RebarTool")
import RebarConfigurator
```

---

## Uso

1. **Seleccionar elemento**: Haz clic en "🎯 Seleccionar" y elige un
   pilar, viga, losa o muro de hormigón en el modelo.

2. **Recubrimiento**: Define el recubrimiento en mm en el campo
   correspondiente (por defecto 25 mm).

3. **Barras Horizontales** (tab ━━):
   - Selecciona el tipo de barra (Ø8, Ø10, Ø12…)
   - Define cantidad y separación
   - Elige posición (Superior+Inferior, solo Superior, etc.)

4. **Barras Verticales** (tab │):
   - Mismos parámetros, distribuidas en dirección vertical

5. **Estribos** (tab □):
   - Tipo de barra, forma (rectangular/circular/U)
   - Separación central y separación en zona de confinamiento
   - Longitud de zona confinada (extremos del elemento)
   - Tipo de gancho (según catálogo de Revit)

6. **Vista Previa**: Revisa el resumen en el tab 📋 antes de confirmar.

7. **⚡ Colocar Armaduras**: Ejecuta la transacción y coloca todo.

---

## Estructura del código

```
RebarConfigurator.py
│
├── ConcreteFilter          # Filtro de selección (ISelectionFilter)
├── mm_to_feet / feet_to_mm # Conversión de unidades
├── get_rebar_bar_types()   # Lee tipos de barra del documento
├── get_hook_types()        # Lee tipos de gancho del documento
│
├── RebarPlacer             # Motor de colocación de armaduras
│   ├── validate()
│   ├── place_all()
│   ├── _place_horizontal()
│   ├── _place_vertical()
│   └── _place_stirrups()
│
├── XAML (string)           # Definición WPF de la interfaz
│
└── RebarWindow             # Controlador de la ventana
    ├── _build_window()
    ├── _populate_combos()
    ├── _bind_events()
    ├── _on_select()         # Selección de elemento Revit
    ├── _on_place()          # Dispara RebarPlacer
    ├── _collect_config()    # Recoge todos los parámetros de la UI
    └── show()
```

---

## Extensión y personalización

### Agregar más formas de estribo

En `_place_stirrups()` detecta `cfg["stirrup_shape"]` y genera las
curvas correspondientes (triangular, espiral, etc.).

### Soporte para `RebarCover` nativo de Revit

Revit permite asignar `CoverType` al host. Para leerlo:

```python
cover_param = host.get_Parameter(
    BuiltInParameter.CLEAR_COVER_OTHER)
if cover_param:
    cover_ft = cover_param.AsDouble()
```

### Zona confinada automática

La longitud de confinamiento suele ser `max(h_columna/6, dim_mayor, 450 mm)`.
Agrega esta lógica en `_place_stirrups()` después de calcular `n_stirrups`.

---

## Notas importantes

- Los tipos de barra y gancho se leen **del documento activo**. Si el
  proyecto no tiene `RebarBarType` cargados, debes cargarlos desde la
  familia de sistema de Revit antes de usar la herramienta.
- La herramienta usa `Rebar.CreateFromCurves()`. Para geometrías complejas
  (elementos curvos, secciones no rectangulares) se requiere adaptar la
  lógica de generación de curvas.
- Todas las colocaciones se realizan en una sola transacción —
  si ocurre un error parcial, se hace **rollback** completo.

---

## Licencia

MIT — libre para uso profesional y académico.
