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


def identify_layer_category(layer_name: str | None) -> str | None:
    """Identifie une catégorie d'ingénierie à partir d'un nom de couche.

    Problème réel:
    - Dans les DXF, les couches ne s'appellent presque jamais exactement "MURS"/"DALLES".
      On trouve plutôt: A-WALL, WALLS_EXT, DALLE_RDC, SLAB-01, BEAM, SEMELLE, etc.

    Stratégie:
    - Matching par mots-clés (inclusion) en MAJUSCULE.
    - Retourne une clé canonique (ex: "MURS", "DALLES", ...) ou None.
    """

    name = _norm_layer(layer_name)
    if not name:
        return None

    # Mapping "catégorie canonique" -> liste de mots clés possibles.
    # NB: on privilégie des tokens courts mais discriminants.
    keywords: dict[str, list[str]] = {
        # Linéaires
        'MURS': ['MUR', 'WALL', 'A-WALL', 'A_WALL', 'WALLS', 'CLOISON', 'CLSN'],
        'FONDATIONS': ['FOND', 'FOUND', 'FOOT', 'FOOTING', 'SEMELLE', 'SML', 'RADIER'],
        'POUTRES': ['POUTRE', 'BEAM', 'PTRL', 'LINTEAU'],
        # Surfaces
        'DALLES': ['DALLE', 'SLAB', 'PLANCHER', 'FLOOR', 'DALLAGE'],
        'CHAPE': ['CHAPE', 'SCREED'],
        'CARRELAGE': ['CARREL', 'TILE', 'FAIENCE', 'REVET', 'FINISH'],
        # Unitaires (souvent représentés par blocs)
        'POTEAUX': ['POTEAU', 'COLUMN', 'COLONNE', 'PILIER'],
        'MENUISERIES': ['MENUIS', 'DOOR', 'PORTE', 'WINDOW', 'FEN', 'BAIE', 'VITR'],
        'SANITAIRES': ['SANITA', 'WC', 'LAVABO', 'SINK', 'BATH', 'DOUCHE'],
    }

    for category, keys in keywords.items():
        for k in keys:
            if k in name:
                return category
    return None


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


def _polyline_points_2d(entity) -> list[tuple[float, float]]:
    """Extrait des points XY d'une POLYLINE (ancienne entité DXF) en 2D.

    Beaucoup de fichiers AutoCAD utilisent encore POLYLINE au lieu de LWPOLYLINE.
    On ne gère ici que les sommets 2D (x,y).
    """

    pts: list[tuple[float, float]] = []
    try:
        for v in entity.vertices():
            loc = v.dxf.location
            pts.append((float(loc.x), float(loc.y)))
    except Exception:
        return []
    return pts


def _polyline_is_closed(entity, pts: Sequence[tuple[float, float]], *, tol_units: float) -> bool:
    """Détermine si une polyline doit être considérée fermée.

    Cas réel:
    - Certains DXF ont des contours "presque" fermés (dernier point proche du premier)
      mais le flag closed n'est pas positionné.

    Règle:
    - Si l'entité est explicitement fermée -> True.
    - Sinon, si distance(first,last) <= tol_units -> True.
    """

    try:
        if bool(getattr(entity, 'closed', False)):
            return True
    except Exception:
        pass
    if len(pts) < 3:
        return False
    return _distance(pts[0], pts[-1]) <= max(0.0, float(tol_units))


def _close_ring(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    if not points:
        return []
    pts = list(points)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def _transform_point_2d(
    p: tuple[float, float],
    *,
    insert: tuple[float, float],
    rotation_deg: float,
    sx: float,
    sy: float,
) -> tuple[float, float]:
    """Applique une transformation 2D de bloc INSERT sur un point.

    Hypothèse (pragmatique):
    - On traite en 2D (plan XY). C'est suffisant pour des plans architecturaux.
    - On applique: mise à l'échelle (sx,sy) -> rotation -> translation (insert).
    """

    x, y = p
    x *= sx
    y *= sy

    a = float(rotation_deg) * pi / 180.0
    ca = cos(a)
    sa = sin(a)
    xr = x * ca - y * sa
    yr = x * sa + y * ca

    return (xr + insert[0], yr + insert[1])


def _iter_entities_with_blocks(msp, doc, *, max_depth: int = 2) -> Iterable[tuple[object, str]]:
    """Itère sur les entités du modelspace + entités contenues dans des INSERT.

    Pourquoi:
    - Beaucoup de DXF encapsulent les murs/dalles dans des blocs (INSERT).
      Si on ne "déplie" pas les blocs, on voit des INSERT mais pas la géométrie.

    Sortie:
    - tuples (entity_like, effective_layer_name)
    """

    def walk(entity, depth: int) -> Iterable[tuple[object, str]]:
        layer_name = getattr(entity.dxf, 'layer', None)
        etype = entity.dxftype()
        if etype != 'INSERT':
            yield (entity, layer_name)
            return

        # INSERT: on émet aussi l'INSERT lui-même (utile pour comptage),
        # puis on parcourt le contenu du block.
        yield (entity, layer_name)

        if depth >= max_depth:
            return

        try:
            block_name = entity.dxf.name
            block = doc.blocks.get(block_name)
        except Exception:
            return

        try:
            ins_pt = entity.dxf.insert
            insert_xy = (float(ins_pt.x), float(ins_pt.y))
        except Exception:
            insert_xy = (0.0, 0.0)

        rot = float(getattr(entity.dxf, 'rotation', 0.0) or 0.0)
        sx = float(getattr(entity.dxf, 'xscale', 1.0) or 1.0)
        sy = float(getattr(entity.dxf, 'yscale', 1.0) or 1.0)

        for child in block:
            ctype = child.dxftype()
            child_layer = getattr(child.dxf, 'layer', None)
            eff_layer = child_layer or layer_name

            if ctype == 'INSERT':
                # INSERT imbriqué: on garde les transforms du child (pragmatique)
                # mais on applique au moins la visite récursive.
                yield from walk(child, depth + 1)
                continue

            # On wrappe l'entité "comme si" elle était en world coords.
            # Pour la robustesse, on transforme seulement les types supportés.
            try:
                if ctype == 'LINE':
                    s = (float(child.dxf.start.x), float(child.dxf.start.y))
                    e = (float(child.dxf.end.x), float(child.dxf.end.y))
                    ws = _transform_point_2d(s, insert=insert_xy, rotation_deg=rot, sx=sx, sy=sy)
                    we = _transform_point_2d(e, insert=insert_xy, rotation_deg=rot, sx=sx, sy=sy)

                    class _LineLike:
                        def __init__(self, start, end, layer):
                            self._start = start
                            self._end = end
                            self.dxf = type('dxf', (), {})()
                            self.dxf.layer = layer
                            self.dxf.start = type('p', (), {'x': start[0], 'y': start[1]})()
                            self.dxf.end = type('p', (), {'x': end[0], 'y': end[1]})()

                        def dxftype(self):
                            return 'LINE'

                    yield (_LineLike(ws, we, eff_layer), eff_layer)
                    continue

                if ctype == 'LWPOLYLINE':
                    raw = list(child.get_points('xyb'))

                    class _LWLike:
                        def __init__(self, pts, closed, layer):
                            self._pts = pts
                            self.closed = closed
                            self.dxf = type('dxf', (), {})()
                            self.dxf.layer = layer

                        def dxftype(self):
                            return 'LWPOLYLINE'

                        def get_points(self, fmt):
                            return self._pts

                    # Transforme chaque point; on garde bulge tel quel (arc intrinsèque)
                    # NB: en cas de scale non uniforme, l'arc n'est plus un cercle.
                    # Ici on accepte une approximation via échantillonnage dans _lwpolyline...
                    tpts = []
                    for x, y, b in raw:
                        tx, ty = _transform_point_2d((float(x), float(y)), insert=insert_xy, rotation_deg=rot, sx=sx, sy=sy)
                        tpts.append((tx, ty, float(b or 0.0)))
                    yield (_LWLike(tpts, bool(getattr(child, 'closed', False)), eff_layer), eff_layer)
                    continue

                if ctype == 'ARC':
                    # Si scale non uniforme, on échantillonne l'arc comme polyline.
                    center = (float(child.dxf.center.x), float(child.dxf.center.y))
                    radius = float(child.dxf.radius)
                    a1 = float(child.dxf.start_angle) * pi / 180.0
                    a2 = float(child.dxf.end_angle) * pi / 180.0

                    pts = _sample_arc_points(center, radius, a1, a2, 1)
                    tpts = [
                        _transform_point_2d(p, insert=insert_xy, rotation_deg=rot, sx=sx, sy=sy)
                        for p in pts
                    ]

                    class _PolyAsLW:
                        def __init__(self, pts, layer):
                            self._pts = [(p[0], p[1], 0.0) for p in pts]
                            self.closed = False
                            self.dxf = type('dxf', (), {})()
                            self.dxf.layer = layer

                        def dxftype(self):
                            return 'LWPOLYLINE'

                        def get_points(self, fmt):
                            return self._pts

                    yield (_PolyAsLW(tpts, eff_layer), eff_layer)
                    continue

            except Exception:
                # Si transformation échoue, on ignore l'entité du bloc.
                continue

    for ent in msp:
        yield from walk(ent, 0)


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

    # Clés canoniques (utilisées dans les sorties)
    linear_layers = ('MURS', 'FONDATIONS', 'POUTRES')
    surface_layers = ('DALLES', 'CHAPE', 'CARRELAGE')
    unit_layers = ('POTEAUX', 'MENUISERIES', 'SANITAIRES')

    def __init__(self) -> None:
        self.diagnostics: list[TakeoffDiagnostic] = []

    def extract_data(
        self,
        filepath: str | Path,
        scale_factor: float,
        *,
        wall_height_m: float = 2.8,
        debug_layers: bool = False,
    ) -> pd.DataFrame:
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

        # Hint d'unité DXF ($INSUNITS) pour diagnostiquer les mauvaises échelles.
        # https://help.autodesk.com/view/OARX/2024/ENU/?guid=OARX-Variable_INSUNITS
        try:
            insunits = doc.header.get('$INSUNITS')
            ins_map = {
                0: ('Unitless', None),
                1: ('Inches', 0.0254),
                2: ('Feet', 0.3048),
                4: ('Millimeters', 0.001),
                5: ('Centimeters', 0.01),
                6: ('Meters', 1.0),
            }
            if insunits in ins_map and ins_map[insunits][1] is not None:
                label, suggested = ins_map[insunits]
                self.diagnostics.append(
                    TakeoffDiagnostic(
                        'info',
                        f"DXF INSUNITS={insunits} ({label}). Échelle conseillée ≈ {suggested} m/unité.",
                    )
                )
        except Exception:
            pass

        lengths_m: dict[str, float] = {layer: 0.0 for layer in self.linear_layers}
        areas_m2: dict[str, float] = {layer: 0.0 for layer in self.surface_layers}
        blocks_count: dict[tuple[str, str], int] = {}

        # Pour la déduction des ouvertures: on collecte les blocs "porte/fenêtre"
        openings_area_m2 = 0.0

        # Tolérance de fermeture (en unités du dessin).
        # On se donne 5 mm par défaut dans le monde réel, converti vers unités du dessin.
        # Exemple: si le DXF est en mm (scale=0.001), tol_units=5.
        tol_units = 0.005 / float(scale_factor) if float(scale_factor) > 0 else 0.0
        tol_units = max(1e-6, min(tol_units, 100.0))

        # Liste des couches (debug) : utile pour vérifier que le DXF contient ce qu'on croit.
        try:
            all_layers = [str(l.dxf.name) for l in doc.layers]
        except Exception:
            all_layers = []

        if debug_layers:
            # Sortie volontairement simple (temporaire) pour support terrain.
            for lname in all_layers:
                print(lname)

        if all_layers:
            sample = ', '.join(all_layers[:40])
            suffix = '' if len(all_layers) <= 40 else f" … (+{len(all_layers)-40})"
            self.diagnostics.append(TakeoffDiagnostic('info', f"Couches détectées: {sample}{suffix}"))

        seen_layers: set[str] = set(_norm_layer(l) for l in all_layers if l)

        # Parcourt modelspace + contenu des blocs (INSERT) pour extraire la géométrie.
        for e, eff_layer_name in _iter_entities_with_blocks(msp, doc):
            layer_norm = _norm_layer(eff_layer_name)
            if layer_norm:
                seen_layers.add(layer_norm)

            etype = e.dxftype()
            category = identify_layer_category(layer_norm) or identify_layer_category(getattr(e.dxf, 'layer', None))

            # -----------------------------------------------------------------
            # 1) Éléments linéaires: LINE, ARC, LWPOLYLINE
            # -----------------------------------------------------------------
            if category in self.linear_layers:
                try:
                    if etype == 'LINE':
                        lengths_m[category] += _line_length(e) * float(scale_factor)
                    elif etype == 'ARC':
                        lengths_m[category] += _arc_length(e) * float(scale_factor)
                    elif etype == 'LWPOLYLINE':
                        ln, _pts = _lwpolyline_length_and_points(e)
                        lengths_m[category] += ln * float(scale_factor)
                    elif etype == 'POLYLINE':
                        pts = _polyline_points_2d(e)
                        if len(pts) >= 2:
                            # Longueur = somme des segments consécutifs (et fermeture si close)
                            ln_units = 0.0
                            for i in range(len(pts) - 1):
                                ln_units += _distance(pts[i], pts[i + 1])
                            if _polyline_is_closed(e, pts, tol_units=tol_units):
                                ln_units += _distance(pts[-1], pts[0])
                            lengths_m[category] += ln_units * float(scale_factor)
                except Exception as exc:
                    self.diagnostics.append(
                        TakeoffDiagnostic('warning', f"Entité linéaire ignorée ({category}/{etype}): {exc}")
                    )

            # -----------------------------------------------------------------
            # 2) Éléments surfaciques: LWPOLYLINE fermée, HATCH
            # -----------------------------------------------------------------
            if category in self.surface_layers:
                try:
                    if etype == 'LWPOLYLINE':
                        _ln, pts = _lwpolyline_length_and_points(e)
                        # Correction "polylines pas fermées":
                        # - Si le contour est presque fermé, on force la fermeture.
                        if _polyline_is_closed(e, pts, tol_units=tol_units):
                            ring = _close_ring(pts)
                            # Conversion en m puis aire en m² => (scale)^2
                            poly_area = _shoelace_area(ring) * (float(scale_factor) ** 2)
                            areas_m2[category] += poly_area
                    elif etype == 'HATCH':
                        hatch_area = self._hatch_area_approx_m2(e, scale_factor=float(scale_factor))
                        areas_m2[category] += hatch_area
                    elif etype == 'POLYLINE':
                        pts = _polyline_points_2d(e)
                        if _polyline_is_closed(e, pts, tol_units=tol_units):
                            ring = _close_ring(pts)
                            poly_area = _shoelace_area(ring) * (float(scale_factor) ** 2)
                            areas_m2[category] += poly_area
                except Exception as exc:
                    self.diagnostics.append(
                        TakeoffDiagnostic('warning', f"Surface ignorée ({category}/{etype}): {exc}")
                    )

            # -----------------------------------------------------------------
            # 3) Éléments unitaires: INSERT (références de blocs)
            # -----------------------------------------------------------------
            if category in self.unit_layers and etype == 'INSERT':
                try:
                    name = (getattr(e.dxf, 'name', None) or '').strip()
                    if name:
                        key = (category, name)
                        blocks_count[key] = blocks_count.get(key, 0) + 1

                    # Déduction d'ouvertures uniquement depuis MENUISERIES
                    if category == 'MENUISERIES' and name:
                        openings_area_m2 += self._estimate_opening_area_m2(e, scale_factor=float(scale_factor))
                except Exception as exc:
                    self.diagnostics.append(
                        TakeoffDiagnostic('warning', f"Bloc ignoré ({category}/{etype}): {exc}")
                    )

        # Diagnostics: couches attendues manquantes
        # Diagnostics: si aucune quantité non nulle -> souvent un mismatch de couches.
        # On ne peut pas l'affirmer à 100%, mais on peut guider l'utilisateur.
        total_len = sum(lengths_m.values())
        total_area = sum(areas_m2.values())
        if total_len <= 0.0 and total_area <= 0.0 and not blocks_count:
            self.diagnostics.append(
                TakeoffDiagnostic(
                    'warning',
                    "Aucune géométrie reconnue. Vérifiez les noms de couches (mots clés) et/ou l'échelle du dessin.",
                )
            )

        # Diagnostic échelle: si on a reconnu des entités mais valeurs ~0, l'échelle est probablement erronée.
        if (total_len > 0.0 and total_len < 1e-6) or (total_area > 0.0 and total_area < 1e-9):
            self.diagnostics.append(
                TakeoffDiagnostic(
                    'warning',
                    f"Quantités extrêmement petites (longueur={total_len:.3e} m, aire={total_area:.3e} m²). L'échelle (scale_factor={scale_factor}) semble incorrecte.",
                )
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
