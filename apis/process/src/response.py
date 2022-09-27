import affine
import numpy as np
import rioxarray 
import xarray as xr

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt

from cartopy.mpl.geoaxes import GeoAxes
from mpl_toolkits.axes_grid1 import AxesGrid
from mpl_toolkits.axes_grid1 import ImageGrid
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER

from sentinelhub import bbox_to_dimensions

class Response:

    def __init__( self, df, resolution, **kwargs ):

        """
        constructor
        """

        # copy args
        self._df = df
        self._resolution = resolution

        # optional args
        self._bbox = kwargs.get( 'bbox' )
        if self._bbox is None:
            self._bbox = kwargs[ 'geometry' ].bbox

        # get map coordinate vectors and extent
        self._transform, self._map_x, self._map_y = self.getMapCoordinates( self._bbox, resolution )
        self._extent = [    np.amin( self._map_x ), 
                            np.amax( self._map_x ), 
                            np.amin( self._map_y ), 
                            np.amax( self._map_y ) ]

        # get image dims
        self._width = len( self._map_x )
        self._height = len( self._map_y )
        return


    def getMapCoordinates( self, bbox, resolution ):

        """
        get vectors mapping pixel location to map coordinate
        """

        # get pixel size of bounding box
        _size = bbox_to_dimensions(bbox, resolution=resolution)
        image_y = np.array(np.arange(0, _size[1] ) )
        image_x = np.array(np.arange(0, _size[0] ) )

        # compute pixel to map transformation
        transform = bbox.get_transform_vector( resx=resolution, resy=resolution )
        return transform, ( transform[0] + image_x * transform[1] ), ( transform[3] + image_y * transform[5] )


    def convertToDataset( self, names=None ):

        """
        convert dataframe output to xarray
        """

        # start with null
        ds = None

        # get field names 
        if names is None:
            names = list( self._df.columns )

        # get time vector
        times = self.getTimeVector()
        if times is not None:

            # for each data field
            for name in names:

                # ignore timestamp columns
                if name not in [ 'time', 'start', 'end' ]:

                    # convert list of data arrays into stacked array
                    data = np.stack( self._df[ name ].values )
                    if len( data.shape ) == 3:              # only 3d supported for now

                        # construct data array
                        da = xr.DataArray(  data=data.transpose( 1, 2, 0 ),
                                            dims=[ "y", "x","time" ],
                                            coords=dict(
                                                east=( ["x"], self._map_x ),
                                                north=( ["y"], self._map_y ),
                                                time=times
                                            ),
                                            attrs=dict(
                                                description=name,
                                            )
                        )

                        # create dataset on first iteration
                        if ds is None:            
                            ds = da.to_dataset( name=name )
                        else:
                            ds[ name ] = da

        # add geotransform and crs to dataset via rioxarray plugin
        ds.rio.write_transform( affine.Affine.from_gdal( *self._transform ), inplace=True )
        ds.rio.write_crs( 'epsg:{}'.format( self._bbox.crs.value ), inplace=True )

        return ds


    def plotColorMesh( self, name, osm_zoom=None, figsize=None, alpha=dict(), suptitle=None, cmap='jet', cbar_label=None, extent=None, gridlines=True, scale=(20,20) ):

        """
        plot time series
        """

        # setup params
        plt.rc('font', size=10)   
        plt.rcParams[ 'mpl_toolkits.legacy_colorbar' ] = False 

        # create osm request
        request = cimgt.OSM()

        # setup projection
        projection = ccrs.epsg( int( self._bbox.crs.value ) )
        axes_class = (GeoAxes,
                    dict(map_projection=projection))

        # pick a good figure size
        if figsize is None:
            ratio = len( self._map_y ) / len( self._map_x )
            figsize=( scale[ 0 ] * ratio, scale[ 1 ] * len( self._df ) * ratio )
    
        # create figure and grid
        fig = plt.figure(figsize=figsize)
        grid = AxesGrid(fig, 111, axes_class=axes_class,
                        nrows_ncols=( len(self._df), 1 ),
                        axes_pad=0.6,
                        cbar_location='right',
                        cbar_mode='each',
                        cbar_pad=0.4,
                        cbar_size='3%',
                        label_mode='' ) 

        # plot suptitle if defined
        if suptitle is not None:
            fig.suptitle( suptitle, 
                        fontsize=32, 
                        horizontalalignment='center',
                        verticalalignment='center' )

        # iterate through dataframe
        for idx, row in self._df.iterrows():

            # set extent and add geometry
            if extent is None:
                extent = self._extent

            grid[ idx ].set_extent( extent, crs=ccrs.epsg( int( self._bbox.crs.value )  ) )
            
            if 'time' in self._df.columns:
                grid[ idx ].set_title( row[ 'time' ].strftime( '%Y-%m-%d %H:%M:%S' ) )
            else:
                grid[ idx ].set_title( row[ 'start' ].strftime( '%Y-%m-%d' ) + ' - ' +  row[ 'end' ].strftime( '%Y-%m-%d' ) )
    
            # optionally add osm backdrop
            if osm_zoom is not None:
                grid[ idx ].add_image( request, osm_zoom )

            # plot colour mesh
            mesh = grid[ idx ].pcolormesh(  self._map_x, 
                                            self._map_y, 
                                            row[ name ], 
                                            cmap=cmap,
                                            zorder=3,
                                            alpha=alpha.get( 'data', 0.4 ) )

            # solid cbar
            cbar = grid.cbar_axes[ idx ].colorbar( mesh )

            cbar.set_alpha(1)
            cbar.solids.set( alpha=1 )

            # add optional gridlines
            if gridlines:
                gl = grid[ idx ].gridlines( draw_labels=True, 
                                            linewidth=1, 
                                            color='gray', 
                                            alpha=alpha.get( 'grid', 0.4 ), 
                                            linestyle=':')

                gl.right_labels = gl.top_labels = False
    
    
        # add optional colorbar labels
        if cbar_label is not None:
            for cax in grid.cbar_axes:
                cax.toggle_label(True)
                cax.axis[cax.orientation].set_label( cbar_label )

        # show subplots
        #plt.tight_layout()
        plt.show()
        return


    def plotImages( self, name=None, osm_zoom=None, figsize=None, alpha=dict(), suptitle=None, gridlines=True, features=[], interpolation='nearest', annotation=None, cmap=None, extent=None, scale=(20,20) ):
    
        # setup params
        plt.rc('font', size=10)   
        plt.rcParams[ 'mpl_toolkits.legacy_colorbar' ] = False 

        # create osm request
        request = cimgt.OSM()

        # pick a good figure size
        if figsize is None:
            ratio = len( self._map_y ) / len( self._map_x )
            figsize=( scale[ 0 ] * ratio, scale[ 1 ] * len( self._df ) * ratio )
    
        # create figure and grid
        crs = ccrs.epsg( int( self._bbox.crs.value ) )
        nrows = 1 if name is None else len( self._df )
               
        fig, axes = plt.subplots(   figsize=figsize, 
                                    nrows=nrows, 
                                    ncols=1, 
                                    subplot_kw={'projection': crs },
                                    constrained_layout=True )

        # plot suptitle if defined
        if suptitle is not None:
            fig.suptitle( suptitle, 
                        fontsize=32, 
                        horizontalalignment='center',
                        verticalalignment='center' )

        # iterate through dataframe
        for idx, row in self._df.iterrows():

            # set title
            ax = axes[ idx ] if isinstance( axes, np.ndarray ) else axes
            ax.set_title( self.getSubTitle( row ) )

            # optionally add osm backdrop
            if osm_zoom is not None:
                ax.add_image( request, osm_zoom )

            # set extent and add geometry
            if extent is None:
                extent = self._extent

            # plot image
            if name is not None:
                ax.imshow( row[ name ], 
                            extent=extent, 
                            origin='upper', 
                            interpolation=interpolation, 
                            aspect='auto', 
                            cmap=cmap,
                            alpha=alpha.get( 'data', 0.4 ),
                            zorder=10 )
                        
            # plot additional annotation
            if annotation is not None:                        
                annotation[ 'features' ].plot(  ax=ax, 
                                                facecolor=annotation.get( 'facecolor', 'cyan' ),
                                                edgecolor=annotation.get( 'edgecolor' , 'black' ), 
                                                linewidth=annotation.get( 'linewidth', 1 ),
                                                alpha=annotation.get( 'alpha', 0.6 ),
                                                transform=crs)
            
            # plot optional features
            if 'coastlines' in features:
                ax.coastlines(resolution='50m', color='black', linewidth=1)

            if 'borders' in features:
                ax.borders(resolution='50m', color='black', linewidth=1)
                
            # optionally plot gridlines
            if gridlines:
                gl = ax.gridlines( draw_labels=True,
                                    linewidth=1, 
                                    color='gray', 
                                    alpha=alpha.get( 'grid', 1.0 ), 
                                    linestyle=':')

                # remove labels from top and right
                gl.right_labels = gl.top_labels = False
                
            # single annotation image
            if name is None:
                break
                   
        # show subplots
        plt.show()
        return

    
    def getSubTitle( self, row ):

        """
        get subtitle - single or start / end aggregation dates
        """

        title = None

        # get columns
        columns = list( row.index )

        # mosaic - start / end times
        if 'start' in columns and 'end' in columns:
            title = row[ 'start' ].strftime( '%Y-%m-%d' ) + ' - ' + row[ 'end' ].strftime( '%Y-%m-%d' )

        # single image, single time
        if title is None and 'time' in columns:
            title = row[ 'time' ].strftime( '%Y-%m-%d %H:%M:%S' )

        return title


    def getTimeVector( self ):

        """
        get primary time vector
        """

        times = None
        
        # variation between single acqusition / mosaic aggregation period
        for name in [ 'time', 'start' ]:
            if name in list( self._df.columns ):
                
                # copy and return time vector
                times = self._df[ name ].values
                break

        return times
