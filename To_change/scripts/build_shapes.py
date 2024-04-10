# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-Earth and PyPSA-Eur Authors
#
# SPDX-License-Identifier: GPL-3.0-or-later

# -*- coding: utf-8 -*-

import logging
import multiprocessing as mp
import os
import shutil
import zipfile
from itertools import takewhile
from math import ceil
from operator import attrgetter

import fiona
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
import rioxarray as rx
import xarray as xr
from _helpers import (
    configure_logging,
    sets_path_to_root,
    three_2_two_digits_country,
    two_2_three_digits_country,
    two_digits_2_name_country,
)
from rasterio.mask import mask
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid
from tqdm import tqdm

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sets_path_to_root("pypsa-earth")


def download_GADM(country_code, update=False, out_logging=False):
    """
    Download gpkg file from GADM for a given country code

    Parameters
    ----------
    country_code : str
        Two letter country codes of the downloaded files
    update : bool
        Update = true, forces re-download of files

    Returns
    -------
    gpkg file per country

    """

    GADM_filename = f"gadm41_{two_2_three_digits_country(country_code)}"
    GADM_url = f"https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/{GADM_filename}.gpkg"

    GADM_inputfile_gpkg = os.path.join(
        os.getcwd(),
        "data",
        "gadm",
        GADM_filename,
        GADM_filename + ".gpkg",
    )  # Input filepath gpkg

    if not os.path.exists(GADM_inputfile_gpkg) or update is True:
        if out_logging:
            logger.warning(
                f"Stage 4/4: {GADM_filename} of country {two_digits_2_name_country(country_code)} does not exist, downloading to {GADM_inputfile_gpkg}"
            )
        #  create data/osm directory
        os.makedirs(os.path.dirname(GADM_inputfile_gpkg), exist_ok=True)

        with requests.get(GADM_url, stream=True) as r:
            with open(GADM_inputfile_gpkg, "wb") as f:
                shutil.copyfileobj(r.raw, f)

    return GADM_inputfile_gpkg, GADM_filename


def filter_gadm(
    geodf,
    layer,
    cc,
    contended_flag,
    output_nonstd_to_csv=False,
):
    # identify non standard geodf rows
    geodf_non_std = geodf[geodf["GID_0"] != two_2_three_digits_country(cc)].copy()

    if not geodf_non_std.empty:
        logger.info(
            f"Contended areas have been found for gadm layer {layer}. They will be treated according to {contended_flag} option"
        )

        # NOTE: in these options GID_0 is not changed because it is modified below
        if contended_flag == "drop":
            geodf.drop(geodf_non_std.index, inplace=True)
        elif contended_flag != "set_by_country":
            # "set_by_country" option is the default; if this elif applies, the desired option falls back to the default
            logger.warning(
                f"Value '{contended_flag}' for option contented_flag is not recognized.\n"
                + "Fallback to 'set_by_country'"
            )

    # force GID_0 to be the country code for the relevant countries
    geodf["GID_0"] = cc

    # country shape should have a single geomerty
    if (layer == 0) and (geodf.shape[0] > 1):
        logger.warning(
            f"Country shape is composed by multiple shapes that are being merged in agreement to contented_flag option '{contended_flag}'"
        )
        # take the first row only to re-define geometry keeping other columns
        geodf = geodf.iloc[[0]].set_geometry([geodf.unary_union])

    # debug output to file
    if output_nonstd_to_csv and not geodf_non_std.empty:
        geodf_non_std.to_csv(
            f"resources/non_standard_gadm{layer}_{cc}_raw.csv", index=False
        )

    return geodf


def get_GADM_layer(
    country_list,
    layer_id,
    geo_crs,
    contended_flag,
    update=False,
    outlogging=False,
):
    """
    Function to retrive a specific layer id of a geopackage for a selection of countries

    Parameters
    ----------
    country_list : str
        List of the countries
    layer_id : int
        Layer to consider in the format GID_{layer_id}.
        When the requested layer_id is greater than the last available layer, then the last layer is selected.
        When a negative value is requested, then, the last layer is requested

    """
    # initialization of the geoDataFrame
    geodf_list = []

    for country_code in country_list:
        # Set the current layer id (cur_layer_id) to global layer_id
        cur_layer_id = layer_id

        # download file gpkg
        file_gpkg, name_file = download_GADM(country_code, update, outlogging)

        # get layers of a geopackage
        list_layers = fiona.listlayers(file_gpkg)

        # get layer name
        if (cur_layer_id < 0) or (cur_layer_id >= len(list_layers)):
            # when layer id is negative or larger than the number of layers, select the last layer
            cur_layer_id = len(list_layers) - 1

        # read gpkg file
        geodf_temp = gpd.read_file(
            file_gpkg, layer="ADM_ADM_" + str(cur_layer_id)
        ).to_crs(geo_crs)

        geodf_temp = filter_gadm(
            geodf=geodf_temp,
            layer=cur_layer_id,
            cc=country_code,
            contended_flag=contended_flag,
            output_nonstd_to_csv=False,
        )

        # create a subindex column that is useful
        # in the GADM processing of sub-national zones
        geodf_temp["GADM_ID"] = geodf_temp[f"GID_{cur_layer_id}"]

        # append geodataframes
        geodf_list.append(geodf_temp)

    geodf_GADM = gpd.GeoDataFrame(pd.concat(geodf_list, ignore_index=True))
    geodf_GADM.set_crs(geo_crs)

    return geodf_GADM


def _simplify_polys(polys, minarea=0.01, tolerance=0.01, filterremote=False):
    "Function to simplify the shape polygons"
    if isinstance(polys, MultiPolygon):
        polys = sorted(polys.geoms, key=attrgetter("area"), reverse=True)
        mainpoly = polys[0]
        mainlength = np.sqrt(mainpoly.area / (2.0 * np.pi))
        if mainpoly.area > minarea:
            polys = MultiPolygon(
                [
                    p
                    for p in takewhile(lambda p: p.area > minarea, polys)
                    if not filterremote or (mainpoly.distance(p) < mainlength)
                ]
            )
        else:
            polys = mainpoly
    return polys.simplify(tolerance=tolerance)


def countries(countries, geo_crs, contended_flag, update=False, out_logging=False):
    "Create country shapes"

    if out_logging:
        logger.info("Stage 1 of 4: Create country shapes")

    # download data if needed and get the layer id 0, corresponding to the countries
    df_countries = get_GADM_layer(
        countries,
        0,
        geo_crs,
        contended_flag,
        update,
        out_logging,
    )

    # select and rename columns
    df_countries = df_countries[["GID_0", "geometry"]].copy()
    df_countries.rename(columns={"GID_0": "name"}, inplace=True)

    # set index and simplify polygons
    ret_df = df_countries.set_index("name")["geometry"].map(_simplify_polys)
    # there may be "holes" in the countries geometry which cause troubles along the workflow
    # e.g. that is the case for enclaves like Dahagram–Angarpota for IN/BD
    ret_df.apply(lambda x: make_valid(x) if not x.is_valid else x)
    ret_df.reset_index()

    return ret_df


def country_cover(country_shapes, eez_shapes=None, out_logging=False, distance=0.1):
    if out_logging:
        logger.info("Stage 3 of 4: Merge country shapes to create continent shape")

    shapes = country_shapes.apply(lambda x: x.buffer(distance))
    shapes_list = list(shapes)
    if eez_shapes is not None:
        shapes_list += list(eez_shapes)

    africa_shape = unary_union(shapes_list)

    return africa_shape


def save_to_geojson(df, fn):
    if os.path.exists(fn):
        os.unlink(fn)  # remove file if it exists
    if not isinstance(df, gpd.GeoDataFrame):
        df = gpd.GeoDataFrame(dict(geometry=df))

    # save file if the GeoDataFrame is non-empty
    if df.shape[0] > 0:
        df = df.reset_index()
        schema = {**gpd.io.file.infer_schema(df), "geometry": "Unknown"}
        df.to_file(fn, driver="GeoJSON", schema=schema)
    else:
        # create empty file to avoid issues with snakemake
        with open(fn, "w") as fp:
            pass


def load_EEZ(countries_codes, geo_crs, EEZ_gpkg="./data/eez/eez_v11.gpkg"):
    """
    Function to load the database of the Exclusive Economic Zones.
    The dataset shall be downloaded independently by the user (see guide) or
    together with pypsa-earth package.
    """
    if not os.path.exists(EEZ_gpkg):
        raise Exception(
            f"File EEZ {EEZ_gpkg} not found, please download it from https://www.marineregions.org/download_file.php?name=World_EEZ_v11_20191118_gpkg.zip and copy it in {os.path.dirname(EEZ_gpkg)}"
        )

    geodf_EEZ = gpd.read_file(EEZ_gpkg).to_crs(geo_crs)
    geodf_EEZ.dropna(axis=0, how="any", subset=["ISO_TER1"], inplace=True)
    # [["ISO_TER1", "TERRITORY1", "ISO_SOV1", "ISO_SOV2", "ISO_SOV3", "geometry"]]
    geodf_EEZ = geodf_EEZ[["ISO_TER1", "geometry"]]
    selected_countries_codes_3D = [
        two_2_three_digits_country(x) for x in countries_codes
    ]
    geodf_EEZ = geodf_EEZ[
        [any([x in selected_countries_codes_3D]) for x in geodf_EEZ["ISO_TER1"]]
    ]
    geodf_EEZ["ISO_TER1"] = geodf_EEZ["ISO_TER1"].map(
        lambda x: three_2_two_digits_country(x)
    )
    geodf_EEZ.reset_index(drop=True, inplace=True)

    geodf_EEZ.rename(columns={"ISO_TER1": "name"}, inplace=True)

    return geodf_EEZ


def eez(
    countries,
    geo_crs,
    country_shapes,
    EEZ_gpkg,
    out_logging=False,
    distance=0.01,
    minarea=0.01,
    tolerance=0.01,
):
    """
    Creates offshore shapes by
    - buffer smooth countryshape (=offset country shape)
    - and differ that with the offshore shape
    Leads to for instance a 100m non-build coastline

    """

    if out_logging:
        logger.info("Stage 2 of 4: Create offshore shapes")

    # load data
    df_eez = load_EEZ(countries, geo_crs, EEZ_gpkg)

    eez_countries = [cc for cc in countries if df_eez.name.str.contains(cc).any()]
    ret_df = gpd.GeoDataFrame(
        {
            "name": eez_countries,
            "geometry": [
                df_eez.geometry.loc[df_eez.name == cc].geometry.unary_union
                for cc in eez_countries
            ],
        }
    ).set_index("name")

    ret_df = ret_df.geometry.map(
        lambda x: _simplify_polys(x, minarea=minarea, tolerance=tolerance)
    )

    ret_df = ret_df.apply(lambda x: make_valid(x))

    country_shapes_with_buffer = country_shapes.buffer(distance)
    ret_df_new = ret_df.difference(country_shapes_with_buffer)

    # repeat to simplify after the buffer correction
    ret_df_new = ret_df_new.map(
        lambda x: x
        if x is None
        else _simplify_polys(x, minarea=minarea, tolerance=tolerance)
    )
    ret_df_new = ret_df_new.apply(lambda x: x if x is None else make_valid(x))

    # Drops empty geometry
    ret_df = ret_df_new.dropna()
    ret_df = ret_df[ret_df.geometry.is_valid & ~ret_df.geometry.is_empty]

    return ret_df


def download_WorldPop(
    country_code,
    worldpop_method,
    year=2020,
    update=False,
    out_logging=False,
    size_min=300,
):
    """
    Download Worldpop using either the standard method or the API method.
        Parameters
        ----------
        worldpop_method: str
             worldpop_method = "api" will use the API method to access the WorldPop 100mx100m dataset.  worldpop_method = "standard" will use the standard method to access the WorldPop 1KMx1KM dataset.
        country_code : str
            Two letter country codes of the downloaded files.
            Files downloaded from https://data.worldpop.org/ datasets WorldPop UN adjusted
        year : int
            Year of the data to download
        update : bool
            Update = true, forces re-download of files
        size_min : int
            Minimum size of each file to download
    """
    if worldpop_method == "api":
        return download_WorldPop_API(country_code, year, update, out_logging, size_min)

    elif worldpop_method == "standard":
        return download_WorldPop_standard(
            country_code, year, update, out_logging, size_min
        )


def download_WorldPop_standard(
    country_code,
    year=2020,
    update=False,
    out_logging=False,
    size_min=300,
):
    """
    Download tiff file for each country code using the standard method from worldpop datastore with 1kmx1km resolution.

    Parameters
    ----------
    country_code : str
        Two letter country codes of the downloaded files.
        Files downloaded from https://data.worldpop.org/ datasets WorldPop UN adjusted
    year : int
        Year of the data to download
    update : bool
        Update = true, forces re-download of files
    size_min : int
        Minimum size of each file to download
    Returns
    -------
    WorldPop_inputfile : str
        Path of the file
    WorldPop_filename : str
        Name of the file
    """
    if out_logging:
        logger.info("Stage 3/4: Download WorldPop datasets")

    if country_code == "XK":
        WorldPop_filename = f"srb_ppp_{year}_UNadj_constrained.tif"
        WorldPop_urls = [
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/SRB/{WorldPop_filename}",
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/maxar_v1/SRB/{WorldPop_filename}",
        ]
    else:
        WorldPop_filename = f"{two_2_three_digits_country(country_code).lower()}_ppp_{year}_UNadj_constrained.tif"
        # Urls used to possibly download the file
        WorldPop_urls = [
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/{two_2_three_digits_country(country_code).upper()}/{WorldPop_filename}",
            f"https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/maxar_v1/{two_2_three_digits_country(country_code).upper()}/{WorldPop_filename}",
        ]

    WorldPop_inputfile = os.path.join(
        os.getcwd(), "data", "WorldPop", WorldPop_filename
    )  # Input filepath tif

    if not os.path.exists(WorldPop_inputfile) or update is True:
        if out_logging:
            logger.warning(
                f"Stage 4/4: {WorldPop_filename} does not exist, downloading to {WorldPop_inputfile}"
            )
        #  create data/osm directory
        os.makedirs(os.path.dirname(WorldPop_inputfile), exist_ok=True)

        loaded = False
        for WorldPop_url in WorldPop_urls:
            with requests.get(WorldPop_url, stream=True) as r:
                with open(WorldPop_inputfile, "wb") as f:
                    if float(r.headers["Content-length"]) > size_min:
                        shutil.copyfileobj(r.raw, f)
                        loaded = True
                        break
        if not loaded:
            logger.error(f"Stage 4/4: Impossible to download {WorldPop_filename}")

    return WorldPop_inputfile, WorldPop_filename


def download_WorldPop_API(
    country_code, year=2020, update=False, out_logging=False, size_min=300
):
    """
    Download tiff file for each country code using the api method from worldpop API with 100mx100m resolution.

    Parameters
    ----------
    country_code : str
        Two letter country codes of the downloaded files.
        Files downloaded from https://data.worldpop.org/ datasets WorldPop UN adjusted
    year : int
        Year of the data to download
    update : bool
        Update = true, forces re-download of files
    size_min : int
        Minimum size of each file to download
    Returns
    -------
    WorldPop_inputfile : str
        Path of the file
    WorldPop_filename : str
        Name of the file
    """
    if out_logging:
        logger.info("Stage 3/4: Download WorldPop datasets")

    WorldPop_filename = f"{two_2_three_digits_country(country_code).lower()}_ppp_{year}_UNadj_constrained.tif"
    # Request to get the file
    WorldPop_inputfile = os.path.join(
        os.getcwd(), "data", "WorldPop", WorldPop_filename
    )  # Input filepath tif
    os.makedirs(os.path.dirname(WorldPop_inputfile), exist_ok=True)
    year_api = int(str(year)[2:])
    loaded = False
    WorldPop_api_urls = [
        f"https://www.worldpop.org/rest/data/pop/wpgp?iso3={two_2_three_digits_country(country_code)}",
    ]
    for WorldPop_api_url in WorldPop_api_urls:
        with requests.get(WorldPop_api_url, stream=True) as r:
            WorldPop_tif_url = r.json()["data"][year_api]["files"][0]

        with requests.get(WorldPop_tif_url, stream=True) as r:
            with open(WorldPop_inputfile, "wb") as f:
                if float(r.headers["Content-length"]) > size_min:
                    shutil.copyfileobj(r.raw, f)
                    loaded = True
                    break
    if not loaded:
        logger.error(f"Stage 4/4: Impossible to download {WorldPop_filename}")

    return WorldPop_inputfile, WorldPop_filename


def convert_GDP(name_file_nc, year=2015, out_logging=False):
    """
    Function to convert the nc database of the GDP to tif, based on the work at https://doi.org/10.1038/sdata.2018.4.
    The dataset shall be downloaded independently by the user (see guide) or toghether with pypsa-earth package.
    """

    if out_logging:
        logger.info("Stage 4/4: Access to GDP raster data")

    # tif namefile
    name_file_tif = name_file_nc[:-2] + "tif"

    # path of the nc file
    GDP_nc = os.path.join(os.getcwd(), "data", "GDP", name_file_nc)  # Input filepath nc

    # path of the tif file
    GDP_tif = os.path.join(
        os.getcwd(), "data", "GDP", name_file_tif
    )  # Input filepath nc

    # Check if file exists, otherwise throw exception
    if not os.path.exists(GDP_nc):
        raise Exception(
            f"File {name_file_nc} not found, please download it from https://datadryad.org/stash/dataset/doi:10.5061/dryad.dk1j0 and copy it in {os.path.dirname(GDP_nc)}"
        )

    # open nc dataset
    GDP_dataset = xr.open_dataset(GDP_nc)

    # get the requested year of data or its closest one
    list_years = GDP_dataset["time"]
    if year not in list_years:
        if out_logging:
            logger.warning(
                f"Stage 3/4 GDP data of year {year} not found, selected the most recent data ({int(list_years[-1])})"
            )
        year = float(list_years[-1])

    # subset of the database and conversion to dataframe
    GDP_dataset = GDP_dataset.sel(time=year).drop("time")
    GDP_dataset.rio.to_raster(GDP_tif)

    return GDP_tif, name_file_tif


def load_GDP(
    countries_codes,
    year=2015,
    update=False,
    out_logging=False,
    name_file_nc="GDP_PPP_1990_2015_5arcmin_v2.nc",
):
    """
    Function to load the database of the GDP, based on the work at https://doi.org/10.1038/sdata.2018.4.
    The dataset shall be downloaded independently by the user (see guide) or toghether with pypsa-earth package.
    """

    if out_logging:
        logger.info("Stage 4/4: Access to GDP raster data")

    # path of the nc file
    name_file_tif = name_file_nc[:-2] + "tif"
    GDP_tif = os.path.join(
        os.getcwd(), "data", "GDP", name_file_tif
    )  # Input filepath tif

    if update | (not os.path.exists(GDP_tif)):
        if out_logging:
            logger.warning(
                f"Stage 4/4: File {name_file_tif} not found, the file will be produced by processing {name_file_nc}"
            )
        convert_GDP(name_file_nc, year, out_logging)

    return GDP_tif, name_file_tif


def generalized_mask(src, geom, **kwargs):
    "Generalize mask function to account for Polygon and MultiPolygon"
    if geom.geom_type == "Polygon":
        return mask(src, [geom], **kwargs)
    elif geom.geom_type == "MultiPolygon":
        return mask(src, geom.geoms, **kwargs)
    else:
        return mask(src, geom, **kwargs)


def _sum_raster_over_mask(shape, img):
    """
    Function to sum the raster value within a shape
    """
    # select the desired area of the raster corresponding to each polygon
    # Approximation: the population is measured including the pixels
    #   where the border of the shape lays. This leads to slightly overestimate
    #   the output, but the error is limited and it enables halving the
    #   computational time
    out_image, out_transform = generalized_mask(
        img, shape, all_touched=True, invert=False, nodata=0.0
    )
    # calculate total output in the selected geometry
    out_image[np.isnan(out_image)] = 0
    out_sum = out_image.sum()
    # out_sum = out_image.sum()/2 + out_image_int.sum()/2

    return out_sum


def add_gdp_data(
    df_gadm,
    year=2020,
    update=False,
    out_logging=False,
    name_file_nc="GDP_PPP_1990_2015_5arcmin_v2.nc",
    nprocesses=2,
    disable_progressbar=False,
):
    """
    Function to add gdp data to arbitrary number of shapes in a country

    Inputs:
    -------
    df_gadm: Geodataframe with one Multipolygon per row
        - Essential column ["country", "geometry"]
        - Non-essential column ["GADM_ID"]

    Outputs:
    --------
    df_gadm: Geodataframe with one Multipolygon per row
        - Same columns as input
        - Includes a new column ["gdp"]
    """
    if out_logging:
        logger.info("Stage 4/4: Add gdp data to GADM GeoDataFrame")

    # initialize new gdp column
    df_gadm["gdp"] = 0.0

    GDP_tif, name_tif = load_GDP(year, update, out_logging, name_file_nc)

    with rasterio.open(GDP_tif) as src:
        # resample data to target shape
        tqdm_kwargs = dict(
            ascii=False,
            unit=" geometries",
            total=df_gadm.shape[0],
            desc="Compute GDP ",
        )
        for i in tqdm(df_gadm.index, **tqdm_kwargs):
            df_gadm.loc[i, "gdp"] = _sum_raster_over_mask(df_gadm.geometry.loc[i], src)
    return df_gadm


def _init_process_pop(df_gadm_, year_, worldpop_method_):
    global df_gadm, year, worldpop_method
    df_gadm, year, worldpop_method = df_gadm_, year_, worldpop_method_


# Auxiliary function to calculate population data in a parallel way
def _process_func_pop(gadm_idxs):
    # get subset by country code
    df_gadm_subset = df_gadm.loc[gadm_idxs].copy()

    country_sublist = df_gadm_subset["country"].unique()

    for c_code in country_sublist:
        # get worldpop image
        WorldPop_inputfile, WorldPop_filename = download_WorldPop(
            c_code, worldpop_method, year, False, False
        )

        idxs_country = df_gadm_subset[df_gadm_subset["country"] == c_code].index

        with rasterio.open(WorldPop_inputfile) as src:
            for i in idxs_country:
                df_gadm_subset.loc[i, "pop"] = _sum_raster_over_mask(
                    df_gadm_subset.geometry.loc[i], src
                )

    return df_gadm_subset


# Auxiliary function to download WorldPop data in a parallel way
def _process_func_download_pop(c_code):
    WorldPop_inputfile, WorldPop_filename = download_WorldPop(
        c_code, worldpop_method, year, False, False
    )


def add_population_data(
    df_gadm,
    country_codes,
    worldpop_method,
    year=2020,
    update=False,
    out_logging=False,
    nprocesses=2,
    nchunks=2,
    disable_progressbar=False,
):
    """
    Function to add population data to arbitrary number of shapes in a country

    Inputs:
    -------
    df_gadm: Geodataframe with one Multipolygon per row
        - Essential column ["country", "geometry"]
        - Non-essential column ["GADM_ID"]

    Outputs:
    --------
    df_gadm: Geodataframe with one Multipolygon per row
        - Same columns as input
        - Includes a new column ["pop"]
    """

    if out_logging:
        logger.info("Stage 4/4 POP: Add population data to GADM GeoDataFrame")

    # initialize new population column
    df_gadm["pop"] = 0.0

    tqdm_kwargs = dict(
        ascii=False,
        desc="Compute population ",
    )
    if (nprocesses is None) or (nprocesses == 1):
        with tqdm(total=df_gadm.shape[0], **tqdm_kwargs) as pbar:
            for c_code in country_codes:
                # get subset by country code
                country_rows = df_gadm.loc[df_gadm["country"] == c_code]

                # get worldpop image
                WorldPop_inputfile, WorldPop_filename = download_WorldPop(
                    c_code, worldpop_method, year, update, out_logging
                )

                with rasterio.open(WorldPop_inputfile) as src:
                    for i, row in country_rows.iterrows():
                        df_gadm.loc[i, "pop"] = _sum_raster_over_mask(row.geometry, src)
                        pbar.update(1)

    else:
        # generator function to split a list ll into n_objs lists
        def divide_list(ll, n_objs):
            for i in range(0, len(ll), n_objs):
                yield ll[i : i + n_objs]

        id_parallel_chunks = list(
            divide_list(df_gadm.index, ceil(len(df_gadm) / nchunks))
        )

        kwargs = {
            "initializer": _init_process_pop,
            "initargs": (df_gadm, year, worldpop_method),
            "processes": nprocesses,
        }
        with mp.get_context("spawn").Pool(**kwargs) as pool:
            if disable_progressbar:
                list(pool.map(_process_func_download_pop, country_codes))
                _ = list(pool.map(_process_func_pop, id_parallel_chunks))
                for elem in _:
                    df_gadm.loc[elem.index, "pop"] = elem["pop"]
            else:
                list(
                    tqdm(
                        pool.imap(_process_func_download_pop, country_codes),
                        total=len(country_codes),
                        ascii=False,
                        desc="Download WorldPop ",
                        unit=" countries",
                    )
                )
                _ = list(
                    tqdm(
                        pool.imap(_process_func_pop, id_parallel_chunks),
                        total=len(id_parallel_chunks),
                        **tqdm_kwargs,
                    )
                )
                for elem in _:
                    df_gadm.loc[elem.index, "pop"] = elem["pop"]


def gadm(
    worldpop_method,
    gdp_method,
    countries,
    geo_crs,
    contended_flag,
    layer_id=2,
    update=False,
    out_logging=False,
    year=2020,
    nprocesses=None,
    nchunks=None,
):
    if out_logging:
        logger.info("Stage 4/4: Creation GADM GeoDataFrame")

    # download data if needed and get the desired layer_id
    df_gadm = get_GADM_layer(countries, layer_id, geo_crs, contended_flag, update)

    # select and rename columns
    df_gadm.rename(columns={"GID_0": "country"}, inplace=True)

    # drop useless columns
    df_gadm.drop(
        df_gadm.columns.difference(["country", "GADM_ID", "geometry"]),
        axis=1,
        inplace=True,
    )

    if worldpop_method != False:
        # add the population data to the dataset
        add_population_data(
            df_gadm,
            countries,
            worldpop_method,
            year,
            update,
            out_logging,
            nprocesses=nprocesses,
            nchunks=nchunks,
        )

    if gdp_method != False:
        # add the gdp data to the dataset
        add_gdp_data(
            df_gadm,
            year,
            update,
            out_logging,
            name_file_nc="GDP_PPP_1990_2015_5arcmin_v2.nc",
        )

    # renaming 3 letter to 2 letter ISO code before saving GADM file
    # solves issue: https://github.com/pypsa-meets-earth/pypsa-earth/issues/671
    df_gadm["GADM_ID"] = (
        df_gadm["GADM_ID"]
        .str.split(".")
        .apply(lambda id: three_2_two_digits_country(id[0]) + "." + id[1])
    )
    df_gadm.set_index("GADM_ID", inplace=True)
    df_gadm["geometry"] = df_gadm["geometry"].map(_simplify_polys)
    df_gadm.geometry = df_gadm.geometry.apply(
        lambda r: make_valid(r) if not r.is_valid else r
    )
    df_gadm = df_gadm[df_gadm.geometry.is_valid & ~df_gadm.geometry.is_empty]

    return df_gadm


if __name__ == "__main__":
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        snakemake = mock_snakemake("build_shapes")
        sets_path_to_root("pypsa-earth")
    configure_logging(snakemake)

    out = snakemake.output

    countries_list = snakemake.config["countries"]
    layer_id = snakemake.config["build_shape_options"]["gadm_layer_id"]
    update = snakemake.config["build_shape_options"]["update_file"]
    out_logging = snakemake.config["build_shape_options"]["out_logging"]
    year = snakemake.config["build_shape_options"]["year"]
    nprocesses = snakemake.config["build_shape_options"]["nprocesses"]
    contended_flag = snakemake.config["build_shape_options"]["contended_flag"]
    EEZ_gpkg = snakemake.input["eez"]
    worldpop_method = snakemake.config["build_shape_options"]["worldpop_method"]
    gdp_method = snakemake.config["build_shape_options"]["gdp_method"]
    geo_crs = snakemake.config["crs"]["geo_crs"]
    distance_crs = snakemake.config["crs"]["distance_crs"]
    nchunks = snakemake.config["build_shape_options"]["nchunks"]
    if nchunks < nprocesses:
        logger.info(f"build_shapes data chunks set to nprocesses {nprocesses}")
        nchunks = nprocesses

    country_shapes = countries(
        countries_list,
        geo_crs,
        contended_flag,
        update,
        out_logging,
    )
    country_shapes.to_file(snakemake.output.country_shapes)

    offshore_shapes = eez(
        countries_list, geo_crs, country_shapes, EEZ_gpkg, out_logging
    )

    offshore_shapes.reset_index().to_file(snakemake.output.offshore_shapes)

    africa_shape = gpd.GeoDataFrame(
        geometry=[country_cover(country_shapes, offshore_shapes.geometry)]
    )
    africa_shape.reset_index().to_file(snakemake.output.africa_shape)

    gadm_shapes = gadm(
        worldpop_method,
        gdp_method,
        countries_list,
        geo_crs,
        contended_flag,
        layer_id,
        update,
        out_logging,
        year,
        nprocesses=nprocesses,
        nchunks=nchunks,
    )
    save_to_geojson(gadm_shapes, out.gadm_shapes)
