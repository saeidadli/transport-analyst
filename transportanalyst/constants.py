"""
Constants useful across modules.
"""
#standard format for respond GeoDataFrame
columns = [
    'trip_name',
    'leg_id',
    'step_id',
    'mode',
    'from',
    'from_name',
    'to',
    'to_name',
    'route_id',
    'trip_id',
    'distance',
    'duration',
    'start_time',
    'end_time',
    'wait_time',
    'geometry']

modes = [
    'public_transport',
    'car_in_traffic',
    'car_free_flow',
    'walk',
    'cycle',
]

google_modes = {
    'public_transport': 'transit',
    'car_in_traffic': 'driving',
    'walk': 'walking',
    'cycle': 'bicycling',    
}

here_modes = {
    'drive_intraffic': 'fastest;car;traffic:enabled',
    'drive_freeflow': 'fastest;car;traffic:disabled',
    'public_transport': 'fastest;publicTransport',
    'walk': 'fastest;pedestrian',
    'cycle':'fastest;bicycle',
    'truck':'fastest;truck',
}

otp_modes = {
    'public_transport': 'TRANSIT,WALK',
    'car_free_flow': 'CAR',
    'walk': 'WALK',
    'cycle': 'BICYCLE',    
}

#Full otp modes: CAR, BUS, FERRY, RAIL, TRANSIT, WALK, BICYCLE, MULTIMODAL

#: WGS84 coordinate reference system for Geopandas
import geopandas as gpd
WGS84 = gpd.GeoDataFrame({'geometry':[]}, crs = "EPSG:4326").crs
