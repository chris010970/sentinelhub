import pandas as pd
from sentinelhub import parse_time

class Response:

    def __init__( self, data ):

        """
        constructor
        """

        # copy args
        self._dfs = [ self.convertToDataFrame(stats) for stats in data ]
        return


    def convertToDataFrame( self, data ):
        
        """
        transform response into a pandas.DataFrame
        """
    
        records = []

        # for all items in response
        for item in data[ 'data' ]:

            entry = {}
            is_valid_entry = True

            # parse data aggregation timeframe
            entry[ 'interval_from' ] = parse_time( item[ 'interval' ][ 'from' ]).date()
            entry[ 'interval_to' ] = parse_time( item[ 'interval' ][ 'to' ]).date()

            for output_name, output_data in item['outputs'].items():
                for band_name, band_values in output_data['bands'].items():

                    band_stats = band_values['stats']
                    if band_stats['sampleCount'] == band_stats['noDataCount']:
                        is_valid_entry = False
                        break

                    # generate unique name
                    for stat_name, value in band_stats.items():
                        col_name = f'{output_name}_{band_name}_{stat_name}'
                        if stat_name == 'percentiles':
                            # parse percentile results
                            for perc, perc_val in value.items():
                                perc_col_name = f'{col_name}_{perc}'
                                entry[perc_col_name] = perc_val
                        else:
                            # copy original result
                            entry[col_name] = value

                    # response includes histogram analysis
                    if band_values.get( 'histogram' ) is not None:

                        # copy raw result
                        col_name = f'{output_name}_{band_name}_histogram'
                        entry[ col_name ] = band_values.get( 'histogram' )

                        # add normalised counts
                        counts = [ value[ 'count' ] for value in entry[ col_name ][ 'bins' ] ]
                        total_counts = sum(counts)
                        
                        entry[ col_name ][ 'normalised_counts' ] = [ round(100 * count / total_counts) if total_counts > 0 else 0 for count in counts ]
                        entry[ col_name ][ 'total_counts' ] = total_counts

                        # add bin edges into array for easy access
                        edges = [ value[ 'lowEdge' ] for value in entry[ col_name ][ 'bins' ] ]
                        edges.append( entry[ col_name ][ 'bins' ][ -1 ][ 'highEdge'] )
                        entry[ col_name ][ 'bin_edges'] = edges


            # append if valid entry
            if is_valid_entry:
                records.append( entry )

        return pd.DataFrame( records )
