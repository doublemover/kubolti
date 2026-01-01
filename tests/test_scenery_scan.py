from __future__ import annotations

from pathlib import Path

from dem2dsf.scenery import scan_custom_scenery
from dem2dsf.xplane_paths import dsf_path as xplane_dsf_path


def test_scan_custom_scenery(tmp_path: Path) -> None:
    pack_a = tmp_path / "PackA"
    pack_b = tmp_path / "PackB"
    dsf_a = xplane_dsf_path(pack_a, "+47+008")
    dsf_b = xplane_dsf_path(pack_b, "+47+008")
    dsf_a.parent.mkdir(parents=True, exist_ok=True)
    dsf_b.parent.mkdir(parents=True, exist_ok=True)
    dsf_a.write_text("a", encoding="utf-8")
    dsf_b.write_text("b", encoding="utf-8")

    (tmp_path / "scenery_packs.ini").write_text(
        "# comment\nSCENERY_PACK PackB\n\nSCENERY_PACK PackA\n",
        encoding="utf-8",
    )

    report = scan_custom_scenery(tmp_path)
    conflicts = report["conflicts"]
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert set(conflict["packages"]) == {"PackA", "PackB"}
    assert conflict["ordered_packages"] == ["PackB", "PackA"]
    assert report["suggested_order"] == ["PackB", "PackA"]
    assert report["suggested_order_snippet"] == [
        "SCENERY_PACK PackB",
        "SCENERY_PACK PackA",
    ]


def test_scan_custom_scenery_without_ini(tmp_path: Path) -> None:
    pack_a = tmp_path / "PackA"
    pack_b = tmp_path / "PackB"
    dsf_a = xplane_dsf_path(pack_a, "+47+008")
    dsf_b = xplane_dsf_path(pack_b, "+47+008")
    dsf_a.parent.mkdir(parents=True, exist_ok=True)
    dsf_b.parent.mkdir(parents=True, exist_ok=True)
    dsf_a.write_text("a", encoding="utf-8")
    dsf_b.write_text("b", encoding="utf-8")

    report = scan_custom_scenery(tmp_path)
    conflicts = report["conflicts"]
    assert conflicts[0]["ordered_packages"] == ["PackA", "PackB"]
    assert report["scenery_packs"] is None
    assert report["suggested_order"] is None
    assert report["suggested_order_snippet"] is None


def test_scan_custom_scenery_single_pack(tmp_path: Path) -> None:
    pack = tmp_path / "Solo"
    dsf_path = xplane_dsf_path(pack, "+47+008")
    dsf_path.parent.mkdir(parents=True, exist_ok=True)
    dsf_path.write_text("dsf", encoding="utf-8")

    report = scan_custom_scenery(tmp_path)

    assert report["conflicts"] == []
