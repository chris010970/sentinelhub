import os
import yaml
import argparse

from munch import munchify
from datetime import datetime
from extractor import Extractor


def validDateTimeArgument ( arg ):

    """
    parse custom argparse *date* type 
    """
    
    try:
        # attempt to parse arg string into datetime obj
        return datetime.strptime( arg, "%d/%m/%Y %H:%M:%S" )
    except ValueError:
        msg = "Argument ({0}) not valid! Expected format, YYYY-MM-DD HH:MM:SS!".format(arg)
        raise argparse.ArgumentTypeError(msg)


def parseArguments(args=None):

    """
    parse arguments
    """

    # parse command line arguments
    parser = argparse.ArgumentParser(description='sh-extractor')

    # mandatory args
    parser.add_argument('config_file', action='store', help='yaml configuration file' )
    parser.add_argument('resolution', type=float, action='store', help='spatial resolution (metres)' )
    parser.add_argument('-o', '--out_path', action='store', help='root directory for output files' )

    # filter options
    parser.add_argument('-s','--start_datetime', type=validDateTimeArgument, help='start acquisition datetime', default=None )
    parser.add_argument('-e','--end_datetime', type=validDateTimeArgument, help='end  acquisition datetime', default=None )    
    parser.add_argument('-a','--aois', nargs='+', help='aoi list', default=None )

    parser.add_argument('--max_downloads', type=int, help='max compliant downloads for aoi', default=100 )
    parser.add_argument('--overwrite', action='store_true', help='overwrite existing files' )
    parser.add_argument('--mosaic', action='store_true', help='generate mosaic' )

    return parser.parse_args(args)


def main():

    """
    main path of execution
    """

    # parse arguments
    args = parseArguments()

    # load config parameters from file
    with open( args.config_file, 'r' ) as f:
        config = munchify( yaml.safe_load( f ) )

    # extract tiles coincident with point geometries
    obj = Extractor( config )
    obj.process( config, args )

    return


# execute main
if __name__ == '__main__':
    main()
