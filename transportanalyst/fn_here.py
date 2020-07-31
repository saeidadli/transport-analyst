import pandas as pd
import geopandas as gpd
import requests

from shapely import geometry

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