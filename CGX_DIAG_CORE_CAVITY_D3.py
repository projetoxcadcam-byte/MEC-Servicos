from __future__ import annotations

"""
CGX Mold Design — Diagnóstico D3
Modelagem das placas macho/fêmea conforme o produto

Objetivo:
- verificar se as placas Cavity Plate A e Core Plate B estão sendo
  esculpidas de acordo com o produto físico em 1, 2 e 4 cavidades;
- medir interferência produto x placas;
- medir se o volume removido/alterado muda com a quantidade de cavidades;
- listar posições dos produtos físicos gerados;
- preparar a próxima etapa de implementação:
  D3 = usinagem/relief multicavidade coerente com cada produto físico.

Execução:
    python .\CGX_DIAG_CORE_CAVITY_D3.py
"""

from pathlib import Path
import sys
from math import isfinite


def _find_root() -> Path:
    root = Path.cwd().resolve()
    while root != root.parent:
        if (root / "src/cgx/mold/mold_base.py").is_file():
            return root
        root = root.parent
    raise RuntimeError("Raiz do projeto CGX-Platform não encontrada.")


ROOT = _find_root()
sys.path.insert(0, str(ROOT / "src"))


from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

from cgx.mold.configuration import MoldConfiguratorState, MoldProductDefinition
from cgx.mold.mold_base import MoldBase
from cgx.mold.product_analysis import analyze_shape, shape_to_embedded_brep
from cgx.mold.components import MoldPlate, MoldProduct


def _volume(shape) -> float:
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    value = float(props.Mass())
    if not isfinite(value):
        return 0.0
    return value


def _bbox(shape):
    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.Add_s(shape, box)
    return box.Get()


def _common_volume(a, b) -> float:
    common = BRepAlgoAPI_Common(a, b)
    common.SetFuzzyValue(1.0e-7)
    common.Build()
    if not common.IsDone():
        return 0.0
    shape = common.Shape()
    if shape.IsNull():
        return 0.0
    return _volume(shape)


def _analyze_product_shape():
    shape = BRepPrimAPI_MakeBox(
        120.0,
        80.0,
        18.0,
    ).Shape()
    analysis = analyze_shape(shape)
    return shape, analysis


def _make_state(cavity_count: int) -> MoldConfiguratorState:
    product_shape, a = _analyze_product_shape()

    state = MoldConfiguratorState()

    state.product = MoldProductDefinition(
        name=f"Produto D3 {cavity_count}x",
        material="ABS",
        embedded_brep=shape_to_embedded_brep(product_shape),
        original_width=a.width,
        original_length=a.length,
        original_height=a.height,
        original_volume=a.volume,
        original_surface_area=a.surface_area,
        opening_direction="+Z",
        opening_direction_mode="manual",
        cavity_count=int(cavity_count),
        draft_angle_deg=1.0,
        tooling_construction_mode="DIRECT_PLATES",
        direct_plate_profile_enabled=True,
        direct_plate_profile_margin=12.0,
        direct_plate_profile_height=8.0,
        direct_plate_profile_clearance=0.05,
        direct_plate_locking_mode="END_LOCKS",
        direct_plate_lock_length=22.0,
        direct_plate_lock_width=26.0,
        direct_plate_lock_height=8.0,
        product_feeding_parameter_mode="MANUAL",
        product_feeding_system_type="TWO_PLATE_CENTERED_OFFSET",
        product_feeding_product_position_mode="AUTO",
        product_feeding_product_offset_side="AUTO",
        product_feeding_gate_type="FAN",
        product_feeding_gate_count=2,
        product_feeding_runner_diameter=8.0,
        product_feeding_gate_width=16.0,
        product_feeding_gate_depth=2.16,
        product_feeding_gate_length=12.5,
        product_feeding_cold_slug_enabled=False,
        product_feeding_applied=False,
    )

    state.analyze_product_opening(apply_suggestion=False)
    state.analyze_product_parting(set_automatic=True)
    state.generate_product_inserts()

    try:
        state.set_sprue_bushing_field("x", 0.0)
        state.set_sprue_bushing_field("y", 0.0)
        state.set_locating_ring_field("x", 0.0)
        state.set_locating_ring_field("y", 0.0)
    except Exception:
        pass

    return state


def _build_case(cavity_count: int):
    state = _make_state(cavity_count)
    assembly = MoldBase(state=state).build()

    products = list(assembly.of_type(MoldProduct))
    plates = list(assembly.of_type(MoldPlate))

    plate_a = None
    plate_b = None

    for plate in plates:
        name = str(getattr(plate, "name", ""))
        if name == "Cavity Plate A":
            plate_a = plate
        elif name == "Core Plate B":
            plate_b = plate

    return assembly, products, plate_a, plate_b


def _print_case(cavity_count: int):
    print()
    print("=" * 100)
    print(f"CAVITY_COUNT={cavity_count}")
    print("=" * 100)

    assembly, products, plate_a, plate_b = _build_case(cavity_count)

    print("PHYSICAL_PRODUCT_COUNT=", len(products))
    print(
        "PRODUCT_POSITIONS=",
        [
            (
                str(getattr(p, "name", "")),
                round(float(getattr(p.position, "x", 0.0)), 3),
                round(float(getattr(p.position, "y", 0.0)), 3),
                round(float(getattr(p.position, "z", 0.0)), 3),
            )
            for p in products
        ],
    )

    if plate_a is None or plate_b is None:
        print("PLATES_FOUND= False")
        return {
            "ok": False,
            "plate_a_volume": 0.0,
            "plate_b_volume": 0.0,
            "plate_a_bbox": None,
            "plate_b_bbox": None,
            "plate_a_clear": False,
            "plate_b_clear": False,
        }

    builder = assembly.shape_builder

    shape_a = builder.build_shape(plate_a, assembly=assembly)
    shape_b = builder.build_shape(plate_b, assembly=assembly)

    print("PLATES_FOUND= True")
    print("PLATE_A_VALID=", BRepCheck_Analyzer(shape_a).IsValid())
    print("PLATE_B_VALID=", BRepCheck_Analyzer(shape_b).IsValid())

    volume_a = _volume(shape_a)
    volume_b = _volume(shape_b)
    bbox_a = _bbox(shape_a)
    bbox_b = _bbox(shape_b)

    print("PLATE_A_VOLUME=", volume_a)
    print("PLATE_B_VOLUME=", volume_b)
    print("PLATE_A_BBOX=", bbox_a)
    print("PLATE_B_BBOX=", bbox_b)

    all_clear_a = True
    all_clear_b = True

    for idx, product in enumerate(products, start=1):
        product_shape = builder.build_shape(product, assembly=assembly)
        common_a = _common_volume(product_shape, shape_a)
        common_b = _common_volume(product_shape, shape_b)
        print(f"PRODUCT_{idx}_PLATE_A_COMMON=", common_a)
        print(f"PRODUCT_{idx}_PLATE_B_COMMON=", common_b)
        if common_a > 1.0e-8:
            all_clear_a = False
        if common_b > 1.0e-8:
            all_clear_b = False

    print("ALL_PRODUCTS_CLEAR_PLATE_A=", all_clear_a)
    print("ALL_PRODUCTS_CLEAR_PLATE_B=", all_clear_b)

    return {
        "ok": True,
        "plate_a_volume": volume_a,
        "plate_b_volume": volume_b,
        "plate_a_bbox": bbox_a,
        "plate_b_bbox": bbox_b,
        "plate_a_clear": all_clear_a,
        "plate_b_clear": all_clear_b,
    }


def main():
    print("CGX Mold Design — Diagnóstico D3 — Placas Macho/Fêmea conforme o Produto")
    print("REVISION=CGX-MOLD-DIAG-D3-CORE-CAVITY-2026-10-09")
    print("ROOT=", ROOT)

    results = {}
    for count in (1, 2, 4):
        results[count] = _print_case(count)

    print()
    print("=" * 100)
    print("COMPARAÇÕES")
    print("=" * 100)

    base = results[1]
    overall_ok = bool(base["ok"])

    for count in (2, 4):
        current = results[count]
        if not current["ok"]:
            overall_ok = False
            continue

        delta_a = current["plate_a_volume"] - base["plate_a_volume"]
        delta_b = current["plate_b_volume"] - base["plate_b_volume"]

        changed_a = abs(delta_a) > 1.0e-6
        changed_b = abs(delta_b) > 1.0e-6

        print(f"DELTA_1_TO_{count}_PLATE_A=", delta_a)
        print(f"DELTA_1_TO_{count}_PLATE_B=", delta_b)
        print(f"PLATE_A_GEOMETRY_CHANGES_WITH_CAVITIES_{count}=", changed_a)
        print(f"PLATE_B_GEOMETRY_CHANGES_WITH_CAVITIES_{count}=", changed_b)

        overall_ok = overall_ok and current["plate_a_clear"] and current["plate_b_clear"]

    print()
    print("=" * 100)
    print("CONCLUSÃO")
    print("=" * 100)

    print("ONE_CAVITY_OK=", results[1]["plate_a_clear"] and results[1]["plate_b_clear"])
    print("TWO_CAVITY_OK=", results[2]["plate_a_clear"] and results[2]["plate_b_clear"])
    print("FOUR_CAVITY_OK=", results[4]["plate_a_clear"] and results[4]["plate_b_clear"])
    print(
        "PLATE_MODELING_RESPONDS_TO_MULTICAVITY=",
        (
            abs(results[2]["plate_a_volume"] - results[1]["plate_a_volume"]) > 1.0e-6
            or abs(results[2]["plate_b_volume"] - results[1]["plate_b_volume"]) > 1.0e-6
            or abs(results[4]["plate_a_volume"] - results[1]["plate_a_volume"]) > 1.0e-6
            or abs(results[4]["plate_b_volume"] - results[1]["plate_b_volume"]) > 1.0e-6
        ),
    )

    print(
        "RESULT=",
        "PASS" if overall_ok else "DIAG_COMPLETE",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
