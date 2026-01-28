"""CivilQuant Pro — Moteur de métré DXF.

Objectif:
- Lire un fichier DXF (plan 2D) et extraire des quantités (métré) sans dépendance Flask.
- Produire un DataFrame pandas au format:
  [Désignation, Quantité, Unité, Catégorie]

Contraintes:
- Précision "ingénierie": on calcule les longueurs exactes (segments + arcs) et les aires via
  polygones (formule du lacet / Shoelace) avec approximation contrôlée pour les arcs.
- Robustesse: ignorer proprement les entités non supportées et continuer.

Notes d'ingénierie:
- Les DXF sont souvent en unités "mm" ou "cm". Le paramètre scale_factor convertit les unités
  de dessin vers des mètres. Ex: mm -> 0.001; cm -> 0.01; m -> 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, ceil, cos, pi, sin, sqrt
from pathlib import Path
from typing import Iterable, List, Sequence

import pandas as pd


@dataclass(frozen=True)
class TakeoffDiagnostic:
    niveau: str  # 'info' | 'warning' | 'error'
    message: str


def _norm_layer(layer: str | None) -> str:
    return (layer or '').strip().upper()


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return sqrt(dx * dx + dy * dy)


def _shoelace_area(points: Sequence[tuple[float, float]]) -> float:
    """Aire d'un polygone simple via la formule du lacet.

    Formule (points (x_i, y_i) fermés):
        A = 1/2 * |Σ (x_i*y_{i+1} - x_{i+1}*y_i)|

    On tolère que le premier point ne soit pas répété à la fin.
    """

    if len(points) < 3:
        return 0.0

    area2 = 0.0
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        area2 += x1 * y2 - x2 * y1
    return abs(area2) * 0.5


def _angle_normalize(theta: float) -> float:
    """Normalise un angle en radians dans [0, 2π)."""

    while theta < 0:
        theta += 2 * pi
    while theta >= 2 * pi:
        theta -= 2 * pi
    return theta


def _arc_delta_ccw(start: float, end: float) -> float:
    """Delta angulaire en sens anti-horaire dans [0, 2π]."""

    start_n = _angle_normalize(start)
    end_n = _angle_normalize(end)
    delta = end_n - start_n
    if delta < 0:
        delta += 2 * pi
    return delta


def _bulge_to_arc(
    start: tuple[float, float],
    end: tuple[float, float],
    bulge: float,
) -> tuple[tuple[float, float], float, float, float, int]:
    """Convertit un segment bulgé (LWPOLYLINE) en arc géométrique.

    Définitions DXF:
    - bulge = tan(θ/4) où θ est l'angle inclus de l'arc.
    - Le signe de bulge détermine le sens (bulge>0: arc CCW de start vers end).

    Retour:
    - center (cx, cy)
    - start_angle_rad, end_angle_rad (mesurés depuis le centre)
    - radius
    - direction (1=CCW, -1=CW)

    Références pratiques:
    - Cette géométrie est standard AutoCAD/DXF.
    """

    if bulge == 0:
        raise ValueError('bulge must be non-zero')

    x1, y1 = start
    x2, y2 = end

    chord = _distance(start, end)
    if chord == 0:
        raise ValueError('degenerate chord')

    theta = 4.0 * atan2(bulge, 1.0)  # angle inclus (rad), signe inclus
    direction = 1 if theta >= 0 else -1
    theta_abs = abs(theta)

    # Rayon: R = c / (2 sin(θ/2))
    sin_half = sin(theta_abs / 2.0)
    if sin_half == 0:
        raise ValueError('invalid bulge angle')
    radius = chord / (2.0 * sin_half)

    # Milieu de corde
    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0

    # Distance du centre au milieu de corde: h = sqrt(R^2 - (c/2)^2)
    half = chord / 2.0
    h_sq = max(radius * radius - half * half, 0.0)
    h = sqrt(h_sq)

    # Vecteur normal unitaire à la corde
    dx = (x2 - x1) / chord
    dy = (y2 - y1) / chord
    # Pour CCW, le centre est du côté gauche de la corde (rotation +90°)
    nx = -dy
    ny = dx

    # Sens CW inverse le côté
    side = 1.0 if direction == 1 else -1.0
    cx = mx + side * nx * h
    cy = my + side * ny * h

    start_angle = atan2(y1 - cy, x1 - cx)
    end_angle = atan2(y2 - cy, x2 - cx)

    return (cx, cy), start_angle, end_angle, radius, direction


def _sample_arc_points(
    center: tuple[float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    direction: int,
    max_step_deg: float = 5.0,
) -> List[tuple[float, float]]:
    """Échantillonne un arc en une polyline (liste de points).

    Pour la précision:
    - On contrôle l'angle max entre points (par défaut 5°).
    - Pour de très grands rayons, l'erreur de corde devient négligeable.

    Note:
    - On inclut les points d'extrémité.
    """

    cx, cy = center

    if max_step_deg <= 0:
        max_step_deg = 5.0

    max_step = max_step_deg * pi / 180.0

    if direction == 1:
        delta = _arc_delta_ccw(start_angle, end_angle)
        steps = max(1, int(ceil(delta / max_step)))
        pts: List[tuple[float, float]] = []
        for i in range(steps + 1):
            t = start_angle + (delta * i / steps)
            pts.append((cx + radius * cos(t), cy + radius * sin(t)))
        return pts

    # CW: on parcourt l'arc dans le sens horaire
    delta_ccw = _arc_delta_ccw(end_angle, start_angle)
    steps = max(1, int(ceil(delta_ccw / max_step)))
    pts = []
    for i in range(steps + 1):
        t = start_angle - (delta_ccw * i / steps)
        pts.append((cx + radius * cos(t), cy + radius * sin(t)))
    return pts


def _lwpolyline_length_and_points(entity) -> tuple[float, List[tuple[float, float]]]:
    """Calcule longueur d'une LWPOLYLINE et renvoie une liste de points aplatis.

    - Longueur: somme des segments droits + longueur des arcs (bulge).
    - Points: servent au calcul d'aire (Shoelace) sur une approximation maîtrisée.

    On récupère les points au format (x, y, bulge).
    """

    points = list(entity.get_points('xyb'))
    if not points:
        return 0.0, []

    is_closed = bool(getattr(entity, 'closed', False))

    # Prépare la liste des sommets (x, y, bulge)
    verts = [(float(x), float(y), float(b or 0.0)) for x, y, b in points]

    length = 0.0
    flat_points: List[tuple[float, float]] = [(verts[0][0], verts[0][1])]

    seg_count = len(verts) if is_closed else (len(verts) - 1)

    for i in range(seg_count):
        x1, y1, bulge = verts[i]
        if i == len(verts) - 1:
            x2, y2, _ = verts[0]
        else:
            x2, y2, _ = verts[i + 1]

        start = (x1, y1)
        end = (x2, y2)

        if bulge == 0.0:
            length += _distance(start, end)
            flat_points.append(end)
            continue

        center, a1, a2, radius, direction = _bulge_to_arc(start, end, bulge)
        if direction == 1:
            delta = _arc_delta_ccw(a1, a2)
        else:
            delta = _arc_delta_ccw(a2, a1)
        length += abs(delta) * radius

        arc_pts = _sample_arc_points(center, radius, a1, a2, direction)
        # Le premier point de arc_pts est start, déjà présent
        for p in arc_pts[1:]:
            flat_points.append(p)

    return length, flat_points


def _line_length(entity) -> float:
    start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
    end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
    return _distance(start, end)


def _arc_length(entity) -> float:
    """Longueur d'un ARC.

    Longueur = R * θ
    où θ est l'angle balayé en radians.

    DXF: start_angle et end_angle sont en degrés.
    """

    radius = float(entity.dxf.radius)
    a1 = float(entity.dxf.start_angle) * pi / 180.0
    a2 = float(entity.dxf.end_angle) * pi / 180.0
    delta = _arc_delta_ccw(a1, a2)
    return radius * delta


class DXFProcessor:
    """Processeur DXF principal."""

    linear_layers = ('MURS', 'FONDATIONS', 'POUTRES')
    surface_layers = ('DALLES', 'CHAPE', 'CARRELAGE')
    unit_layers = ('POTEAUX', 'MENUISERIES', 'SANITAIRES')

    def __init__(self) -> None:
        self.diagnostics: list[TakeoffDiagnostic] = []

    def extract_data(self, filepath: str | Path, scale_factor: float, *, wall_height_m: float = 2.8) -> pd.DataFrame:
        """Extrait les données de métré d'un DXF.

        Params:
        - filepath: chemin du DXF.
        - scale_factor: facteur de conversion vers m (unités dessin -> mètres).
        - wall_height_m: hauteur des murs en mètres (pour surfaces murs/déductions).

        Return:
        - pandas.DataFrame (Désignation, Quantité, Unité, Catégorie)
        """

        self.diagnostics = []

        try:
            import ezdxf
        except Exception as exc:  # pragma: no cover
            raise RuntimeError('Le paquet ezdxf est requis pour analyser les DXF.') from exc

        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(str(path))

        doc = ezdxf.readfile(str(path))
        msp = doc.modelspace()

        lengths_m: dict[str, float] = {layer: 0.0 for layer in self.linear_layers}
        areas_m2: dict[str, float] = {layer: 0.0 for layer in self.surface_layers}
        blocks_count: dict[tuple[str, str], int] = {}

        # Pour la déduction des ouvertures: on collecte les blocs "porte/fenêtre"
        openings_area_m2 = 0.0

        seen_layers: set[str] = set()

        for e in msp:
            layer = _norm_layer(getattr(e.dxf, 'layer', None))
            if layer:
                seen_layers.add(layer)

            etype = e.dxftype()

            # -----------------------------------------------------------------
            # 1) Éléments linéaires: LINE, ARC, LWPOLYLINE
            # -----------------------------------------------------------------
            if layer in self.linear_layers:
                try:
                    if etype == 'LINE':
                        lengths_m[layer] += _line_length(e) * float(scale_factor)
                    elif etype == 'ARC':
                        lengths_m[layer] += _arc_length(e) * float(scale_factor)
                    elif etype == 'LWPOLYLINE':
                        ln, _pts = _lwpolyline_length_and_points(e)
                        lengths_m[layer] += ln * float(scale_factor)
                except Exception as exc:
                    self.diagnostics.append(
                        TakeoffDiagnostic('warning', f"Entité linéaire ignorée ({layer}/{etype}): {exc}")
                    )

            # -----------------------------------------------------------------
            # 2) Éléments surfaciques: LWPOLYLINE fermée, HATCH
            # -----------------------------------------------------------------
            if layer in self.surface_layers:
                try:
                    if etype == 'LWPOLYLINE' and bool(getattr(e, 'closed', False)):
                        _ln, pts = _lwpolyline_length_and_points(e)
                        # Conversion en m puis aire en m² => (scale)^2
                        poly_area = _shoelace_area(pts) * (float(scale_factor) ** 2)
                        areas_m2[layer] += poly_area
                    elif etype == 'HATCH':
                        hatch_area = self._hatch_area_approx_m2(e, scale_factor=float(scale_factor))
                        areas_m2[layer] += hatch_area
                except Exception as exc:
                    self.diagnostics.append(
                        TakeoffDiagnostic('warning', f"Surface ignorée ({layer}/{etype}): {exc}")
                    )

            # -----------------------------------------------------------------
            # 3) Éléments unitaires: INSERT (références de blocs)
            # -----------------------------------------------------------------
            if layer in self.unit_layers and etype == 'INSERT':
                try:
                    name = (getattr(e.dxf, 'name', None) or '').strip()
                    if name:
                        key = (layer, name)
                        blocks_count[key] = blocks_count.get(key, 0) + 1

                    # Déduction d'ouvertures uniquement depuis MENUISERIES
                    if layer == 'MENUISERIES' and name:
                        openings_area_m2 += self._estimate_opening_area_m2(e, scale_factor=float(scale_factor))
                except Exception as exc:
                    self.diagnostics.append(
                        TakeoffDiagnostic('warning', f"Bloc ignoré ({layer}/{etype}): {exc}")
                    )

        # Diagnostics: couches attendues manquantes
        expected = set(self.linear_layers) | set(self.surface_layers) | set(self.unit_layers)
        missing = sorted(expected - seen_layers)
        if missing:
            self.diagnostics.append(
                TakeoffDiagnostic('warning', f"Couches DXF manquantes (continuer quand même): {', '.join(missing)}")
            )

        # Assemble DataFrame
        rows: list[dict[str, object]] = []

        for layer in self.linear_layers:
            qty = lengths_m.get(layer, 0.0)
            rows.append(
                {
                    'Désignation': f"{layer} — Longueur totale",
                    'Quantité': float(qty),
                    'Unité': 'm',
                    'Catégorie': 'Linéaires',
                }
            )

        for layer in self.surface_layers:
            qty = areas_m2.get(layer, 0.0)
            rows.append(
                {
                    'Désignation': f"{layer} — Surface totale",
                    'Quantité': float(qty),
                    'Unité': 'm²',
                    'Catégorie': 'Surfaces',
                }
            )

        for (layer, name), count in sorted(blocks_count.items(), key=lambda x: (x[0][0], x[0][1])):
            rows.append(
                {
                    'Désignation': f"{layer} — {name}",
                    'Quantité': int(count),
                    'Unité': 'U',
                    'Catégorie': 'Unités',
                }
            )

        # Surfaces murs + déduction ouvertures
        murs_length_m = lengths_m.get('MURS', 0.0)
        if murs_length_m > 0 and wall_height_m > 0:
            surface_murs_brute = murs_length_m * float(wall_height_m)
            surface_ouvertures = max(0.0, float(openings_area_m2))
            surface_murs_nette = max(0.0, surface_murs_brute - surface_ouvertures)

            rows.append(
                {
                    'Désignation': 'MURS — Surface brute (Longueur × Hauteur)',
                    'Quantité': float(surface_murs_brute),
                    'Unité': 'm²',
                    'Catégorie': 'Déductions',
                }
            )
            rows.append(
                {
                    'Désignation': 'MENUISERIES — Ouvertures (surface estimée)',
                    'Quantité': float(surface_ouvertures),
                    'Unité': 'm²',
                    'Catégorie': 'Déductions',
                }
            )
            rows.append(
                {
                    'Désignation': 'MURS — Surface nette (brute − ouvertures)',
                    'Quantité': float(surface_murs_nette),
                    'Unité': 'm²',
                    'Catégorie': 'Déductions',
                }
            )

        df = pd.DataFrame(rows, columns=['Désignation', 'Quantité', 'Unité', 'Catégorie'])
        return df

    def _estimate_opening_area_m2(self, insert_entity, *, scale_factor: float) -> float:
        """Estimation de surface d'ouverture à partir d'un bloc INSERT.

        Hypothèses (plan 2D):
        - La largeur de l'ouverture est estimée par l'encombrement XY du bloc.
        - La hauteur d'ouverture est une hypothèse selon le type (porte/fenêtre).

        IMPORTANT:
        - En 2D, la hauteur réelle n'est généralement pas dans le DXF.
          Cette estimation reste une heuristique exploitable en métré.
        """

        name = (getattr(insert_entity.dxf, 'name', None) or '').upper()
        if not name:
            return 0.0

        # Détection heuristique
        is_door = any(k in name for k in ('PORTE', 'DOOR'))
        is_window = any(k in name for k in ('FEN', 'WINDOW', 'VITR'))
        if not (is_door or is_window):
            return 0.0

        # Hauteurs standard (paramétrables plus tard si besoin)
        opening_height_m = 2.10 if is_door else 1.20

        width_m = self._estimate_block_width_m(insert_entity, scale_factor=scale_factor)
        if width_m <= 0:
            return 0.0

        return max(0.0, width_m * opening_height_m)

    def _estimate_block_width_m(self, insert_entity, *, scale_factor: float) -> float:
        """Estime la largeur d'un bloc en mètres.

        Méthode:
        - On récupère le block definition et son bounding box 2D si possible.
        - On applique les facteurs d'échelle de l'INSERT.

        Si impossible (bloc externe, proxy, etc.), on retourne 0.
        """

        try:
            doc = insert_entity.doc
            block_name = insert_entity.dxf.name
            block = doc.blocks.get(block_name)

            # Approximation: bbox des entités du bloc en coordonnées locales
            minx = miny = float('inf')
            maxx = maxy = float('-inf')
            found = False

            for ent in block:
                et = ent.dxftype()
                if et == 'LINE':
                    pts = [
                        (float(ent.dxf.start.x), float(ent.dxf.start.y)),
                        (float(ent.dxf.end.x), float(ent.dxf.end.y)),
                    ]
                elif et == 'LWPOLYLINE':
                    pts = [(float(x), float(y)) for x, y, _b in ent.get_points('xyb')]
                else:
                    continue

                for x, y in pts:
                    found = True
                    minx = min(minx, x)
                    maxx = max(maxx, x)
                    miny = min(miny, y)
                    maxy = max(maxy, y)

            if not found:
                return 0.0

            width_units = max(maxx - minx, maxy - miny)

            sx = float(getattr(insert_entity.dxf, 'xscale', 1.0) or 1.0)
            sy = float(getattr(insert_entity.dxf, 'yscale', 1.0) or 1.0)
            scale_xy = max(abs(sx), abs(sy))

            return float(width_units) * scale_xy * float(scale_factor)
        except Exception:
            return 0.0

    def _hatch_area_approx_m2(self, hatch_entity, *, scale_factor: float) -> float:
        """Calcule une aire approximative d'un HATCH.

        DXF HATCH:
        - Peut contenir plusieurs boucles (loops): contours extérieurs + trous.
        - Les contours peuvent être décrits par polylines ou par arêtes (edges).

        Implémentation (pragmatique):
        - On gère les chemins "polyline" de manière fiable.
        - Pour les chemins "edge", on tente LINE/ARC et on échantillonne.

        Limitation:
        - La gestion des trous dépend de l'orientation; faute d'orientation fiable
          dans tous les DXF, on additionne les aires absolues. Pour des hachures
          complexes avec trous, cette approximation peut sur-estimer.
        """

        total_units2 = 0.0

        try:
            paths = hatch_entity.paths
        except Exception:
            return 0.0

        for p in paths:
            try:
                # PolylinePath (souvent le cas)
                if hasattr(p, 'vertices') and p.vertices:
                    verts = [(float(v[0]), float(v[1])) for v in p.vertices]
                    total_units2 += _shoelace_area(verts)
                    continue

                # EdgePath
                if hasattr(p, 'edges') and p.edges:
                    poly: List[tuple[float, float]] = []
                    for edge in p.edges:
                        et = getattr(edge, 'type', None)
                        if et == 'LineEdge':
                            s = (float(edge.start[0]), float(edge.start[1]))
                            e = (float(edge.end[0]), float(edge.end[1]))
                            if not poly:
                                poly.append(s)
                            poly.append(e)
                        elif et == 'ArcEdge':
                            center = (float(edge.center[0]), float(edge.center[1]))
                            radius = float(edge.radius)
                            start = float(edge.start_angle) * pi / 180.0
                            end = float(edge.end_angle) * pi / 180.0
                            direction = 1 if bool(getattr(edge, 'ccw', True)) else -1
                            pts = _sample_arc_points(center, radius, start, end, direction)
                            if not poly:
                                poly.append(pts[0])
                            poly.extend(pts[1:])
                        else:
                            # SplineEdge, EllipseEdge, etc. ignorés
                            continue

                    total_units2 += _shoelace_area(poly)
            except Exception:
                continue

        return float(total_units2) * (float(scale_factor) ** 2)
