import tempfile
from pathlib import Path

import pytest


def test_dxf_processor_extracts_basic_quantities():
    ezdxf = pytest.importorskip("ezdxf")

    from logic.dxf_engine import DXFProcessor

    # Crée un DXF minimal en mm
    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()

    # Mur: 1000 mm (=> 1.0 m avec scale_factor=0.001)
    msp.add_line((0, 0), (1000, 0), dxfattribs={"layer": "MURS"})

    # Dalle: carré 1000x1000 mm => 1 m²
    pl = msp.add_lwpolyline(
        [(0, 0), (1000, 0), (1000, 1000), (0, 1000)],
        dxfattribs={"layer": "DALLES"},
    )
    pl.closed = True

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "sample.dxf"
        doc.saveas(str(path))

        proc = DXFProcessor()
        df = proc.extract_data(path, scale_factor=0.001, wall_height_m=3.0)

    assert list(df.columns) == ["Désignation", "Quantité", "Unité", "Catégorie"]

    # Vérifie longueur murs ~ 1.0 m
    murs_len = df[df["Désignation"].str.contains("MURS — Longueur totale")]["Quantité"].iloc[0]
    assert murs_len == pytest.approx(1.0, abs=1e-6)

    # Vérifie surface dalles ~ 1.0 m²
    dalles = df[df["Désignation"].str.contains("DALLES — Surface totale")]["Quantité"].iloc[0]
    assert dalles == pytest.approx(1.0, abs=1e-6)

    # Vérifie surface brute murs: 1.0 * 3.0 = 3.0 m²
    murs_surface = df[df["Désignation"].str.contains("MURS — Surface brute")]["Quantité"].iloc[0]
    assert murs_surface == pytest.approx(3.0, abs=1e-6)
