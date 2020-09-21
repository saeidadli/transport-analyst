"""
Uses otp API to preform network analysis.
"""

import json
import time
import zipfile
import io

from datetime import datetime

import requests
import tempfile

import pandas as pd
import geopandas as gpd
import shapely.geometry as geom

from pathlib import Path
from googlemaps.convert import decode_polyline

from . import constants as cs

#=====================api functions====================================
def otp_route(
    in_gdf, 
    mode,
    date_time = datetime.now(),
    trip_name = '',
):
    """
    Return a GeoDataFrame with detailed trip information for the best option.
    Parameters
    ----------
    in_gdf : GeoDataFrame
        It should only contain two records, first record is origina and
        the second record is destination. If more than two records only
        the first two records are considered.
    mode : string
        Indicates transport modes. Modes that can be used 
        include 'public_transport', 'car_in_traffic', 'car_free_flow',
        'walk', 'cycle'
    trip_name : string
        gives the trip a name which is stored in the trip_name in output
        GeoDataFrame.
    date_time : a datetime object
        Sets the start time of a trip. Only important if the mode is 
        transit or a subset of transit.
        
    Returns
    -------
    GeoDataFrame
        Has the structure
        -``trip_name`` the name given as an input to the trip.
        -``leg_id`` A counter for each trip leg
        -``mode``  returns the mode for each trip leg
        -``from`` the shaply point data in WSG84 for the origin location
        -``from_name`` the interim stop id on the network or 'Origin'
        -``to`` the shaply point data in WSG84 for the destination location
        -``to_name`` the interim stop id on the network or 'Destination'
        -``route_id`` the route id for the trip leg if the mode is transit
        -``trip_id`` the trip id for the trip leg if the mode is transit
        -``distance`` Distance traveled in meters for the trip leg
        -``duration``  Travel time for the trip leg in seconds
        -``startTime`` time stamp for the start time of the trip leg
        -``endTime`` time stamp for the end time of the trip leg
        -``waitTime``  Wait time for the trip leg in seconds
        -``geometry``  The goemetry of the trip leg in shaply object and WGS84
    """
    # The mode parameter is not validated by the Maps API
    # Check here to prevent silent failures.
    if mode not in list(cs.otp_modes.keys()):
        raise ValueError("{0} is an invalid travel mode.".format(mode))
        
    
    if in_gdf.crs['init'] not in cs.WGS84['init']:
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")
        
    if mode == 'public_transport' and not date_time:
        date_time = datetime.now()
        
    #get from and to location from locations_gdf
    orig = in_gdf['geometry'].iat[0]
    dest = in_gdf['geometry'].iat[-1]
    orig_text = "{0}, {1}".format(orig.y, orig.x)
    dest_text = "{0}, {1}".format(dest.y, dest.x)
    

    t = date_time.strftime("%H:%M%p")
    d = date_time.strftime("%m-%d-%Y")

    #send query to api
    url = 'http://localhost:8080/otp/routers/default/plan'
    query = {
        "fromPlace":orig_text,
        "toPlace":dest_text,
        "time":t,
        "date":d,
        "mode":cs.otp_modes[mode],
    }

    r = requests.get(url, params=query)
    
    #check for request error
    r.raise_for_status()

    #if error then return emptly GeoDataFrame
    if not 'error' in r.json():

        #convert request output ot a GeoDataFrame
        df = pd.DataFrame(r.json()['plan']['itineraries'][0]['legs']).reset_index()
        df = df.rename(columns={
            'index': 'leg_id', 
            'mode': 'mode',
            'routeId': 'route_id',
            'tripId': 'trip_id',
            'startTime': 'start_time',
            'endTime': 'end_time',
            'wait_time': 'waitTime',   
        })
        
        df['geometry'] = df['legGeometry'].map(
            lambda x: geom.LineString([(p['lng'], p['lat']) for p in decode_polyline(x['points'])])
        )
        
        df['from_name'] = df['from'].map(lambda x: x['stopId'] if 'stopId' in x else x['name'])
        df['to_name'] = df['to'].map(lambda x: x['stopId'] if 'stopId' in x else x['name'])

        df['from'] = df['from'].map(lambda x: geom.Point(x['lon'], x['lat']))
        df['to'] = df['to'].map(lambda x: geom.Point(x['lon'], x['lat']))
        
        df['start_time'] = df['start_time'].map(lambda x: datetime.fromtimestamp(x/1000))
        df['end_time'] = df['end_time'].map(lambda x: datetime.fromtimestamp(x/1000))    

        
        #calculate wait time
        df['wait_time'] = df['start_time'].shift(-1)
        df['wait_time'] = df['wait_time']-df['end_time']
        
        df['trip_name'] = trip_name
        
        for column in cs.columns:
            if column not in df.columns.values:
                df[column] = ''
                
                
        #reorder the fields
        df = df[cs.columns].copy()
        gdf = gpd.GeoDataFrame(df, crs = cs.WGS84)
    else:
        gdf = gpd.GeoDataFrame()
    
    gdf = gdf[gdf['geometry'].notnull()].copy()
    return gdf

def otp_service_area(
    in_gdf, 
    mode, 
    breaks,
    id_field ='',
    date_time = '',
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
    if not id_field:
        in_gdf = in_gdf.reset_index()
        in_gdf = in_gdf.rename(columns={
            'index': 'id_field',  
        })
        id_field = 'id_field'
        
    if mode not in list(cs.otp_modes.keys()):
        raise ValueError("{0} is an invalid travel mode.".format(mode))
        
    
    if in_gdf.crs['init'] not in cs.WGS84['init']:
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")
        
    if not date_time:
        date_time = datetime.now()
    
    #convert time into text
    t = date_time.strftime("%H:%M%p")
    d = date_time.strftime("%Y/%m/%d")
    
    #run for each single point in GeoDataFrame
    url = 'http://localhost:8080/otp/routers/default/isochrone'
    iso_list = list()
    for row in in_gdf.iterrows():
        indx = row[0]
        orig = row[1]['geometry']

        #convert origin from shapely to text
        orig_text = "{0}, {1}".format(orig.y, orig.x)

        #send query to api
        query = {
            "fromPlace":orig_text,
            "date":d,
            "time":t,
            "mode":cs.otp_modes[mode],
            "cutoffSec":[x*60 for x in breaks],
        }
        r = requests.get(url, params=query)

        if r.status_code == 500:
            iso_gdf = gpd.GeoDataFrame()
        elif 'zip' in r.headers['Content-Type']:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            tmp_dir = tempfile.TemporaryDirectory()
            z.extractall(tmp_dir.name)
            shapefiles = list()
            for f in Path(tmp_dir.name).glob("*.shp"):
                shapefiles.append(f)
            iso_gdf = gpd.read_file(str(shapefiles[0]))
            tmp_dir.cleanup()
        elif r.json():
            iso_gdf = gpd.GeoDataFrame.from_features(r.json()['features'])
        else:
            iso_gdf = gpd.GeoDataFrame()

        iso_gdf['name'] = row[1][id_field]

        iso_list.append(iso_gdf)

    if iso_list:
        df = pd.concat(iso_list) 
        if not df.empty:
            df = df[df['geometry'].notnull()].copy()
            gdf = gpd.GeoDataFrame(df, crs = cs.WGS84).copy()
        else:
            gdf = gpd.GeoDataFrame(crs = cs.WGS84)
    else:
        gdf = gpd.GeoDataFrame(crs = cs.WGS84)
    
    return gdf.reset_index(drop = True)

def od_matrix(
    origins,
    destinations,
    mode,
    origins_name,
    destinations_name,
    max_travel_time = 60,
    date_time = datetime.now(),
): # a dictionary of control variables
    """
    Return a GeoDataFrame with detailed trip information for the best option.
    Parameters
    ----------
    origins : GeoDataFrame
        It should only contain a series of points.
    destinations : GeoDataFrame
        It should only contain a series of points.
    mode : string
        Indicates transport modes. Modes that can be used 
        include 'public_transport', 'car_in_traffic', 'car_free_flow',
        'walk', 'cycle'
    origins_name : string
        gives the origin a name which is stored in the ``trip_name`` in output
        GeoDataFrame.
    max_travel_time : integer
        maximum travel time from each origin in minutes. Use ``None`` to disable
        it.
    date_time : a datetime object
        Sets the start time of a trip. Only important if the mode is 
        transit or a subset of transit.  

    Returns
    -------
    GeoDataFrame
        Has the structure
        trip_name -> contains ``origins_name`` for each origin.
        The rest are similar to the ``route`` function. 
    """    
       
    if not origins.crs or not destinations.crs:
        print('please define projection for the input gdfs')
        sys.exit()
    
    #convert the geometry into a list of dictinoaries
    origins = origins.to_crs({'init': 'epsg:4326'})
    destinations = destinations.to_crs({'init': 'epsg:4326'})
    
    od_list = list()
    cnt = 0
    #mark time before start
    t1 = datetime.now()
    print('Analysis started at: {0}'.format(t1))
    
    if max_travel_time:
        iso  = service_area(
            origins, 
            id_field = origins_name,
            mode = mode, 
            breaks = [max_travel_time], #in seconds
            date_time = date_time,
            control_vars = control_vars,
        )
    
    poly_destinations = destinations.copy()
    poly_destinations['geometry']= poly_destinations.buffer(0.00001)
    
    for o in origins[['geometry', origins_name]].itertuples():
        o_name = o[2]
        selected_iso = iso[iso['name']==o_name].copy()
        selected_iso = gpd.GeoDataFrame(selected_iso)
        
        res_intersection = gpd.overlay(poly_destinations, selected_iso, how='intersection')
        
        selected_destinations = destinations[destinations[destinations_name].isin(res_intersection[destinations_name])].copy()

        #selected_destinations
        for d in selected_destinations[['geometry', destinations_name]].itertuples():
            od = pd.DataFrame(
                [[o[1], o[2]],
                 [d[1], d[2]]],
                columns = ['geometry', 'location Name'])
            od = gpd.GeoDataFrame(od, crs = {'init': 'epsg:4326'})
            r = route(
                locations_gdf = od, #a pair of locations in geodataframe fromat
                mode = mode,
                trip_name = 'from {0} to {1}'.format(o[2], d[2]),
                date_time = date_time,
            )
            od_list.append(r)
            
        cnt += 1
        t_delta = datetime.now() - t1
        eta = t_delta * origins.shape[0] / cnt
        print("calculating {0} ODs, remaining origins {1}, estimated remaining time: {2}".format(selected_destinations.shape[0], origins.shape[0] - cnt, eta - t_delta))

    od_df = pd.concat(od_list).reset_index(drop = True)
    od_gdf = gpd.GeoDataFrame(od_df, crs = {'init': 'epsg:4326'})
    print("Elapsed time was {0} seconds".format(datetime.now() - t1))
    
    return od_gdf

    
    
    
    
    
    
    