import os
import re
import uuid
import json
import pyproj

from shapely import geometry
from shapely.ops import transform
from shapely.geometry import shape
from shapely.wkt import loads

class Aoi:

    @staticmethod
    def fromOgrFeature( feature, config ):

        """
        convert ogr feature into aoi object
        """

        def getBufferGeometry( geom ):

            """
            get geometry 
            """
            
            # switch on geometry type            
            if geom.geom_type == 'Point':

                # convert points to bbox 
                distance = config.get( 'distance', 1000 )
                buffer = Aoi.getBoundingBox( geom.bounds, distance )

            else:

                if config.get( 'bbox' ) is not None:
                
                    # convert points to bbox 
                    distance = config.get( 'distance', 1000 )
                    buffer = Aoi.getBoundingBox( ( geom.centroid.x, geom.centroid.y ), distance )

                else:

                    # transform shapely object to utm
                    proj = Aoi.getUtmTransformation( ( geom.bounds[ 0 ], geom.bounds[ 1 ] ) )
                    geom_utm = transform( proj[ 'geo2utm' ].transform, geom ) 

                    # apply buffer (in meters) and convert back to epsg4326
                    distance = config.get( 'distance', 1000 )
                    geom_utm = geom_utm.buffer( distance )

                    buffer = transform( proj[ 'utm2geo' ].transform, geom_utm )

            return buffer, distance


        # open geometry from ogr feature
        json_obj = json.loads( feature.ExportToJson() )
        _name = config.get( 'name', str( uuid.uuid1() )[:6] )

        # refine name if field property defined
        field = config.get( 'field' )
        if field in json_obj[ 'properties' ]:
            
            temp = json_obj[ 'properties' ][ field ]
            if temp is not None:

                # replace invalid chars / spaces with hyphens 
                temp = temp.encode('ascii', 'ignore' ).decode('utf-8').strip()
        
                temp = re.sub('[^\\w\\-_\\. ]', ' ', temp ).strip()
                temp = re.sub( '\s+', '-', temp )
                
                # strip and check name is valid
                if len( temp ) > 0:
                    _name = temp

        # locate geometry
        geom = json_obj.get( 'geometry' )
        if geom is None:
            geom = json_obj[ 'properties' ].get( 'geometry' )

        # convert wkt string into shapely object
        if geom is not None:
            geom = loads( geom ) if isinstance( geom, str ) else shape( geom )

        # get geometry and buffer distance
        buffer, distance = getBufferGeometry( geom )
        return { 'name' : _name, 'type' : geom.geom_type, 'distance' : distance, 'geometry' : buffer }


    @staticmethod
    def getBoundingBox( centroid, distance ):

        """
        construct epsg4326 bounding box around centroid location with distance in metres
        """

        # get utm zone for centroid
        proj = Aoi.getUtmTransformation( centroid )

        # centroid to utm
        x, y = proj[ 'geo2utm' ].transform( centroid[0], centroid[1] )

        x0 = x - distance; y0 = y - distance
        x1 = x + distance; y1 = y + distance

        # convert back to geo
        pt0 = proj[ 'utm2geo' ].transform( x0, y0 )
        pt1 = proj[ 'utm2geo' ].transform( x1, y1 )

        return geometry.Polygon( [  [ pt0[ 0 ], pt0[ 1 ] ], 
                                    [ pt1[ 0 ], pt0[ 1 ] ], 
                                    [ pt1[ 0 ], pt1[ 1 ] ],
                                    [ pt0[ 0 ], pt1[ 1 ] ],
                                    [ pt0[ 0 ], pt0[ 1 ] ] ] )


    @staticmethod
    def getUtmTransformation( latlon ):

        """
        get epsg4326 <-> utm transformation objects
        """

        # get utm zone and letter
        z = Aoi.getZone( latlon )
        l = Aoi.getLetter( latlon )

        # create projections
        proj = { 'geo' : pyproj.Proj( init='epsg:4326', ellps='WGS84') }

        if latlon[ 1 ] > 0:
            proj[ 'utm' ] =  pyproj.Proj(proj='utm', zone=z, ellps='WGS84')
        else:
            proj[ 'utm' ] =  pyproj.Proj(proj='utm', zone=z, ellps='WGS84', south=True)

        # create transformations
        proj[ 'utm2geo' ] = pyproj.Transformer.from_proj( proj[ 'utm' ], proj[ 'geo' ] )
        proj[ 'geo2utm' ] = pyproj.Transformer.from_proj( proj[ 'geo' ], proj[ 'utm' ] )

        return proj


    @staticmethod
    def getEpsg( latlon  ):

        """
        get epsg code for centroid coordinates
        """

        # get utm zone for centroid
        z = Aoi.getZone( latlon )
        l = Aoi.getLetter( latlon )

        # create pyproj object
        proj = None
        if latlon[ 1 ] > 0:
            proj = pyproj.Proj(proj='utm', zone=z, ellps='WGS84')
        else:
            proj = pyproj.Proj(proj='utm', zone=z, ellps='WGS84', south=True)

        # return epsg code
        return proj.crs.to_epsg()


    @staticmethod
    def getZone( lonlat ):

        """
        get utm zone code from latlon
        """

        # decision tree for evaluate utm zone from longitude
        if 56 <= lonlat[1] < 64 and 3 <= lonlat[0] < 12:
            return 32
        if 72 <= lonlat[1] < 84 and 0 <= lonlat[0] < 42:
            if lonlat[0] < 9:
                return 31
            elif lonlat[0] < 21:
                return 33
            elif lonlat[0] < 33:
                return 35
            return 37

        return int( ( lonlat[0] + 180) / 6) + 1


    @staticmethod
    def getLetter( lonlat ):

        """
        get utm zone letter
        """

        # extract designated letter code from latitude
        return 'CDEFGHJKLMNPQRSTUVWXX'[int((lonlat[1] + 80) / 8)]
