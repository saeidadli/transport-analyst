"""
Uses Google API to preform network analysis.
"""

import json
from datetime import datetime

import googlemaps

import pandas as pd
import geopandas as gpd
import shapely.geometry as geom

from . import constants as cs

#=====================general functions==========================
# Request directions
def google_route(
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
    if mode not in list(cs.google_modes.keys()):
        raise ValueError("{0} is an invalid travel mode.".format(mode))

    if in_gdf.crs.name != 'WGS 84':
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")

    
    points = in_gdf['geometry'].tolist()
    origin = (points[0].y, points[0].x)
    destination = (points[-1].y, points[-1].x)
    waypoints = [(p.y, p.x) for p in points[1:-1]]
    
    
    gmaps = googlemaps.Client(key=api_key)
    
    columns = cs.columns
    
    if date_time == '':
        date_time = datetime.now()
    directions_result = gmaps.directions(
        origin = origin,
        destination = destination,
        waypoints = waypoints,
        mode = cs.google_modes[mode],
        departure_time=date_time,
    )
    

    df_list = list()
    simple_df_list = list()

    if directions_result:
        legs = directions_result[0]['legs']
        for i, leg in enumerate(legs):
            df = pd.DataFrame(leg['steps']).reset_index()

            df = df.rename(columns={
                'index': 'step_id', 
                'travel_mode': 'mode',
                'start_location': 'from',
                'end_location': 'to',
            })

            df['from'] = df['from'].map(lambda x: (x['lat'], x['lng']))
            df['to'] = df['to'].map(lambda x: (x['lat'], x['lng']))
            df['distance'] = df['distance'].map(lambda x: (x['value']))
            df['duration'] = df['duration'].map(lambda x: (x['value']/60))
            
            df['polyline'] = df['polyline'].map(
                lambda x: [(p['lng'], p['lat']) for p in googlemaps.convert.decode_polyline(x['points'])]
            )

            df['geometry'] = df['polyline'].map(lambda x: geom.LineString(x))

            df['trip_name'] = trip_name
            df['leg_id'] = i
            

            for column in columns:
                if column not in df.columns.values:
                    df[column] = ''

            df_list.append(df[columns].copy())
            
            if result == 'simple':
                polyline = [item for sublist in df['polyline'].to_list() for item in sublist]
                polyline = geom.LineString(polyline)
                simple_df = pd.DataFrame([leg])
                simple_df = simple_df.rename(columns={
                    'start_location': 'from',
                    'start_address': 'from_name',
                    'end_location': 'to',
                    'end_address': 'to_name',
                    'arrival_time': 'start_time',
                })
                
                if 'start_time' in simple_df.columns:
                    simple_df['start_time'] = simple_df['start_time'].map(lambda x: datetime.fromtimestamp(x['value']))
                simple_df['from'] = simple_df['from'].map(lambda x: (x['lat'], x['lng']))
                simple_df['to'] = simple_df['to'].map(lambda x: (x['lat'], x['lng']))
                simple_df['distance'] = simple_df['distance'].map(lambda x: (x['value']))
                simple_df['duration'] = simple_df['duration'].map(lambda x: (x['value']/60))
                simple_df['geometry'] = polyline
                simple_df['mode'] = mode
                simple_df['leg_id'] = i
                simple_df['trip_name'] = trip_name
                simple_df['route_id'] = [df['route_id'].to_list()]
                simple_df['trip_id'] = [df['trip_id'].to_list()]
                simple_df['wait_time'] = df['wait_time'].sum()
                for column in columns:
                    if column not in simple_df.columns.values:
                        simple_df[column] = ''
                
                simple_df_list.append(simple_df[columns].copy())
    if result == 'simple':
        gdf = gpd.GeoDataFrame(pd.concat(simple_df_list), crs=cs.WGS84)
    elif result == 'detailed':
        gdf = gpd.GeoDataFrame(pd.concat(df_list), crs=cs.WGS84)
      
    return gdf

def od_matrix(
    origins,
    destinations,
    mode = 'transit', 
    departure_time = datetime.now()):
    
    assert mode in ['transit', 'bus', 'subway', 'train', 'tram', 'rail']

    origins = origins.to_crs({'init': 'epsg:4326'})
    o_list = [{"lat": point.y, "lng": point.x} for point in origins.geometry.tolist()] 
    
    destinations = destinations.to_crs({'init': 'epsg:4326'})
    d_list = [{"lat": point.y, "lng": point.x} for point in destinations.geometry.tolist()] 
    
    gmaps = googlemaps.Client(key=key)
    origins = o_list
    destinations = d_list
    odm = gmaps.distance_matrix(
        origins, 
        destinations,
        mode = mode,
        departure_time=dt,
        language="en-AU",
        units="metric",
        traffic_model="optimistic",
    )
    
    pass


