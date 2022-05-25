import os
import json

from s3util import S3Util
from sentinelhub import SHConfig
from sentinelhub import DataCollection
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import BackendApplicationClient


class Client():

    def __init__ ( self, config, base_url='https://services.sentinel-hub.com/api/v1/statistics/batch' ):

        # get configuration 
        self.setConfiguration( config ) 

        self._base_url = base_url
        self._headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
            }

        # create user-specific session
        self._config = SHConfig()

        self._obj = BackendApplicationClient( client_id=self._config.sh_client_id )
        self._session = OAuth2Session( client=self._obj )

        # all sessiom requests have access token automatically added
        _ = self._session.fetch_token( token_url='https://services.sentinel-hub.com/oauth/token',
                                        client_secret= self._config.sh_client_secret )

        return


    def setConfiguration( self, config ):

        # get config sub-parameter groups
        self._request = config.request
        self._inputs = self._request.inputs 
        #self._calculations = self._request.calculations 

        return


    def getDataCollection( self, _input ):

        """ 
        return standard or byoc collection
        """

        if 'byoc-' in _input.collection:
            return DataCollection.define_byoc( _input.collection.replace( 'byoc-', '' ) )
        else:
            return DataCollection[ _input.collection ]


    def getSession( self ):

        return self._session


    def getStatus( self, request_id ):

        # get status of api request
        base_url = self._base_url
        response = self._session.request( 'GET', f'{base_url}/{request_id}/status' )        
        return response.json()


    def getInformation( self, request_id ):

        # get api request information 
        base_url = self._base_url
        response = self._session.request( 'GET', f'{base_url}/{request_id}' )
        return response.json()


    def setAnalysis( self, request_id ):

        # get api request information 
        base_url = self._base_url
        response = self._session.request( 'POST', f'{base_url}/{request_id}/analyse' )
        return response.status_code


    def startRequest( self, request_id ):

        # get api request information 
        base_url = self._base_url
        response = self._session.request( 'POST', f'{base_url}/{request_id}/start' )
        return response.status_code


    def cancelRequest( self, request_id ):

        # get api request information 
        base_url = self._base_url
        response = self._session.request( 'POST', f'{base_url}/{request_id}/cancel' )
        return response.status_code


    def postRequest( self, pathname, aws, args ):

        def set_default(obj):
            if isinstance(obj, set):
                return list(obj)
            raise TypeError


        uri = Client.uploadGeoDatabase( pathname, aws )
        payload = { 'input' : self.getInputs( uri ),
                    'aggregation' : self.getAggregation( args ),
                    'output' : self.getOutput( aws ) 
        }
        
        print( json.dumps( payload, default=set_default) )

        # post request
        response = self._session.request(   'POST', 
                                            url=self._base_url, 
                                            headers=self._headers, 
                                            json=payload )

        return response.status_code, response.json()


    @staticmethod
    def uploadGeoDatabase( pathname, aws ):

        # create bucket object
        bucket = S3Util.getS3Bucket( aws.bucket )    
        return S3Util.uploadFile( bucket, pathname, os.path.join( aws.prefix, 'aois' ) )


    def getInputs( self, uri ):

        # get access info for aws-located geodatabase comprising feature aois
        features = { 's3': {    'url': uri,
                                'accessKey': self._config.aws_access_key_id,
                                'secretAccessKey': self._config.aws_secret_access_key }
        }

        # parse input configuration into format compliant with batch api
        data = []
        for _input in self._inputs:

            # evaluate mosaicking order
            options = _input.get( 'mosaic' )
            mosaic_order = options.get( 'order' ) if options is not None else None

            # create input configuration dict
            obj = { 'type' : self.getDataCollection( _input ).api_id,
                    'dataFilter' : { 'mosaickingOrder' : mosaic_order if mosaic_order is not None else 'mostRecent' }
            }

            # evaluate optional args
            options = _input.get( 'options' )
            if options is not None:

                # filter and processing optional args
                for arg in [ 'dataFilter', 'processing' ]:

                    # merge configuration dicts
                    if options.get( arg ) is not None:
                        obj[ arg ] = dict ( options.get( arg ) ) if arg not in obj else obj[ arg ] | dict ( options.get( arg ) )

            # optional parameters
            if _input.get( 'id' ):
                obj[ 'id' ] = _input.get( 'id' )
            
            data.append ( obj )


        return { 'features' : features, 'data' : data }

    
    def getAggregation( self, args ):

        tz_format = '%Y-%m-%dT%H:%M:%SZ'
        timeRange =  {  "from": args.timeframe[ 'start' ].strftime( tz_format ),
                        "to": args.timeframe[ 'end' ].strftime( tz_format )
        }

        return {    'timeRange' : timeRange,
                    'aggregationInterval' : { 'of' : args.interval },
                    'evalscript' : self._request.evalscript,
                    'resx' : args.resolution,
                    'resy' : args.resolution
        }


    def getOutput( self, aws ):

        s3_path = os.path.join( aws.bucket, os.path.join( aws.prefix, 'stats' ) )
        s3_path = s3_path.replace(os.sep, '/' )

        return { 's3': {    'url': f"s3://{s3_path}",
                            'accessKey': self._config.aws_access_key_id,
                            'secretAccessKey': self._config.aws_secret_access_key }
        }

