"""
Functions about accessibility analysis.
"""

import pandas as pd
import geopandas as gpd
import requests

from datetime import datetime
from shapely import geometry

from . import fn_otp
from . import fn_here
from . import constants as cs




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
        
    if catchment.crs['init'] not in cs.WGS84['init']:
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")
        
    if census.crs['init'] not in cs.WGS84['init']:
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")
        
    if '__uid__' not in catchment.columns: #Add a unique filed ID
        catchment.insert(0, '__uid__', range(0, len(catchment)))
    else:
        catchment['__uid__'] = range(0, len(catchment))
    
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
    census,
    fields,
    mode,
    travel_time,
    api,
    api_key = '',
    date_time = '',
    show_progress = True,
):
    """
    Adds accessiblity data to inuput census GeoDataFrame.
    Parameters
    ----------
    in_gdf : GeoDataFrame
        Contains census zone boundaries. The attribute data should have
        number of jobs for each zone.
    fields : A list of names of numerical fieds in census GeoDataFrame
        fields are the name of the fields in 'in_gdf' that contains numerical
        information such as total jobs for each zone.
    mode : string
        Indicates the mode of transport. It can include walk, cycle,
        public_transport.
    travel_time : minutes
        A time break in minutes. Shows maximum time someone is allowed to travel
        to access a destination.
    api : string
        Defines the api that should be used for routing. 
        The avialable apis are otp, here and google
    date_time : a datetime object
        Sets the start time of a trip. Only important if the mode is 
        transit or a subset of transit.  

    Returns
    -------
    GeoDataFrame
        Has the ``census`` structure and only adds one more field:
        -``accessiblity`` total jobs available for each zone in the sepcified
        time of day, the speficified mode and the specified travel time.
    """

     
    if mode not in list(cs.otp_modes.keys()):
        raise ValueError("{0} is an invalid travel mode.".format(mode))
        
    
    if census.crs['init'] not in cs.WGS84['init']:
        # Check the cooridnate is WGS84
        raise ValueError("Invalid coordinate system.")
        
    if not date_time:
        date_time = datetime.now()
        
    census['centroid'] = census.centroid
    
    def accessibility(row):
        o = row['centroid']
        gdf = gpd.GeoDataFrame({'geometry':[o]}, crs = cs.WGS84)
        
        if api == 'otp':
            sa = fn_otp.otp_service_area(
                in_gdf = gdf,
                mode = mode, 
                breaks = [travel_time],
                date_time = date_time,
            )
        elif api == 'here':
            sa = fn_here.here_service_area(
                in_gdf = gdf,
                mode = mode, 
                breaks = [travel_time],
                date_time = date_time,
                api_key=api_key,
            )

        
        emp = catchment_pop(
            catchment = sa,
            census = census, 
            fields = fields,
            show_progress = False,
        )

        if not emp.empty:
            emp = emp[fields].iloc[0]
        if emp.empty:
            emp = pd.Series(dict.fromkeys(fields, 0))
        
        progress = (row.name+1)/len(census)*100
        if show_progress == True and round(progress, 0)%10==0:
            print('{0}% is done.'.format(round(progress, 1)))        
        return emp


    columns = ['{0}_{1}_{2}'.format(mode, date_time.strftime('%Y%m%d_%H%M'), f) for f in fields]
    df = census.apply(accessibility, axis=1)
    df.columns = columns
    census = census.join(df).copy()
   
    return census
    
    