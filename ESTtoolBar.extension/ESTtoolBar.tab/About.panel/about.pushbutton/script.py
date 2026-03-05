# -*- coding: utf-8 -*-
#pylint: disable=E0401,E0602,W0703,W0613,C0103

# IMPORTS
import sys
import os
from pyrevit import forms
from pyrevit import script
from System.Windows.Media.Imaging import BitmapImage, BitmapCacheOption, BitmapCreateOptions
from System import Uri

# LOGGING
logger = script.get_logger()

# CLASS
class AboutWindow(forms.WPFWindow):
    def __init__(self, xaml_file_name):
        # Inicializar la ventana desde un archivo XAML
        forms.WPFWindow.__init__(self, xaml_file_name)

        # Titulo de la ventana
        self.Title = "EST toolBar"

        # Descripción
        self.description.Text = (
            "Conjunto de scripts creados en Python y Dynamo por "
            "la disciplina de Estructuras(EST). "
            "Ordenados mediante pyRevit, para uso en Revit 2022 a 2024."
        )
        
        # Segunda Descripción
        self.second_description.Text = (
            "EST toolBar | 2025 Sebastian Sáez | Versión 1.1"
        )

        # Imagen al costado izquierdo
        self.logo_image.Source = self.load_image("logo.png")

        # Configuración del botón de GitHub
        self.github_button.ToolTip = "Ir a la página de GitHub"
        self.github_icon.Source = self.load_image("github_icon.png")

        # Configuración del botón de pyRevit
        self.pyrevit_button.ToolTip = "Ir a la página de pyRevit"
        self.pyrevit_icon.Source = self.load_image("pyrevit_icon.png")

        # Configuración del botón de Dynamo
        self.dynamo_button.ToolTip = "Ir a la página de Dynamo"
        self.dynamo_icon.Source = self.load_image("dynamo_icon.png")

        # Configuración del botón de Python
        self.python_button.ToolTip = "Ir a la página de Python"
        self.python_icon.Source = self.load_image("python_icon.png")

    def load_image(self, image_filename):
        """Carga una imagen desde el disco usando una ruta absoluta."""
        try:
            # Calcula la ruta absoluta basada en la ubicación del script
            script_directory = os.path.dirname(os.path.abspath(__file__))  # Directorio del script
            image_path = os.path.join(script_directory, image_filename)   # Ruta absoluta de la imagen

            # Verifica si la imagen existe
            if not os.path.isfile(image_path):
                logger.error("La imagen %s no se encontró en %s.", image_filename, script_directory)
                return None

            # Carga la imagen como BitmapImage
            image = BitmapImage()
            image.BeginInit()
            image.UriSource = Uri(image_path)
            image.CacheOption = BitmapCacheOption.OnLoad
            image.CreateOptions = BitmapCreateOptions.IgnoreImageCache
            image.EndInit()
            return image

        except Exception as e:
            logger.error("Error cargando la imagen %s: %s", image_filename, e)
            return None

    def open_github(self, sender, args):
        """Abre la página de GitHub en el navegador."""
        script.open_url("https://github.com")

    def open_pyrevit(self, sender, args):
        """Abre la página de pyRevit en el navegador."""
        script.open_url("https://www.pyrevitlabs.io")

    def open_dynamo(self, sender, args):
        """Abre la página de Dynamo en el navegador."""
        script.open_url("https://dynamobim.org")
        
    def open_python(self, sender, args):
        """Abre la página de Python en el navegador."""
        script.open_url("https://www.python.org")        

    def handle_click(self, sender, args):
        """Cierra la ventana y detiene la música."""
        self.Close()

# MAIN
# ==================================================

# Crear la ventana y mostrarla
AboutWindow("about.xaml").show_dialog()
