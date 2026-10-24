"""Config-driven scene contract for the React Three Fiber digital twin.

Geometry remains procedural, but every major object and pipe is emitted with a
stable engineering identifier. Coordinates use the project convention
(X=east, Y=north, Z=up), in metres. The frontend performs the only Z-up ->
Three.js Y-up conversion.
"""
from __future__ import annotations

from typing import Any

from .config_loader import expand_rack_ids, load_config


def _box(id_: str, kind: str, center: list[float], size: list[float], **extra: Any) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": id_, "kind": kind, "type": "box", "center": center, "size": size
    }
    obj.update(extra)
    return obj


def _marker(
    item: dict[str, Any], kind: str, size: list[float], *, floor_id: str | None = None,
    shape: str = "box", **extra: Any,
) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "id": item["id"],
        "kind": kind,
        "type": shape,
        "center": item["position"],
        "size": size,
    }
    if floor_id or item.get("floor"):
        obj["floor_id"] = floor_id or item.get("floor")
    obj.update({k: v for k, v in item.items() if k not in {"position", "floor"}})
    obj.update(extra)
    return obj


def build_scene(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    geom = cfg["geometry"]
    equip = cfg["equipment"]
    mb = geom["main_building"]
    gh = geom["greenhouse"]
    objects: list[dict[str, Any]] = []

    objects.append(_box(
        mb["id"], "building_shell", [0.0, 0.0, mb["height_z"] / 2.0],
        [mb["width_x"], mb["depth_y"], mb["height_z"]], opacity=0.12,
    ))

    # Floor volumes provide IDs and visibility bounds. The R3F client builds
    # slabs, columns, beams and interiors from these authoritative z-ranges.
    for floor in geom["floors"]:
        z0, z1 = floor["z"]
        objects.append(_box(
            f"floor_{floor['id']}", "floor_zone", [0.0, 0.0, (z0 + z1) / 2.0],
            [mb["width_x"], mb["depth_y"], z1 - z0], floor_id=floor["id"],
            name=floor["name"], use=floor["use"], z_range=floor["z"], opacity=0.04,
        ))

    layout = geom["gpu_floor_layout"]
    rack_size = layout["rack_size"]
    racks_per_row = layout["racks_per_row"]
    floor_z = {floor["id"]: floor["z"] for floor in geom["floors"]}
    for rack in expand_rack_ids(cfg):
        floor_id = rack["floor"]
        z0, _ = floor_z[floor_id]
        index = int(rack["id"].rsplit("_", 1)[1]) - 1
        row, column = divmod(index, racks_per_row)
        center = [
            -14.0 + column * (rack_size["width_x"] + 2.0),
            -4.0 + row * 8.0,
            z0 + 0.35 + rack_size["height_z"] / 2.0,
        ]
        objects.append(_box(
            rack["id"], "gpu_rack", center,
            [rack_size["width_x"], rack_size["depth_y"], rack_size["height_z"]],
            floor_id=floor_id, nominal_power_kW=rack["nominal_power_kW"],
        ))

    objects.append(_box(
        gh["id"], "greenhouse_shell",
        [gh["center"][0], gh["center"][1], gh["max_height_z"] / 2.0],
        [gh["width_x"], gh["depth_y"], gh["max_height_z"]],
        roof=gh["roof"], opacity=0.18,
    ))
    for index in range(6):
        bed_x = gh["center"][0] - 10.0 + (index % 3) * 10.0
        bed_y = gh["center"][1] - 4.0 + (index // 3) * 8.0
        objects.append(_box(
            f"bed_greenhouse_{index + 1:03d}", "growing_bed", [bed_x, bed_y, 0.25],
            [8.0, 6.0, 0.5], zone="zone_greenhouse_soil",
        ))

    corridor = geom["utility_corridor"]
    p0, p1 = corridor["path"]
    objects.append(_box(
        corridor["id"], "utility_corridor",
        [(p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0, (corridor["z"][0] + corridor["z"][1]) / 2.0],
        [abs(p1[0] - p0[0]), corridor["width_y"], corridor["z"][1] - corridor["z"][0]],
        opacity=0.22,
    ))

    for hx in equip["heat_exchangers"]:
        objects.append(_marker(hx, "heat_exchanger", [2.4, 1.2, 2.4], shape="plate_hx"))
    for pump in equip["pumps"]:
        objects.append(_marker(pump, "pump", [1.2, 1.2, 1.2], shape="pump"))
    for valve in equip["valves"]:
        objects.append(_marker(valve, "valve", [0.55, 0.55, 0.55], shape="valve"))
    for tank in equip["tanks"]:
        size = [3.4, 3.4, 3.2] if tank["type"] == "thermal_buffer" else [2.3, 2.3, 2.8]
        objects.append(_marker(tank, "tank", size, shape="tank"))
    objects.append(_marker(equip["heat_pump"], "heat_pump", [2.8, 1.8, 2.2]))
    objects.append(_marker(equip["dry_cooler"], "dry_cooler", [5.0, 2.2, 1.4]))

    for pdu in equip.get("power_distribution", []):
        objects.append(_marker(pdu, "power_distribution", [1.8, 1.0, 2.4]))
    for manifold in equip.get("manifolds", []):
        objects.append(_marker(manifold, "manifold", [2.8, 0.35, 0.35], shape="manifold"))
    for robot in equip.get("lab_equipment", []):
        kind = "robot_arm" if "robot_arm" in robot["id"] else "robot_test_cell"
        objects.append(_marker(robot, kind, [2.2, 2.2, 2.5]))
    for seed in equip.get("seed_equipment", []):
        kind = "seed_rack" if "seed_rack" in seed["id"] else "growth_chamber"
        objects.append(_marker(seed, kind, [2.0, 1.2, 2.5]))
    for zone in equip.get("thermal_zones", []):
        objects.append(_marker(zone, "thermal_zone", zone["size"], opacity=0.025))
    for sensor in equip.get("sensors", []):
        objects.append(_marker(sensor, "sensor", [0.24, 0.24, 0.45], shape="sensor"))

    pipes: list[dict[str, Any]] = []
    for circuit_name, circuit in cfg["network"]["circuits"].items():
        for segment in circuit.get("segments", []):
            pipes.append({
                "id": segment["id"],
                "kind": "pipe",
                "type": "pipe",
                "circuit": circuit_name,
                "from": segment["from"],
                "to": segment["to"],
                "role": segment.get("role"),
                "color": segment.get("color"),
                "length_m": segment.get("length_m"),
                "diameter_m": segment.get("diameter_m"),
                "buried": segment.get("buried", False),
                "branch_fraction": segment.get("branch_fraction", 1.0),
                "points": segment.get("points", []),
            })

    return {
        "site_id": cfg["site"]["site_id"],
        "name": cfg["site"]["name"],
        "units": "m",
        "axes": geom["world"]["axes"],
        "objects": objects,
        "pipes": pipes,
        "counts": {
            "objects": len(objects),
            "pipes": len(pipes),
            "gpu_racks": sum(obj["kind"] == "gpu_rack" for obj in objects),
            "floors": len(geom["floors"]),
            "sensors": len(equip.get("sensors", [])),
        },
    }
