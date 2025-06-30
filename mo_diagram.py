import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

# Data extracted from your provided text
mo_labels = [
    "F2_1_1a1g", "F2_1_1a1u", "F2_1_2a1g", "F2_1_1e1u", "F2_1_2e1u",
    "F2_1_1e1g", "F2_1_2e1g", "F2_1_2a1u"
]
mo_energies = [
    -24.64444, -18.53454, -6.11194, -3.51814, -3.51814,
    -0.24424, -0.24414, 3.17096
]
ao_labels = [
    "F1_2s", "F1_2p_y", "F1_2p_z", "F1_2p_x",
    "F2_2s", "F2_2p_y", "F2_2p_z", "F2_2p_x"
]
ao_energies = [
    -20.32243, -1.88119, -1.88114, -2.73753,
    -20.32244, -1.88119, -1.88114, -2.73757
]
coefficients = np.array([
    [-0.67665, -0.69110, -0.20530,  0.00000,  0.00000,  0.00000,  0.00000,  0.14963],
    [ 0.00000,  0.00000,  0.00000, -0.23748, -0.66603, -0.70711,  0.00039,  0.00000],
    [ 0.00000, -0.00000,  0.00000, -0.66603,  0.23748,  0.00039,  0.70711, -0.00000],
    [ 0.20530, -0.14963, -0.67665, -0.00000,  0.00000, -0.00000, -0.00000, -0.69110],
    [-0.67665,  0.69109, -0.20530, -0.00000,  0.00000, -0.00000,  0.00000, -0.14963],
    [ 0.00000, -0.00000, -0.00000, -0.23749, -0.66603,  0.70711, -0.00039, -0.00000],
    [ 0.00000,  0.00000,  0.00000, -0.66603,  0.23749, -0.00039, -0.70711,  0.00000],
    [-0.20530, -0.14963,  0.67665,  0.00000, -0.00000, -0.00000, -0.00000, -0.69109]
])

# Plot setup
fig, ax = plt.subplots(figsize=(10, 6))

# Plot MOs
for i, (label, energy) in enumerate(zip(mo_labels, mo_energies)):
    ax.hlines(energy, 0.6, 1.4, colors='blue', linewidth=2, label=f'MO: {label}')
    ax.text(1.5, energy, label, fontsize=9, va='center')

# Plot AOs
for i, (label, energy) in enumerate(zip(ao_labels, ao_energies)):
    ax.hlines(energy, -0.4, 0.4, colors='red', linewidth=2, label=f'AO: {label}')
    ax.text(-0.5, energy, label, fontsize=9, va='center')

# Draw connections
lines = []
for ao_idx, ao_energy in enumerate(ao_energies):
    for mo_idx, mo_energy in enumerate(mo_energies):
        if abs(coefficients[ao_idx, mo_idx]) > 0.1:  # Threshold to show connection
            lines.append([(0.4, ao_energy), (0.6, mo_energy)])

line_segments = LineCollection(lines, colors='gray', alpha=0.5, linewidths=0.8)
ax.add_collection(line_segments)

# Add interactivity
import mplcursors
cursor = mplcursors.cursor(line_segments, hover=True)

@cursor.connect("add")
def on_add(sel):
    sel.annotation.set_visible(False)  # Hide annotation
    ao_energy, mo_energy = sel.target
    ax.set_title(f"Connection between AO (E={ao_energy:.2f}) and MO (E={mo_energy:.2f})", fontsize=12)

# Axis settings
ax.set_xlim(-1, 2)
ax.set_ylim(min(ao_energies + mo_energies) - 2, max(ao_energies + mo_energies) + 2)
ax.set_xlabel("Orbitals", fontsize=12)
ax.set_ylabel("Energy (eV)", fontsize=12)
ax.axvline(0, color='black', linewidth=0.5, linestyle='--')  # Divider

plt.tight_layout()
plt.show()
