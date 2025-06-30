import numpy as np
from ase.io import read
from ase.neighborlist import NeighborList, natural_cutoffs
from ase.constraints import FixAtoms, FixBondLength, FixLinearTriatomic
from itertools import combinations

# Read POSCAR file
atoms = read("D:\\syncme-from-c120\\modelowanie DFT\\CeO2\\CeO2_bulk\\Ceria_bulk_vacancy\\0.Ceria_bulk_1vacancy\\scale_0.98\\POSCAR")

# Set up NeighborList (use a suitable cutoff radius for your system)
cutoffs = natural_cutoffs(atoms, Ce=1.5)
neighbor_list = NeighborList(cutoffs, self_interaction=False, bothways=True)
neighbor_list.update(atoms)

#selected_atoms = np.array([7, 10, 12, 13, 23, 26, 28, 29, 39, 42, 44, 45, 55, 58, 60, 61, 76, 77, 79, 82, 84, 85, 87, 90, 92, 93, 95, 98, 100, 101, 103, 106])-1
selected_atoms = np.array([0,8,9,10,11])-1
constraints_list = []
def set_distance_constraints(atom1, atom2):
    const = FixBondLength(atom1, atom2)
    #atoms.set_constraint(const)
    return const

def set_angle_constraints(atom1, atom2, atom3):
    const = FixLinearTriatomic(triples=[(atom1, atom2, atom3)])
    #atoms.set_constraint(const)
    return const
def find_selected_neighbours(atom):
    indices, offets = neighbor_list.get_neighbors(atom)
    indices_in_selected = list(set(indices) & set(selected_atoms))
    return indices_in_selected

def find_constrained_bonds(atom):
    neighours = find_selected_neighbours(atom)
    bonds = [(atom, neighbour) for neighbour in neighours]
    return bonds

def find_constrained_triples(atom):
    neighours = find_selected_neighbours(atom)
    triples = [(a, atom, b) for a, b, in combinations(neighours, 2)]
    return triples

def constrain_bonds(atom):
    bonds = find_constrained_bonds(atom)
    for bond in bonds:
        const = set_distance_constraints(bond[0], bond[1])
        constraints_list.append(const)

def constrain_triples(atom):
    triples = find_constrained_triples(atom)
    for triple in triples:
        const = set_angle_constraints(triple[0], triple[1], triple[2])
        constraints_list.append(const)

def apply_constraints():
    atoms.set_constraint(constraints_list)

def constraint_to_ICONST(const):
    const = const.todict()
    if const["name"] == "FixBondLengths":
        flag = "R"
        atoms = const['kwargs']['pairs'][0]
        line = [flag, atoms[0], atoms[1], 0]
    if const["name"] == "FixLinearTriatomic":
        flag = "A"
        atoms = const['kwargs']['triples'][0]
        line = [flag, atoms[0], atoms[1], atoms[2], 0]
    return line

def write_ICONST():
    file_name = "ICONST"
    with open(file_name, 'w') as file:
        for const in constraints_list:
            line = constraint_to_ICONST(const)
            line = " ".join(map(str, line))
            file.write(line)
            file.write('\n')

constrain_bonds(0)
constrain_triples(0)

write_ICONST()
print("cont...")