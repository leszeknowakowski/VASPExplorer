from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple
import re
import sys
from pathlib import Path
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QCloseEvent
import numpy as np
import os
import pyqtgraph as pg
from pymatgen.electronic_structure.core import Spin
from lobster.cube_reader import CubeManager
from structure_plot import QtInteractor

ORB_LINE_WIDTH = 3.5
MO_IMAGE_EXPORT_HEIGHT = 1200

@dataclass
class SpinData:
    molecular_orbitals: List[str]
    atomic_orbital_labels: List[str]
    atomic_groups: Dict[str, List[str]]
    ao_energies_by_group: List[np.ndarray]
    mo_energies: np.ndarray
    coefficient_matrix: np.ndarray


class ParsedDiagram:
    def __init__(self, alpha: SpinData, beta: SpinData):
        self.alpha = alpha
        self.beta = beta


@dataclass(frozen=True)
class OrbitalMatch:
    source_mo_index: int
    target_mo_index: int
    source_mo_label: str
    target_mo_label: str
    score: float
    compared_coefficients: int
    matching_coefficients: int
    matched_atomic_orbitals: Tuple[str, ...]


@dataclass(frozen=True)
class OrbitalTrackStep:
    file_index: int
    path: str
    spin: str
    mo_index: int
    mo_label: str
    mo_energy: float
    score_from_previous: Optional[float] = None
    compared_coefficients: Optional[int] = None
    matching_coefficients: Optional[int] = None
    matched_atomic_orbitals: Tuple[str, ...] = ()


@dataclass
class OrbitalTrack:
    spin: str
    start_mo_index: int
    start_mo_label: str
    steps: List[OrbitalTrackStep]


@dataclass
class OrbitalTrackingSequence:
    paths: List[str]
    spin: str
    tracks: List[OrbitalTrack]
    transition_matches: List[List[OrbitalMatch]]


@dataclass(frozen=True)
class AtomicOrbitalContribution:
    file_index: int
    path: str
    spin: str
    atomic_orbital_label: str
    atomic_orbital_index: int
    mo_index: int
    mo_label: str
    mo_energy: float
    coefficient: float
    abs_coefficient: float


@dataclass
class AtomicOrbitalTrack:
    spin: str
    atomic_orbital_label: str
    start_atomic_orbital_index: int
    contributions: List[AtomicOrbitalContribution]


@dataclass
class AtomicOrbitalTrackingSequence:
    paths: List[str]
    spin: str
    atomic_orbital_labels: Tuple[str, ...]
    tracks: List[AtomicOrbitalTrack]


@dataclass(frozen=True)
class FlowChartFrame:
    file_index: int
    path: str
    lcfo_path: str
    spin: str
    mo_index: int
    mo_label: str
    mo_energy: float
    contributions: Tuple[AtomicOrbitalContribution, ...]
    dos_orbital_label: str
    entity_labels: Tuple[str, ...]
    energies: np.ndarray
    dos_values: np.ndarray
    intervals: Tuple[Tuple[float, float], ...]


@dataclass
class FlowChartData:
    paths: List[str]
    atomic_orbital_labels: Tuple[str, ...]
    ao_coefficient_threshold: float
    dos_threshold_fraction: float
    frames: List[FlowChartFrame]
    errors: List[str] = field(default_factory=list)

    def molecular_orbitals(self) -> List[str]:
        return list(dict.fromkeys(frame.mo_label for frame in self.frames))

    def frames_for(self, mo_label: str, spin: Optional[str] = None) -> List[FlowChartFrame]:
        return [
            frame for frame in self.frames
            if frame.mo_label == mo_label and (spin is None or frame.spin == spin)
        ]

    def frames_by_file(self) -> Dict[int, List[FlowChartFrame]]:
        grouped = {index: [] for index in range(len(self.paths))}
        for frame in self.frames:
            grouped.setdefault(frame.file_index, []).append(frame)
        return grouped


class LobsterModel:
    """Handles file parsing and data preparation."""

    @staticmethod
    def _print_matching_output(sequence):
        for track in sequence.tracks:
            print(f"\nTrack starting from {track.start_mo_label} / MO index {track.start_mo_index}")
            for step in track.steps:
                file_name = Path(step.path).name
                if step.score_from_previous is None:
                    print(
                        f"  file {step.file_index}: {file_name} -> "
                        f"{step.mo_label} index={step.mo_index}, energy={step.mo_energy:.4f}"
                    )
                else:
                    print(
                        f"  file {step.file_index}: {file_name} -> "
                        f"{step.mo_label} index={step.mo_index}, energy={step.mo_energy:.4f}, "
                        f"score={step.score_from_previous:.2f}, "
                        f"matched={step.matching_coefficients}/{step.compared_coefficients}, "
                        f"AOs={', '.join(step.matched_atomic_orbitals)}"
                    )

    @staticmethod
    def _parse_token(token: str):
        token = token.strip()
        if token == "":
            return ""
        try:
            return float(token.replace("D", "E"))
        except ValueError:
            return token

    @classmethod
    def read_table(cls, path: str):
        rows = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue
                parts = re.split(r"\s+", raw)
                rows.append([cls._parse_token(p) for p in parts])
        return rows

    @staticmethod
    def _split_spin(rows):
        molecular_orbitals = [str(x) for x in rows[1]]
        mo_energies = np.array(rows[2][2:], dtype=float)

        atomic_rows = rows[3:]
        ao_labels = [str(r[0]) for r in atomic_rows]
        ao_energies = np.array([r[1] for r in atomic_rows], dtype=float)
        coeff = np.array([r[2:] for r in atomic_rows], dtype=float)

        group_map = {}
        group_energies = {}

        for lbl, e in zip(ao_labels, ao_energies):
            atom = lbl.split("_", 1)[0]
            group_map.setdefault(atom, []).append(lbl)
            group_energies.setdefault(atom, []).append(e)

        return SpinData(
            molecular_orbitals,
            ao_labels,
            group_map,
            [np.array(v) for v in group_energies.values()],
            mo_energies,
            coeff,
        )

    @classmethod
    def load(cls, path: str) -> ParsedDiagram:
        rows = cls.read_table(path)
        half = len(rows) // 2

        alpha = cls._split_spin(rows[:half])
        beta = cls._split_spin(rows[half:])

        return ParsedDiagram(alpha, beta)

    @classmethod
    def load_many(cls, paths: Sequence[str]) -> List[ParsedDiagram]:
        return [cls.load(path) for path in paths]

    @staticmethod
    def _validate_similarity_options(tolerance: float, coefficient_threshold: float):
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        if coefficient_threshold < 0:
            raise ValueError("coefficient_threshold must be non-negative")

    @staticmethod
    def _mo_count(spin_data: SpinData) -> int:
        return int(np.asarray(spin_data.coefficient_matrix).shape[1])

    @staticmethod
    def _mo_label(spin_data: SpinData, mo_index: int) -> str:
        if 0 <= mo_index < len(spin_data.molecular_orbitals):
            return spin_data.molecular_orbitals[mo_index]
        return str(mo_index)

    @staticmethod
    def _mo_energy(spin_data: SpinData, mo_index: int) -> float:
        if 0 <= mo_index < len(spin_data.mo_energies):
            return float(spin_data.mo_energies[mo_index])
        return float("nan")

    @staticmethod
    def _ao_atom(label: str) -> str:
        return label.split("_", 1)[0]

    @staticmethod
    def _ao_name(label: str) -> str:
        parts = label.split("_", 1)
        return parts[1] if len(parts) == 2 else label

    @staticmethod
    def _normalize_string_sequence(values):
        if values is None:
            return None
        if isinstance(values, str):
            return [values]
        return list(values)

    @classmethod
    def atomic_orbital_labels(
            cls,
            spin_data: SpinData,
            atom: Optional[str] = None,
            orbital_names: Optional[Sequence[str]] = None,
    ) -> List[str]:
        names = cls._normalize_string_sequence(orbital_names)
        name_set = set(names) if names is not None else None

        labels = []
        for label in spin_data.atomic_orbital_labels:
            if atom is not None and cls._ao_atom(label) != atom:
                continue
            if name_set is not None and label not in name_set and cls._ao_name(label) not in name_set:
                continue
            labels.append(label)
        return labels

    @classmethod
    def atomic_orbital_contributions(
            cls,
            spin_data: SpinData,
            atomic_orbital_label: str,
            file_index: int = 0,
            path: str = "",
            spin: str = "alpha",
            coefficient_threshold: float = 0.0,
    ) -> List[AtomicOrbitalContribution]:
        cls._validate_similarity_options(0.0, coefficient_threshold)

        coeff = np.asarray(spin_data.coefficient_matrix, dtype=float)
        labels = spin_data.atomic_orbital_labels

        if coeff.ndim != 2:
            raise ValueError("coefficient_matrix must be a 2D array")
        if len(labels) != coeff.shape[0]:
            raise ValueError("atomic_orbital_labels length must match coefficient_matrix rows")

        try:
            ao_index = labels.index(atomic_orbital_label)
        except ValueError as exc:
            raise ValueError(f"atomic orbital label not found: {atomic_orbital_label}") from exc

        contributions = []
        for mo_index, coefficient in enumerate(coeff[ao_index, :]):
            coefficient = float(coefficient)
            abs_coefficient = abs(coefficient)
            if abs_coefficient + 1e-12 < coefficient_threshold:
                continue
            contributions.append(AtomicOrbitalContribution(
                file_index=file_index,
                path=path,
                spin=spin,
                atomic_orbital_label=atomic_orbital_label,
                atomic_orbital_index=ao_index,
                mo_index=mo_index,
                mo_label=cls._mo_label(spin_data, mo_index),
                mo_energy=cls._mo_energy(spin_data, mo_index),
                coefficient=coefficient,
                abs_coefficient=abs_coefficient,
            ))
        return contributions

    @staticmethod
    def _select_spin_data(diagram: ParsedDiagram, spin: str) -> SpinData:
        if spin == "alpha":
            return diagram.alpha
        if spin == "beta":
            return diagram.beta
        raise ValueError("spin must be 'alpha' or 'beta'")

    @staticmethod
    def _within_relative_tolerance(reference: float, value: float, tolerance: float) -> bool:
        reference = abs(float(reference))
        value = abs(float(value))
        if reference == 0:
            return value == 0
        return abs(value - reference) <= (tolerance * reference) + 1e-12

    @classmethod
    def dominant_coefficients(
            cls,
            spin_data: SpinData,
            mo_index: int,
            coefficient_threshold: float = 0.3,
    ) -> List[Tuple[str, float, float]]:
        cls._validate_similarity_options(0.0, coefficient_threshold)
        coeff = np.asarray(spin_data.coefficient_matrix, dtype=float)
        labels = spin_data.atomic_orbital_labels

        if coeff.ndim != 2:
            raise ValueError("coefficient_matrix must be a 2D array")
        if len(labels) != coeff.shape[0]:
            raise ValueError("atomic_orbital_labels length must match coefficient_matrix rows")
        if not 0 <= mo_index < coeff.shape[1]:
            raise IndexError("mo_index out of range")

        column = coeff[:, mo_index]
        order = np.argsort(np.abs(column))[::-1]
        dominant = []

        for ao_index in order:
            value = float(column[ao_index])
            abs_value = abs(value)
            if abs_value < coefficient_threshold:
                continue
            dominant.append((labels[ao_index], value, abs_value))

        return dominant

    @classmethod
    def coefficient_similarity_details(
            cls,
            left: SpinData,
            source_mo_index: int,
            right: SpinData,
            target_mo_index: int,
            tolerance: float = 0.20,
            coefficient_threshold: float = 0.3,
    ) -> Tuple[float, int, int, Tuple[str, ...]]:
        cls._validate_similarity_options(tolerance, coefficient_threshold)

        source_coefficients = cls.dominant_coefficients(
            left,
            source_mo_index,
            coefficient_threshold=coefficient_threshold,
        )
        target_matrix = np.asarray(right.coefficient_matrix, dtype=float)

        if target_matrix.ndim != 2:
            raise ValueError("coefficient_matrix must be a 2D array")
        if len(right.atomic_orbital_labels) != target_matrix.shape[0]:
            raise ValueError("atomic_orbital_labels length must match coefficient_matrix rows")
        if not 0 <= target_mo_index < target_matrix.shape[1]:
            raise IndexError("target_mo_index out of range")

        target_by_label = {
            label: abs(float(target_matrix[ao_index, target_mo_index]))
            for ao_index, label in enumerate(right.atomic_orbital_labels)
        }

        matched_labels = []
        for label, _source_value, source_abs in source_coefficients:
            target_abs = target_by_label.get(label)
            if target_abs is None:
                continue
            if cls._within_relative_tolerance(source_abs, target_abs, tolerance):
                matched_labels.append(label)

        compared = len(source_coefficients)
        matching = len(matched_labels)
        score = matching / compared if compared else 0.0
        return score, compared, matching, tuple(matched_labels)

    @classmethod
    def coefficient_similarity(
            cls,
            left: SpinData,
            source_mo_index: int,
            right: SpinData,
            target_mo_index: int,
            tolerance: float = 0.20,
            coefficient_threshold: float = 0.3,
    ) -> Tuple[float, int, int]:
        score, compared, matching, _matched_labels = cls.coefficient_similarity_details(
            left,
            source_mo_index,
            right,
            target_mo_index,
            tolerance=tolerance,
            coefficient_threshold=coefficient_threshold,
        )
        return score, compared, matching

    @classmethod
    def match_spin_data(
            cls,
            left: SpinData,
            right: SpinData,
            tolerance: float = 0.20,
            min_score: float = 1.0,
            coefficient_threshold: float = 0.3,
            one_to_one: bool = True,
            source_mo_indices: Optional[Sequence[int]] = None,
            target_mo_indices: Optional[Sequence[int]] = None,
    ) -> List[OrbitalMatch]:
        cls._validate_similarity_options(tolerance, coefficient_threshold)
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")

        left_mo_count = cls._mo_count(left)
        right_mo_count = cls._mo_count(right)
        if source_mo_indices is None:
            source_indices = list(range(left_mo_count))
        elif isinstance(source_mo_indices, int):
            source_indices = [source_mo_indices]
        else:
            source_indices = list(source_mo_indices)

        if target_mo_indices is None:
            target_indices = list(range(right_mo_count))
        elif isinstance(target_mo_indices, int):
            target_indices = [target_mo_indices]
        else:
            target_indices = list(target_mo_indices)

        for source_mo_index in source_indices:
            if not 0 <= source_mo_index < left_mo_count:
                raise IndexError("source_mo_indices contains an out-of-range MO index")
        for target_mo_index in target_indices:
            if not 0 <= target_mo_index < right_mo_count:
                raise IndexError("target_mo_indices contains an out-of-range MO index")

        candidates = []
        for source_mo_index in source_indices:
            for target_mo_index in target_indices:
                score, compared, matching, matched_labels = cls.coefficient_similarity_details(
                    left,
                    source_mo_index,
                    right,
                    target_mo_index,
                    tolerance=tolerance,
                    coefficient_threshold=coefficient_threshold,
                )
                if compared == 0 or score + 1e-12 < min_score:
                    continue
                candidates.append(OrbitalMatch(
                    source_mo_index=source_mo_index,
                    target_mo_index=target_mo_index,
                    source_mo_label=cls._mo_label(left, source_mo_index),
                    target_mo_label=cls._mo_label(right, target_mo_index),
                    score=score,
                    compared_coefficients=compared,
                    matching_coefficients=matching,
                    matched_atomic_orbitals=matched_labels,
                ))

        candidates.sort(key=lambda match: (
            -match.score,
            -match.matching_coefficients,
            -match.compared_coefficients,
            match.source_mo_index,
            match.target_mo_index,
        ))

        if one_to_one:
            used_sources = set()
            used_targets = set()
            matches = []
            for match in candidates:
                if match.source_mo_index in used_sources or match.target_mo_index in used_targets:
                    continue
                used_sources.add(match.source_mo_index)
                used_targets.add(match.target_mo_index)
                matches.append(match)
        else:
            matches = candidates

        return sorted(matches, key=lambda match: (match.source_mo_index, match.target_mo_index))

    @classmethod
    def _track_step(
            cls,
            file_index: int,
            path: str,
            spin: str,
            spin_data: SpinData,
            mo_index: int,
            match: Optional[OrbitalMatch] = None,
    ) -> OrbitalTrackStep:
        return OrbitalTrackStep(
            file_index=file_index,
            path=path,
            spin=spin,
            mo_index=mo_index,
            mo_label=cls._mo_label(spin_data, mo_index),
            mo_energy=cls._mo_energy(spin_data, mo_index),
            score_from_previous=match.score if match else None,
            compared_coefficients=match.compared_coefficients if match else None,
            matching_coefficients=match.matching_coefficients if match else None,
            matched_atomic_orbitals=match.matched_atomic_orbitals if match else (),
        )

    @classmethod
    def track_orbitals(
            cls,
            paths: Sequence[str],
            spin: str = "alpha",
            tolerance: float = 0.20,
            min_score: float = 1.0,
            coefficient_threshold: float = 0.3,
            start_mo_indices: Optional[Sequence[int]] = None,
            one_to_one: bool = True,
    ) -> OrbitalTrackingSequence:
        cls._validate_similarity_options(tolerance, coefficient_threshold)
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")

        path_list = [str(path) for path in paths]
        diagrams = cls.load_many(path_list)
        if not diagrams:
            return OrbitalTrackingSequence(path_list, spin, [], [])

        spin_data_by_file = [cls._select_spin_data(diagram, spin) for diagram in diagrams]
        first_spin_data = spin_data_by_file[0]
        mo_count = cls._mo_count(first_spin_data)

        if start_mo_indices is None:
            start_indices = list(range(mo_count))
        elif isinstance(start_mo_indices, int):
            start_indices = [start_mo_indices]
        else:
            start_indices = list(start_mo_indices)

        for mo_index in start_indices:
            if not 0 <= mo_index < mo_count:
                raise IndexError("start_mo_indices contains an out-of-range MO index")

        tracks = [
            OrbitalTrack(
                spin=spin,
                start_mo_index=mo_index,
                start_mo_label=cls._mo_label(first_spin_data, mo_index),
                steps=[cls._track_step(0, path_list[0], spin, first_spin_data, mo_index)],
            )
            for mo_index in start_indices
        ]

        transition_matches = []
        for file_index in range(len(spin_data_by_file) - 1):
            active_source_indices = [
                track.steps[-1].mo_index
                for track in tracks
                if track.steps[-1].file_index == file_index
            ]
            matches = cls.match_spin_data(
                spin_data_by_file[file_index],
                spin_data_by_file[file_index + 1],
                tolerance=tolerance,
                min_score=min_score,
                coefficient_threshold=coefficient_threshold,
                one_to_one=one_to_one,
                source_mo_indices=active_source_indices,
            )
            transition_matches.append(matches)

            matches_by_source = {}
            for match in matches:
                matches_by_source.setdefault(match.source_mo_index, match)

            for track in tracks:
                last_step = track.steps[-1]
                if last_step.file_index != file_index:
                    continue
                match = matches_by_source.get(last_step.mo_index)
                if match is None:
                    continue
                next_spin_data = spin_data_by_file[file_index + 1]
                track.steps.append(cls._track_step(
                    file_index + 1,
                    path_list[file_index + 1],
                    spin,
                    next_spin_data,
                    match.target_mo_index,
                    match,
                ))

        return OrbitalTrackingSequence(path_list, spin, tracks, transition_matches)

    @classmethod
    def track_atomic_orbitals(
            cls,
            paths: Sequence[str],
            spin: str = "alpha",
            atomic_orbital_labels: Optional[Sequence[str]] = None,
            atom: Optional[str] = None,
            orbital_names: Optional[Sequence[str]] = None,
            coefficient_threshold: float = 0.0,
    ) -> AtomicOrbitalTrackingSequence:
        cls._validate_similarity_options(0.0, coefficient_threshold)

        path_list = [str(path) for path in paths]
        diagrams = cls.load_many(path_list)
        if not diagrams:
            return AtomicOrbitalTrackingSequence(path_list, spin, (), [])

        spin_data_by_file = [cls._select_spin_data(diagram, spin) for diagram in diagrams]
        first_spin_data = spin_data_by_file[0]

        if atomic_orbital_labels is None:
            selected_labels = cls.atomic_orbital_labels(
                first_spin_data,
                atom=atom,
                orbital_names=orbital_names,
            )
        else:
            selected_labels = cls._normalize_string_sequence(atomic_orbital_labels)

        selected_labels = list(dict.fromkeys(selected_labels or []))
        if not selected_labels:
            raise ValueError("No atomic orbitals selected")

        missing_first_file = [
            label for label in selected_labels
            if label not in first_spin_data.atomic_orbital_labels
        ]
        if missing_first_file:
            raise ValueError(
                "atomic_orbital_labels not found in the first file: "
                + ", ".join(missing_first_file)
            )

        tracks = []
        for label in selected_labels:
            start_index = first_spin_data.atomic_orbital_labels.index(label)
            contributions = []
            for file_index, spin_data in enumerate(spin_data_by_file):
                if label not in spin_data.atomic_orbital_labels:
                    continue
                contributions.extend(cls.atomic_orbital_contributions(
                    spin_data,
                    label,
                    file_index=file_index,
                    path=path_list[file_index],
                    spin=spin,
                    coefficient_threshold=coefficient_threshold,
                ))
            tracks.append(AtomicOrbitalTrack(
                spin=spin,
                atomic_orbital_label=label,
                start_atomic_orbital_index=start_index,
                contributions=contributions,
            ))

        return AtomicOrbitalTrackingSequence(
            paths=path_list,
            spin=spin,
            atomic_orbital_labels=tuple(selected_labels),
            tracks=tracks,
        )

    @classmethod
    def dos_threshold_intervals(
            cls,
            energies,
            intensity,
            threshold_fraction: float = 0.1,
    ) -> Tuple[Tuple[float, float], ...]:
        if threshold_fraction < 0:
            raise ValueError("threshold_fraction must be non-negative")

        energies = np.asarray(energies, dtype=float)
        intensity = np.abs(np.asarray(intensity, dtype=float))
        if energies.shape != intensity.shape:
            raise ValueError("energies and intensity must have the same shape")
        if energies.size == 0:
            return ()

        finite = np.isfinite(energies) & np.isfinite(intensity)
        energies = energies[finite]
        intensity = intensity[finite]
        if energies.size == 0:
            return ()

        order = np.argsort(energies)
        energies = energies[order]
        intensity = intensity[order]

        max_intensity = float(np.max(intensity))
        if np.isclose(max_intensity, 0.0):
            return ()

        threshold = float(threshold_fraction) * max_intensity
        above = intensity > threshold
        intervals = []
        start = None

        for idx, is_above in enumerate(above):
            if is_above and start is None:
                if idx == 0:
                    start = float(energies[idx])
                else:
                    start = cls._threshold_crossing_energy(
                        energies[idx - 1],
                        intensity[idx - 1],
                        energies[idx],
                        intensity[idx],
                        threshold,
                    )
            elif not is_above and start is not None:
                end = cls._threshold_crossing_energy(
                    energies[idx - 1],
                    intensity[idx - 1],
                    energies[idx],
                    intensity[idx],
                    threshold,
                )
                intervals.append((float(start), float(end)))
                start = None

        if start is not None:
            intervals.append((float(start), float(energies[-1])))

        return tuple(intervals)

    @staticmethod
    def _threshold_crossing_energy(energy_a, intensity_a, energy_b, intensity_b, threshold) -> float:
        energy_a = float(energy_a)
        intensity_a = float(intensity_a)
        energy_b = float(energy_b)
        intensity_b = float(intensity_b)
        if np.isclose(intensity_a, intensity_b):
            return energy_a
        fraction = (float(threshold) - intensity_a) / (intensity_b - intensity_a)
        fraction = min(max(fraction, 0.0), 1.0)
        return energy_a + fraction * (energy_b - energy_a)

    @staticmethod
    def default_lcfo_path(mo_diagram_path: str) -> str:
        directory = Path(mo_diagram_path).parent
        exact = directory / "DOSCAR.LCFO.lobster"
        if exact.exists():
            return str(exact)

        for path in (directory.iterdir() if directory.is_dir() else []):
            if path.is_file() and path.name.lower() == "doscar.lcfo.lobster":
                return str(path)
        return str(exact)

    @staticmethod
    def default_structure_path(lcfo_path: str) -> str:
        directory = Path(lcfo_path).parent
        for name in ("CONTCAR", "POSCAR"):
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
        raise FileNotFoundError(f"No CONTCAR or POSCAR found next to {lcfo_path}")

    @classmethod
    def default_lcfo_doscar_loader(cls, lcfo_path: str):
        from lobster.lobster_outputs import Doscar as DOSCAR

        path = Path(lcfo_path)
        if not path.exists():
            raise FileNotFoundError(f"LCFO DOSCAR not found: {lcfo_path}")
        return DOSCAR(str(path), False, cls.default_structure_path(str(path)))

    @staticmethod
    def _spin_to_dos_spin(spin: str):
        if spin == "alpha":
            return Spin.up
        if spin == "beta":
            return Spin.down
        raise ValueError("spin must be 'alpha' or 'beta'")

    @staticmethod
    def _label_suffix_match(value: str, suffix: str) -> bool:
        value = str(value).strip().lower()
        suffix = str(suffix).strip().lower()
        if not suffix or not value.endswith(suffix):
            return False

        prefix_length = len(value) - len(suffix)
        if prefix_length == 0:
            return True
        return not value[prefix_length - 1].isalnum()

    @classmethod
    def _find_pdos_orbital_key(cls, pdos, mo_label: str):
        if mo_label in pdos:
            return mo_label

        def normalized(value):
            return re.sub(r"[^a-z0-9]+", "", str(value).lower())

        target = normalized(mo_label)
        for key in pdos:
            if normalized(key) == target:
                return key

        for key in pdos:
            key_text = str(key)
            if cls._label_suffix_match(key_text, mo_label) or cls._label_suffix_match(mo_label, key_text):
                return key
        return None

    @classmethod
    def _lcfo_dos_for_molecular_orbital(cls, doscar, mo_label: str, spin: str):
        dos_spin = cls._spin_to_dos_spin(spin)
        energies = np.asarray(doscar.energies, dtype=float)
        values = np.zeros_like(energies, dtype=float)
        entity_labels = []
        dos_orbital_label = None

        entities = getattr(doscar, "entities", [])
        for entity_index, pdos in enumerate(doscar.pdos):
            orbital_key = cls._find_pdos_orbital_key(pdos, mo_label)
            if orbital_key is None:
                continue
            spin_data = pdos[orbital_key]
            if dos_spin not in spin_data:
                continue

            data = np.asarray(spin_data[dos_spin], dtype=float)
            if data.shape != energies.shape:
                raise ValueError(
                    f"DOS shape for {mo_label} in entity {entity_index} does not match energies"
                )
            values += data
            dos_orbital_label = str(orbital_key)
            if entity_index < len(entities):
                entity_labels.append(str(entities[entity_index]))
            else:
                entity_labels.append(str(entity_index))

        if dos_orbital_label is None:
            return None
        return dos_orbital_label, tuple(entity_labels), energies, values

    @classmethod
    def build_flow_chart_data(
            cls,
            paths: Sequence[str],
            atomic_orbital_labels: Sequence[str],
            ao_coefficient_threshold: float = 0.3,
            dos_threshold_fraction: float = 0.1,
            doscar_loader: Optional[Callable[[str], object]] = None,
            lcfo_path_resolver: Optional[Callable[[str], str]] = None,
            spins: Sequence[str] = ("alpha", "beta"),
            strict: bool = True,
    ) -> FlowChartData:
        cls._validate_similarity_options(0.0, ao_coefficient_threshold)
        if dos_threshold_fraction < 0:
            raise ValueError("dos_threshold_fraction must be non-negative")

        path_list = [str(path) for path in paths]
        selected_labels = cls._normalize_string_sequence(atomic_orbital_labels)
        selected_labels = list(dict.fromkeys(selected_labels or []))
        if not selected_labels:
            raise ValueError("No atomic orbitals selected")

        if isinstance(spins, str):
            spin_values = [spins]
        else:
            spin_values = list(spins)
        for spin in spin_values:
            if spin not in {"alpha", "beta"}:
                raise ValueError("spins must contain only 'alpha' and/or 'beta'")

        diagrams = cls.load_many(path_list)
        doscar_loader = doscar_loader or cls.default_lcfo_doscar_loader
        lcfo_path_resolver = lcfo_path_resolver or cls.default_lcfo_path

        frames = []
        errors = []
        doscar_cache = {}

        for file_index, diagram in enumerate(diagrams):
            path = path_list[file_index]
            lcfo_path = lcfo_path_resolver(path)
            doscar = None

            for spin in spin_values:
                spin_data = cls._select_spin_data(diagram, spin)
                contributions_by_mo = {}

                for label in selected_labels:
                    if label not in spin_data.atomic_orbital_labels:
                        continue
                    for contribution in cls.atomic_orbital_contributions(
                            spin_data,
                            label,
                            file_index=file_index,
                            path=path,
                            spin=spin,
                            coefficient_threshold=0.0,
                    ):
                        contributions_by_mo.setdefault(contribution.mo_index, []).append(contribution)

                try:
                    if lcfo_path not in doscar_cache:
                        doscar_cache[lcfo_path] = doscar_loader(lcfo_path)
                    doscar = doscar_cache[lcfo_path]
                except Exception as exc:
                    message = f"{Path(path).name}: {exc}"
                    if strict:
                        raise
                    errors.append(message)
                    continue

                for mo_index in range(cls._mo_count(spin_data)):
                    mo_label = cls._mo_label(spin_data, mo_index)
                    try:
                        dos_result = cls._lcfo_dos_for_molecular_orbital(doscar, mo_label, spin)
                    except Exception as exc:
                        message = f"{Path(path).name} {mo_label} {spin}: {exc}"
                        if strict:
                            raise
                        errors.append(message)
                        continue
                    if dos_result is None:
                        errors.append(f"{Path(path).name}: no LCFO DOS for {mo_label} ({spin})")
                        continue

                    dos_orbital_label, entity_labels, energies, dos_values = dos_result
                    frames.append(FlowChartFrame(
                        file_index=file_index,
                        path=path,
                        lcfo_path=lcfo_path,
                        spin=spin,
                        mo_index=mo_index,
                        mo_label=mo_label,
                        mo_energy=cls._mo_energy(spin_data, mo_index),
                        contributions=tuple(contributions_by_mo.get(mo_index, ())),
                        dos_orbital_label=dos_orbital_label,
                        entity_labels=entity_labels,
                        energies=energies,
                        dos_values=dos_values,
                        intervals=cls.dos_threshold_intervals(
                            energies,
                            dos_values,
                            threshold_fraction=dos_threshold_fraction,
                        ),
                    ))

        return FlowChartData(
            paths=path_list,
            atomic_orbital_labels=tuple(selected_labels),
            ao_coefficient_threshold=float(ao_coefficient_threshold),
            dos_threshold_fraction=float(dos_threshold_fraction),
            frames=frames,
            errors=errors,
        )


class MODiagramViewModel(QtCore.QObject):
    """Application logic + state."""

    data_changed = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.diagram = None
        self.spin = "alpha"
        self.threshold = 0.3
        self.path = None
        self.files = []
        self.cube_manager = None

    def load_file(self, path: str):
        from pathlib import Path
        if not Path(path).exists():
            return
        self.path = str(path)
        self.diagram = LobsterModel.load(path)
        self.data_changed.emit()
        self.cube_manager = CubeManager()
        basename = os.path.basename(path).split("_")[0]
        self.cube_manager.load_directory(os.path.dirname(path), basename)
        self.cube_manager.render_all_screenshots()
        self.save_mo_images()
        self.files = os.listdir(os.path.dirname(path))

    @staticmethod
    def is_mo_diagram_file(path: Path) -> bool:
        return path.is_file() and path.name.lower().endswith("mo_diagram.lobster")

    @classmethod
    def find_mo_diagram_paths(cls, directory: str) -> List[str]:
        root = Path(directory)
        if not root.is_dir():
            return []
        return sorted(str(path) for path in root.rglob("*") if cls.is_mo_diagram_file(path))

    def mo_diagram_paths_in_loaded_dir(self) -> List[str]:
        if not self.path:
            return []
        directory = os.path.dirname(self.path)
        if not os.path.isdir(directory):
            return [self.path]
        paths = self.find_mo_diagram_paths(directory)
        return sorted(paths) or [self.path]

    def set_spin(self, spin: str):
        self.spin = spin
        self.data_changed.emit()

    def set_threshold(self, value: int):
        self.threshold = value / 100.0
        self.data_changed.emit()

    def active(self):
        if not self.diagram:
            return None
        return self.diagram.alpha if self.spin == "alpha" else self.diagram.beta

    def get_cube_for_mo(self, label):
        spin_data = self.active()

        insertion = '1' if self.spin == "alpha" else '2'

        lst = label.split("_")
        lst.insert(2, insertion)
        cube_name = "_".join(lst)

        for file in self.files:
            if cube_name in file:
                if file.endswith(".cube"):
                    return file

        return None

    @staticmethod
    def spread_positions(energies, x_center, tol=2):
        rounded = np.round(energies / tol) * tol
        out = [None] * len(energies)
        for r in np.unique(rounded):
            idx = np.where(rounded == r)[0]
            offsets = [0.0] if len(idx) == 1 else np.linspace(-0.5, 0.5, len(idx))
            for i, dx in zip(idx, offsets):
                out[i] = (energies[i], x_center + dx)

        return out

    def save_mo_images(self):
        qm = QtWidgets.QMessageBox()
        ret = qm.question(None, '', "Do You want to save MO images?", qm.Yes | qm.No)
        if ret == qm.Yes:
            for mo_name, mo_image in self.cube_manager.screenshots.items():
                clean_name = self.clean_mo_image_name(mo_name)
                output_path = self.mo_image_output_path(clean_name)
                self.save_mo_image_array(
                    mo_image,
                    output_path,
                    height=MO_IMAGE_EXPORT_HEIGHT,
                    label=clean_name,
                )

    @classmethod
    def save_mo_image_array(
            cls,
            image,
            output_path: Path,
            height: int = MO_IMAGE_EXPORT_HEIGHT,
            label: Optional[str] = None,
    ):
        qimage = cls.qimage_from_array(image)
        if qimage.isNull():
            raise ValueError("Cannot save an empty MO image")

        source_width = qimage.width()
        source_height = qimage.height()
        if source_width <= 0 or source_height <= 0:
            raise ValueError("Cannot save an empty MO image")

        target_height = int(height)
        if target_height <= 0:
            raise ValueError("MO image export height must be positive")
        target_width = max(1, round(target_height * source_width / source_height))
        target_size = QtCore.QSize(target_width, target_height)

        scaled = qimage.scaled(
            target_size,
            QtCore.Qt.KeepAspectRatioByExpanding,
            QtCore.Qt.SmoothTransformation,
        )
        if scaled.size() != target_size:
            left = max(0, (scaled.width() - target_width) // 2)
            top = max(0, (scaled.height() - target_height) // 2)
            scaled = scaled.copy(left, top, target_width, target_height)

        if label:
            cls.draw_mo_image_label(scaled, str(label))

        if not scaled.save(str(output_path)):
            raise OSError(f"Could not save MO image: {output_path}")

    @staticmethod
    def draw_mo_image_label(image: QtGui.QImage, label: str):
        painter = QtGui.QPainter(image)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)

            band_height = max(40, round(image.height() * 0.06))
            margin = max(12, round(image.height() * 0.015))
            band_rect = QtCore.QRect(0, image.height() - band_height, image.width(), band_height)
            painter.fillRect(band_rect, QtGui.QColor(0, 0, 0, 0))

            font = QtGui.QFont("Arial")
            font.setBold(True)
            font.setPixelSize(max(20, round(band_height * 0.45)))
            painter.setFont(font)
            painter.setPen(QtGui.QColor(0,0,0))

            text_rect = band_rect.adjusted(margin, 0, -margin, 0)
            metrics = QtGui.QFontMetrics(font)
            elided_label = metrics.elidedText(label, QtCore.Qt.ElideMiddle, text_rect.width())
            painter.drawText(text_rect, QtCore.Qt.AlignCenter, elided_label)
        finally:
            painter.end()

    @staticmethod
    def qimage_from_array(image) -> QtGui.QImage:
        array = np.asarray(image)
        if array.ndim == 2:
            array = np.stack((array, array, array), axis=-1)
        if array.ndim != 3 or array.shape[2] not in (3, 4):
            raise ValueError("MO image array must be grayscale, RGB, or RGBA")

        if array.dtype != np.uint8:
            array = np.clip(array, 0, 255).astype(np.uint8)
        array = np.ascontiguousarray(array)

        height, width, channels = array.shape
        bytes_per_line = channels * width
        if channels == 3:
            image_format = QtGui.QImage.Format_RGB888
        else:
            image_format = QtGui.QImage.Format_RGBA8888

        return QtGui.QImage(
            array.data,
            width,
            height,
            bytes_per_line,
            image_format,
        ).copy()

    def mo_image_output_path(self, clean_name: str) -> Path:
        output_dir = Path(self.path).parent if self.path else Path.cwd()
        return output_dir / f"{clean_name}.jpg"

    def clean_mo_image_name(self, mo_name: str) -> str:
        stem = Path(str(mo_name)).stem

        labels = []
        if self.diagram is not None:
            for spin_data, insertion in ((self.diagram.alpha, "1"), (self.diagram.beta, "2")):
                for label in spin_data.molecular_orbitals:
                    labels.append(str(label))
                    parts = str(label).split("_")
                    parts.insert(2, insertion)
                    labels.append("_".join(parts))

        for label in sorted(set(labels), key=len, reverse=True):
            if stem == label:
                return label
            if stem.startswith(label) and not stem[len(label):len(label) + 1].isalnum():
                return label

        return stem.split("-", 1)[0]


class MODiagramView(QtWidgets.QMainWindow):
    def __init__(self, vm: MODiagramViewModel):
        super().__init__()
        self.vm = vm
        self.setWindowTitle("MO Diagram (MVVM)")
        self.resize(1200, 800)

        self.plot = pg.PlotWidget(background="w")
        self.setCentralWidget(self.plot)

        self.proxy = pg.SignalProxy(
            self.plot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.on_mouse_moved
        )

        self.hover_window = QtWidgets.QDialog()
        self.hover_window.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )

        layout = QtWidgets.QVBoxLayout(self.hover_window)
        self.hover_img = pg.ImageView()
        self.hover_img.ui.histogram.hide()
        self.hover_img.ui.roiBtn.hide()
        self.hover_img.ui.menuBtn.hide()
        layout.addWidget(self.hover_img)
        self.hover_window.resize(500, 500)

        self.plot.scene().sigMouseClicked.connect(self.on_mouse_clicked)

        self._build_toolbar()

        self.vm.data_changed.connect(self.first_render)

    def _build_toolbar(self):
        tb = QtWidgets.QToolBar()
        self.addToolBar(tb)

        btn = QtWidgets.QPushButton("Open")
        btn.clicked.connect(self.open_file)
        tb.addWidget(btn)

        self.spin = QtWidgets.QComboBox()
        self.spin.addItems(["alpha", "beta"])
        self.spin.currentTextChanged.connect(self.vm.set_spin)
        tb.addWidget(self.spin)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(30)
        self.slider.valueChanged.connect(self.vm.set_threshold)
        tb.addWidget(self.slider)

        track_ao_btn = QtWidgets.QPushButton("Track AO")
        track_ao_btn.clicked.connect(self.track_atomic_orbitals)
        tb.addWidget(track_ao_btn)

    def open_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open", os.getcwd()
        )
        if path:
            self.vm.load_file(path)

    def track_atomic_orbitals(self):
        if not self.vm.diagram:
            QtWidgets.QMessageBox.warning(self, "Track AO", "Open an MO diagram file first.")
            return

        setup_dialog = AOTrackingSetupDialog(self, self.vm)
        if setup_dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        try:
            sequence = LobsterModel.track_atomic_orbitals(
                setup_dialog.selected_paths(),
                spin=self.vm.spin,
                atomic_orbital_labels=setup_dialog.selected_labels(),
                coefficient_threshold=setup_dialog.coefficient_threshold(),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Track AO", str(exc))
            return

        result_dialog = AOTrackingResultDialog(self, sequence)
        result_dialog.resize(900, 600)
        result_dialog.exec_()

    def first_render(self):
        self.mo_items = []
        self.ao_items = []
        self.conn_items = []
        self.mo_labels = []
        self.ao_labels = []
        self.plot.clear()
        spin_data = self.vm.active()
        if not spin_data:
            return

        group_names = list(spin_data.atomic_groups.keys())
        x_positions = [(i + 1) * 3 + 5 for i in range(len(group_names) + 1)]

        mo_x = x_positions.pop(len(group_names) // 2)
        ao_x = x_positions

        ao_positions = []

        for i, energies in enumerate(spin_data.ao_energies_by_group):
            pts = self.vm.spread_positions(energies, ao_x[i])
            labels = spin_data.atomic_groups[group_names[i]]

            for k, (e, x) in enumerate(pts):
                item = self.plot.plot([x - 0.15, x + 0.15], [e, e], pen="k", width=ORB_LINE_WIDTH)
                item.ao_index = len(self.ao_items)
                self.ao_items.append(item)

                label = pg.TextItem(labels[k], anchor=(0.5, 0))
                label.setPos(x, e - 0.1)
                label.ao_index = len(self.ao_labels)
                self.ao_labels.append(label)
                self.plot.addItem(label)

            ao_positions.extend(pts)

        mo_positions = self.vm.spread_positions(spin_data.mo_energies, mo_x)
        for j, (e, x) in enumerate(mo_positions):
            item = self.plot.plot([x - 0.15, x + 0.15], [e, e], pen="b", width=ORB_LINE_WIDTH)
            item.mo_index = j
            self.mo_items.append(item)

            label = pg.TextItem(spin_data.molecular_orbitals[j], anchor=(0.5, 0))
            label.setPos(x, e - 0.1)
            label.mo_index = j
            self.mo_labels.append(label)
            self.plot.addItem(label)

        for i in range(spin_data.coefficient_matrix.shape[0]):
            for j in range(spin_data.coefficient_matrix.shape[1]):
                val = spin_data.coefficient_matrix[i, j]
                if abs(val) < self.vm.threshold:
                    continue

                item = self.plot.plot(
                    [ao_positions[i][1], mo_positions[j][1]],
                    [ao_positions[i][0], mo_positions[j][0]],
                    pen=pg.mkPen(width=1)
                )
                item.ao_index = i
                item.mo_index = j
                self.conn_items.append(item)

    def on_mouse_moved(self, evt):
        pos = evt[0]
        vb = self.plot.getViewBox()

        closest_mo = None
        min_dist = 3  # pixels

        for j, item in enumerate(self.mo_items):
            data = item.getData()
            x_vals = data[0]
            y_val = data[1][0]

            x_min = np.min(x_vals)
            x_max = np.max(x_vals)

            # map segment endpoints to scene (pixel space)
            p1 = vb.mapViewToScene(QtCore.QPointF(x_min, y_val))
            p2 = vb.mapViewToScene(QtCore.QPointF(x_max, y_val))

            px, py = pos.x(), pos.y()

            # check if mouse is horizontally within the segment
            if p1.x() <= px <= p2.x() or p2.x() <= px <= p1.x():
                dx = 0
            else:
                dx = min(abs(px - p1.x()), abs(px - p2.x()))

            dy = abs(py - p1.y())

            dist = (dx ** 2 + dy ** 2) ** 0.5

            if dist < min_dist:
                closest_mo = j
                min_dist = dist

        self.highlight_mo(closest_mo)

    def highlight_mo(self, mo_index):
        # reset visuals (unchanged)
        for item in self.mo_items:
            item.setPen(pg.mkPen("b", width=ORB_LINE_WIDTH))
        for item in self.ao_items:
            item.setPen(pg.mkPen("k", width=ORB_LINE_WIDTH))
        for item in self.conn_items:
            item.setPen(pg.mkPen(width=1))

        for label in self.mo_labels:
            label.setColor("k")
        for label in self.ao_labels:
            label.setColor("k")

        # hide window if nothing selected
        if mo_index is None:
            self.hover_window.hide()
            return

        # highlight MO
        self.mo_items[mo_index].setPen(pg.mkPen("r", width=ORB_LINE_WIDTH+1))
        self.mo_labels[mo_index].setColor("r")

        for item in self.conn_items:
            if item.mo_index == mo_index:
                item.setPen(pg.mkPen("r", width=1.5))
                ao_i = item.ao_index
                self.ao_items[ao_i].setPen(pg.mkPen("r", width=ORB_LINE_WIDTH+1))
                self.ao_labels[ao_i].setColor("r")

        # show screenshot
        spin_data = self.vm.active()
        mo_label = spin_data.molecular_orbitals[mo_index]
        cube_name = self.vm.get_cube_for_mo(mo_label)

        if cube_name:
            shot = self.vm.cube_manager.screenshots.get(cube_name)
            if shot is not None:
                self.hover_img.setImage(shot, axes={'x': 1, 'y': 0, 'c': 2})

                # position near cursor / window
                cursor_pos = QtGui.QCursor.pos()
                self.hover_window.move(cursor_pos + QtCore.QPoint(20, 20))
                self.hover_window.show()

    def on_mouse_clicked(self, evt):
        self.hover_window.hide()
        pos = evt.scenePos()
        vb = self.plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)

        x = mouse_point.x()
        y = mouse_point.y()

        closest_mo = None
        min_dist = 0.3

        for j, item in enumerate(self.mo_items):
            data = item.getData()
            y_mo = data[1][0]
            x_mo = np.mean(data[0])

            dist = abs(y - y_mo) + abs(x - x_mo)
            if dist < min_dist:
                closest_mo = j
                min_dist = dist

        if closest_mo is not None:
            self.show_mo_popup(closest_mo)

    def show_mo_popup(self, mo_index):
        dialog = MODialog(self, self.vm, mo_index)
        dialog.resize(900, 600)
        dialog.exec_()


class AOTrackingSetupDialog(QtWidgets.QDialog):
    def __init__(self, parent, vm):
        super().__init__(parent)
        self.vm = vm
        self.spin_data = vm.active()
        self.setWindowTitle("Track Atomic Orbitals")
        self.resize(650, 520)

        layout = QtWidgets.QVBoxLayout(self)

        files_label = QtWidgets.QLabel("MO diagram files")
        layout.addWidget(files_label)

        self.file_list = QtWidgets.QListWidget()
        layout.addWidget(self.file_list, 2)

        file_buttons = QtWidgets.QHBoxLayout()
        add_directory_btn = QtWidgets.QPushButton("Choose Directory")
        add_directory_btn.clicked.connect(self.add_directory)
        add_files_btn = QtWidgets.QPushButton("Add Files")
        add_files_btn.clicked.connect(self.add_files)
        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self.set_all_files_checked(True))
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(self.file_list.clear)
        file_buttons.addWidget(add_directory_btn)
        file_buttons.addWidget(add_files_btn)
        file_buttons.addWidget(select_all_btn)
        file_buttons.addWidget(clear_btn)
        layout.addLayout(file_buttons)

        for path in self.vm.mo_diagram_paths_in_loaded_dir():
            self.add_path(path, checked=True)

        form = QtWidgets.QFormLayout()
        self.atom_combo = QtWidgets.QComboBox()
        self.atom_combo.addItems(list(self.spin_data.atomic_groups.keys()))
        self.atom_combo.currentTextChanged.connect(self.populate_orbitals)
        form.addRow("Atom", self.atom_combo)

        self.threshold = QtWidgets.QDoubleSpinBox()
        self.threshold.setRange(0.0, 10.0)
        self.threshold.setDecimals(3)
        self.threshold.setSingleStep(0.05)
        self.threshold.setValue(self.vm.threshold)
        form.addRow("Minimum |coefficient|", self.threshold)
        layout.addLayout(form)

        orbitals_label = QtWidgets.QLabel("Atomic orbitals")
        layout.addWidget(orbitals_label)

        self.orbital_list = QtWidgets.QListWidget()
        layout.addWidget(self.orbital_list, 1)

        orbital_buttons = QtWidgets.QHBoxLayout()
        select_atom_btn = QtWidgets.QPushButton("Select Atom Orbitals")
        select_atom_btn.clicked.connect(lambda: self.set_all_orbitals_checked(True))
        clear_orbitals_btn = QtWidgets.QPushButton("Clear Orbitals")
        clear_orbitals_btn.clicked.connect(lambda: self.set_all_orbitals_checked(False))
        orbital_buttons.addWidget(select_atom_btn)
        orbital_buttons.addWidget(clear_orbitals_btn)
        layout.addLayout(orbital_buttons)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.atom_combo.count():
            self.populate_orbitals(self.atom_combo.currentText())

    def add_path(self, path: str, checked: bool = True):
        path = str(path)
        for row in range(self.file_list.count()):
            if self.file_list.item(row).data(QtCore.Qt.UserRole) == path:
                return

        item = QtWidgets.QListWidgetItem(self.path_label(path))
        item.setData(QtCore.Qt.UserRole, path)
        item.setToolTip(path)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        self.file_list.addItem(item)

    @staticmethod
    def path_label(path: str) -> str:
        file_path = Path(path)
        parent = file_path.parent.name
        if parent:
            return f"{parent} / {file_path.name}"
        return file_path.name

    def add_directory(self):
        start_dir = os.path.dirname(self.vm.path) if self.vm.path else os.getcwd()
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose directory with MO diagrams",
            start_dir,
        )
        if not directory:
            return

        paths = self.vm.find_mo_diagram_paths(directory)
        if not paths:
            QtWidgets.QMessageBox.information(
                self,
                "Track AO",
                "No *MO_Diagram.lobster files found in the selected directory.",
            )
            return

        for path in paths:
            self.add_path(path, checked=True)

    def add_files(self):
        start_dir = os.path.dirname(self.vm.path) if self.vm.path else os.getcwd()
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Add MO diagram files",
            start_dir,
            "LOBSTER files (*.lobster);;All files (*)",
        )
        for path in paths:
            self.add_path(path, checked=True)

    def set_all_files_checked(self, checked: bool):
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        for row in range(self.file_list.count()):
            self.file_list.item(row).setCheckState(state)

    def populate_orbitals(self, atom: str):
        self.orbital_list.clear()
        labels = self.spin_data.atomic_groups.get(atom, [])
        for row, label in enumerate(labels):
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            checked = row == 0 and len(labels) == 1
            item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            self.orbital_list.addItem(item)

    def set_all_orbitals_checked(self, checked: bool):
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        for row in range(self.orbital_list.count()):
            self.orbital_list.item(row).setCheckState(state)

    def selected_paths(self) -> List[str]:
        paths = []
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            if item.checkState() == QtCore.Qt.Checked:
                paths.append(item.data(QtCore.Qt.UserRole))
        return paths

    def selected_labels(self) -> List[str]:
        labels = []
        for row in range(self.orbital_list.count()):
            item = self.orbital_list.item(row)
            if item.checkState() == QtCore.Qt.Checked:
                labels.append(item.data(QtCore.Qt.UserRole))
        return labels

    def coefficient_threshold(self) -> float:
        return float(self.threshold.value())

    def accept(self):
        if not self.selected_paths():
            QtWidgets.QMessageBox.warning(self, "Track AO", "Select at least one MO diagram file.")
            return
        if not self.selected_labels():
            QtWidgets.QMessageBox.warning(self, "Track AO", "Select at least one atomic orbital.")
            return
        super().accept()


class AOTrackingResultDialog(QtWidgets.QDialog):
    def __init__(self, parent, sequence: AtomicOrbitalTrackingSequence):
        super().__init__(parent)
        self.sequence = sequence
        self.setWindowTitle("Atomic Orbital Tracking")

        layout = QtWidgets.QVBoxLayout(self)

        selected = ", ".join(sequence.atomic_orbital_labels)
        title = QtWidgets.QLabel(f"{sequence.spin} spin: {selected}")
        layout.addWidget(title)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "File",
            "AO",
            "MO",
            "Energy",
            "Coefficient",
            "|Coefficient|",
        ])
        layout.addWidget(self.table, 1)

        self.populate_table()

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_table(self):
        rows = []
        for track in self.sequence.tracks:
            rows.extend(track.contributions)
        rows.sort(key=lambda item: (
            item.file_index,
            item.atomic_orbital_label,
            -item.abs_coefficient,
            item.mo_index,
        ))

        self.table.setRowCount(len(rows))
        for row_index, contribution in enumerate(rows):
            file_item = QtWidgets.QTableWidgetItem(AOTrackingSetupDialog.path_label(contribution.path))
            file_item.setToolTip(contribution.path)
            file_item.setData(QtCore.Qt.UserRole, contribution.file_index)
            self.table.setItem(row_index, 0, file_item)

            self.table.setItem(row_index, 1, QtWidgets.QTableWidgetItem(contribution.atomic_orbital_label))
            self.table.setItem(row_index, 2, QtWidgets.QTableWidgetItem(contribution.mo_label))

            energy_item = QtWidgets.QTableWidgetItem(f"{contribution.mo_energy:.4f}")
            energy_item.setData(QtCore.Qt.UserRole, contribution.mo_energy)
            self.table.setItem(row_index, 3, energy_item)

            coefficient_item = QtWidgets.QTableWidgetItem(f"{contribution.coefficient:.4f}")
            coefficient_item.setData(QtCore.Qt.UserRole, contribution.coefficient)
            if contribution.coefficient < 0:
                coefficient_item.setForeground(QtCore.Qt.darkBlue)
            else:
                coefficient_item.setForeground(QtCore.Qt.darkRed)
            self.table.setItem(row_index, 4, coefficient_item)

            abs_item = QtWidgets.QTableWidgetItem(f"{contribution.abs_coefficient:.4f}")
            abs_item.setData(QtCore.Qt.UserRole, contribution.abs_coefficient)
            self.table.setItem(row_index, 5, abs_item)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()


class MODialog(QtWidgets.QDialog):
    def __init__(self, parent, vm, mo_index):
        super().__init__(parent)

        self.vm = vm
        self.mo_index = mo_index

        spin_data = self.vm.active()
        self.coeffs = spin_data.coefficient_matrix[:, mo_index]
        self.mo_label = spin_data.molecular_orbitals[mo_index]

        self.setWindowTitle(f"MO {self.mo_label}")
        self.resize(900, 600)

        layout = QtWidgets.QHBoxLayout(self)

        # left panel: table
        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Atomic Orbital", "Coefficient"])
        table.setRowCount(len(self.coeffs))

        for i, val in enumerate(self.coeffs):
            ao_label = spin_data.atomic_orbital_labels[i]
            table.setItem(i, 0, QtWidgets.QTableWidgetItem(ao_label))

            item = QtWidgets.QTableWidgetItem(f"{val:.4f}")
            if abs(val) > 0.3:
                item.setForeground(QtCore.Qt.red)
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            table.setItem(i, 1, item)

        table.resizeColumnsToContents()
        layout.addWidget(table, 1)

        # right: 3d view
        self.pv_widget = QtInteractor()
        self.pv_widget.enable_depth_peeling()
        self.pv_widget.enable_anti_aliasing('msaa', multi_samples=16)
        layout.addWidget(self.pv_widget, 2)

        # load cube
        cube_name = self.vm.get_cube_for_mo(self.mo_label)

        if cube_name:
            cube = self.vm.cube_manager.cubes[cube_name]
            self.vm.cube_manager.default_plotter_setup(self.pv_widget)
            self.vm.cube_manager.add_to_plotter(cube, self.pv_widget)

    def closeEvent(self, QCloseEvent):
        self.pv_widget.Finalize()
        super().closeEvent(QCloseEvent)


def main():
    app = QtWidgets.QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)

    vm = MODiagramViewModel()

    view = MODiagramView(vm)
    pth = r"D:\syncme\modelowanie DFT\co3o4_new_new\9.deep_o2_reduction\GOOD\1.spin_up\HSE\1.gas_to_metaloxo\2.1_almost_desorbed_small\1.mofe_o2\O2_1.MO_Diagram.lobster"
    view.vm.load_file(pth)
    view.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
