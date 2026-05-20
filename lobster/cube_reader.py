import PyQt5
import pyqtgraph as pg
from ase.io.cube import read_cube
from ase.neighborlist import NeighborList, natural_cutoffs
from ase.data import covalent_radii
import pyvista as pv
import numpy as np
import os
import json
import vtk
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from PyQt5.QtGui import QPixmap,QFont, QColor, QPainter, QPen
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt
from QtInteractor import QtInteractor
import time


@dataclass
class IsosurfaceSettings:
    positive_fraction: float = 0.02
    negative_fraction: float = 0.02
    opacity: float = 0.7
    specular: float = 0.1
    specular_power: float = 50.0
    diffuse: float = 0.7
    positive_color: tuple = (255, 170, 0)
    negative_color: tuple = (3, 146, 255)
    backface_params: dict = field(default_factory=dict)

class CubeData:
    def __init__(self, filepath):
        self.filepath = filepath

        script_dir = os.path.dirname(__file__)
        colors_file = os.path.join(os.path.dirname(script_dir), 'elementColorSchemes.json')
        with open(colors_file, "r") as f:
            self.all_colors = json.load(f)

        with open(filepath, "r") as f:
            cube = read_cube(f)

        self.data = cube["data"]
        self.atoms = cube["atoms"]
        self.origin = cube["origin"]
        self.spacing = cube["spacing"]

        self.positions = self.atoms.positions

        self._build_bonds()

    def get_colors(self):
        colors = []
        for atom in self.atoms:
            symb = atom.symbol
            if symb in self.all_colors:
                colors.append(self.all_colors[symb])
        return colors

    def _build_bonds(self):
        cutoffs = natural_cutoffs(self.atoms)
        nl = NeighborList(cutoffs, self_interaction=False, bothways=True)
        nl.update(self.atoms)

        bonds = []
        for i in range(len(self.atoms)):
            indices, _ = nl.get_neighbors(i)
            for j in indices:
                if i < j:
                    bonds.append((i, j))

        self.bonds = bonds


class CubeManager:
    default_camera_position = None
    default_camera_focal_point = None
    default_camera_up = None
    default_camera_view_angle = None
    default_camera_clipping_range = None
    default_camera_parallel_projection = None
    default_camera_parallel_scale = None
    default_camera_window_size = None

    def __init__(self):
        self.cubes = {}          # filename -> CubeData
        self.screenshots = {}    # filename -> image (numpy array)
        self.isosurface_settings = IsosurfaceSettings()

    @staticmethod
    def _load_single_cube(item):
        filename, path = item
        return filename, CubeData(path)

    def load_directory(self, folder, basename, show_splash=True):
        if show_splash:
            splash_pix = QPixmap(600,300)
            splash_pix.fill(QColor(240,240,240))
            # Draw border
            painter = QPainter(splash_pix)
            pen = QPen(Qt.black)
            pen.setWidth(6)
            painter.setPen(pen)
            painter.drawRect(splash_pix.rect().adjusted(0, 0, -1, -1))
            painter.end()

            self.splash = QSplashScreen(splash_pix)
            self.splash.setMask(splash_pix.mask())
            self.splash.setFont(QFont("Arial", 18))
            self.splash.show()
            self.splash.showMessage("Initializing...", Qt.AlignCenter, Qt.black)

        tic = time.perf_counter()
        cube_files = [
            f for f in os.listdir(folder)
            if f.endswith(".cube") and f.startswith(basename)
        ]
        cube_files.sort()

        if not cube_files:
            return

        workers = min(len(cube_files), os.cpu_count() or 1, 8)
        loaded = {}
        errors = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._load_single_cube, (f, os.path.join(folder, f))): f
                for f in cube_files
            }

            completed = 0
            total = len(cube_files)
            for future in as_completed(futures):
                filename = futures[future]
                completed += 1
                if show_splash:
                    self.splash.showMessage(
                        f"Loading {filename} ({completed}/{total})",
                        Qt.AlignCenter,
                        Qt.black
                    )
                try:
                    loaded_name, cube = future.result()
                    loaded[loaded_name] = cube
                except Exception as exc:
                    errors.append((filename, exc))

        for f in cube_files:
            if f in loaded:
                self.cubes[f] = loaded[f]

        if errors:
            failed_files = ", ".join(name for name, _ in errors)
            raise RuntimeError(f"Failed to load cube files: {failed_files}") from errors[0][1]

        toc = time.perf_counter()
        print(f"Loading time: {toc - tic:.2f} seconds")

    def _render_single_screenshot(self, item):
        name, cube = item
        plotter = self.build_plotter(cube, offscreen=True)
        self.add_to_plotter(cube, plotter)
        plotter.hide_axes()
        self.apply_default_camera(plotter)
        screenshot = plotter.screenshot(scale=5)
        plotter.clear()
        plotter.close()
        return name, screenshot

    def make_cylinder(self, p1, p2, radius=0.08):
        direction = p2 - p1
        length = np.linalg.norm(direction)
        center = (p1 + p2) / 2

        return pv.Cylinder(
            center=center,
            direction=direction,
            radius=radius,
            height=length,
            resolution=24
        )

    def build_plotter(self, cube: CubeData, offscreen=True):
        window_size = None
        if offscreen and self.has_default_camera():
            window_size = type(self).default_camera_window_size

        kwargs = {"off_screen": offscreen}
        if window_size is not None:
            kwargs["window_size"] = window_size

        plotter = pv.Plotter(**kwargs)
        plotter.disable_anti_aliasing()
        plotter.enable_depth_peeling(number_of_peels=8, occlusion_ratio=0.0)
        self.default_plotter_setup(plotter)
        return plotter

    def default_plotter_setup(self, plotter, show_save_camera_control=True):
        light = pv.Light()
        light.set_headlight()
        light.intensity = 1.2
        plotter.add_light(light)
        if show_save_camera_control:
            self.add_save_default_camera_control(plotter)
        return plotter

    def add_save_default_camera_control(self, plotter):
        if getattr(plotter, "off_screen", False):
            return

        def save_camera_default(*_):
            self.save_default_camera(plotter)

        try:
            plotter.add_checkbox_button_widget(
                save_camera_default,
                value=False,
                position=(10.0, 10.0),
                size=32,
                border_size=2,
                color_on=(0.2, 0.6, 0.2),
                color_off=(0.35, 0.35, 0.35),
                background_color=(1.0, 1.0, 1.0),
            )
            plotter.add_text(
                "Save default camera",
                position=(50, 16),
                font_size=10,
                color="black",
                name="save_default_camera_label",
            )
        except Exception as exc:
            print(f"Could not add camera save button: {exc}")

    def has_default_camera(self):
        cls = type(self)
        camera_parameters = (
            cls.default_camera_position,
            cls.default_camera_focal_point,
            cls.default_camera_up,
            cls.default_camera_view_angle,
            cls.default_camera_clipping_range,
            cls.default_camera_parallel_projection,
            cls.default_camera_parallel_scale,
        )
        return all(value is not None for value in camera_parameters)

    @staticmethod
    def _plotter_active_camera(plotter):
        renderer = getattr(plotter, "renderer", None)
        if renderer is not None:
            try:
                return renderer.GetActiveCamera()
            except AttributeError:
                pass
        return plotter.camera

    @staticmethod
    def _plotter_window_size(plotter):
        try:
            width, height = plotter.window_size
            width, height = int(width), int(height)
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass

        render_window = getattr(plotter, "ren_win", None)
        if render_window is not None:
            try:
                width, height = render_window.GetSize()
                width, height = int(width), int(height)
                if width > 0 and height > 0:
                    return width, height
            except Exception:
                pass
        return None

    def save_default_camera(self, plotter, show_status=True):
        camera = self._plotter_active_camera(plotter)
        cls = type(self)

        cls.default_camera_position = tuple(float(value) for value in camera.GetPosition())
        cls.default_camera_focal_point = tuple(float(value) for value in camera.GetFocalPoint())
        cls.default_camera_up = tuple(float(value) for value in camera.GetViewUp())
        cls.default_camera_view_angle = float(camera.GetViewAngle())
        cls.default_camera_clipping_range = tuple(float(value) for value in camera.GetClippingRange())
        cls.default_camera_parallel_projection = bool(camera.GetParallelProjection())
        cls.default_camera_parallel_scale = float(camera.GetParallelScale())
        cls.default_camera_window_size = self._plotter_window_size(plotter)

        print("\nSaved default cube camera:")
        print("Position       :", cls.default_camera_position)
        print("Focal point    :", cls.default_camera_focal_point)
        print("View up        :", cls.default_camera_up)
        print("View angle     :", cls.default_camera_view_angle)
        print("Clipping range :", cls.default_camera_clipping_range)
        print("Parallel       :", cls.default_camera_parallel_projection)
        print("Parallel scale :", cls.default_camera_parallel_scale)
        print("Window size    :", cls.default_camera_window_size)

        if not show_status:
            return

        try:
            plotter.add_text(
                "Camera defaults saved",
                position="lower_left",
                font_size=10,
                color="black",
                name="camera_defaults_saved_status",
            )
            plotter.render()
        except Exception:
            pass

    def set_default_camera_before_screenshots(self, item):
        name, cube = item
        print(f"Set default screenshot camera using {name}")
        dialog = CubeIsosurfaceControlWindow(self, cube)
        dialog.exec_()

        if not self.has_default_camera():
            print("Default screenshot camera was not saved.")

    def apply_default_camera(self, plotter):
        if not self.has_default_camera():
            return False

        cls = type(self)
        camera = self._plotter_active_camera(plotter)
        try:
            plotter.camera_position = (
                cls.default_camera_position,
                cls.default_camera_focal_point,
                cls.default_camera_up,
            )
            camera = self._plotter_active_camera(plotter)
        except Exception:
            pass
        camera.SetPosition(*cls.default_camera_position)
        camera.SetFocalPoint(*cls.default_camera_focal_point)
        camera.SetViewUp(*cls.default_camera_up)
        camera.SetViewAngle(cls.default_camera_view_angle)
        camera.SetClippingRange(*cls.default_camera_clipping_range)
        camera.SetParallelProjection(1 if cls.default_camera_parallel_projection else 0)
        camera.SetParallelScale(cls.default_camera_parallel_scale)
        camera.Modified()

        try:
            plotter.render()
        except Exception:
            pass

        return True

    def on_camera_stop(selfself, caller, event):
        renderer = caller.GetRenderWindow().GetRenderers().GetFirstRenderer()
        cam = renderer.GetActiveCamera()

        print("\n=== CAMERA ===")

        print("Position       :", cam.GetPosition())
        print("Focal point    :", cam.GetFocalPoint())
        print("View up        :", cam.GetViewUp())
        print("View angle     :", cam.GetViewAngle())
        print("Clipping range :", cam.GetClippingRange())

    def add_to_plotter(self, cube: CubeData, plotter: pv.Plotter, **kwargs):
        isosurf_actors = self.build_isosurfaces(cube, plotter, **kwargs)
        setattr(plotter, "_cube_isosurface_actors", isosurf_actors)
        atom_meshes = self.build_atoms(cube)
        bond_meshes = self.build_bonds(cube)

        for mesh, color in atom_meshes:
            plotter.add_mesh(
                mesh,
                color=color,
                smooth_shading=True,
                specular=0.5,
                specular_power=20
            )

        for mesh, color in bond_meshes:
            plotter.add_mesh(
                mesh,
                color=color,
                smooth_shading=True,
                specular=0.3
            )


        axes_actor = plotter.add_axes(
            line_width=5,
            cone_radius=0.6,
            shaft_length=0.8,
            tip_length=0.2,
            ambient=0.1,
            label_size=(0.4, 0.16),
        )
        transform = vtk.vtkTransform()
        transform.RotateZ(-45)   # TODO: do not hardcode it :)

        axes_actor.SetUserTransform(transform)

        if not self.apply_default_camera(plotter):
            plotter.reset_camera()

        return plotter

    def build_grid(self, cube: CubeData):
        grid = pv.ImageData()
        grid.dimensions = cube.data.shape
        grid.origin = cube.origin
        grid.spacing = (
            cube.spacing[0][0],
            cube.spacing[1][1],
            cube.spacing[2][2],
        )
        grid.point_data["values"] = cube.data.flatten(order="F")
        return grid

    def build_isosurfaces(self,
                          cube: CubeData,
                          plotter: pv.Plotter,
                          opacity=None,
                          specular=None,
                          specular_power=None,
                          diffuse=None,
                          positive_fraction=None,
                          negative_fraction=None,
                          positive_color=None,
                          negative_color=None,
                          backface_params=None
                          ):
        settings = self.isosurface_settings
        opacity = settings.opacity if opacity is None else opacity
        specular = settings.specular if specular is None else specular
        specular_power = settings.specular_power if specular_power is None else specular_power
        diffuse = settings.diffuse if diffuse is None else diffuse
        positive_fraction = settings.positive_fraction if positive_fraction is None else positive_fraction
        negative_fraction = settings.negative_fraction if negative_fraction is None else negative_fraction
        positive_color = settings.positive_color if positive_color is None else positive_color
        negative_color = settings.negative_color if negative_color is None else negative_color
        backface_params = settings.backface_params if backface_params is None else backface_params

        grid = self.build_grid(cube)
        data_max = np.max(cube.data)
        data_min = np.min(cube.data)
        value_scale = np.max([data_max, np.abs(data_min)])
        if value_scale == 0:
            return []

        contour_positive = grid.contour([positive_fraction * value_scale])
        contour_negative = grid.contour([-negative_fraction * value_scale])

        actors = []
        for contour, color in zip([contour_positive, contour_negative], [positive_color, negative_color]):
            if contour.n_points == 0:
                continue
            actor = plotter.add_mesh(
                contour,
                color=color,
                opacity=opacity,
                specular=specular,
                specular_power=specular_power,
                diffuse=diffuse,
                smooth_shading=True,
                backface_params=backface_params
            )
            actors.append(actor)
        return actors

    def build_atoms(self, cube: CubeData):
        atom_meshes = []
        atoms = cube.atoms

        # atoms
        for atom in atoms:
            pos = atom.position
            Z = atom.number
            symbol = atom.symbol

            radius = covalent_radii[Z] * 0.6
            color = cube.all_colors[symbol]

            sphere = pv.Sphere(
                radius=radius,
                center=pos,
                theta_resolution=24,
                phi_resolution=24
            )

            atom_meshes.append((sphere, color))
        return atom_meshes

    def make_cylinder(self, p1, p2, radius=0.08):
        direction = p2 - p1
        length = np.linalg.norm(direction)
        center = (p1 + p2) / 2

        return pv.Cylinder(
            center=center,
            direction=direction,
            radius=radius,
            height=length,
            resolution=24
        )

    def build_bonds(self, cube: CubeData):
        bond_meshes = []
        bonds = cube.bonds
        atoms = cube.atoms

        for i, j in bonds:
            p1 = cube.atoms.positions[i]
            p2 = cube.atoms.positions[j]

            midpoint = (p1 + p2) / 2

            color1 = cube.all_colors[atoms[i].symbol]
            color2 = cube.all_colors[atoms[j].symbol]

            cyl1 = self.make_cylinder(p1, midpoint)
            cyl2 = self.make_cylinder(midpoint, p2)

            bond_meshes.append((cyl1, color1))
            bond_meshes.append((cyl2, color2))
        return bond_meshes

    def render_all_screenshots(self, show_splash=True):
        cube_items = list(self.cubes.items())
        if not cube_items:
            if show_splash:
                self.splash.close()
                return

        splash = getattr(self, "splash", None)
        if show_splash and splash is not None:
            splash.hide()
        try:
            self.set_default_camera_before_screenshots(cube_items[0])
        finally:
            if show_splash and splash is not None:
                splash.show()
                splash.showMessage(
                    "Rendering screenshots...",
                    Qt.AlignCenter,
                    Qt.black
                )

        workers = min(len(cube_items), os.cpu_count() or 1, 8)
        rendered = {}
        errors = []

        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(self._render_single_screenshot, item): item[0]
                    for item in cube_items
                }

                completed = 0
                total = len(cube_items)
                for future in as_completed(futures):
                    name = futures[future]
                    completed += 1
                    if show_splash:
                        self.splash.showMessage(
                            f"building plotter for {name} ({completed}/{total})",
                            Qt.AlignCenter,
                            Qt.black
                        )
                    try:
                        rendered_name, image = future.result()
                        rendered[rendered_name] = image
                    except Exception as exc:
                        errors.append((name, exc))

            for name, _ in cube_items:
                if name in rendered:
                    self.screenshots[name] = rendered[name]

            if errors:
                failed_files = ", ".join(name for name, _ in errors)
                raise RuntimeError(f"Failed to render screenshots: {failed_files}") from errors[0][1]
        finally:
            if show_splash:
                self.splash.close()

    def get_plotter(self, filename):
        cube = self.cubes[filename]
        plotter = self.build_plotter(cube, offscreen=False)
        self.add_to_plotter(cube, plotter)
        return plotter


class CubeIsosurfaceControlWindow(QtWidgets.QDialog):
    """Interactive cube preview used to choose screenshot camera and surface style."""

    def __init__(self, manager: CubeManager, cube: CubeData, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.cube = cube
        self.isosurface_actors = []
        self._updating = False
        self._plotter_closed = False

        self.setWindowTitle("Cube camera and isosurfaces")
        self.resize(1200, 760)

        layout = QtWidgets.QHBoxLayout(self)

        self.plotter = QtInteractor(self)
        self.plotter.disable_anti_aliasing()
        self.plotter.enable_depth_peeling(number_of_peels=8, occlusion_ratio=0.0)
        self.manager.default_plotter_setup(self.plotter, show_save_camera_control=False)
        self.manager.add_to_plotter(self.cube, self.plotter)
        self.isosurface_actors = list(getattr(self.plotter, "_cube_isosurface_actors", []))
        layout.addWidget(self.plotter, 1)

        controls = QtWidgets.QWidget(self)
        controls.setFixedWidth(310)
        controls_layout = QtWidgets.QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)

        settings = self.manager.isosurface_settings
        controls_layout.addWidget(QtWidgets.QLabel("Positive color"))
        self.positive_color_button = pg.ColorButton(color=settings.positive_color)
        self.positive_color_button.sigColorChanged.connect(self.update_isosurfaces)
        self.positive_color_button.sigColorChanging.connect(self.update_isosurfaces)
        controls_layout.addWidget(self.positive_color_button)

        controls_layout.addWidget(QtWidgets.QLabel("Negative color"))
        self.negative_color_button = pg.ColorButton(color=settings.negative_color)
        self.negative_color_button.sigColorChanged.connect(self.update_isosurfaces)
        self.negative_color_button.sigColorChanging.connect(self.update_isosurfaces)
        controls_layout.addWidget(self.negative_color_button)

        self.positive_iso_slider, self.positive_iso_value = self.add_slider(
            controls_layout,
            "Positive isovalue",
            1,
            100,
            int(settings.positive_fraction * 1000),
            self.format_iso_value,
        )
        self.negative_iso_slider, self.negative_iso_value = self.add_slider(
            controls_layout,
            "Negative isovalue",
            1,
            100,
            int(settings.negative_fraction * 1000),
            self.format_iso_value,
        )
        self.opacity_slider, self.opacity_value = self.add_slider(
            controls_layout,
            "Opacity",
            0,
            100,
            int(settings.opacity * 100),
            self.format_unit_value,
        )
        self.specular_slider, self.specular_value = self.add_slider(
            controls_layout,
            "Specular",
            0,
            100,
            int(settings.specular * 100),
            self.format_unit_value,
        )
        self.specular_power_slider, self.specular_power_value = self.add_slider(
            controls_layout,
            "Specular power",
            0,
            100,
            int(settings.specular_power),
            lambda value: f"{value:d}",
        )
        self.diffuse_slider, self.diffuse_value = self.add_slider(
            controls_layout,
            "Diffuse",
            0,
            100,
            int(settings.diffuse * 100),
            self.format_unit_value,
        )

        controls_layout.addStretch(1)

        button_layout = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.accept)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        controls_layout.addLayout(button_layout)

        layout.addWidget(controls)

    def add_slider(self, layout, label, minimum, maximum, value, formatter):
        caption = QtWidgets.QLabel(label)
        value_label = QtWidgets.QLabel(formatter(value))
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(caption)
        header.addWidget(value_label)
        layout.addLayout(header)

        slider = QtWidgets.QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(max(minimum, min(maximum, value)))
        slider.valueChanged.connect(lambda slider_value: value_label.setText(formatter(slider_value)))
        slider.valueChanged.connect(self.update_isosurfaces)
        layout.addWidget(slider)

        return slider, value_label

    @staticmethod
    def format_unit_value(value):
        return f"{value / 100:.2f}"

    @staticmethod
    def format_iso_value(value):
        return f"{value / 10:.1f}%"

    def current_settings(self):
        return IsosurfaceSettings(
            positive_fraction=self.positive_iso_slider.value() / 1000,
            negative_fraction=self.negative_iso_slider.value() / 1000,
            opacity=self.opacity_slider.value() / 100,
            specular=self.specular_slider.value() / 100,
            specular_power=float(self.specular_power_slider.value()),
            diffuse=self.diffuse_slider.value() / 100,
            positive_color=self.positive_color_button.color().getRgb()[:3],
            negative_color=self.negative_color_button.color().getRgb()[:3],
            backface_params=self.manager.isosurface_settings.backface_params,
        )

    def remove_isosurface_actors(self):
        for actor in self.isosurface_actors:
            try:
                self.plotter.remove_actor(actor, reset_camera=False)
            except TypeError:
                self.plotter.remove_actor(actor)
            except Exception:
                pass
        self.isosurface_actors = []

    def update_isosurfaces(self, *_):
        if self._updating:
            return

        self._updating = True
        try:
            self.manager.isosurface_settings = self.current_settings()
            self.remove_isosurface_actors()
            self.isosurface_actors = self.manager.build_isosurfaces(self.cube, self.plotter)
            setattr(self.plotter, "_cube_isosurface_actors", self.isosurface_actors)
            self.plotter.render()
        finally:
            self._updating = False

    def save_and_close_plotter(self):
        if self._plotter_closed:
            return

        self.manager.isosurface_settings = self.current_settings()
        self.manager.save_default_camera(self.plotter, show_status=False)
        try:
            self.plotter.Finalize()
        except Exception:
            pass
        self._plotter_closed = True

    def accept(self):
        self.save_and_close_plotter()
        super().accept()

    def reject(self):
        self.save_and_close_plotter()
        super().reject()

    def closeEvent(self, event):
        self.save_and_close_plotter()
        super().closeEvent(event)


class CubeViewer:
    def __init__(self, manager: CubeManager):
        self.manager = manager

    def show(self, filename):
        plotter = self.manager.get_plotter(filename)
        plotter.show()

if __name__ == "__main__":
    import sys
    app = PyQt5.QtWidgets.QApplication(sys.argv)
    manager = CubeManager()
    path = r"D:\syncme\modelowanie DFT\co3o4_new_new\9.deep_o2_reduction\GOOD\1.spin_up\HSE\1.gas_to_metaloxo\2.1_almost_desorbed_small\1.mofe_o2"
    path = "/net/storage/pr3/plgrid/plgg_zkln/1.LUMI/3.Co3O4/2.deep_reduction/1.octa-octa/1.gas_to_metaloxo/3.steps/03.02_small_almost_desorbed/1.befre_EF/1.8nodes/1.lobster/1.mofe_co2o2/"
    #manager.load_directory(path, "CoHO2", show_splash=False)
    mo = "Co2O2_1_1_10a.cube"
    cubedata = manager._load_single_cube((path,path+mo))
    #manager.render_all_screenshots(show_splash=False)
    viewer = CubeViewer(manager)

    plotter = viewer.manager.build_plotter(cubedata, offscreen=False)
    bparams = dict(opacity=1)
    manager.add_to_plotter(cubedata[1], plotter,
                        opacity = 0.99,
                          specular = 0,
                          specular_power = 50,
                          diffuse = 0.9
                           )
    plotter.show()
    app.exec_()
