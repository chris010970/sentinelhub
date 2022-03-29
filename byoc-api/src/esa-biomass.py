import os
import re
import glob
import boto3
import argparse

from osgeo import gdal
from datetime import datetime, timedelta
from s3util import S3Util

# sentinelhub imports
from sentinelhub import (
    SHConfig, 
    SentinelHubBYOC, ByocCollection, ByocTile, ByocCollectionAdditionalData,
)

# Dataset Summary: https://catalogue.ceda.ac.uk/uuid/5f331c418e9f4935b8eb1b836f8a91b8
class EsaBiomass():

    # constants
    _bands = {  'agb' : 'ESACCI-BIOMASS-L4-AGB-MERGED',
                'agb_sd' : 'ESACCI-BIOMASS-L4-AGB_SD-MERGED' }

    """
    @staticmethod
    def getStackedImage( scene ):

        return gdal.BuildVRT(  '/vsimem/stack.vrt', 
                             [ scene, scene.replace( EsaBiomass._fid, 'ESACCI-BIOMASS-L4-AGB_SD-MERGED' ) ],
                             options=gdal.BuildVRTOptions( separate=True ) )
    """                


    @staticmethod
    def createCog( scene, band, out_path ):

        """
        convert stacked esa biomass dataset to cog format
        """

        # split on hyphen
        tokens = re.split('_|-', os.path.basename( scene ) )
        tile = tokens[ 0 ]
        
        # get timeframe for dataset
        dt = datetime(year=int( tokens[ -2 ] ), day=1, month=1 )

        # create output path
        out_path = os.path.join( out_path, dt.strftime( '%Y' ) )
        out_path = os.path.join( out_path, tile )
        
        if not os.path.exists( out_path ):
            os.makedirs( out_path )

        # check pathname exists
        pathname = os.path.join( out_path, f'{band}.tif' )
        if not os.path.exists( pathname ):

            # open newly created tile with gdal
            ds = gdal.Open( scene )
            if ds is not None:
                
                # additional info from: https://docs.sentinel-hub.com/api/latest/api/byoc/#constraints-and-settings
                # remember to define NO_DATA_VALUE if input data has nodata values: -a_nodata NO_DATA_VALUE
                # add a predictor to further reduce the file size: add -co PREDICTOR=YES.
                
                # setup options
                options = '-of COG -co COMPRESS=DEFLATE -co BLOCKSIZE=1024 -co RESAMPLING=AVERAGE -co OVERVIEWS=IGNORE_EXISTING '
                options += '-co PREDICTOR=YES'
                                    
                # translate png / jpg into geotiff
                ds = gdal.Translate( pathname, ds, options=options )
                ds = None

        return


    @staticmethod
    def getCollection( byoc, args ):

        """
        get target byoc collection
        """

        # locate target in byoc collections if exists
        target = None
        for collection in list( byoc.iter_collections() ):
            if collection['name'] == args.collection_name:
                target = collection
                break

        # create target if not exists
        if target is None:
            new_collection = ByocCollection(name=args.collection_name, s3_bucket=args.bucket_name)
            target = byoc.create_collection( new_collection )

        return target


    @staticmethod
    def createCollection( args ):

        """
        create byoc collection from sedac pm2.5 images
        """

        # create bucket object
        s3 = boto3.resource('s3')
        bucket = s3.Bucket( args.bucket_name )
        out_path = os.path.join( args.out_path, args.collection_name )

        for item in EsaBiomass._bands.items():

            # generate cog images from inputs
            scenes = glob.glob( os.path.join( args.data_path, '**/*{fid}*.tif'.format( fid=item[ 1 ] ) ), recursive=True )
            for scene in scenes:
                EsaBiomass.createCog( scene, item[ 0 ], out_path )

        # upload cogs to s3 bucket
        cogs = glob.glob( os.path.join( out_path, '**/*.tif' ), recursive=True )
        for cog in cogs:
            S3Util.uploadFile( bucket, cog, args.out_path )

        # get listing of uploaded s3 cogs
        s3_paths = []
        for p in S3Util.getListing( bucket, args.collection_name ):
            s3_paths.append( os.path.dirname( str( p.key ) ) )

        # initialize SentinelHubBYOC class
        byoc = SentinelHubBYOC(config=SHConfig() )
        collection = EsaBiomass.getCollection( byoc, args )

        # create list of byoc tiles 
        tiles = []
        for s3_path in set( s3_paths ):
    
            tokens = s3_path.split( '/' )
            tiles.append( ByocTile(
                    path=f'{s3_path}/(BAND).tif',
                    sensing_time=datetime( year=int(tokens[ -2 ] ), month=1, day=1 ) ) )

        # add tiles to collection
        for tile in tiles:
            byoc.create_tile( collection, tile )


        return


    @staticmethod
    def parseArguments(args=None):

        """
        parse arguments
        """

        # parse command line arguments
        parser = argparse.ArgumentParser(description='sedac-pm25')

        # mandatory args
        parser.add_argument('data_path', action='store', help='read location of esa cci biomass geotiffs' )
        parser.add_argument('out_path', action='store', help='write location of esa cci biomass cogs' )
        parser.add_argument('--bucket_name', action='store', help='s3 bucket name', default='4rd-climate-finance' )
        parser.add_argument('--collection_name', action='store', help='s3 bucket name', default='esa-cci/biomass' )

        return parser.parse_args(args)


def main():

    """
    main path of execution
    """

    # parse arguments and execute 
    args = EsaBiomass.parseArguments()
    EsaBiomass.createCollection( args )

    return


# execute main
if __name__ == '__main__':
    main()
