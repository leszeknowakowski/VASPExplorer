import numpy as np
from collections import defaultdict
from ase.io import read
from scipy.spatial import ConvexHull

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QSlider, QTextEdit, QHBoxLayout
)

from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QSlider
)

from PyQt5.QtCore import Qt

import pyvista as pv
from pyvistaqt import QtInteractor

# ------------------------ Convex Hull Functions ------------------------

def cartesian_positions(atoms):
    return atoms.get_positions()

def reciprocal_basis(cell):
    cell = np.asarray(cell)
    return np.linalg.inv(cell).T

def facet_normal(vertices):
    v0, v1, v2 = vertices
    n = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(n)
    if norm == 0:
        return n
    return n / norm

def canonical_hkl(hkl):
    hkl = np.array(hkl)
    if np.all(hkl == 0):
        return (0, 0, 0)
    abs_sorted = tuple(sorted(np.abs(hkl)))
    return abs_sorted

def normalize_hkl(hkl):
    h, k, l = hkl
    for val in (h, k, l):
        if val < 0:
            return tuple([-x for x in hkl])
        if val > 0:
            break
    return tuple(hkl)

def find_best_hkl_for_normal(normal, reciprocal, max_index=1):
    best = None
    best_angle = 90.0
    rng = range(-max_index, max_index + 1)
    for h in rng:
        for k in rng:
            for l in rng:
                if h == 0 and k == 0 and l == 0:
                    continue
                hkl = np.array([h, k, l], dtype=float)
                cart_n = reciprocal.dot(hkl)
                nrm = np.linalg.norm(cart_n)
                if nrm == 0:
                    continue
                cart_n = cart_n / nrm
                cosang = np.clip(np.dot(normal, cart_n), -1.0, 1.0)
                ang = np.degrees(np.arccos(abs(cosang)))
                if ang < best_angle:
                    best_angle = ang
                    best = (h, k, l)
    return best, best_angle


# ------------------------ PyQt Widget ------------------------

class ConvexHullWidget(QWidget):
    def __init__(self, atoms, parent=None, plotter=None):
        super().__init__(parent)
        self.atoms = atoms
        self.plotter = plotter
        self.hull_actors = []
        self.cube_actor = None
        self.facet_to_hkl_map = {}
        self.max_index = 1

        self.initUI()

    def initUI(self):
        # ---- Layout ----
        self.convex_layout = QVBoxLayout(self)
        if self.plotter is None:
            self.plotter = QtInteractor(self)
            self.convex_layout.addWidget(self.plotter.interactor)

        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        # ---- Buttons and Controls ----
        self.controls_layout = QHBoxLayout()
        self.show_hull_btn = QPushButton("Show/Hide Convex Hull")
        self.show_cube_btn = QPushButton("Show/Hide Bounding Cube")
        self.slider_label = QLabel(f"max_index: {self.max_index}")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(1)
        self.slider.setMaximum(5)
        self.slider.setValue(self.max_index)
        self.controls_layout.addWidget(self.show_hull_btn)
        self.controls_layout.addWidget(self.show_cube_btn)
        self.controls_layout.addWidget(self.slider_label)
        self.controls_layout.addWidget(self.slider)

        self.convex_layout.addLayout(self.controls_layout)

        # ---- Text Output ----
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.convex_layout.addWidget(self.text_output)

        # ---- Connections ----
        self.show_hull_btn.clicked.connect(self.toggle_hull)
        self.show_cube_btn.clicked.connect(self.toggle_cube)
        self.slider.valueChanged.connect(self.on_slider_change)

        # ---- Initial compute and visualize ----
        self.compute_and_draw()

        self.repr_layout()

        self.setLayout(self.convex_layout)

    def compute_and_draw(self):
        points = cartesian_positions(self.atoms)
        cell = self.atoms.get_cell()
        if len(points) < 4:
            self.text_output.setText("Too few atoms for convex hull.")
            return

        hull = ConvexHull(points)
        reciprocal = reciprocal_basis(cell)

        facet_to_hkl_map = {}
        for idx, simplex in enumerate(hull.simplices):
            tri_pts = points[simplex]
            n = facet_normal(tri_pts)
            centroid = tri_pts.mean(axis=0)
            if np.dot(centroid - points.mean(axis=0), n) < 0:
                n = -n
            best_hkl, _ = find_best_hkl_for_normal(n, reciprocal, self.max_index)
            if best_hkl is None:
                best_hkl = (0, 0, 0)
            best_hkl = normalize_hkl(best_hkl)
            facet_to_hkl_map[idx] = best_hkl

        self.facet_to_hkl_map = facet_to_hkl_map
        self.draw_convex_hull(points, hull,facet_to_hkl_map)
        if self.cube_actor is not None:
            if self.cube_actor.GetVisibility():
                self.draw_bounding_cube(points)
        else:
            self.draw_bounding_cube(points)
        self.update_summary()


    def draw_convex_hull(self, points, hull, facet_to_hkl_map):
        for actor in self.hull_actors:
            self.plotter.remove_actor(actor)
        # map each unique canonical (hkl) to a color
        unique_canonical = list({canonical_hkl(hkl) for hkl in facet_to_hkl_map.values()})
        import matplotlib.pyplot as plt
        cmap = plt.get_cmap('tab10')
        self.color_by_canonical = {canon: cmap(i % 10) for i, canon in enumerate(unique_canonical)}

        color_map = {hkl: self.color_by_canonical[canonical_hkl(hkl)] for hkl in facet_to_hkl_map.values()}

        # Group facets by assigned (h,k,l)
        self.hull_actors = []
        for hkl in color_map:
            color = color_map[hkl]
            faces_for_hkl = [hull.simplices[i] for i, v in facet_to_hkl_map.items() if v == hkl]
            all_faces = []
            for s in faces_for_hkl:
                all_faces.append([3, *s])
            if not all_faces:
                continue
            faces_flat = np.hstack(all_faces)
            mesh_hkl = pv.PolyData(points, faces_flat)
            self.hull_actors.append(
                self.plotter.add_mesh(mesh_hkl, color=color, opacity=1, show_edges=False)
            )

    def draw_bounding_cube(self, points):
        if self.cube_actor is not None:
            self.plotter.remove_actor(self.cube_actor)
        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        bounds = [x for pair in zip(bounds_min, bounds_max) for x in pair]
        cube = pv.Cube(bounds=bounds)
        self.cube_actor = self.plotter.add_mesh(cube, color="gold", style="wireframe", line_width=2)

    def repr_layout(self):
        # Add control panels
        self.hull_controls = self.create_surface_controls("Convex Hull", self.hull_actors)
        self.cube_controls = self.create_surface_controls("Bounding Cube", self.cube_actor)
        self.controls_layout.addWidget(self.hull_controls)
        self.controls_layout.addWidget(self.cube_controls)

    def toggle_hull(self):
        for actor in self.hull_actors:
            actor.SetVisibility(not actor.GetVisibility())
        self.plotter.render()

    def toggle_cube(self):
        self.cube_actor.SetVisibility(not self.cube_actor.GetVisibility())

    def on_slider_change(self, value):
        self.max_index = value
        self.slider_label.setText(f"max_index: {value}")
        self.compute_and_draw()

    def compute_total_areas(self, points, hull):
        """Compute total convex hull area and bounding cube area."""
        total_hull_area = hull.area

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        dx, dy, dz = bounds_max - bounds_min
        total_cube_area = 2 * (dx * dy + dy * dz + dz * dx)

        return total_hull_area, total_cube_area


    def compute_area_by_canonical(self, points, hull):
        """Compute surface area contribution for each canonical (h, k, l) facet group."""
        area_by_canon = defaultdict(float)

        for idx, simplex in enumerate(hull.simplices):
            hkl = self.facet_to_hkl_map[idx]
            canon = canonical_hkl(hkl)
            tri = points[simplex]
            v0, v1, v2 = tri
            area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0))
            area_by_canon[canon] += area

        return area_by_canon


    def generate_summary_html(self, total_hull_area, total_cube_area, area_by_canon):
        """Generate HTML summary text with colored entries."""
        total_area = sum(area_by_canon.values())

        lines = [
            f"<b>Total convex hull area:</b> {total_hull_area:.3f} Å²<br>",
            f"<b>Total bounding cube area:</b> {total_cube_area:.3f} Å²<br>",
            f"<b>Total unique canonical faces:</b> {len(area_by_canon)}<br><br>"
        ]

        for canon, area in sorted(area_by_canon.items(), key=lambda x: -x[1]):
            percent = 100 * area / total_area if total_area > 0 else 0
            rgba = self.color_by_canonical.get(canon, (0.5, 0.5, 0.5, 1.0))
            r, g, b, _ = [int(255 * c) for c in rgba]
            color_hex = f"#{r:02x}{g:02x}{b:02x}"
            lines.append(
                f'<span style="color:{color_hex}">'
                f"Plane {canon}: {area:.3f} Å² ({percent:.1f}%)"
                f"</span><br>"
            )

        return "".join(lines)


    def update_summary(self):
        """Update the text output area with convex hull and surface summary."""
        points = self.atoms.get_positions()
        hull = ConvexHull(points)

        total_hull_area, total_cube_area = self.compute_total_areas(points, hull)
        area_by_canon = self.compute_area_by_canonical(points, hull)
        html = self.generate_summary_html(total_hull_area, total_cube_area, area_by_canon)

        self.text_output.setHtml(html)

    def create_surface_controls(self, name, actor):
        """Create control widgets for an actor (hull or cube)."""
        group = QGroupBox(f"{name} Settings")
        layout = QVBoxLayout(group)

        # Representation dropdown
        rep_layout = QHBoxLayout()
        rep_label = QLabel("Representation:")
        rep_combo = QComboBox()
        rep_combo.addItems(["Surface", "Wireframe"])
        rep_combo.currentIndexChanged.connect(
            lambda i: self.apply_surface_settings(actor, rep_combo.currentText(),
                                                  show_edges_cb.isChecked(),
                                                  opacity_slider.value() / 100.0)
        )
        rep_layout.addWidget(rep_label)
        rep_layout.addWidget(rep_combo)
        layout.addLayout(rep_layout)

        # Show edges checkbox
        show_edges_cb = QCheckBox("Show Edges")
        show_edges_cb.setChecked(False)
        show_edges_cb.stateChanged.connect(
            lambda _: self.apply_surface_settings(actor, rep_combo.currentText(),
                                                  show_edges_cb.isChecked(),
                                                  opacity_slider.value() / 100.0)
        )
        layout.addWidget(show_edges_cb)

        # Opacity slider
        op_layout = QHBoxLayout()
        op_label = QLabel("Opacity:")
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(100)
        opacity_slider.valueChanged.connect(
            lambda _: self.apply_surface_settings(actor, rep_combo.currentText(),
                                                  show_edges_cb.isChecked(),
                                                  opacity_slider.value() / 100.0)
        )
        op_layout.addWidget(op_label)
        op_layout.addWidget(opacity_slider)
        layout.addLayout(op_layout)

        return group

    def apply_surface_settings(self, actor, representation, show_edges, opacity):
        """Apply the selected visualization options to a PyVista actor."""
        if actor is None:
            return

        actors = actor if isinstance(actor, list) else [actor]

        if representation.lower() == "wireframe":
            wireframe_mode = True
        else:
            wireframe_mode = False

        for ac in actors:
            if wireframe_mode:
                ac.GetProperty().SetRepresentationToWireframe()
            else:
                ac.GetProperty().SetRepresentationToSurface()
            ac.GetProperty().SetEdgeVisibility(show_edges)
            ac.GetProperty().SetOpacity(opacity)

        self.plotter.render()


    def closeEvent(self, event):
        for actor in self.hull_actors:
            self.plotter.remove_actor(actor)
        if self.cube_actor is not None:
            self.plotter.remove_actor(self.cube_actor)



# ------------------------ Example Use ------------------------

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    path = r"D:\syncme\modelowanie DFT\2.all_from_lumi\6.interface\1.precursors_and_clusters\5.larger_513\POSCAR"
    app = QApplication(sys.argv)
    atoms = read(path)  # Replace with your path
    w = ConvexHullWidget(atoms)
    w.resize(800, 600)
    w.show()
    sys.exit(app.exec_())