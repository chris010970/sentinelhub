import os
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

class GripRoads():

    _fid = 'grip4_total_dens_m_km2.asc'

    @staticmethod
    def createCog( scene, out_path ):

        """
        convert sedac dataset to cloud optimised geotiff format
        """

        # create output path - single dataset
        out_path = os.path.join( out_path, '2018' )
        if not os.path.exists( out_path ):
            os.makedirs( out_path )

        # check pathname exists
        pathname = os.path.join( out_path, 'density.tif' )
        if not os.path.exists( pathname ):

            # open newly created tile with gdal
            ds = gdal.Open( scene )
            if ds is not None:
                
                # additional info from: https://docs.sentinel-hub.com/api/latest/api/byoc/#constraints-and-settings
                # remember to define NO_DATA_VALUE if input data has nodata values: -a_nodata NO_DATA_VALUE
                # add a predictor to further reduce the file size: add -co PREDICTOR=YES.
                
                # setup options
                # options = '-a_nodata 0 '
                options = '-of COG -ot FLOAT32 -a_srs EPSG:4326 -co COMPRESS=DEFLATE -co BLOCKSIZE=1024 -co RESAMPLING=AVERAGE -co OVERVIEWS=IGNORE_EXISTING '
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

        """
        # generate cog images from inputs
        scenes = glob.glob( os.path.join( args.data_path, '{fid}'.format( fid=GripRoads._fid ) ) )
        for scene in scenes:
            GripRoads.createCog( scene, out_path )

        # upload cogs to s3 bucket
        cogs = glob.glob( os.path.join( out_path, '**/*.tif' ) )
        for cog in cogs:
            S3Util.uploadFile( bucket, cog, args.out_path )
        """

        # get listing of uploaded s3 cogs
        s3_paths = []
        for p in S3Util.getListing( bucket, args.collection_name ):
            s3_paths.append( os.path.dirname( str( p.key ) ) )

        # initialize SentinelHubBYOC class
        byoc = SentinelHubBYOC(config=SHConfig() )
        collection = GripRoads.getCollection( byoc, args )

        # create list of byoc tiles 
        tiles = []
        for s3_path in set( s3_paths ):
    
            tokens = s3_path.split( '/' )
            tiles.append( ByocTile(
                    path=f'{s3_path}/(BAND).tif',
                    sensing_time=datetime( year=int(tokens[ -1 ] ), month=1, day=1 ) ) )

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
        parser.add_argument('data_path', action='store', help='read location of globio geotiffs' )
        parser.add_argument('out_path', action='store', help='write location of globio cogs' )
        parser.add_argument('--bucket_name', action='store', help='s3 bucket name', default='4ei-risk-report' )
        parser.add_argument('--collection_name', action='store', help='s3 bucket name', default='globio/grip' )

        return parser.parse_args(args)


def main():

    """
    main path of execution
    """

    # parse arguments and execute 
    args = GripRoads.parseArguments()
    GripRoads.createCollection( args )

    return


# execute main
if __name__ == '__main__':
    main()
