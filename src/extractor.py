import os
import re
import json
import shutil
import pandas as pd
import geopandas as gpd

from glob import glob
from pathlib import Path
from shapely.geometry import shape

from aoi import Aoi
from osgeo import ogr
from client_update import ShClient
#from client import ShClient

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

                # create bounding box in mercator projection
                bbox = self._client.getBoundingBox( aoi.geometry.bounds )

                # get catalogue records
                # df = self._client.getRecords( bbox, timeframe )
                # print ( df )

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
                                                        out_path=os.path.join( args.out_path, aoi.name ),
                                                        max_downloads=args.max_downloads )


                # rename / move output files - if any
                self.moveOutputFiles( aoi, args.out_path )


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


    def moveOutputFiles( self, aoi, out_path ):

        """
        move images into datetime folder 
        """

        if out_path is not None:

            # look for request outputs
            pathnames = glob( os.path.join( out_path, '**/response.tiff' ), recursive=True )
            for pathname in pathnames:

                # locate datetime folder
                m = re.search( '[0-9]{8}_[0-9]{6}([0-9]{2})?', os.path.dirname( pathname ) )
                root_path = pathname[ : m.end() ]

                # move image into datetime folder with unique name
                shutil.move(    pathname, 
                                os.path.join( root_path, '{aoi}_{datetime}.tif'.format ( aoi=aoi.name, datetime=str( m.group(0) ) ) )
                )

                # move remaining files to datetime folder
                for f in Path( os.path.dirname( pathname ) ).glob('*.*'):
                    shutil.move( f, os.path.join( root_path, os.path.basename( f )  ) )

                try:
                    # remove request-id specific sub-path
                    os.rmdir ( os.path.dirname( pathname ) ) 
                except:
                    print ( 'Unable to remove folder {path}'.format( path=os.path.dirname( pathname ) ) )

        return
