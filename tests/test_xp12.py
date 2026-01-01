from __future__ import annotations

import textwrap

from dem2dsf.xp12 import (
    enrich_dsf_rasters,
    inventory_dsf_rasters,
    parse_raster_names,
    summarize_rasters,
)


def test_parse_raster_names() -> None:
    text = textwrap.dedent(
        """
        PROPERTY sim/north 48
        RASTER_DEF 0 "elevation"
        RASTER_DEF 1 "soundscape"
        RASTER_DEF 2 "season_winter_start"
        RASTER_DEF 3 "season_winter_end"
        """
    ).strip()
    names = parse_raster_names(text)
    summary = summarize_rasters(names)
    assert "soundscape" in summary.raster_names
    assert summary.soundscape_present is True
    assert summary.season_raster_count == 2


def test_inventory_dsf_rasters(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "args = sys.argv[1:]\n"
        'if "--dsf2text" in args:\n'
        "    out_path = Path(args[-1])\n"
        "    out_path.write_text(\n"
        '        "RASTER_DEF 0 \\"soundscape\\"\\n"\n'
        '        "RASTER_DEF 1 \\"season_spring_start\\"\\n",\n'
        '        encoding="utf-8",\n'
        "    )\n"
        "else:\n"
        "    sys.exit(1)\n",
        encoding="utf-8",
    )
    dsf_path = tmp_path / "tile.dsf"
    dsf_path.write_text("dsf", encoding="utf-8")

    summary = inventory_dsf_rasters(tool, dsf_path, tmp_path / "work")
    assert summary.soundscape_present is True
    assert summary.season_raster_count == 1


def test_enrich_dsf_rasters(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "args = sys.argv[1:]\n"
        'if "--dsf2text" in args:\n'
        '    dsf_path = Path(args[args.index("--dsf2text") + 1])\n'
        "    out_path = Path(args[-1])\n"
        '    if dsf_path.name.startswith("global"):\n'
        "        out_path.write_text(\n"
        '            "RASTER_DEF 0 \\"elevation\\"\\n"\n'
        '            "RASTER_DEF 1 \\"soundscape\\"\\n"\n'
        '            "RASTER_DEF 2 \\"season_summer_start\\"\\n",\n'
        '            encoding="utf-8",\n'
        "        )\n"
        "    else:\n"
        "        out_path.write_text(\n"
        '            "RASTER_DEF 0 \\"elevation\\"\\n",\n'
        '            encoding="utf-8",\n'
        "        )\n"
        'elif "--text2dsf" in args:\n'
        "    out_path = Path(args[-1])\n"
        '    out_path.write_text("dsf", encoding="utf-8")\n'
        "else:\n"
        "    sys.exit(1)\n",
        encoding="utf-8",
    )

    target_dsf = tmp_path / "target.dsf"
    global_dsf = tmp_path / "global.dsf"
    target_dsf.write_text("dsf", encoding="utf-8")
    global_dsf.write_text("dsf", encoding="utf-8")

    result = enrich_dsf_rasters(tool, target_dsf, global_dsf, tmp_path / "work")
    assert result.status == "enriched"
    enriched_text = (tmp_path / "work" / "target.enriched.txt").read_text(encoding="utf-8")
    assert "soundscape" in enriched_text
    assert "season_summer_start" in enriched_text
    assert (tmp_path / "target.original.dsf").exists()


def test_enrich_dsf_rasters_copies_raw_sidecars(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "args = sys.argv[1:]\n"
        'if "--dsf2text" in args:\n'
        '    dsf_path = Path(args[args.index("--dsf2text") + 1])\n'
        "    out_path = Path(args[-1])\n"
        '    if dsf_path.name.startswith("global"):\n'
        '        out_path.write_text("RASTER_DEF 0 \\"soundscape\\"\\n", encoding="utf-8")\n'
        '        (out_path.parent / f"{out_path.name}.soundscape.raw").write_text(\n'
        '            "raw", encoding="utf-8"\n'
        "        )\n"
        "    else:\n"
        '        out_path.write_text("RASTER_DEF 0 \\"elevation\\"\\n", encoding="utf-8")\n'
        'elif "--text2dsf" in args:\n'
        '    Path(args[-1]).write_text("dsf", encoding="utf-8")\n'
        "else:\n"
        "    sys.exit(1)\n",
        encoding="utf-8",
    )

    target_dsf = tmp_path / "target.dsf"
    global_dsf = tmp_path / "global.dsf"
    target_dsf.write_text("dsf", encoding="utf-8")
    global_dsf.write_text("dsf", encoding="utf-8")

    result = enrich_dsf_rasters(tool, target_dsf, global_dsf, tmp_path / "work")
    assert result.status == "enriched"
    assert (tmp_path / "work" / "target.enriched.txt.soundscape.raw").exists()


def test_enrich_dsf_rasters_reindexes_conflicts(tmp_path) -> None:
    tool = tmp_path / "dsftool.py"
    tool.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "args = sys.argv[1:]\n"
        'if "--dsf2text" in args:\n'
        '    dsf_path = Path(args[args.index("--dsf2text") + 1])\n'
        "    out_path = Path(args[-1])\n"
        '    if dsf_path.name.startswith("global"):\n'
        "        out_path.write_text(\n"
        '            "RASTER_DEF 0 \\"elevation\\"\\n"\n'
        '            "RASTER_DEF 1 \\"soundscape\\"\\n",\n'
        '            encoding="utf-8",\n'
        "        )\n"
        "    else:\n"
        "        out_path.write_text(\n"
        '            "RASTER_DEF 0 \\"elevation\\"\\n"\n'
        '            "RASTER_DEF 1 \\"custom\\"\\n",\n'
        '            encoding="utf-8",\n'
        "        )\n"
        'elif "--text2dsf" in args:\n'
        '    Path(args[-1]).write_text("dsf", encoding="utf-8")\n'
        "else:\n"
        "    sys.exit(1)\n",
        encoding="utf-8",
    )

    target_dsf = tmp_path / "target.dsf"
    global_dsf = tmp_path / "global.dsf"
    target_dsf.write_text("dsf", encoding="utf-8")
    global_dsf.write_text("dsf", encoding="utf-8")

    result = enrich_dsf_rasters(tool, target_dsf, global_dsf, tmp_path / "work")
    assert result.status == "enriched"
    enriched_text = (tmp_path / "work" / "target.enriched.txt").read_text(encoding="utf-8")
    assert 'RASTER_DEF 2 "soundscape"' in enriched_text
