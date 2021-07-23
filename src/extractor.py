import os
import ogr
import json
import pandas as pd
import geopandas as gpd

from shapely.geometry import shape

from aoi import Aoi
from client import ShClient

class Extractor:

    def __init__( self, config ):

        """
        constructor
        """
        self._client = ShClient( config )
        return

    
    def process( self, config, args ):

        """
        process main control
        """

        # get aois from vector file
        aois = self.getAoIs( config.aoi )
        if aois is not None:

            # for each aoi
            timeframe = { 'start' : args.start_datetime, 'end' : args.end_datetime }
            for aoi in aois.itertuples():

                # get catalogue records
                # df = self._client.getRecords( aoi.geometry.bounds, timeframe )
                # print ( df )

                # create bounding box in mercator projection
                bbox = self._client.getBoundingBox( aoi.geometry.bounds )

                # mosaic mode ?
                if args.mosaic:

                    # create mosaic aggregating imagery collocated with aoi
                    response = self._client.getMosaics(  bbox, 
                                                    timeframe,
                                                    args.resolution, 
                                                    out_path=os.path.join( args.out_path, aoi.name ) )

                else:

                    # create individual time series collocated with aoi
                    response = self._client.getTimeSeries(  bbox, 
                                                        timeframe,
                                                        args.resolution, 
                                                        out_path=os.path.join( args.out_path, aoi.name ) )

                print ( response )

        return


    def getAoIs( self, config ):

        """
        load aois from file into geodataframe
        """

        # error handling
        aois = []
        try:

            # open geometries pathname
            ds = ogr.Open( config.pathname )
            if ds is not None:

                # convert ogr feature to shapely object
                layer = ds.GetLayer( 0 )
                for idx, feature in enumerate( layer ):
                    
                    # create aoi object
                    config.name = f'aoi-{idx}'
                    aois.append( Aoi.fromOgrFeature( feature, config ) )
            else:
                # file not found
                raise Exception ( 'pathname not found' )

        # error processing aoi feature
        except Exception as e:
            print ( 'AoI Exception {}: -> {}'.format( str( e ), config.pathname ) )
            aois.clear()

        return gpd.GeoDataFrame( aois, crs='EPSG:4326', geometry='geometry' ) if len( aois ) > 0 else None
