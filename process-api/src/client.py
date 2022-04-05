import os
import json
import numpy as np
import pandas as pd
import geopandas as gpd

from shapely.geometry import shape
from datetime import datetime, timedelta

from sentinelhub import SHConfig
from sentinelhub import CRS
from sentinelhub import BBox
from sentinelhub import MimeType
from sentinelhub import SentinelHubRequest
from sentinelhub import SentinelHubDownloadClient
from sentinelhub import DataCollection
from sentinelhub import ByocCollection
from sentinelhub import bbox_to_dimensions
from sentinelhub import DownloadRequest
from sentinelhub import SentinelHubCatalog
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


    def getTimeSeries ( self, bbox, timeframe, resolution, out_path=None, timestamps=None, max_downloads=100 ):

        """
        get time series imagery satisfying filtering conditions
        """

        requests = []

        # use timeframe to generate timestamp list by default
        if timestamps is None:
            timestamps = self.getDatasetTimeStamps( self._inputs[ 0 ], bbox, timeframe )

        # for each scene timestamp    
        timestamps = timestamps[ : max_downloads ]
        for timestamp in timestamps:

            # check data path does not already exist
            collection =  self.getDataCollection( self._inputs[ 0 ] ) if len( self._inputs ) == 1 else 'FUSION'

            data_path = self.getDataPath( out_path, collection, timestamp )
            if data_path is None or not os.path.exists( data_path ):

                # initialise timeframes
                timeframe = {}
                for _input in self._inputs:

                    # compute temporal window around timestamp
                    timeframe[ _input.collection ] = self.getTimeFrame( _input, bbox, timestamp )
                                        
                # construct new request covering 1 hour time slice
                requests.append (   self.getRequest( bbox, 
                                    timeframe, 
                                    resolution, 
                                    data_path=data_path ) )

            else:
               
                # path already exists
                if data_path is not None:
                    print ( f'... path already exists: {data_path}' )


        # check minimum of one valid request
        data = None
        if len( requests ) > 0:

            # setup download requests
            client = SentinelHubDownloadClient( config=self._config )
            downloads = [ request.download_list[0] for request in requests ]

            # download data - parse into dict if required
            data = client.download( downloads )
            if not isinstance( data [ 0 ], dict ):
                data = { 'default' : data }

        # parse responses into dataframe        
        return None if data is None else Response ( pd.DataFrame.from_dict( data ).assign( time=timestamps ), bbox, resolution )


    def getMosaics ( self, bbox, timeframes, resolution, out_path=None ):

        """
        get aggregated mosaics satisfying filtering conditions
        """

        # handle list conversion
        timeframes = timeframes if type( timeframes ) is list else [ timeframes ]

        requests = []
        for timeframe in timeframes:

            # check data path does not already exist
            data_path = self.getMosaicDataPath( out_path, timeframe )
            if data_path is None or not os.path.exists( data_path ):

                # create and forward request
                requests.append( self.getRequest(   bbox, 
                                                    timeframe, 
                                                    resolution, 
                                                    data_path=data_path ) )
            else:
                
                # path already exists
                if data_path is not None:
                    print ( f'... path already exists: {data_path}' )


        # check minimum of one valid request
        data = None
        if len( requests ) > 0:

            # download datasets
            client = SentinelHubDownloadClient( config=self._config )
            downloads = [ request.download_list[0] for request in requests ]

            # download data - parse into dict if required
            data = client.download( downloads )
            if not isinstance( data [ 0 ], dict ):
                data = { 'default' : data }

        return None if data is None else Response ( pd.concat( [ pd.DataFrame.from_dict( data ), pd.DataFrame.from_dict( timeframes ) ], axis=1 ), bbox, resolution )
        

    def getRequest( self, bbox, timeframe, resolution, data_path=None ):

        """
        get request
        """

        # compile list of responses
        responses = []
        for key, value in self._responses.items():

            # check various forms of TIF(F)
            if 'TIF' in value.upper():
                responses.append( SentinelHubRequest.output_response( key, MimeType.TIFF ) )

            # png, jpeg to follow

        # initialise input data
        input_data = [];         
        for _input in self._inputs:

            # append data to list
            collection = _input.collection
            input_data.append( self.getInputData(   _input, 
                                                    timeframe[ collection ] if collection in timeframe else timeframe ) )

        # construct request
        return  SentinelHubRequest(
                    data_folder=data_path,
                    evalscript=self._request.evalscript,
                    input_data=input_data,
                    responses=responses,
                    bbox=bbox,
                    size=self.getBoxDimensions( bbox, resolution ),
                    config=self._config
        )


    def getTimeFrame( self, _input, bbox, timestamp ):

        """
        initialise start and end lag
        """

        # default to 1 hour
        value = _input.get( 'lag' )
        if value is not None:

            # single value or comma separated
            params=value.split(',')
            start_lag = end_lag = int( params[ 0 ] )

            if len( params ) > 1:
                end_lag = int( params[ 1 ] )

            # get timestamps of datasets within lag temporal window
            lag_timestamps = self.getDatasetTimeStamps(  _input, 
                                                            bbox, 
                                                        {   'start' : ( timestamp - ( self._delta * start_lag ) ), 
                                                            'end' : ( timestamp + ( self._delta * end_lag ) ) } )

            # locate closest available dataset in time
            min_diff = timedelta( weeks=1000 )
            for lag_timestamp in lag_timestamps:

                diff = timestamp - lag_timestamp
                if diff < min_diff:

                    # track timestamp of dataset closest in time
                    min_diff = diff
                    timestamp = lag_timestamp

        return  { 'start' : ( timestamp - ( self._delta ) ), 'end' : ( timestamp + ( self._delta ) ) }


    def getCatalog( self ):

        """
        get catalog pertaining to data collection
        """

        # get catalog for collection
        return SentinelHubCatalog(
            config=self._config
        )


    def getDataPath( self, root_path, collection, timestamp ):

        """
        return data path
        """

        # construct data path
        data_path = None
        if root_path is not None:

            # unique path based on collection name and timestamp
            data_path = os.path.join( root_path, collection.lower() )
            data_path = os.path.join( data_path, timestamp.strftime( '%Y%m%d_%H%M%S' ) )

        return data_path


    def getMosaicDataPath( self, root_path, timeframe ):

        """
        return data path
        """

        # construct data path
        data_path = None
        if root_path is not None:

            # unique path based on collection name and timestamp
            data_path = os.path.join( root_path, self._request.collection.lower() )
            data_path = os.path.join( data_path, timeframe[ 'start' ].strftime( '%Y%m%d' ) + '_' + timeframe[ 'end' ].strftime( '%Y%m%d' ) )

        return data_path


    def getBoundingBox( self, bounds, src_crs=CRS.WGS84, dst_crs=None ):

        """
        return bounding box object
        """

        # construct bbox - apply optional transform (default to mercator)
        bbox = BBox( bbox=bounds, crs=src_crs )
        return geo_utils.to_utm_bbox( bbox ) if dst_crs is None else bbox.transform( CRS( dst_crs ) )


    def getBoxDimensions( self, bbox, resolution ):

        """
        return image dimensions of bounding box geometry
        """

        # return image dimensions of bounding box
        return bbox_to_dimensions( bbox, resolution=resolution)


    def getTimeInterval( self, timeframe ):

        """
        return time interval tuple
        """

        # get time interval tuple        
        tz_format = '%Y-%m-%dT%H:%M:%S%z'
        return timeframe[ 'start' ].strftime( tz_format ), timeframe[ 'end' ].strftime( tz_format )


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

        return SentinelHubRequest.input_data(   data_collection=self.getDataCollection( _input ),
                                                identifier=_input.get( 'id' ),
                                                maxcc=_input.get( 'maxcc' ),
                                                upsampling=_input.get( 'upsampling' ),
                                                downsampling=_input.get( 'downsampling' ),
                                                time_interval=self.getTimeInterval( timeframe ),
                                                mosaicking_order=mosaic_order if mosaic_order is not None else 'mostRecent',
                                                other_args=other_args if bool ( other_args ) else None )
