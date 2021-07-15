#!/usr/bin/env python
#
# Copyright (C) Nira, Inc. - All Rights Reserved

from __future__ import print_function

# Retrieve deps from this repo rather than requiring globally installed versions.
# This ensures we're fully self-contained.
import os
myDir = os.path.dirname(os.path.realpath(__file__))
myDir += "/deps"

import sys
sys.path.insert(0, myDir)

import time
from niraclient import NiraClient, NiraUploadInfo, NiraJobStatus, isoUtcDateParse
import argparse
import requests.exceptions
import datetime
import traceback
import json

# Used to verify we're using our repo's copy of requests
#print(requests.__file__)

class ArgumentParserFullHelpPrintOnError(argparse.ArgumentParser):
  def error(self, message):
    self.print_help(sys.stderr)
    self.exit(2, '\n%s: error: %s\n' % (self.prog, message))

class _HelpAction(argparse._HelpAction):
  def __call__(self, parser, namespace, values, option_string=None):
    parser.print_help()

    # retrieve subparsers from parser
    subparsers_actions = [
      action for action in parser._actions
      if isinstance(action, argparse._SubParsersAction)]

    for subparsers_action in subparsers_actions:
      # get all subparsers and print help
      for choice, subparser in subparsers_action.choices.items():
        print("'{}' Command".format(choice))
        print(subparser.format_help())

    parser.exit()

parser = ArgumentParserFullHelpPrintOnError(description='Nira Client CLI', add_help=False)
parser.add_argument('--help', action=_HelpAction, help='show this help message and exit')
parser.add_argument('--apikey', type=str)
parser.add_argument('--url', type=str)
parser.add_argument('--user', dest='user', type=str, default='', help="Specifies the user account that API operations occur under. For example, if an asset upload is performed, that user's name will appear in the `Uploader` column of Nira's asset listing page.")
parser.add_argument('--print-requests', dest='print_requests', action='store_true', default=False, help="Print HTTP requests stderr. Useful for leaning about the API, or for debugging purposes")
parser.add_argument('--print-responses', dest='print_responses', action='store_true', default=False, help="Print HTTP requests stderr. Useful for leaning about the API, or for debugging purposes")

subparsers = parser.add_subparsers(help='Operation')
#subparsers.required = True

assetParser = subparsers.add_parser('asset', help='Perform asset related operations')
assetSubParser = assetParser.add_subparsers(help='Asset related operations')

userParser = subparsers.add_parser('user', help='Perform user related operations')
userSubParser = userParser.add_subparsers(help='User related operations')

def addUploadOptionsToParser(thisParser):
  thisParser.add_argument('--upload-threads', dest='uploadthreads', type=int, default=4, help="Number of simultaneous upload connection threads to use. Using mulitple simultaneous connections for uploads can accelerate them significantly, particularly over long-distance WAN links.")
  thisParser.add_argument('--upload-chunk-size', dest='uploadchunksize', type=int, default=1024 * 1024 * 10, help="Size of each uploaded chunk, in bytes. When uploading, files will be divided into chunks of this size and sent to the Nira server using the number of threads specified by the --upload-threads option.")
  thisParser.add_argument('--no-upload-compression', action='store_false', dest='use_upload_compression', help="Disables the use of automatic upload compression. Upload compression is enabled by default. You may wish to disable it if you have a particularly upstream network speed (1gbps+) or have concerns about CPU utilization on the machine doing the uploading.")
  #thisParser.add_argument("--asset-name", dest="asset_name", help="When using --upload, specify an asset name")
  #thisParser.add_argument('--compress-textures', action='store_true', dest='compress_textures', help='If specified, when using --upload, compresses textures on the server.')
  #thisParser.add_argument('--ignore-mtl', action='store_true', dest='ignore_mtl', help='If specified, when using --upload and uploading an OBJ file, do not use the texture assignments and material paramters specified in the MTL file.')
  #thisParser.add_argument('--no-vertex-colors', action='store_true', dest='no_vertex_colors', help='If specified, when using --upload, do not use the vertex colors specified in the scene file(s)')
  #thisParser.add_argument('--no-normals', action='store_true', dest='no_normals', help='If specified, when using --upload, do not use the normals specified in the scene file(s), and do not generate smooth normals on the server.')
  thisParser.add_argument('--wait-for-asset-processing', dest='wait_max_seconds', default=3600, type=int, help='When using --upload, wait up to WAIT_MAX_SECONDS for the asset to be processed on the server before returning. If set to 0, the command will return immediately after upload, and asset processing will not have finished yet. Note, --upload will not print an asset url unless the asset has finished processing, so it is best to use a sufficiently large value for this argument. If an error occurs during upload or processing, the command will exit with a non-zero status and print an error message.')

def addListOptionsToParser(thisParser):
  thisParser.add_argument('--paginate', action='store_const', const='true', default='false', help="Return a paginated result")

assetCreateParser = assetSubParser.add_parser('create', help='Create a new asset, upload the provided files to it, then print a URL to the resulting asset on stdout or an error message if unsuccessful.')
assetCreateParser.add_argument('name', type=str, metavar='asset_name', help='A name for the asset. If an asset with this name already exists, an error message will be printed. If you wish to add files to an existing asset, use the addfiles command, instead.')
assetCreateParser.add_argument('type', choices=["default", "sculpt", "photogrammetry", "volumetric_video"], help="Specifies the type of the asset.")
assetCreateParser.add_argument('file_path', default=[], nargs='+', type=str, help='A space separated list of file paths to upload to the asset. At least one of the files should be a primary scene file (ma, mb, zpr, etc). Accompanying files can also be included (e.g. texture files).')
addUploadOptionsToParser(assetCreateParser)

assetListParser = assetSubParser.add_parser('list', help='List assets, optionally filtering by some criteria')
addListOptionsToParser(assetListParser)
assetListFilteringGroup = assetListParser.add_argument_group(title='Filtering options', description='If multiple filter arguments are provided, they are appied in an AND fashion')
assetListFilteringGroup.add_argument('--name', type=str, help='Filter by asset name')
assetListFilteringGroup.add_argument('--uuid', type=str, help='Filter by UUID')

userListParser = userSubParser.add_parser('list', help='List users, optionally filtering by some criteria')
addListOptionsToParser(userListParser)
userListFilteringGroup = userListParser.add_argument_group(title='Filtering options', description='If multiple filter arguments are provided, they are appied in an AND fashion')
userListFilteringGroup.add_argument('--email', type=str, help='Filter by email')

assetFilesParser = assetSubParser.add_parser('files', help='Perform operations related to an asset\'s files')
assetFilesSubParser = assetFilesParser.add_subparsers(help="Asset file related operations")

assetAddfilesParser = assetFilesSubParser.add_parser('add', help='Upload the provided files to an existing asset, then print a URL to the asset on stdout or an error message if unsuccessful.')
assetAddfilesParser.add_argument('name', type=str, metavar='asset_name', help='A name for an existing asset. If an asset with this name does not exist, an error message will be printed. If you wish to create a new asset and add files to it, use the \'asset create\' command, instead.')
assetAddfilesParser.add_argument('file_path', default=[], nargs='+', type=str, help='A space separated list of file paths to upload to the asset.')
addUploadOptionsToParser(assetAddfilesParser)

assetStateParser = assetSubParser.add_parser('state', help='Perform operations related to an asset\'s state')
assetStateSubParser = assetStateParser.add_subparsers(help="Asset state related operations")
assetStateGetParser = assetStateSubParser.add_parser('get', help='Retrieve an asset\'s state')
assetStateSetParser = assetStateSubParser.add_parser('set', help='Set an asset\'s state')


import argparse

#group = parser.add_mutually_exclusive_group(required=True)
#group.add_argument('--upload', dest="asset_path", default=[], nargs='+', type=str, help='Takes a space separated list of file paths to upload, uploads them, then prints a URL to the resulting asset on stdout, or an error message if unsuccessful. Accompanying files should also be included (e.g. texture files). At least one of the files should be a primary scene file (ma, mb, zpr, etc)')
#parser.add_argument("--asset-id", dest="asset_id", help='When using --upload, specify an asset id')
#group.add_argument('--download', dest="download", default=[], nargs=1, type=str, help='Takes two parameters: An asset\'s URL (or the asset\'s short UUID) and a local destination folder to store the asset. The asset and all of its accompanying assets will be downloaded into this folder.')
#group.add_argument('--get-state', dest="get_asset_state_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID) and returns the latest state for the asset.')
#group.add_argument('--set-state', dest="set_asset_state_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID), reads state JSON from stdin, and merges this state to the asset on the Nira server.')
#group.add_argument('--set-metadata', dest="set_metadata_asset_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID), reads metadata JSON from stdin, and attaches this metadata to the asset on the Nira server. Also see --metadata-level.')
#group.add_argument('--get-metadata', dest="get_metadata_asset_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID) and returns metadata for the asset or assetversion. Also see --metadata-level.')
#group.add_argument('--get-manifest', dest="get_manifest_asset_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID) and returns the manifest for the asset.')
#parser.add_argument('--metadata-level', dest='metadata_level', choices=["assetversion", "asset"], default='assetversion', help='When using --set-metadata or --get-metadata, specifying "--metadata-level assetversion" or "--metadata-level asset" controls whether to set/retrieve the metadata attached to the assetversion specified, or the entire asset.')
#group.add_argument('--show-updated-assets-every', dest='update_seconds', default=0, type=int, help='Polls the server every UPDATE_SECONDS, showing any asset updates that have occurred since the last poll. The command does not exit unless it encounters an error or is interrupted by the user.')
#group.add_argument('--show-updated-assets-within', dest='seconds_ago', default=0, type=int, help='Show any asset updates that have occurred within SECONDS_AGO, then exit.')

def getNiraClient(args):
  niraApiKey = args.apikey or os.environ.get('NIRA_APIKEY')
  niraUrl = args.url or os.environ.get('NIRA_URL')
  niraUser = args.user or os.environ.get('NIRA_USER')

  if not niraApiKey:
    parser.print_help()
    sys.exit("A Nira API key must be defined either via the --apikey option or the NIRA_APIKEY environment variable!")

  if not niraUrl:
    parser.print_help()
    sys.exit("A Nira URL must be defined either via the --url option or the NIRA_URL environment variable!")

  if not niraUser:
    parser.print_help()
    sys.exit("A Nira user account email must be defined either via the --user option or the NIRA_USER environment variable!")

  return NiraClient(niraUrl, niraApiKey, userEmail=niraUser, printRequests=args.print_requests, printResponses=args.print_responses)

def assetCreate(args):
  nirac = getNiraClient(args)

  assets = nirac.listAssets({'name': args.name});

  if len(assets) != 0:
    sys.exit("Asset '" + args.name + "' already exists! Use the addfiles command to add files to this asset.")

  uploadInfo = nirac.uploadAsset(args.file_path, args.type, args.name, useCompression=args.use_upload_compression, maxWaitSeconds=args.wait_max_seconds)

  if uploadInfo.jobStatus == NiraJobStatus.Processed:
    print(uploadInfo.assetUrl)
    sys.exit(0)

  print(uploadInfo.jobStatus)
  sys.exit(1)

def assetFilesAdd(args):
  nirac = getNiraClient(args)

  assets = nirac.listAssets({'name': args.name});

  if len(assets) == 0:
    sys.exit("Asset '" + args.name + "' does not exist! Use the create command to create a new asset.")

  asset = assets[0]

  uploadInfo = nirac.uploadAsset(args.file_path, asset['type'], asset['name'], useCompression=args.use_upload_compression, maxWaitSeconds=args.wait_max_seconds)

  if uploadInfo.jobStatus == NiraJobStatus.Processed:
    print(uploadInfo.assetUrl)
    sys.exit(0)

  print(uploadInfo.jobStatus)
  sys.exit(1)

def assetList(args):
  nirac = getNiraClient(args)

  query = {}

  if args.name:
    query['name'] = args.name

  if args.uuid:
    query['uuid'] = args.uuid

  query['$paginate'] = args.paginate

  assets = nirac.listAssets(query);
  print(str(json.dumps(assets, indent=2)))

def userList(args):
  nirac = getNiraClient(args)

  query = {}

  if args.email:
    query['email'] = args.email

  query['$paginate'] = args.paginate

  users = nirac.listUsers(query);
  print(str(json.dumps(users, indent=2)))

assetCreateParser.set_defaults(func=assetCreate)
assetAddfilesParser.set_defaults(func=assetFilesAdd)
assetListParser.set_defaults(func=assetList)
userListParser.set_defaults(func=userList)

args = parser.parse_args()

try:
  args.func(args)
except requests.exceptions.HTTPError as error:
  print(error, file=sys.stderr)
  print(error.response.text, file=sys.stderr)
  sys.exit(1)
except (KeyboardInterrupt, SystemExit):
  raise
except Exception as e:
  print(traceback.format_exc(), file=sys.stderr)
  sys.exit(1)
