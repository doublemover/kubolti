"""DEM mosaic builder using rasterio merge."""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

import rasterio
from rasterio.dtypes import _gdal_typename
from rasterio.merge import merge
from rasterio.transform import from_origin

from dem2dsf.dem.models import MosaicResult


def _build_vrt_mosaic(
    dem_paths: Sequence[Path],
    output_path: Path,
    *,
    method: str,
) -> MosaicResult:
    """Build a VRT mosaic from source DEMs."""
    sources = [rasterio.open(path) for path in dem_paths]
    try:
        base = sources[0]
        if base.crs is None:
            raise ValueError("Source DEM CRS is required for mosaics.")
        crs = base.crs
        res_x, res_y = abs(base.res[0]), abs(base.res[1])
        dtype = base.dtypes[0]
        band_count = base.count
        nodata = base.nodata
        for src in sources[1:]:
            if src.crs != crs:
                raise ValueError("All mosaic sources must share the same CRS.")
            if src.count != band_count:
                raise ValueError("All mosaic sources must share the same band count.")
            if src.dtypes[0] != dtype:
                raise ValueError("All mosaic sources must share the same dtype.")

        min_x = min(src.bounds.left for src in sources)
        min_y = min(src.bounds.bottom for src in sources)
        max_x = max(src.bounds.right for src in sources)
        max_y = max(src.bounds.top for src in sources)
        width = max(1, int(math.ceil((max_x - min_x) / res_x)))
        height = max(1, int(math.ceil((max_y - min_y) / res_y)))
        transform = from_origin(min_x, max_y, res_x, res_y)
        geotransform = ", ".join(
            f"{value:.10f}" for value in transform.to_gdal()  # type: ignore[reportAttributeAccessIssue]
        )
        srs = crs.to_wkt()
        if srs:
            srs = " ".join(srs.split())

        if method not in {"first", "last"}:
            raise ValueError("VRT mosaics support only 'first' or 'last' methods.")
        ordered_sources = list(reversed(sources)) if method == "first" else sources

        root = ET.Element(
            "VRTDataset",
            rasterXSize=str(width),
            rasterYSize=str(height),
        )
        srs_node = ET.SubElement(root, "SRS")
        srs_node.text = srs
        geo_node = ET.SubElement(root, "GeoTransform")
        geo_node.text = geotransform

        relative_root = output_path.parent
        dtype_name = _gdal_typename(dtype)
        for band_index in range(1, band_count + 1):
            band_node = ET.SubElement(
                root,
                "VRTRasterBand",
                dataType=dtype_name,
                band=str(band_index),
            )
            if nodata is not None:
                nodata_node = ET.SubElement(band_node, "NoDataValue")
                nodata_node.text = str(nodata)
            for src in ordered_sources:
                bounds = src.bounds
                dst_x_off = int(round((bounds.left - min_x) / res_x))
                dst_y_off = int(round((max_y - bounds.top) / res_y))
                dst_x_size = max(
                    1,
                    int(round((bounds.right - bounds.left) / res_x)),
                )
                dst_y_size = max(
                    1,
                    int(round((bounds.top - bounds.bottom) / res_y)),
                )
                source_node = ET.SubElement(band_node, "SimpleSource")
                rel_path = os.path.relpath(src.name, relative_root)
                ET.SubElement(
                    source_node,
                    "SourceFilename",
                    relativeToVRT="1",
                ).text = Path(rel_path).as_posix()
                ET.SubElement(source_node, "SourceBand").text = str(band_index)
                ET.SubElement(
                    source_node,
                    "SrcRect",
                    xOff="0",
                    yOff="0",
                    xSize=str(src.width),
                    ySize=str(src.height),
                )
                ET.SubElement(
                    source_node,
                    "DstRect",
                    xOff=str(dst_x_off),
                    yOff=str(dst_y_off),
                    xSize=str(dst_x_size),
                    ySize=str(dst_y_size),
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree = ET.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return MosaicResult(
            path=output_path,
            crs=crs.to_string(),
            bounds=(min_x, min_y, max_x, max_y),
            resolution=(res_x, res_y),
        )
    finally:
        for src in sources:
            src.close()


def build_mosaic(
    dem_paths: Sequence[Path],
    output_path: Path,
    *,
    method: str = "first",
    driver: str = "GTiff",
    compression: str | None = None,
) -> MosaicResult:
    """Merge DEM inputs into a single mosaic dataset."""
    if not dem_paths:
        raise ValueError("At least one DEM path is required.")

    if driver.upper() == "VRT":
        return _build_vrt_mosaic(dem_paths, output_path, method=method)

    sources = [rasterio.open(path) for path in dem_paths]
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dst_kwds = {"driver": driver}
        if compression and driver.upper() != "VRT":
            dst_kwds["compress"] = compression
        merge(
            sources,
            method=method,
            dst_path=output_path,
            dst_kwds=dst_kwds,
        )
    finally:
        for src in sources:
            src.close()

    with rasterio.open(output_path) as dataset:
        bounds = dataset.bounds
        return MosaicResult(
            path=output_path,
            crs=dataset.crs.to_string(),
            bounds=(bounds.left, bounds.bottom, bounds.right, bounds.top),
            resolution=(abs(dataset.res[0]), abs(dataset.res[1])),
        )
