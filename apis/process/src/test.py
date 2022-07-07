import os
import yaml
import geopandas as gpd

from client import Client
from munch import munchify
from datetime import datetime

from sentinelhub import CRS


class SentinelTest:

    class TimeSeries:

        @staticmethod
        def getBoundingBox( pathname, coords, resolution, timeframe ):

            """
            get imagery via bounding box request
            """

            # load cfg file using yaml parser
            with open( pathname, 'r' ) as f:
                config = munchify( yaml.safe_load( f ) )

            # create instance of shclient class
            client = Client( config )
            bbox = client.getBoundingBox( coords )

            # get time series
            response = client.getTimeSeries ( timeframe, resolution, bbox=bbox )
            response.plotImages( 'rgb.tif', alpha={ 'data' : 1.0, 'grid' : 0.0 } )

            return


        @staticmethod
        def getGeometry( pathname, gdf, resolution, timeframe ):

            """
            get imagery via geometry-based request
            """

            # load cfg file using yaml parser
            with open( pathname, 'r' ) as f:
                config = munchify( yaml.safe_load( f ) )

            # create instance of shclient class
            client = Client( config )
            geometry = Client.getGeometry( gdf.geometry.values[ 0 ], dst_crs=CRS(gdf.estimate_utm_crs()) )

            # get time series
            response = client.getTimeSeries ( timeframe, resolution, geometry=geometry )
            response.plotImages( 'rgb.tif', alpha={ 'data' : 1.0, 'grid' : 0.0 } )

            return


    class Mosaic:

        @staticmethod
        def getBoundingBox( pathname, coords, resolution, timeframe ):

            """
            get imagery via bounding box request
            """

            # load cfg file using yaml parser
            with open( pathname, 'r' ) as f:
                config = munchify( yaml.safe_load( f ) )

            # create instance of shclient class
            client = Client( config )
            bbox = client.getBoundingBox( coords )

            # get time series
            response = client.getMosaics ( timeframe, resolution, bbox=bbox )
            response.plotImages( 'default', alpha={ 'data' : 1.0, 'grid' : 0.0 } )

            return


    @staticmethod
    def runS2Tests():

        """
        execute sentinel-2 based requests
        """

        # define repo name and get root working directory
        repo = 'process'
        root_path = os.getcwd()[ 0 : os.getcwd().find( repo ) + len ( repo )]

        # get path to configuration files
        cfg_path = os.path.join( root_path, 'cfg' )
        cfg_path = os.path.join( cfg_path, 'sentinel-2' )

        # chicago example    
        SentinelTest.TimeSeries.getBoundingBox(    os.path.join( cfg_path, 's2-timeseries-rgb.yml' ),
                                                [-83.039886,42.262866,-82.777136,42.473535],
                                                20,
                                                { 'start' : datetime( 2020, 5, 2, 0, 0, 0 ), 
                                                'end' : datetime( 2020, 5, 15, 23, 59, 59 ) }
        )
        input( 'Press Enter to continue...' )

        # wells geometry example
        SentinelTest.TimeSeries.getGeometry(    os.path.join( cfg_path, 's2-timeseries-rgb.yml' ),
                                                gpd.read_file( os.path.join( root_path, 'test/wells.geojson' ) ),
                                                20,
                                                { 'start' : datetime( 2020, 5, 2, 0, 0, 0 ), 
                                                'end' : datetime( 2020, 5, 7, 23, 59, 59 ) }
        )
        input( 'Press Enter to continue...' )

        # Betsiboka estuary example
        SentinelTest.Mosaic.getBoundingBox(     os.path.join( cfg_path, 's2-mosaic-rgb.yml' ),
                                                [ 46.16, -16.15, 46.51, -15.58 ],
                                                60,
                                                { 'start' : datetime.strptime('2020-06-12', '%Y-%m-%d'), 
                                                'end' : datetime.strptime('2020-06-13', '%Y-%m-%d') }
        )
        input( 'Press Enter to continue...' )
        return


    @staticmethod
    def runS3Tests():

        """
        execute sentinel-3 based requests
        """

        # define repo name and get root working directory
        repo = 'process'
        root_path = os.getcwd()[ 0 : os.getcwd().find( repo ) + len ( repo )]

        # get path to configuration files
        cfg_path = os.path.join( root_path, 'cfg' )
        cfg_path = os.path.join( cfg_path, 'sentinel-3' )

        # chicago example    
        SentinelTest.TimeSeries.getBoundingBox(    os.path.join( cfg_path, 's3-timeseries-slstr-bt8.yml' ),
                                                [-83.039886,42.262866,-82.777136,42.473535],
                                                20,
                                                { 'start' : datetime( 2020, 5, 2, 0, 0, 0 ), 
                                                'end' : datetime( 2020, 5, 15, 23, 59, 59 ) }
        )
        input( 'Press Enter to continue...' )

        return

SentinelTest.runS2Tests()
