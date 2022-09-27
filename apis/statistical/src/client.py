import json

from munch import unmunchify 
from datetime import timedelta

from sentinelhub import BBox
from sentinelhub import SHConfig
from sentinelhub import CRS
from sentinelhub import DataCollection
from sentinelhub import SentinelHubStatistical
from sentinelhub import SentinelHubStatisticalDownloadClient
from sentinelhub import SentinelHubCatalog
from sentinelhub import Geometry
from sentinelhub import filter_times
from sentinelhub import geo_utils

# app class
#from response import Response
from .response import Response

class Client:

    def __init__( self, config, base_url=None ):

        """
        constructor
        """

        # get configuration 
        self.setConfiguration( config ) 
        base_url = config.get( 'base_url', base_url )

        # create sh config
        self._config = SHConfig()
        if base_url is not None:
            self._config.sh_base_url = base_url

        self._delta = timedelta(hours=1)

        return


    def setConfiguration( self, config ):

        """
        set configuration
        """

        # set configuration 
        self._request = config.request
        self._inputs = self._request.inputs 
        self._responses = config.responses

        return


    def getDataCollections( self ):

        """ 
        get list of data collections
        """

        # available collections
        return DataCollection.get_available_collections()


    def getDataCollection( self, _input ):

        """ 
        return standard or byoc collection
        """

        if 'byoc-' in _input.collection:
            return DataCollection.define_byoc( _input.collection.replace( 'byoc-', '' ) )
        else:
            return DataCollection[ _input.collection ]


    def getCatalog( self ):

        """
        get catalog pertaining to data collection
        """

        # get catalog for collection
        return SentinelHubCatalog(
            config=self._config
        )


    def getDatasetTimeStamps( self, _input, bbox, timeframe ):

        """
        get timestamps of scenes collocated with bbox acquired between timeframe
        """

        # one hour interval
        timestamps = []

        # get catalog
        catalog = self.getCatalog()
        if catalog is not None:
        
            # execute search
            iterator = catalog.search (
                        self.getDataCollection( _input ),
                        bbox=bbox,
                        time=self.getTimeInterval( timeframe ),
                        query=self.getQuery( _input.get( 'catalog' ) ),
                        fields=self.getFields( _input.get( 'catalog' ) )
            )

            # filter timestamps into +- 1 hour groupings
            timestamps = iterator.get_timestamps()
            timestamps = filter_times( timestamps, self._delta )

        return timestamps


    def getStatistics( self, timeframes, **kwargs ):
    
        """
        get statistics
        """

        # parse optional args
        bbox = kwargs.get( 'bbox' )
        polygons = kwargs.get( 'polygons' )
        verbose = kwargs.get( 'verbose', False )

        # build requests from args
        requests = []; ids = None
        for timeframe in timeframes:

            # polygon aois encoded as geodataframe
            if polygons is not None:
                for feature in polygons.geometry.values:

                    kwargs[ 'geometry' ] = Geometry( feature, crs=CRS( polygons.crs ) )
                    requests.append( self.getRequest( timeframe, **kwargs ) )

                # get polygon ids
                if 'id' in polygons.columns:
                    ids = polygons.id.values

            # bounding box based request
            if bbox is not None:
                requests.append( self.getRequest( timeframe, **kwargs ) )

        # create client downloader
        client = SentinelHubStatisticalDownloadClient(config=self._config )
        downloads = [ request.download_list[0] for request in requests ]

        # download data - parse into dict if required
        data = client.download( downloads )
        if not isinstance( data [ 0 ], dict ):
            data = { 'default' : data }

        # parse responses into dataframe        
        return None if data is None else Response ( data, ids=ids, verbose=verbose )


    def getRequest( self, timeframe, **kwargs ):

        """
        construct request for feature and timeframe
        """

        # parse optional args
        bbox = kwargs.get( 'bbox' )
        geometry = kwargs.get( 'geometry' )
        interval = kwargs.get( 'interval', 'P1D' )
        resolution = kwargs.get( 'resolution', 100 )

        # create aggregation object
        aggregation = SentinelHubStatistical.aggregation(
            evalscript=self._request.evalscript,
            time_interval=self.getTimeInterval( timeframe ),
            aggregation_interval=interval, 
            resolution=(resolution,resolution)
        )

        # initialise input data
        input_data = [];         
        for _input in self._inputs:

            # append data to list
            collection = _input.collection
            input_data.append( self.getInputData(   _input, 
                                                    timeframe[ collection ] if collection in timeframe else timeframe ) )

        # create and return statistical api request
        return SentinelHubStatistical (
            aggregation=aggregation,
            input_data=input_data,
            bbox=bbox,
            geometry=geometry, 
            calculations=unmunchify( self._responses ),
            config=self._config,
        )


    def getInputData( self, _input, timeframe ):

        """
        get fields to populate input data structure
        """

        # evaluate mosaicking order
        options = _input.get( 'mosaic' )
        mosaic_order = options.get( 'order' ) if options is not None else None

        # evaluate optional args
        other_args = {}

        options = _input.get( 'options' )
        if options is not None:

            # filter and processing optional args
            for arg in [ 'dataFilter', 'processing' ]:

                if options.get( arg ) is not None:
                    other_args[ arg ] = dict ( options.get( arg ) )

        return SentinelHubStatistical.input_data(   data_collection=self.getDataCollection( _input ),
                                                identifier=_input.get( 'id' ),
                                                maxcc=_input.get( 'maxcc' ),
                                                upsampling=_input.get( 'upsampling' ),
                                                downsampling=_input.get( 'downsampling' ),
                                                time_interval=self.getTimeInterval( timeframe ),
                                                mosaicking_order=mosaic_order if mosaic_order is not None else 'mostRecent',
                                                other_args=other_args if bool ( other_args ) else None )


    def getTimeInterval( self, timeframe ):

        """
        return time interval tuple
        """

        # get time interval tuple        
        tz_format = '%Y-%m-%dT%H:%M:%S%z'
        return timeframe[ 'start' ].strftime( tz_format ), timeframe[ 'end' ].strftime( tz_format )


    def getBoundingBox( self, bounds, src_crs=CRS.WGS84, dst_crs=None ):

        """
        return bounding box object
        """

        # construct bbox - apply optional transform (default to mercator)
        bbox = BBox( bbox=bounds, crs=src_crs )
        return geo_utils.to_utm_bbox( bbox ) if dst_crs is None else bbox.transform( CRS( dst_crs ) )


    def getQuery( self, config ):

        """
        get json encoded query
        """

        # default to none
        query = None
        if config is not None:
            # convert json obj to dict
            if config.get( 'query' ) is not None:
                query = json.loads( config.get( 'query' ) )
            
        return query 


    def getFields( self, config ):

        """
        get json encoded query
        """

        # default to none
        fields = None
        if config is not None:

            # convert json obj to dict
            if config.get( 'fields' ) is not None:

                # add geoemtry field
                fields = json.loads( config.get( 'fields' ) )
                fields[ 'include' ].append( 'geometry' )
            

        return fields


"""
import os 
import yaml
from munch import munchify
import geopandas as gpd
import time

from shapely.geometry import box

import pyproj
from shapely.ops import transform

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


coords = 36.65, -0.85, 36.72, -0.82
bbox = box( *coords )

# transform bounding box to mercator
project = pyproj.Transformer.from_crs( 'epsg:4326', 'epsg:3857', always_xy=True ) 
bbox = transform(project.transform, bbox)
xmin, ymin, xmax, ymax = bbox.bounds


cell_size = 200

# generate grid of nominated cell size in metres
samples = []; idx = 0
for x in np.arange( xmin, xmax+cell_size, cell_size ):
    for y in np.arange( ymin, ymax+cell_size, cell_size):
        samples.append( { 'id' : idx, 'geometry' : Point( x + (cell_size / 2) , y + ( cell_size / 2 ) ) } )
        idx += 1


samples = gpd.GeoDataFrame( samples, crs='epsg:3857' )
samples.geometry = samples.geometry.buffer( 30 )

# define repo name and get root working directory
repo = 'statistical'
root_path = os.getcwd()[ 0 : os.getcwd().find( repo ) + len ( repo )]

# get path to configuration files
cfg_path = os.path.join( root_path, 'cfg' )
cfg_path = os.path.join( cfg_path, 'sentinel-2' )

# get pathname to configuration file
cfg_file = os.path.join( cfg_path, 's2-agdb-metrics.yml' )

# load cfg file using yaml parser
with open( cfg_file, 'r' ) as f:
    config = munchify( yaml.safe_load( f ) )


# define aggregation timeframe
from datetime import datetime
timeframe = { 'start' : datetime.strptime('2022-05-01', '%Y-%m-%d'), 
              'end' : datetime.strptime('2022-06-30', '%Y-%m-%d') }


client = Client( config )

s2_metrics = pd.DataFrame()

chunk_size = 100
for offset in range ( 0, len( samples ), chunk_size ):

    # process records in chunks - transform to local utm
    subset = samples[ offset : offset + chunk_size ].copy()
    subset = subset.to_crs( subset.estimate_utm_crs() )

    response = client.getStatistics( [ timeframe ], resolution=10, polygons=subset, interval='P1D' )   
    if response is not None:

        filtered = list()
        for df in response._dfs:
            filtered.append( df [ ( df[ 'stats_clm_mean' ] < 0.1 ) & ( df[ 'stats_clm_noDataCount'] < 10 ) ] )

        filtered = pd.concat( [ x for x in filtered if not x.empty ], ignore_index=True )
        if not filtered.empty:
            s2_metrics = pd.concat( [ filtered, s2_metrics ] )


s2_metrics.to_pickle( 's2_metrics.pkl' )

import os 
import yaml
from munch import munchify
import geopandas as gpd

# define repo name and get root working directory
repo = 'statistical'
root_path = os.getcwd()[ 0 : os.getcwd().find( repo ) + len ( repo )]

# get path to configuration files
cfg_path = os.path.join( root_path, 'cfg' )
cfg_path = os.path.join( cfg_path, 'sentinel-2' )

# get pathname to configuration file
cfg_file = os.path.join( cfg_path, 's2-lai.yml' )
cfg_file = 'C:\\Users\\crwil\\Documents\\GitHub\\uhi\\cfg\\landsat\\etm\\statistical-lst.yml'

# load cfg file using yaml parser
with open( cfg_file, 'r' ) as f:
    config = munchify( yaml.safe_load( f ) )

#gdf = gpd.read_file( os.path.join( root_path, 'test/wells.geojson' ) )
#gdf = gdf.to_crs( gdf.estimate_utm_crs()  )

gdf = gpd.read_file( os.path.join( root_path, 'test/polygons.shp' ) )

# define aggregation timeframe
from datetime import datetime
timeframe = { 'start' : datetime.strptime('2016-10-01', '%Y-%m-%d'), 'end' : datetime.strptime('2016-10-30', '%Y-%m-%d') }

# get mosaic between timeframe at specified pixel resolution
client = Client( config )

# define min and max latlons
#coords = 414315, 4958219, 414859, 4958819
#crs = CRS( 32633 )
#bbox = client.getBoundingBox( coords, crs )

response = client.getStatistics( [ timeframe ], resolution=10, polygons=gdf[ : 10 ] )
#response = client.getStatistics( [ timeframe ], resolution=10, bbox=bbox )
response._dfs

"""

