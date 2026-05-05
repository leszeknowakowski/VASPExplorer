from ase.io.cube import read_cube
from ase.neighborlist import NeighborList, natural_cutoffs
from ase.data import covalent_radii
import pyvista as pv
import numpy as np
import os
import json
import vtk
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtGui import QPixmap,QFont, QColor, QPainter, QPen
from PyQt5.QtWidgets import QSplashScreen
from PyQt5.QtCore import Qt
import time

class CubeData:
    def __init__(self, filepath):
        self.filepath = filepath

        script_dir = os.path.dirname(__file__)
        colors_file = os.path.join(script_dir, 'elementColorSchemes.json')
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
    def __init__(self):
        self.cubes = {}          # filename -> CubeData
        self.screenshots = {}    # filename -> image (numpy array)

    # -------------------------
    # LOAD ALL FILES ONCE
    # -------------------------
    @staticmethod
    def _load_single_cube(item):
        filename, path = item
        return filename, CubeData(path)

    def load_directory(self, folder, basename):
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
        screenshot = plotter.screenshot()
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

    # -------------------------
    # BUILD SCENE (NO UI)
    # -------------------------
    def build_plotter(self, cube: CubeData, offscreen=True):
        plotter = pv.Plotter(off_screen=offscreen)
        plotter.enable_anti_aliasing('msaa', multi_samples=16)
        return plotter

    def add_to_plotter(self, cube: CubeData, plotter: pv.Plotter):
        isosurf_meshes = self.build_isosurfaces(cube, plotter)
        atom_meshes = self.build_atoms(cube, plotter)
        bond_meshes = self.build_bonds(cube, plotter)

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

        plotter.add_light(pv.Light(position=(10, 10, 10), intensity=0.8))
        axes_actor = plotter.add_axes(
            line_width=5,
            cone_radius=0.6,
            shaft_length=0.8,
            tip_length=0.2,
            ambient=0.1,
            label_size=(0.4, 0.16),
        )
        transform = vtk.vtkTransform()
        transform.RotateZ(-45)  # degrees

        axes_actor.SetUserTransform(transform)


        return plotter

    def build_isosurfaces(self, cube: CubeData, plotter: pv.Plotter):
        grid = pv.ImageData()
        grid.dimensions = cube.data.shape
        grid.origin = cube.origin
        grid.spacing = (
            cube.spacing[0][0],
            cube.spacing[1][1],
            cube.spacing[2][2],
        )

        grid.point_data["values"] = cube.data.flatten(order="F")
        data_max = np.max(cube.data)
        data_min = np.min(cube.data)
        max = np.max([data_max, np.abs(data_min)])

        self.isosurf_threshold = 0.05
        contour_positive = grid.contour([self.isosurf_threshold*max])
        contour_negative = grid.contour([-self.isosurf_threshold*max])

        plotter.add_mesh(contour_positive, color=(255, 170, 0), opacity=0.7, smooth_shading=True)
        plotter.add_mesh(contour_negative, color=(3, 146, 255), opacity=0.7, smooth_shading=True)

    def build_atoms(self, cube: CubeData, plotter: pv.Plotter):
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

    def build_bonds(self, cube: CubeData, plotter: pv.Plotter):
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

    # -------------------------
    # BATCH SCREENSHOTS (KEY FEATURE)
    # -------------------------
    def render_all_screenshots(self):
        cube_items = list(self.cubes.items())
        if not cube_items:
            self.splash.close()
            return

        workers = min(len(cube_items), os.cpu_count() or 1, 4)
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
            self.splash.close()

    # -------------------------
    # GET READY-TO-VIEW SCENE
    # -------------------------
    def get_plotter(self, filename):
        cube = self.cubes[filename]
        return self.build_plotter(cube, offscreen=False)


class CubeViewer:
    def __init__(self, manager: CubeManager):
        self.manager = manager

    def show(self, filename):
        plotter = self.manager.get_plotter(filename)
        plotter.show()

if __name__ == "__main__":
    manager = CubeManager()
    manager.load_directory(r"D:\syncme\modelowanie DFT\co3o4_new_new\9.deep_o2_reduction\GOOD\1.spin_up\HSE\1.gas_to_metaloxo\2.1_almost_desorbed_small\1.mofe_o2")
    manager.render_all_screenshots()
    viewer = CubeViewer(manager)
    viewer.show('O2_1_1_2e1g.cube')