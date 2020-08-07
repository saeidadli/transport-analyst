"""
Functions about accessibility analysis.
"""

import pandas as pd
import geopandas as gpd
import requests

from shapely import geometry




def catchment_pop(
    catchment, 
    census, 
    fields,
    show_progress = True,
):
    """
    ``fields`` are usually population or employment data from census. 
    Calculates the how many people work or live in the catchment areas and
    adds these fields to the catchment GeoDataFrame.

    Parameters
    ----------
    catchment : GeoDataFrame
        It is a GeoDataFrame of many catchment isochrones.
    census : GeoDataFrame
        It is a census file that usually has population and palce of work data.
    fields : A list of GeoDataFrame columns
        The numeric comlumns in the census GeoDataFrame that usually contain
        population and place of work data.

    Returns
    -------
    GeoDataFrame
        Has the structure
        All coulumns that already exists in catchment GeoDataFrame
        -``fields`` coulumns are added.
    """
    
    agg_dict = dict(zip(fields, ['sum' for i in fields]))
    
    if not catchment.crs or not census.crs:
        # Check the cooridnate system
        raise ValueError("Input GeoDataFrame must have a cooridnate system.")
        
    catchment = catchment.to_crs({'init': 'epsg:4326'}) #Convert CRS to WGS84
    if '__uid__' not in catchment.columns: #Add a unique filed ID
        catchment.insert(0, '__uid__', range(0, len(catchment)))
    else:
        catchment['__uid__'] = range(0, len(catchment))
    
    census = census.to_crs({'init': 'epsg:4326'}) #Convert CRS to WGS84
    census['__orig_area__'] = census['geometry'].area #Add a unique filed ID
    
    #intersect the catchment individually with the census to avoid any data losses
    catchments_cnt = catchment.shape[0]
    results_list = list()
    step = 10
    for i in range(0, catchments_cnt, step):
#         try:
        #process a batch of 100 catchments - intersects each catchment with the SA1 polygons
        intersect = gpd.overlay(catchment.iloc[i:i+step, :], census, how='intersection')
        intersect['__area__']= intersect['geometry'].area

        #recalculate fields - intersected area/orignal area coverage
        for field in fields:
            intersect[field] = intersect['__area__']/intersect['__orig_area__']*intersect[field]

        #group by SA1 and aggregate results
        result_df = intersect.groupby('__uid__').agg(agg_dict).reset_index()

        results_list.append(result_df)
        progress = round((i+step)/catchments_cnt*100, 1)
        progress = 100 if progress>100 else progress

        if show_progress == True:
            print('{0}% is done.'.format(progress))
#         except Exception as e: print(e)

    if results_list:
        result_df = pd.concat(results_list)
        output = catchment.merge(result_df, how='left')
        output = output.drop(['__uid__'], axis=1)
    else:
        output = pd.DataFrame()
    return output


       

def accessibility(
    census_gdf,
    fields,
    date_time,
    travel_ranges, #minutes
    modes,
    api = '',
    api_key = '',
):
    """
    Calculates the how many people work or live in a certain time by certian travel range
    and certain modes of transport. The input census geodataframe should include socio-economic
    data.

    Parameters
    ----------
    census_gdf : GeoDataFrame
        It is a GeoDataFrame of census zones.
    fields : List of field names,
        A list of numerical field names that include socio economic data (usually total jobs
        in the census zones).
    date_time : A string that shows data and time for the analysis.
        The format should be "yyyymmdd hhmm".
    travel_range : A list of times in minutes.
        The list can also be generated automatically by a code for example: ``list(range(5, 65,5))``
        generats a list of every 5 minutes from 5 to 60 minutes.
    modes : list of all travel modes.
        The list can include: drive_intraffic, drive_freeflow, walk, cycle, truck.
    api: string.
        The api used for routing.
    api_key: API key is a key for Here API.
        More information is available here:
        

    Returns
    -------
    GeoDataFrame
        Has the structure
        All coulumns that already exists in census_gdf. The accessiblity fields are added.
        An example of field names is: POW_20200305_0800_30min_drive_intraffic
    """
    
    def catchment(row):
        feature_point_geom = row.geometry
        start = [feature_point_geom.x, feature_point_geom.y]

        g = iso_drive(
            modes = modes,
            start = start,
            date_time = date_time,
            travel_ranges = travel_ranges,
            api_key = api_key,
        )

        catchment = gpd.GeoDataFrame(g)
        catchment = catchment_pop(catchment, census_gdf, fields)

        row = row.coombine_first(catchment.iloc[0])
    
    
    census_gdf = census_gdf.apply(catchment, axis = 1)

    return census_gdf 
    
    