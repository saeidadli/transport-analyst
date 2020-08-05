"""
Uses Here API to preform network analysis.
"""
import pandas as pd
import geopandas as gpd
import requests

from shapely import geometry
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

    if in_gdf.crs['init'] not in cs.WGS84['init']:
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

def iso_drive(
    date_time,
    travel_ranges, #in minutes
    modes,
    start,
    api_key,

):
    """
    This function calculates a catchment (isochrone) from a location by any modes.
    It uses Here API so an API key should be provided.

    Parameters
    ----------
    mode : Mode is a text string. 
        The possible modes are:
            1- 'drive_intraffic'
            2- 'drive_freeflow'
            3- 'walk'
            4- 'cycle'
            5- 'truck'
    start : coorditate in WGS84 system
        Start is a text string that shows a coorditate in WGS84 system.
    date_time : text string.
        The format for the date and time is yyyymmdd hh:mm.

    Returns
    -------
    A shaply polygon that shows the catchment in WGS84 coordinate system.
    """
    #reference mode: 
    #  type: [ fastest | shortest | balanced ], 
    #  TransportMode: [car | pedestrian | carHOV | publicTransport | publicTransportTimeTable | truck | bicycle ]
    #  TrafficMode: [enabled | disabled | default]
    
    mode_dict = {
        'drive_intraffic': 'fastest;car;traffic:enabled',
        'drive_freeflow': 'fastest;car;traffic:disabled',
        'walk': 'fastest;pedestrian',
        'cycle':'fastest;bicycle',
        'truck':'fastest;truck',
    }
    
    dt = '{0}-{1}-{2}T{3}:{4}:00'.format(
        date_time[:4], 
        date_time[4:6], 
        date_time[6:8], 
        date_time[9:11], 
        date_time[:-2],
    )
    start = '{0},{1}'.format(start[1], start[0]) #'y,x'
    travel_ranges = ','.join([str(i*60) for i in travel_ranges])
    
    for mode in modes:
        p = {
            'mode': mode_dict[mode],
            'start': start,
            'departure': dt,
            'rangetype': 'time',
            'range': travel_ranges, #in seconds
            'apiKey': api_key,
        }

        url = 'https://isoline.route.ls.hereapi.com/routing/7.2/calculateisoline.json'
        r = requests.get(url, params=p)
        if r.status_code==200 and 'isoline' in r.json()['response']:
            iso_list = r.json()['response']['isoline'][0]['component'][0]['shape']
            g = geometry.Polygon([[float(i) for i in reversed(i.split(','))] for i in iso_list])
        else:
            g = geometry.Polygon()
    return g