# -*- coding: utf-8 -*-
"""
RebarTool Pro v3.0.5
Versión corregida para pyRevit CPython3 + Revit 2026.

Correcciones principales:
- XAML limpio, sin HTML ni entidades &lt; / &gt;.
- Eventos WPF simplificados para evitar ejecuciones múltiples.
- Filtro de selección incluye StructuralColumns y Columns.
- Validación de host con RebarHostData.
- Diagnóstico mejorado.
- Motor activo: Columnas.
"""

import clr
import traceback

clr.AddReference("RevitAPI")
clr.AddReference("RevitAPIUI")
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")
clr.AddReference("System")
clr.AddReference("System.Xml")

from System.Collections.Generic import List
from System.Windows import Visibility, RoutedEventHandler
from System.Windows.Markup import XamlReader
from System.Xml import XmlReader
from System.IO import StringReader
from System.Windows.Media import SolidColorBrush, Color
from System.Windows.Controls import ComboBoxItem, TextChangedEventHandler

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    Transaction,
    XYZ,
    Line,
    Curve,
    ElementId,
    Element,
    BuiltInParameter,
    BuiltInCategory
)

from Autodesk.Revit.DB.Structure import (
    Rebar,
    RebarBarType,
    RebarStyle,
    RebarHookType,
    RebarHookOrientation,
    RebarShape,
    RebarHostData
)

from Autodesk.Revit.UI import TaskDialog
from Autodesk.Revit.UI.Selection import ObjectType, ISelectionFilter


# ------------------------------------------------------------
# Documento activo
# ------------------------------------------------------------

uidoc = None
doc = None

try:
    uidoc = __revit__.ActiveUIDocument
    doc = uidoc.Document
except Exception:
    try:
        from pyrevit import revit
        uidoc = revit.uidoc
        doc = revit.doc
    except Exception:
        uidoc = None
        doc = None


# ------------------------------------------------------------
# Categorías
# ------------------------------------------------------------

CAT_FOUNDATION = [
    BuiltInCategory.OST_StructuralFoundation
]

CAT_COLUMN = [
    BuiltInCategory.OST_StructuralColumns,
    BuiltInCategory.OST_Columns
]

CAT_BEAM = [
    BuiltInCategory.OST_StructuralFraming
]

CAT_WALL = [
    BuiltInCategory.OST_Walls
]

CAT_PILE = [
    BuiltInCategory.OST_StructuralFoundation,
    BuiltInCategory.OST_StructuralColumns,
    BuiltInCategory.OST_Columns
]


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def mm(value):
    return float(value) / 304.8


def ft_to_mm(value):
    return round(float(value) * 304.8)


def safe_f(text, default=0.0):
    try:
        return float(str(text).replace(",", "."))
    except Exception:
        return default


def safe_i(text, default=0):
    try:
        return int(float(str(text).replace(",", ".")))
    except Exception:
        return default


def get_bool(cb):
    try:
        return bool(cb.IsChecked)
    except Exception:
        return False


def element_id_value(eid):
    if eid is None:
        return None

    try:
        return eid.Value
    except Exception:
        pass

    try:
        return eid.IntegerValue
    except Exception:
        pass

    try:
        return int(str(eid))
    except Exception:
        return None


def make_element_id(value):
    if isinstance(value, ElementId):
        return value

    try:
        return ElementId(value)
    except Exception:
        pass

    try:
        return ElementId(int(value))
    except Exception:
        pass

    try:
        return ElementId(value.value__)
    except Exception:
        raise


def to_curve_list(curves):
    out = List[Curve]()
    for curve in curves:
        out.Add(curve)
    return out


def revit_element_name(element, fallback="Sin nombre"):
    if element is None:
        return fallback

    try:
        name = Element.Name.GetValue(element)
        if name:
            return str(name)
    except Exception:
        pass

    try:
        param = element.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM)
        if param:
            name = param.AsString()
            if name:
                return str(name)
    except Exception:
        pass

    try:
        name = element.Name
        if name:
            return str(name)
    except Exception:
        pass

    try:
        if element.Category and element.Category.Name:
            return str(element.Category.Name)
    except Exception:
        pass

    return fallback


def bbox_dims(element):
    try:
        bb = element.get_BoundingBox(None)
        if bb is None:
            return None, None, None

        dx = ft_to_mm(bb.Max.X - bb.Min.X)
        dy = ft_to_mm(bb.Max.Y - bb.Min.Y)
        dz = ft_to_mm(bb.Max.Z - bb.Min.Z)
        return dx, dy, dz
    except Exception:
        return None, None, None


def supports_rebar_host(element):
    if element is None:
        return False, "Elemento nulo."

    try:
        rhd = RebarHostData.GetRebarHostData(element)
        if rhd is None:
            return False, "El elemento seleccionado no soporta armaduras como host. Usa una columna estructural de hormigón o una familia habilitada para rebar."
        return True, ""
    except Exception as ex:
        return False, "No se pudo validar RebarHostData: {}".format(str(ex))


# ------------------------------------------------------------
# Filtro de selección
# ------------------------------------------------------------

class CategoryFilter(ISelectionFilter):
    def __init__(self, categories):
        self.cat_ids = set()

        for cat in categories:
            try:
                eid = make_element_id(cat)
                self.cat_ids.add(element_id_value(eid))
            except Exception:
                pass

    def AllowElement(self, element):
        try:
            if element is None:
                return False

            if element.Category is None:
                return False

            return element_id_value(element.Category.Id) in self.cat_ids
        except Exception:
            return False

    def AllowReference(self, reference, point):
        return False


# ------------------------------------------------------------
# Colectores
# ------------------------------------------------------------

def collect_named(cls, none_label=None):
    if doc is None:
        return [("Sin documento", None)]

    try:
        elements = FilteredElementCollector(doc).OfClass(cls).ToElements()
        result = []

        for element in elements:
            result.append((revit_element_name(element, "Sin nombre"), element.Id))

        result.sort(key=lambda x: x[0].lower() if x[0] else "")

        if none_label:
            result = [(none_label, None)] + result

        if not result:
            return [("Sin elementos", None)]

        return result

    except Exception:
        print(traceback.format_exc())
        return [("Error leyendo elementos", None)]


def get_bar_types():
    return collect_named(RebarBarType)


def get_hook_types():
    return collect_named(RebarHookType, "Sin gancho")


def get_rebar_shapes():
    return collect_named(RebarShape, "Sin shape específico")


# ------------------------------------------------------------
# Motor de armaduras
# ------------------------------------------------------------

class RebarEngine(object):
    def __init__(self, host, cfg):
        self.host = host
        self.cfg = cfg
        self.failures = []
        self.created_ids = []

    def _bar_type(self, key):
        eid = self.cfg.get(key)

        if eid is None or doc is None:
            return None

        try:
            return doc.GetElement(eid)
        except Exception:
            return None

    def _hook_type(self, key):
        eid = self.cfg.get(key)

        if eid is None or doc is None:
            return None

        try:
            return doc.GetElement(eid)
        except Exception:
            return None

    def _box(self, default_cover):
        try:
            bb = self.host.get_BoundingBox(None)
        except Exception:
            bb = None

        if not bb:
            return None, ["El elemento no tiene bounding box utilizable."]

        cover = mm(self.cfg.get("cover", default_cover))

        xmin = bb.Min.X + cover
        xmax = bb.Max.X - cover
        ymin = bb.Min.Y + cover
        ymax = bb.Max.Y - cover
        zmin = bb.Min.Z + cover
        zmax = bb.Max.Z - cover

        if xmin >= xmax or ymin >= ymax or zmin >= zmax:
            return None, ["El recubrimiento deja dimensiones útiles negativas o nulas."]

        return (xmin, xmax, ymin, ymax, zmin, zmax), []

    def _create_rebar(self, style, bar_t, hook_s, hook_e, normal, curves, label):
        try:
            if not bar_t:
                self.failures.append(label + ": tipo de barra nulo.")
                return 0

            curve_list = to_curve_list(curves)

            rb = Rebar.CreateFromCurves(
                doc,
                style,
                bar_t,
                hook_s,
                hook_e,
                self.host,
                normal,
                curve_list,
                RebarHookOrientation.Left,
                RebarHookOrientation.Left,
                True,
                True
            )

            if rb:
                try:
                    self.created_ids.append(element_id_value(rb.Id))
                except Exception:
                    pass
                return 1

            self.failures.append(label + ": Rebar.CreateFromCurves devolvió None.")
            return 0

        except Exception:
            self.failures.append(label + ":\n" + traceback.format_exc())
            return 0

    def _longitudinal_points(self, xmin, xmax, ymin, ymax):
        nx = max(1, self.cfg.get("col_long_nx", 3))
        ny = max(1, self.cfg.get("col_long_ny", 3))

        if nx > 1:
            xs = [xmin + i * (xmax - xmin) / float(nx - 1) for i in range(nx)]
        else:
            xs = [(xmin + xmax) / 2.0]

        if ny > 1:
            ys = [ymin + i * (ymax - ymin) / float(ny - 1) for i in range(ny)]
        else:
            ys = [(ymin + ymax) / 2.0]

        pts = set()

        for x in xs:
            pts.add((round(x, 6), round(ymin, 6)))
            pts.add((round(x, 6), round(ymax, 6)))

        for y in ys:
            pts.add((round(xmin, 6), round(y, 6)))
            pts.add((round(xmax, 6), round(y, 6)))

        return list(pts)

    def _rect_stirrup(self, bt, hk, x0, x1, y0, y1, z, label):
        curves = [
            Line.CreateBound(XYZ(x0, y0, z), XYZ(x1, y0, z)),
            Line.CreateBound(XYZ(x1, y0, z), XYZ(x1, y1, z)),
            Line.CreateBound(XYZ(x1, y1, z), XYZ(x0, y1, z)),
            Line.CreateBound(XYZ(x0, y1, z), XYZ(x0, y0, z))
        ]

        return self._create_rebar(
            RebarStyle.StirrupTie,
            bt,
            hk,
            hk,
            XYZ(0, 0, 1),
            curves,
            label
        )

    def place_column(self):
        host_ok, host_msg = supports_rebar_host(self.host)
        if not host_ok:
            return {}, [host_msg]

        box, errs = self._box(30)
        if errs:
            return {}, errs

        xmin, xmax, ymin, ymax, zmin, zmax = box

        stats = {}
        pts = self._longitudinal_points(xmin, xmax, ymin, ymax)

        # Barras longitudinales
        if self.cfg.get("col_long_enabled"):
            bt = self._bar_type("col_long_type")
            placed = 0

            if not bt:
                self.failures.append("Barras longitudinales: no hay tipo de barra seleccionado.")
            else:
                for x, y in pts:
                    curves = [
                        Line.CreateBound(
                            XYZ(x, y, zmin),
                            XYZ(x, y, zmax)
                        )
                    ]

                    placed += self._create_rebar(
                        RebarStyle.Standard,
                        bt,
                        None,
                        None,
                        XYZ(1, 0, 0),
                        curves,
                        "Barras longitudinales"
                    )

            stats["Barras longitudinales"] = placed

        # Estribos centrales y confinados
        if self.cfg.get("col_stir_enabled"):
            bt_stir = self._bar_type("col_stir_type")
            hk = self._hook_type("col_stir_hook")

            central_sp = max(mm(self.cfg.get("col_stir_sp", 150)), mm(10))
            zone_sp = max(mm(self.cfg.get("col_zone_sp", 75)), mm(10))
            zone_len = max(mm(self.cfg.get("col_zone_len", 500)), 0)

            central = 0
            confined = 0

            if not bt_stir:
                self.failures.append("Estribos: no hay tipo de barra seleccionado.")
            else:
                if self.cfg.get("col_zone_enabled") and zone_len > 0:
                    # Zona inferior
                    z = zmin
                    z_end_inf = min(zmin + zone_len, zmax)

                    while z <= z_end_inf + 1e-6:
                        confined += self._rect_stirrup(
                            bt_stir,
                            hk,
                            xmin,
                            xmax,
                            ymin,
                            ymax,
                            z,
                            "Estribos confinados inferiores"
                        )
                        z += zone_sp

                    # Zona superior
                    z = max(zmax - zone_len, zmin)
                    while z <= zmax + 1e-6:
                        confined += self._rect_stirrup(
                            bt_stir,
                            hk,
                            xmin,
                            xmax,
                            ymin,
                            ymax,
                            z,
                            "Estribos confinados superiores"
                        )
                        z += zone_sp

                # Zona central
                if self.cfg.get("col_zone_enabled") and zone_len > 0:
                    z0 = zmin + zone_len
                    z1 = zmax - zone_len
                else:
                    z0 = zmin
                    z1 = zmax

                if z0 <= z1:
                    z = z0
                    while z <= z1 + 1e-6:
                        central += self._rect_stirrup(
                            bt_stir,
                            hk,
                            xmin,
                            xmax,
                            ymin,
                            ymax,
                            z,
                            "Estribos centrales"
                        )
                        z += central_sp

            stats["Estribos centrales"] = central
            stats["Estribos confinados"] = confined

        # Dowels / empalmes
        if self.cfg.get("col_dowels_enabled"):
            bt = self._bar_type("col_dowel_type") or self._bar_type("col_long_type")
            below = max(mm(self.cfg.get("col_dowel_below", 600)), 0)
            above = max(mm(self.cfg.get("col_dowel_above", 600)), 0)
            placed = 0

            if not bt:
                self.failures.append("Dowels: no hay tipo de barra seleccionado.")
            else:
                for x, y in pts:
                    curves = [
                        Line.CreateBound(
                            XYZ(x, y, zmin - below),
                            XYZ(x, y, zmin + above)
                        )
                    ]

                    placed += self._create_rebar(
                        RebarStyle.Standard,
                        bt,
                        None,
                        None,
                        XYZ(1, 0, 0),
                        curves,
                        "Dowels / empalmes"
                    )

            stats["Dowels / empalmes"] = placed

        return stats, []

    def run(self, etype):
        if doc is None:
            return False, ["No se pudo obtener el documento activo de Revit."]

        if etype != "COLUMN":
            return False, [
                "En esta versión el motor activo se concentra en COLUMNAS."
            ]

        t = Transaction(doc, "RebarTool Pro v3.0.5 - Columna")

        try:
            t.Start()

            stats, errs = self.place_column()

            if errs:
                t.RollBack()
                return False, errs

            total = sum([int(v) for v in stats.values()]) if stats else 0

            if total <= 0:
                t.RollBack()
                msg = [
                    "No se creó ninguna barra.",
                    "Diagnóstico del motor:"
                ]

                if self.failures:
                    msg.extend(self.failures)
                else:
                    msg.append("Contador en cero sin excepción.")

                return False, msg

            t.Commit()

            try:
                uidoc.RefreshActiveView()
            except Exception:
                pass

            return True, stats

        except Exception:
            try:
                if t.HasStarted():
                    t.RollBack()
            except Exception:
                pass

            return False, [traceback.format_exc()]


# ------------------------------------------------------------
# XAML limpio
# ------------------------------------------------------------

XAML = r'''
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="RebarTool Pro v3.0.5"
        Width="1120"
        Height="790"
        MinWidth="1000"
        MinHeight="690"
        WindowStartupLocation="CenterScreen"
        ResizeMode="CanResize"
        FontFamily="Segoe UI"
        FontSize="13"
        Background="#0F1117">

    <Window.Resources>
        <Style x:Key="Txb" TargetType="TextBox">
            <Setter Property="Background" Value="#242938"/>
            <Setter Property="Foreground" Value="#FFFFFF"/>
            <Setter Property="BorderBrush" Value="#3B4258"/>
            <Setter Property="Padding" Value="9,7"/>
            <Setter Property="Margin" Value="0,4,0,8"/>
        </Style>

        <Style x:Key="Cmb" TargetType="ComboBox">
            <Setter Property="Background" Value="#F9FAFB"/>
            <Setter Property="Foreground" Value="#111827"/>
            <Setter Property="Height" Value="36"/>
            <Setter Property="Padding" Value="8,5"/>
            <Setter Property="Margin" Value="0,4,0,8"/>
            <Setter Property="IsTextSearchEnabled" Value="True"/>
        </Style>

        <Style TargetType="ComboBoxItem">
            <Setter Property="Foreground" Value="#111827"/>
            <Setter Property="Background" Value="#FFFFFF"/>
        </Style>

        <Style TargetType="CheckBox">
            <Setter Property="Foreground" Value="#FFFFFF"/>
            <Setter Property="Margin" Value="0,4,0,4"/>
        </Style>

        <Style x:Key="Btn" TargetType="Button">
            <Setter Property="Padding" Value="14,9"/>
            <Setter Property="FontWeight" Value="SemiBold"/>
            <Setter Property="BorderThickness" Value="0"/>
            <Setter Property="Margin" Value="8,0,0,0"/>
        </Style>

        <Style x:Key="BtnPrimary" TargetType="Button" BasedOn="{StaticResource Btn}">
            <Setter Property="Background" Value="#38BDF8"/>
            <Setter Property="Foreground" Value="#0F1117"/>
        </Style>

        <Style x:Key="BtnGhost" TargetType="Button" BasedOn="{StaticResource Btn}">
            <Setter Property="Background" Value="#2D3145"/>
            <Setter Property="Foreground" Value="#FFFFFF"/>
        </Style>

        <Style x:Key="BtnNav" TargetType="Button">
            <Setter Property="Background" Value="#1A1D27"/>
            <Setter Property="Foreground" Value="#FFFFFF"/>
            <Setter Property="BorderBrush" Value="#333750"/>
            <Setter Property="Padding" Value="14,10"/>
            <Setter Property="Margin" Value="0,0,0,8"/>
            <Setter Property="HorizontalContentAlignment" Value="Left"/>
            <Setter Property="FontWeight" Value="SemiBold"/>
        </Style>

        <Style x:Key="Section" TargetType="Border">
            <Setter Property="Background" Value="#1A1D27"/>
            <Setter Property="BorderBrush" Value="#333750"/>
            <Setter Property="BorderThickness" Value="1"/>
            <Setter Property="CornerRadius" Value="10"/>
            <Setter Property="Padding" Value="16"/>
            <Setter Property="Margin" Value="0,0,0,14"/>
        </Style>
    </Window.Resources>

    <Grid>
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <Border Grid.Row="0" Background="#1A1D27" Padding="22,14">
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                </Grid.ColumnDefinitions>

                <StackPanel>
                    <TextBlock Text="RebarTool Pro v3.0.5" Foreground="#FFFFFF" FontSize="22" FontWeight="Bold"/>
                    <TextBlock Text="Columnas: longitudinales, estribos confinados, dowels y selector Shape" Foreground="#D1D5DB"/>
                </StackPanel>

                <StackPanel Grid.Column="1" Orientation="Horizontal" VerticalAlignment="Center">
                    <Ellipse x:Name="StatusDot" Width="8" Height="8" Fill="#D1D5DB" Margin="0,0,8,0"/>
                    <TextBlock x:Name="StatusTxt" Text="Sin elemento" Foreground="#D1D5DB"/>
                </StackPanel>
            </Grid>
        </Border>

        <Grid Grid.Row="1" Margin="18">
            <Grid.ColumnDefinitions>
                <ColumnDefinition Width="210"/>
                <ColumnDefinition Width="*"/>
                <ColumnDefinition Width="360"/>
            </Grid.ColumnDefinitions>

            <Border Grid.Column="0" Background="#151923" BorderBrush="#333750" BorderThickness="1" CornerRadius="12" Padding="14">
                <StackPanel>
                    <TextBlock Text="MÓDULOS" Foreground="#D1D5DB" FontSize="11" FontWeight="Bold" Margin="0,0,0,10"/>
                    <Button x:Name="NavColumn" Style="{StaticResource BtnNav}" Content="Columnas"/>
                    <Button x:Name="NavFoundation" Style="{StaticResource BtnNav}" Content="Fundaciones (prep.)"/>
                    <Button x:Name="NavBeam" Style="{StaticResource BtnNav}" Content="Vigas (prep.)"/>
                    <Button x:Name="NavWall" Style="{StaticResource BtnNav}" Content="Muros (prep.)"/>
                    <Button x:Name="NavPile" Style="{StaticResource BtnNav}" Content="Pilas (prep.)"/>

                    <Separator Margin="0,12,0,12"/>

                    <TextBlock Text="Plantillas" Foreground="#D1D5DB" FontWeight="Bold"/>
                    <ComboBox x:Name="TemplateCombo" Style="{StaticResource Cmb}"/>
                </StackPanel>
            </Border>

            <ScrollViewer Grid.Column="1" VerticalScrollBarVisibility="Auto" Margin="16,0">
                <Grid>
                    <StackPanel x:Name="ViewStart">
                        <TextBlock Text="Selecciona Columnas" Foreground="#FFFFFF" FontSize="22" FontWeight="Bold"/>
                        <TextBlock Text="Esta versión corrige el motor de columnas y añade dowels, estribos confinados y selector de Shape."
                                   Foreground="#D1D5DB"
                                   TextWrapping="Wrap"
                                   Margin="0,8,0,0"/>
                    </StackPanel>

                    <StackPanel x:Name="ViewColumn" Visibility="Collapsed">
                        <TextBlock Text="Columnas" Foreground="#38BDF8" FontSize="22" FontWeight="Bold"/>

                        <Border Style="{StaticResource Section}">
                            <StackPanel>
                                <TextBlock Text="Geometría y selección" Foreground="#FFFFFF" FontWeight="Bold"/>

                                <Grid Margin="0,10,0,0">
                                    <Grid.ColumnDefinitions>
                                        <ColumnDefinition Width="*"/>
                                        <ColumnDefinition Width="130"/>
                                        <ColumnDefinition Width="130"/>
                                    </Grid.ColumnDefinitions>

                                    <TextBox x:Name="ColTxbElem" Style="{StaticResource Txb}" Text="Seleccionar columna" IsReadOnly="True"/>
                                    <Button x:Name="ColBtnSel" Grid.Column="1" Content="Seleccionar" Style="{StaticResource BtnPrimary}"/>
                                    <Button x:Name="ColBtnApplyLocal" Grid.Column="2" Content="Aplicar" Style="{StaticResource BtnPrimary}"/>
                                </Grid>

                                <Grid>
                                    <Grid.ColumnDefinitions>
                                        <ColumnDefinition/>
                                        <ColumnDefinition/>
                                        <ColumnDefinition/>
                                        <ColumnDefinition/>
                                    </Grid.ColumnDefinitions>

                                    <TextBox x:Name="ColTxbX" Style="{StaticResource Txb}" Text="-" IsReadOnly="True"/>
                                    <TextBox x:Name="ColTxbY" Grid.Column="1" Style="{StaticResource Txb}" Text="-" IsReadOnly="True" Margin="6,4,0,8"/>
                                    <TextBox x:Name="ColTxbZ" Grid.Column="2" Style="{StaticResource Txb}" Text="-" IsReadOnly="True" Margin="6,4,0,8"/>
                                    <TextBox x:Name="ColTxbCover" Grid.Column="3" Style="{StaticResource Txb}" Text="30" Margin="6,4,0,8"/>
                                </Grid>
                            </StackPanel>
                        </Border>

                        <Border Style="{StaticResource Section}">
                            <StackPanel>
                                <TextBlock Text="Barras longitudinales" Foreground="#FFFFFF" FontWeight="Bold"/>
                                <CheckBox x:Name="ColChkLong" Content="Activar" IsChecked="True"/>

                                <TextBlock Text="Tipo de barra" Foreground="#D1D5DB"/>
                                <ComboBox x:Name="ColCmbLong" Style="{StaticResource Cmb}"/>

                                <TextBlock Text="Shape de barra" Foreground="#D1D5DB"/>
                                <ComboBox x:Name="ColCmbLongShape" Style="{StaticResource Cmb}"/>

                                <Grid>
                                    <Grid.ColumnDefinitions>
                                        <ColumnDefinition/>
                                        <ColumnDefinition/>
                                    </Grid.ColumnDefinitions>

                                    <TextBox x:Name="ColTxbLongNX" Style="{StaticResource Txb}" Text="3"/>
                                    <TextBox x:Name="ColTxbLongNY" Grid.Column="1" Style="{StaticResource Txb}" Text="3" Margin="6,4,0,8"/>
                                </Grid>

                                <TextBlock x:Name="ColLblLongInfo" Text="Total estimado: 8 barras perimetrales" Foreground="#38BDF8"/>
                            </StackPanel>
                        </Border>

                        <Border Style="{StaticResource Section}">
                            <StackPanel>
                                <TextBlock Text="Estribos y confinamiento" Foreground="#FFFFFF" FontWeight="Bold"/>
                                <CheckBox x:Name="ColChkStir" Content="Activar estribos" IsChecked="True"/>

                                <TextBlock Text="Tipo de estribo" Foreground="#D1D5DB"/>
                                <ComboBox x:Name="ColCmbStir" Style="{StaticResource Cmb}"/>

                                <TextBlock Text="Shape de estribo" Foreground="#D1D5DB"/>
                                <ComboBox x:Name="ColCmbStirShape" Style="{StaticResource Cmb}"/>

                                <TextBlock Text="Gancho de estribo" Foreground="#D1D5DB"/>
                                <ComboBox x:Name="ColCmbHook" Style="{StaticResource Cmb}"/>

                                <TextBlock Text="Separación central mm" Foreground="#D1D5DB"/>
                                <TextBox x:Name="ColTxbStirSp" Style="{StaticResource Txb}" Text="150"/>

                                <CheckBox x:Name="ColChkZone" Content="Zona confinada" IsChecked="True"/>

                                <TextBlock Text="Separación confinada mm" Foreground="#D1D5DB"/>
                                <TextBox x:Name="ColTxbZoneSp" Style="{StaticResource Txb}" Text="75"/>

                                <TextBlock Text="Longitud confinada mm" Foreground="#D1D5DB"/>
                                <TextBox x:Name="ColTxbZoneLen" Style="{StaticResource Txb}" Text="500"/>
                            </StackPanel>
                        </Border>

                        <Border Style="{StaticResource Section}">
                            <StackPanel>
                                <TextBlock Text="Dowels / empalmes" Foreground="#FFFFFF" FontWeight="Bold"/>
                                <CheckBox x:Name="ColChkDowels" Content="Activar dowels / empalmes" IsChecked="True"/>

                                <TextBlock Text="Tipo de barra dowel" Foreground="#D1D5DB"/>
                                <ComboBox x:Name="ColCmbDowel" Style="{StaticResource Cmb}"/>

                                <TextBlock Text="Shape dowel" Foreground="#D1D5DB"/>
                                <ComboBox x:Name="ColCmbDowelShape" Style="{StaticResource Cmb}"/>

                                <Grid>
                                    <Grid.ColumnDefinitions>
                                        <ColumnDefinition/>
                                        <ColumnDefinition/>
                                    </Grid.ColumnDefinitions>

                                    <TextBox x:Name="ColTxbDowelBelow" Style="{StaticResource Txb}" Text="600"/>
                                    <TextBox x:Name="ColTxbDowelAbove" Grid.Column="1" Style="{StaticResource Txb}" Text="600" Margin="6,4,0,8"/>
                                </Grid>
                            </StackPanel>
                        </Border>
                    </StackPanel>

                    <StackPanel x:Name="ViewPlaceholder" Visibility="Collapsed">
                        <TextBlock x:Name="PlaceholderTitle" Text="Módulo preparado" Foreground="#FFFFFF" FontSize="22" FontWeight="Bold"/>
                        <TextBlock Text="Este módulo queda preparado para la siguiente iteración. El motor corregido se concentra en columnas."
                                   Foreground="#D1D5DB"
                                   TextWrapping="Wrap"
                                   Margin="0,8,0,0"/>
                    </StackPanel>
                </Grid>
            </ScrollViewer>

            <Border Grid.Column="2" Background="#151923" BorderBrush="#333750" BorderThickness="1" CornerRadius="12" Padding="16">
                <StackPanel>
                    <TextBlock Text="Vista previa" Foreground="#FFFFFF" FontSize="18" FontWeight="Bold"/>
                    <TextBlock x:Name="PreviewTitle" Text="Sin módulo" Foreground="#D1D5DB" Margin="0,4,0,12"/>

                    <Border Background="#0F1117" BorderBrush="#2D3145" BorderThickness="1" Padding="12" CornerRadius="8">
                        <TextBlock x:Name="PreviewText"
                                   Text="Selecciona Columnas."
                                   FontFamily="Consolas"
                                   Foreground="#E5E7EB"
                                   FontSize="12"
                                   TextWrapping="Wrap"/>
                    </Border>

                    <TextBlock x:Name="PreviewInfo"
                               Text="Vista previa esquemática. No crea armaduras."
                               Foreground="#E5E7EB"
                               Margin="0,12,0,0"
                               TextWrapping="Wrap"/>
                </StackPanel>
            </Border>
        </Grid>

        <Border Grid.Row="2" Background="#1A1D27" Padding="18">
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="Auto"/>
                    <ColumnDefinition Width="Auto"/>
                    <ColumnDefinition Width="Auto"/>
                </Grid.ColumnDefinitions>

                <TextBlock x:Name="FooterMsg" Text="Selecciona Columnas para comenzar." Foreground="#D1D5DB" VerticalAlignment="Center"/>
                <Button x:Name="BtnDiagnostic" Grid.Column="1" Content="Diagnóstico" Style="{StaticResource BtnGhost}"/>
                <Button x:Name="BtnApply" Grid.Column="2" Content="Aplicar armaduras" Style="{StaticResource BtnPrimary}"/>
                <Button x:Name="BtnClose" Grid.Column="3" Content="Cerrar" Style="{StaticResource BtnGhost}"/>
            </Grid>
        </Border>
    </Grid>
</Window>
'''


# ------------------------------------------------------------
# Ventana WPF
# ------------------------------------------------------------

class RebarToolWindow(object):
    FILTER_CATS = {
        "COLUMN": CAT_COLUMN,
        "FOUNDATION": CAT_FOUNDATION,
        "BEAM": CAT_BEAM,
        "WALL": CAT_WALL,
        "PILE": CAT_PILE
    }

    def __init__(self):
        self.element_type = None
        self.selected_elem_id = None
        self._handlers = []
        self._runtime_ready = False

        self.bar_types = get_bar_types()
        self.hook_types = get_hook_types()
        self.shape_types = get_rebar_shapes()

        self._build()
        self._bind()
        self._populate_all()
        self._set_module(None)
        self._warmup_runtime()

    def _build(self):
        self.w = XamlReader.Load(XmlReader.Create(StringReader(XAML)))
        c = self.w.FindName

        names = [
            "StatusDot",
            "StatusTxt",
            "FooterMsg",
            "BtnDiagnostic",
            "BtnApply",
            "BtnClose",
            "NavColumn",
            "NavFoundation",
            "NavBeam",
            "NavWall",
            "NavPile",
            "TemplateCombo",
            "ViewStart",
            "ViewColumn",
            "ViewPlaceholder",
            "PlaceholderTitle",
            "PreviewTitle",
            "PreviewText",
            "PreviewInfo",
            "ColTxbElem",
            "ColBtnSel",
            "ColBtnApplyLocal",
            "ColTxbX",
            "ColTxbY",
            "ColTxbZ",
            "ColTxbCover",
            "ColChkLong",
            "ColCmbLong",
            "ColCmbLongShape",
            "ColTxbLongNX",
            "ColTxbLongNY",
            "ColLblLongInfo",
            "ColChkStir",
            "ColCmbStir",
            "ColCmbStirShape",
            "ColCmbHook",
            "ColTxbStirSp",
            "ColChkZone",
            "ColTxbZoneSp",
            "ColTxbZoneLen",
            "ColChkDowels",
            "ColCmbDowel",
            "ColCmbDowelShape",
            "ColTxbDowelBelow",
            "ColTxbDowelAbove"
        ]

        for n in names:
            setattr(self, n, c(n))

    def _keep(self, handler):
        self._handlers.append(handler)
        return handler

    def _add_click(self, control, func):
        try:
            def wrapper(sender, args):
                func(sender, args)

            h = self._keep(RoutedEventHandler(wrapper))
            control.Click += h
        except Exception:
            print(traceback.format_exc())

    def _add_text_changed(self, control):
        try:
            def wrapper(sender, args):
                self._preview_changed(sender, args)

            h = self._keep(TextChangedEventHandler(wrapper))
            control.TextChanged += h
        except Exception:
            try:
                control.TextChanged += self._preview_changed
            except Exception:
                pass

    def _bind(self):
        self._add_click(self.NavColumn, lambda s, e: self._set_module("COLUMN"))
        self._add_click(self.NavFoundation, lambda s, e: self._set_module("FOUNDATION"))
        self._add_click(self.NavBeam, lambda s, e: self._set_module("BEAM"))
        self._add_click(self.NavWall, lambda s, e: self._set_module("WALL"))
        self._add_click(self.NavPile, lambda s, e: self._set_module("PILE"))

        self._add_click(self.ColBtnSel, lambda s, e: self._select_element())
        self._add_click(self.ColBtnApplyLocal, self._on_apply)
        self._add_click(self.BtnDiagnostic, self._on_diagnostic)
        self._add_click(self.BtnApply, self._on_apply)
        self._add_click(self.BtnClose, lambda s, e: self.w.Close())

        try:
            self.w.Loaded += self._keep(RoutedEventHandler(self._on_loaded))
        except Exception:
            pass

        text_controls = [
            self.ColTxbCover,
            self.ColTxbLongNX,
            self.ColTxbLongNY,
            self.ColTxbStirSp,
            self.ColTxbZoneSp,
            self.ColTxbZoneLen,
            self.ColTxbDowelBelow,
            self.ColTxbDowelAbove
        ]

        for ctrl in text_controls:
            self._add_text_changed(ctrl)

    def _on_loaded(self, sender, args):
        self._warmup_runtime()

        try:
            self.w.Activate()
        except Exception:
            pass

    def _warmup_runtime(self):
        if self._runtime_ready:
            return

        try:
            _ = doc.Title if doc else None
            _ = uidoc.ActiveView.Id if uidoc and uidoc.ActiveView else None
        except Exception:
            pass

        self._runtime_ready = True

    def _populate_combo(self, cmb, items):
        try:
            cmb.Items.Clear()

            for name, eid in items:
                item = ComboBoxItem()
                item.Content = name
                item.Tag = eid
                cmb.Items.Add(item)

            if cmb.Items.Count > 0:
                cmb.SelectedIndex = 0

        except Exception:
            print(traceback.format_exc())

    def _populate_all(self):
        try:
            self.TemplateCombo.Items.Add("<En sesión>")
            self.TemplateCombo.Items.Add("Columna estándar")
            self.TemplateCombo.SelectedIndex = 0
        except Exception:
            pass

        for cmb in [self.ColCmbLong, self.ColCmbStir, self.ColCmbDowel]:
            self._populate_combo(cmb, self.bar_types)

        for cmb in [self.ColCmbLongShape, self.ColCmbStirShape, self.ColCmbDowelShape]:
            self._populate_combo(cmb, self.shape_types)

        self._populate_combo(self.ColCmbHook, self.hook_types)

    def _set_module(self, etype):
        self._warmup_runtime()

        self.element_type = etype
        self.selected_elem_id = None

        self.ViewStart.Visibility = Visibility.Collapsed
        self.ViewColumn.Visibility = Visibility.Collapsed
        self.ViewPlaceholder.Visibility = Visibility.Collapsed

        if etype is None:
            self.ViewStart.Visibility = Visibility.Visible
            self.FooterMsg.Text = "Selecciona Columnas para comenzar."
        elif etype == "COLUMN":
            self.ViewColumn.Visibility = Visibility.Visible
            self.FooterMsg.Text = "Selecciona una columna estructural."
        else:
            self.ViewPlaceholder.Visibility = Visibility.Visible
            self.PlaceholderTitle.Text = etype + " preparado"
            self.FooterMsg.Text = "Módulo preparado para siguiente iteración."

        self._set_status("Sin elemento", False)
        self._draw_preview()

    def _select_element(self):
        self._warmup_runtime()

        if self.element_type != "COLUMN":
            TaskDialog.Show("RebarTool Pro v3.0.5", "Selecciona el módulo Columnas.")
            return

        if uidoc is None or doc is None:
            TaskDialog.Show("RebarTool Pro v3.0.5", "No se pudo acceder al documento activo de Revit.")
            return

        try:
            self.w.Hide()

            ref = uidoc.Selection.PickObject(
                ObjectType.Element,
                CategoryFilter(CAT_COLUMN),
                "Selecciona una columna"
            )

            elem = doc.GetElement(ref.ElementId)

            ok, msg = supports_rebar_host(elem)
            if not ok:
                TaskDialog.Show("RebarTool Pro v3.0.5 - Host inválido", msg)
                return

            self.selected_elem_id = ref.ElementId

            name = "{} [ID {}]".format(
                revit_element_name(elem, "Elemento"),
                element_id_value(elem.Id)
            )

            dx, dy, dz = bbox_dims(elem)

            self.ColTxbElem.Text = name
            self.ColTxbX.Text = str(dx or "-")
            self.ColTxbY.Text = str(dy or "-")
            self.ColTxbZ.Text = str(dz or "-")

            self._set_status("Listo - " + name, True)
            self.FooterMsg.Text = "Columna seleccionada. Puedes aplicar armaduras."

            self._draw_preview()

        except Exception:
            print(traceback.format_exc())

        finally:
            try:
                self.w.Show()
                self.w.Activate()
                self.w.Focus()
            except Exception:
                pass

    def _preview_changed(self, sender, args):
        try:
            self._draw_preview()
        except Exception:
            pass

    def _draw_preview(self):
        if self.element_type != "COLUMN":
            if self.element_type:
                self.PreviewTitle.Text = "Módulo preparado"
            else:
                self.PreviewTitle.Text = "Sin módulo"

            self.PreviewText.Text = "Selecciona Columnas para el motor activo."
            return

        nx = safe_i(self.ColTxbLongNX.Text, 3)
        ny = safe_i(self.ColTxbLongNY.Text, 3)
        total = max(4, 2 * nx + 2 * ny - 4)

        self.ColLblLongInfo.Text = "Total estimado: {} barras perimetrales".format(total)

        self.PreviewTitle.Text = "Columna: sección + elevación"

        self.PreviewText.Text = (
            "SECCIÓN TRANSVERSAL\n"
            "┌────────────────────┐\n"
            "│ ●              ●   │\n"
            "│                    │\n"
            "│ ●              ●   │\n"
            "└────────────────────┘\n"
            "Barras perimetrales: {}\n\n"
            "ELEVACIÓN\n"
            "Zona confinada sup. @ {} mm\n"
            "├────────────────────┤\n"
            "├────────────────────┤\n"
            "Zona central @ {} mm\n"
            "├────────────────────┤\n"
            "├────────────────────┤\n"
            "Zona confinada inf. @ {} mm\n\n"
            "Dowels: {}\n"
            "Shape long.: {}\n"
            "Shape stir.: {}"
        ).format(
            total,
            safe_f(self.ColTxbZoneSp.Text, 75),
            safe_f(self.ColTxbStirSp.Text, 150),
            safe_f(self.ColTxbZoneSp.Text, 75),
            "Sí" if get_bool(self.ColChkDowels) else "No",
            self._combo_text(self.ColCmbLongShape),
            self._combo_text(self.ColCmbStirShape)
        )

        self.PreviewInfo.Text = "El motor crea longitudinales, estribos centrales, estribos confinados y dowels/empalmes."

    def _combo_tag(self, cmb):
        try:
            if cmb.SelectedItem:
                return cmb.SelectedItem.Tag
            return None
        except Exception:
            return None

    def _combo_text(self, cmb):
        try:
            if cmb.SelectedItem:
                return str(cmb.SelectedItem.Content)
            return ""
        except Exception:
            return ""

    def _collect_config(self):
        return {
            "cover": safe_f(self.ColTxbCover.Text, 30),

            "col_long_enabled": get_bool(self.ColChkLong),
            "col_long_type": self._combo_tag(self.ColCmbLong),
            "col_long_shape": self._combo_tag(self.ColCmbLongShape),
            "col_long_nx": safe_i(self.ColTxbLongNX.Text, 3),
            "col_long_ny": safe_i(self.ColTxbLongNY.Text, 3),

            "col_stir_enabled": get_bool(self.ColChkStir),
            "col_stir_type": self._combo_tag(self.ColCmbStir),
            "col_stir_shape": self._combo_tag(self.ColCmbStirShape),
            "col_stir_hook": self._combo_tag(self.ColCmbHook),
            "col_stir_sp": safe_f(self.ColTxbStirSp.Text, 150),

            "col_zone_enabled": get_bool(self.ColChkZone),
            "col_zone_sp": safe_f(self.ColTxbZoneSp.Text, 75),
            "col_zone_len": safe_f(self.ColTxbZoneLen.Text, 500),

            "col_dowels_enabled": get_bool(self.ColChkDowels),
            "col_dowel_type": self._combo_tag(self.ColCmbDowel),
            "col_dowel_shape": self._combo_tag(self.ColCmbDowelShape),
            "col_dowel_below": safe_f(self.ColTxbDowelBelow.Text, 600),
            "col_dowel_above": safe_f(self.ColTxbDowelAbove.Text, 600)
        }

    def _on_apply(self, sender, args):
        self._warmup_runtime()

        if self.element_type != "COLUMN":
            TaskDialog.Show("RebarTool Pro v3.0.5", "En esta versión el motor activo es Columnas.")
            return

        if not self.selected_elem_id:
            TaskDialog.Show("RebarTool Pro v3.0.5", "Primero selecciona una columna.")
            return

        try:
            host = doc.GetElement(self.selected_elem_id)

            if host is None:
                TaskDialog.Show("RebarTool Pro v3.0.5", "No se encontró el elemento seleccionado.")
                return

            engine = RebarEngine(host, self._collect_config())
            ok, res = engine.run("COLUMN")

            if ok:
                msg = "Se crearon armaduras:\n\n"
                msg += "\n".join(["{}: {}".format(k, v) for k, v in res.items()])
                TaskDialog.Show("RebarTool Pro v3.0.5 - Éxito", msg)
            else:
                TaskDialog.Show(
                    "RebarTool Pro v3.0.5 - Diagnóstico",
                    "\n\n".join([str(x) for x in res])
                )

        except Exception:
            TaskDialog.Show(
                "RebarTool Pro v3.0.5 - Error crítico",
                traceback.format_exc()
            )

    def _on_diagnostic(self, sender, args):
        self._warmup_runtime()

        msg = (
            "Módulo activo: {}\n"
            "Elemento seleccionado: {}\n"
            "Documento activo: {}\n"
            "Tipos de barra encontrados: {}\n"
            "Hooks encontrados: {}\n"
            "Shapes encontrados: {}\n"
            "Runtime inicializado: {}\n"
        ).format(
            self.element_type,
            element_id_value(self.selected_elem_id),
            "Sí" if doc else "No",
            len(self.bar_types),
            len(self.hook_types),
            len(self.shape_types),
            "Sí" if self._runtime_ready else "No"
        )

        TaskDialog.Show("RebarTool Pro v3.0.5 - Diagnóstico", msg)

    def _set_status(self, text, ok=True):
        self.StatusTxt.Text = text

        if ok:
            color = Color.FromRgb(0x34, 0xD3, 0x99)
        else:
            color = Color.FromRgb(0xD1, 0xD5, 0xDB)

        brush = SolidColorBrush(color)
        self.StatusDot.Fill = brush
        self.StatusTxt.Foreground = brush

    def show(self):
        self.w.ShowDialog()


# ------------------------------------------------------------
# Ejecución
# ------------------------------------------------------------

if __name__ == "__main__":
    try:
        if doc is None or uidoc is None:
            TaskDialog.Show(
                "RebarTool Pro v3.0.5",
                "No se pudo acceder al documento activo de Revit."
            )
        else:
            RebarToolWindow().show()

    except Exception:
        TaskDialog.Show(
            "RebarTool Pro v3.0.5 - Error crítico",
            traceback.format_exc()
        ) 