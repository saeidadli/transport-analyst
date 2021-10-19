"""
Uses Here API to preform network analysis.
"""
import pandas as pd
import geopandas as gpd
import zipfile
import io
import requests
import tempfile

import shapely.geometry as geom

from datetime import datetime
from . import constants as cs

def here_route(
    in_gdf, 
    mode,
    date_time = '',
    trip_name = '',
    api_key='', 
    result = 'detailed',
):
    
    """
    Get directions between an origin point and a destination point. 
    Parameters
    ----------
    in_gdf : GeoDataFrame
        It should only contain two records, first record is origina and
        the second record is destination. If more than two records only
        the first and the last records are considered.
    mode : string
        A transport mode that can be 'public_transport', 'car_in_traffic',
        'car_free_flow', 'walk', 'cycle'.
    date_time : a datetime object
        Sets the start time of a trip. Only important if the mode is 
        transit or a subset of transit.
    trip_name : string
        gives the trip a name which is stored in the trip_name in output
        GeoDataFrame.
    api_key : string
        api key.

    Returns
    -------
    GeoDataFrame
        Has the structure
        -``mode``: the travel mode for this route.
        -``date and time``: the date and time of travel.
        -``duration``: the duration of travel in minutes.
        -``geometry``: the geometry of the trip.
    """
    # The mode parameter is not validated by the Maps API
    # Check here to prevent silent failures.
    if mode not in list(cs.here_modes.keys()):
        raise ValueError("{0} is an invalid travel mode.".format(mode))

    if in_gdf.crs.name != 'WGS 84':
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")
    
    waypoints = dict()
    for i, p in enumerate(in_gdf['geometry'].tolist()):
        waypoints['waypoint{0}'.format(i)] = '{0},{1}'.format(p.y, p.x)
    
    if date_time == '':
        date_time = datetime.now()
        
    date_time = date_time.strftime('%Y-%m-%dT%H:%M:00')
    
    url = 'https://route.ls.hereapi.com/routing/7.2/calculateroute.json'
    query = {
        "mode":cs.here_modes[mode],
        "departure": date_time,
        "apiKey": api_key,
    }
    query = {**query, **waypoints}
    print(query)
    r = requests.get(url, params=query)
    
    output = r.json()
    
    #out_gdf = gpd.GeoDataFrame(r.json()['route'])
      
    return output

def here_service_area(
    in_gdf,
    mode, 
    breaks,
    id_field ='',
    date_time = '',
    api_key='',
): 

    
    """
    Return a GeoDataFrame of catchments for each point in 'in_gdf'.
    Parameters
    ----------
    in_gdf : GeoDataFrame
        Contains a series of points and optionally a name for each point
        as the origins of the catchment analysis.
    id_field : string
        id_field is the name of the field in 'in_gdf' that contains
        the ids for each origin. Each point has to have a unique id.
    mode : string
        Indicates transport modes. Modes that can be used 
        include 'public_transport', 'car_in_traffic', 'car_free_flow',
        'walk', 'cycle'
    breaks : list
        A list of time breaks in minutes. A catchment for each time break
        will be created for each origin.
    date_time : a datetime object
        Sets the start time of a trip. Only important if the mode is 
        transit or a subset of transit. 

    Returns
    -------
    GeoDataFrame
        Has the structure
        -``time`` time break for the isochrone in seconds.
        -``geometry`` Shaply polygon geometry
        -``name`` name of the origin from the input 'id_field'.

    """
    # The mode parameter is not validated by the Maps API
    # Check here to prevent silent failures.
    if mode not in list(cs.here_modes.keys()):
        raise ValueError("{0} is an invalid travel mode.".format(mode))
    if mode in ['cycle', 'public_transport']:
        raise ValueError("{0} is an invalid travel mode.".format(mode))
        
    if in_gdf.crs.name != 'WGS 84':
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")
    
    
    if date_time == '':
        date_time = datetime.now()
        
    date_time = date_time.strftime('%Y-%m-%dT%H:%M:00')
    
    if not id_field:
        in_gdf = in_gdf.reset_index()
        in_gdf = in_gdf.rename(columns={
            'index': 'id_field',  
        })
        id_field = 'id_field'

    #run for each single point in GeoDataFrame
    url = 'https://isoline.route.ls.hereapi.com/routing/7.2/calculateisoline.json'
    df_list = list()
    for row in in_gdf.iterrows():
        indx = row[0]
        orig = row[1]['geometry']
        
        start = '{0},{1}'.format(orig.y, orig.x) #'y,x'
        travel_ranges = ','.join([str(i*60) for i in breaks])
    
        query = {
            'mode': cs.here_modes[mode],
            'start': start,
            'departure': date_time,
            'rangetype': 'time',
            'range': travel_ranges, #in seconds
            'apiKey': api_key,
        }

        r = requests.get(url, params=query)

        
        if r.status_code==200 and 'isoline' in r.json()['response']:
            df = pd.DataFrame(r.json()['response']['isoline'])
            df['geometry'] = df['component'].map(
                lambda x: geom.Polygon(
                    [[float(i) for i in reversed(i.split(','))] for i in x[0]['shape']]
                )
            )
            df['name'] = row[1][id_field]
            df = df.rename(columns={'range': 'time'})
            df_list.append(df)

            
        
        
    if df_list:
        df = pd.concat(df_list)   
        df = df[df['geometry'].notnull()].copy()
        gdf = gpd.GeoDataFrame(df[['name', 'time', 'geometry']], crs = cs.WGS84)
    else:
        gdf = gpd.GeoDataFrame(crs = cs.WGS84)
            
    return gdf