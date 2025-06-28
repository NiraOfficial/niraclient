#!/usr/bin/env python
#
# Copyright (C) Nira, Inc. - All Rights Reserved

from __future__ import print_function

import os
import sys

# Retrieve deps from this repo rather than requiring globally installed versions.
# This ensures we're fully self-contained.
myDir = os.path.dirname(os.path.realpath(__file__))
if sys.version_info.major == 2:
  myDir += "/deps-py2"
else:
  myDir += "/deps"
sys.path.insert(0, myDir)

import time
from niraclient import NiraClient, NiraUploadInfo, NiraJobStatus, NiraConfig, isoUtcDateParse
import argparse
import requests.exceptions
import datetime
import traceback
import json
import csv
from getpass import getpass

try:
  from urllib.parse import urlparse
except ImportError:
  from urlparse import urlparse

try:
  input = raw_input
except NameError:
  pass

# Used to verify we're using our repo's copy of requests
#print(requests.__file__)

def get_subparser_action(parser):
  neg1_action = parser._actions[-1]

  if isinstance(neg1_action, argparse._SubParsersAction):
    return neg1_action

  for a in parser._actions:
    if isinstance(a, argparse._SubParsersAction):
      return a

def get_parsers(parser, maxdepth=0, depth=0):
  if maxdepth and depth >= maxdepth:
    return

  # Current parser
  yield parser

  # Subparsers
  if parser._subparsers:
    choices = ()

    subp_action = get_subparser_action(parser)
    if subp_action:
      choices = subp_action.choices.items()

    for _, sub in choices:
      if isinstance(sub, argparse.ArgumentParser):
        for p in get_parsers(
          sub, maxdepth, depth + 1
          ):
            yield p

class SmartFormatter(argparse.HelpFormatter):
  def _split_lines(self, text, width):
    if '\n' in text:
      return text.splitlines()
    return argparse.HelpFormatter._split_lines(self, text, width)

class ArgumentParserFullHelpPrintOnError(argparse.ArgumentParser):
  def error(self, message):
    self.print_help(sys.stderr)
    self.exit(2, '\n%s: error: %s\n' % (self.prog, message))

class _HelpAction(argparse._HelpAction):
  def __call__(self, parser, namespace, values, option_string=None):
    parser.print_help()
    parser.exit()

class _FullHelpAction(argparse._HelpAction):
  def __call__(self, parser, namespace, values, option_string=None):
      par = get_parsers(parser)
      for p in par:
        print("---------------")
        print(p.format_help())
      parser.exit()

uploadFilesHelpText = '''
There are two different methods for providing the files you wish to upload:

* Method 1: Provide a list of file paths on the command line

  For example:
     nira.py asset create myasset photogrammetry assets/tpot.obj assets/tpot.mtl
  Will upload tpot.obj and tpot.mtl to a new asset called 'myasset'

  The server will attempt to automatically determine file types based
  on their content. For photogrammetry files with photos, there's a potential
  downside of relying upon automatic file type detection -- it is not always
  possible to automatically determine the difference between a texture ("image")
  or photo ("photogrammetry_image"). Therefore, for photogrammetry assets
  with photos, "Method 2" below is suggested.

* Method 2: Provide a json array on stdin
    (Recommended for photogrammetry assets with photos)

    Here's an example of a json file list:
    [{
      "path": "assets/tpot.obj",
      "type": "scene"
    }, {
      "path": "assets/tpot.mtl",
      "type": "extra"
    }, {
      "path": "assets/blue.png",
      "type": "image"
    }, {
      "path": "assets/photos/tpot-photo01.jpg",
      "type": "photogrammetry_image"
    }]
    Providing this array will cause 4 files to be uploaded:
      An obj geometry file (tpot.obj)
      An MTL file (tpot.mtl)
      A texture file (blue.png)
      A photo (tpot-photo01.jpg)

Other Notes:
  * If you don't provide any file paths on the command line,
    you wil be prompted to enter a files json array.
  * If you're trying to automate Nira commands but you're
    not familiar how to provide data through a command's stdin,
    you can search for "Piping and redirection" along with your
    operating system ("linux", "windows") to learn more about it.
  * File paths may be absolute or relative to the runtime directory.
  * When creating a new asset, at least one of the files should be
    a geometry file (obj, ma, mb, zpr, etc). When adding files to an
    existing asset, this does not apply.
'''

parser = ArgumentParserFullHelpPrintOnError(description='Nira Client CLI', add_help=False)
parser.add_argument('--help', action=_HelpAction, help='show this help message and exit')
parser.add_argument('--full-help', action=_FullHelpAction, help='show help for all possible subcommands and exit')
parser.add_argument('--print-requests', dest='print_requests', action='store_true', default=False, help="Print HTTP requests stderr. Useful for leaning about the API, or for debugging purposes")
parser.add_argument('--print-responses', dest='print_responses', action='store_true', default=False, help="Print HTTP requests stderr. Useful for leaning about the API, or for debugging purposes")
parser.add_argument('--print-and-dump-requests', dest='print_and_dump_requests', action='store_true', default=False, help="Print HTTP requests stderr and also dump the requests to 'request-body-NNN' files in your current directory. Useful for inspecting large request bodies such as file part upload requests")
parser.add_argument('--org', type=str, dest='org', default=None, help="Your Nira organization name, including the domain name. This is only for advanced usage where multiple orgs are being used.")
parser.add_argument('--use-client-side-auth-token-exchange', dest='use_client_side_auth_token_exchange', action='store_true', default=False, help="Perform auth token exchange on the client side. Advanced use cases only.")
parser.add_argument('--request-api-token-expiration-time', type=int, dest='request_api_token_expiration_time', default=None, help="When using client side auth token exchange, this specifies the token's expiration time in seconds. The default is 1200 (20 minutes), and the maximum is 14400 (4 hours). Advanced use cases only.")

subparsers = parser.add_subparsers(help='Operation', dest='Operation')
subparsers.required = True

configureParser = subparsers.add_parser('configure', help='Perform initial configuration. This is required to use any Nira API commands.')

assetParser = subparsers.add_parser('asset', help='Perform asset related operations')
assetSubParser = assetParser.add_subparsers(help='Asset related operations', dest='AssetOperation')
assetSubParser.required = True

groupParser = subparsers.add_parser('group', help='Perform group related operations')
groupSubParser = groupParser.add_subparsers(help='Group related operations', dest='GroupOperation')
groupSubParser.required = True

groupListParser = groupSubParser.add_parser('list', help='List groups')
groupListFilteringGroup = groupListParser.add_argument_group(title='Filtering options')
groupListFilteringGroup.add_argument('--name', type=str, help='Filter by group name')

groupGetParser = groupSubParser.add_parser('get', help='Get group')
groupGetParser.add_argument('group_uuid', type=str, help='Specify the uuid of the group to retrieve')

groupDeleteParser = groupSubParser.add_parser('delete', help='Delete group.')
groupDeleteParser.add_argument('group_uuid', type=str, help='Specify the uuid of the group to delete')

groupCreateParser = groupSubParser.add_parser('create', help='Create a new group.')
groupCreateParser.add_argument('name', type=str, metavar='group_name', help='A name for the group. If an group with this name already exists, an error message will be printed.')

userParser = subparsers.add_parser('user', help='Perform user related operations')
userSubParser = userParser.add_subparsers(help='User session related operations', dest='UserOperation')
userSubParser.required = True

userSessionsParser = userSubParser.add_parser('sessions', help='Perform user session related operations')
userSessionsSubParser = userSessionsParser.add_subparsers(help='User session related operations', dest='UserSessionOperation')
userSessionsSubParser.required = True

userSessionsDeleteParser = userSessionsSubParser.add_parser('expire', help='Expire all sessions of the user account with the specified email.')
userSessionsDeleteParser.add_argument('user_email', type=str, help='Specify a user account\'s email address')

def addUploadOptionsToParser(thisParser):
  thisParser.add_argument('--no-upload-compression', action='store_false', dest='use_upload_compression', help="Disables the use of automatic upload compression. Upload compression is enabled by default. You may wish to disable it if you have a particularly capable upstream network throughput (1gbps+) or have concerns about CPU utilization on the machine doing the uploading.")
  thisParser.add_argument('--wait-for-asset-processing', dest='wait_max_seconds', default=0, type=int, help='Wait up to WAIT_MAX_SECONDS for the asset to be processed on the server before returning. By default, the command will return immediately after upload and will not wait for processing.')
  thisParser.add_argument('--dccname', dest='dccname', choices=["3dfzephyr", "djiterra", "agisoft", "contextcapture", "pix4d", "realitycapture", "mantisvision"], help='Specify the name of the dcc used to create the files that you are uploading. This allows Nira to set an appropriate Coordinate System (ZY up).')

assetCreateParser = assetSubParser.add_parser('create', help='Create a new asset, upload the provided files to it, then print a URL to the asset on stdout or an error message if unsuccessful.', formatter_class=SmartFormatter)
assetCreateParser.add_argument('name', type=str, metavar='asset_name', help='A name for the asset. If an asset with this name already exists, an error message will be printed. If you wish to add files to an existing asset, use the addfiles command, instead.')
assetCreateParser.add_argument('type', choices=["default", "sculpt", "photogrammetry", "volumetric_video"], help="Specifies the type of the asset.")
assetCreateParser.add_argument('files', default=[], nargs='*', type=str, help=uploadFilesHelpText)
addUploadOptionsToParser(assetCreateParser)

assetDeleteParser = assetSubParser.add_parser('delete', help='Delete an existing asset')
assetDeleteParser.add_argument('asset_short_uuid',  metavar='asset_short_uuid', help='A short uuid or URL for an existing asset. If the asset cannot be found, an error message will be printed.')

assetDeleteBeforeParser = assetSubParser.add_parser('delete-before', help='Delete all assets that were created prior to the specified point in time and print information about the impacted assets to stdout in JSON format.')
assetDeleteBeforeParser.add_argument('before', type=str, metavar='before', help='A timestamp (milliseconds since epoch) or a relative date string in the format "Nd", where N is a positive integer and "d" represents days. For example, "30d" would delete assets created before 30 days ago, and the timestamp 1741201439963 would delete all assets created before 2025-03-05 19:03:59 UTC.')
assetDeleteBeforeParser.add_argument('--confirm', dest='confirm', action='store_true', default=False, help="Assets will only be deleted if this is specified. If not specified, information about the assets that would have been deleted are printed to stdout, but they are not actually deleted.")

assetSharingParser = assetSubParser.add_parser('sharing', help='Perform asset sharing related operations')
assetSharingSubParser = assetSharingParser.add_subparsers(help='Asset sharing related operations', dest='AssetSharingOperation')
assetSharingSubParser.required = True

calloutsParser = assetSubParser.add_parser('callouts', help='Perform callouts related operations')
calloutsSubParser = calloutsParser.add_subparsers(help='Callouts related operations', dest='CalloutOperation')
calloutsSubParser.required = True
calloutsExportParser = calloutsSubParser.add_parser('export', help='Export callouts')
calloutsExportParser.add_argument('asset_short_uuid', type=str, metavar='asset_short_uuid', help='A short uuid or URL for an existing asset. If the asset cannot be found, an error message will be printed.')
calloutsExportParser.add_argument('--output-file', type=str, dest='output_file', help='Optionally specify an output file path. By default, print to stdout.')
calloutsExportParser.add_argument('--format', type=str, choices=['csv', 'tsv', 'json'], default='json', help='Optionally specify the format of exported callouts. By default, use json.')

calloutsImportParser = calloutsSubParser.add_parser('import', help='Import callouts')
calloutsImportParser.add_argument('asset_short_uuid', type=str, metavar='asset_short_uuid', help='A short uuid or URL for an existing asset. If the asset cannot be found, an error message will be printed.')
calloutsImportParser.add_argument('input_file_path', type=str, help='Specify the path to the local input file')
calloutsImportParser.add_argument('--remove-all-existing-callouts', action='store_true', dest='remove_all_existing_callouts', help='Controls whether the existing callouts are removed before importing.')
calloutsImportParser.add_argument('--format', type=str, choices=['csv', 'tsv', 'json'], default=None, help='Optionally specify the format of the input file. By default, the file extension will be used to determine the format. If the format cannot be determined, an error will be printed.')

assetUserParser = assetSharingSubParser.add_parser('user', help='Managing sharing of an asset for particular users')
assetUserSubParser = assetUserParser.add_subparsers(help='Asset sharing related operations', dest='AssetSharingUserOperation')
assetUserSubParser.required = True
assetShareUserAddParser = assetUserSubParser.add_parser('add', help='Share asset with a user specified by email.')
assetShareUserAddParser.add_argument('asset_short_uuid', type=str, metavar='asset_short_uuid', help='A short uuid or URL for an existing asset. If the asset cannot be found, an error message will be printed.')
assetShareUserAddParser.add_argument('user_email', type=str, help='Specify a user by email')
assetShareUserAddParser.add_argument('role', type=str, help='Role name. Could be "viewer" or "contributor"')
assetShareUserAddParser.add_argument('expiration_date', type=str, help='Optional expiration datetime in ISO format. e.g. 2022-02-24T23:00:00.000Z', nargs='?')

assetSetPublicParser = assetSharingSubParser.add_parser('set-public', help='Set the public sharing flag on or off for an asset')
assetSetPublicParser.add_argument('asset_short_uuid',  metavar='asset_short_uuid', help='A short uuid or URL for an existing asset. If the asset cannot be found, an error message will be printed.')
assetSetPublicParser.add_argument('public_flag', choices=["on", "off"], help='Enables or disables the public flag for the asset')

assetListParser = assetSubParser.add_parser('list', help='List assets, optionally filtering by some criteria')
assetListFilteringGroup = assetListParser.add_argument_group(title='Filtering options', description='If multiple filter arguments are provided, they are appied in an AND fashion')
assetListFilteringGroup.add_argument('--name', type=str, help='Filter by asset name')
assetListFilteringGroup.add_argument('--uuid', type=str, help='Filter by UUID')

assetFilesParser = assetSubParser.add_parser('files', help='Perform operations related to an asset\'s files')
assetFilesSubParser = assetFilesParser.add_subparsers(help="Asset file related operations", dest='AssetFileOperation')
assetFilesSubParser.required = True

assetAddfilesParser = assetFilesSubParser.add_parser('add', help='Upload the provided files to an existing asset, then print a URL to the asset on stdout or an error message if unsuccessful.', formatter_class=SmartFormatter)
assetAddfilesParser.add_argument('name', type=str, metavar='asset_name', help='A name for an existing asset. If an asset with this name does not exist, an error message will be printed. If you wish to create a new asset and add files to it, use the \'asset create\' command, instead.')
assetAddfilesParser.add_argument('files', default=[], nargs='*', type=str, help=uploadFilesHelpText)
addUploadOptionsToParser(assetAddfilesParser)

def getNiraClient(args):
  try:
    niraClient = NiraClient(org=args.org, printRequests=args.print_requests, printResponses=args.print_responses, printAndDumpRequests=args.print_and_dump_requests, useClientSideAuthTokenExchange=args.use_client_side_auth_token_exchange, requestApiTokenExpirationTime=args.request_api_token_expiration_time)
    return niraClient
  except Exception as e:
    print("ERROR: " + str(e))
    print("\nMake sure you run '%s configure'!"% sys.argv[0])
    sys.exit(1)

def getShortUuidFromPossibleUrl(shortUuidOrUrl):
  if len(shortUuidOrUrl) == 22:
    return shortUuidOrUrl

  urlParams = urlparse(shortUuidOrUrl)
  pathparts = urlParams.path.split("/", 3)

  if pathparts[1] != 'a':
    print("%s is not a valid asset URL or short uuid!" %shortUuidOrUrl, file=sys.stderr)
    sys.exit(1)

  for pathpart in pathparts:
    if len(pathpart) == 22:
      return pathpart

  print("%s is not a valid asset URL or short uuid!" %shortUuidOrUrl, file=sys.stderr)
  sys.exit(1)

def importCallouts(args):
  nirac = getNiraClient(args)

  callouts = nirac.importCallouts(
    getShortUuidFromPossibleUrl(args.asset_short_uuid),
    args.input_file_path,
    args.remove_all_existing_callouts,
    args.format
  )

  sys.exit(1)

def exportCallouts(args):
  nirac = getNiraClient(args)

  callouts = nirac.exportCallouts(getShortUuidFromPossibleUrl(args.asset_short_uuid), args.format)

  def saveToFile(content, file_name):
    with open(file_name, 'w') as file:
      file.write(content)

  if args.format == "json":
    jsonContent = str(json.dumps(callouts.json(), indent=2))

    if (args.output_file == None):
      print(jsonContent)
    else:
      saveToFile(jsonContent, args.output_file)
  else:
    content = callouts.content.decode(encoding="utf-8")

    if (args.output_file == None):
      print(content)
    else:
      saveToFile(content, args.output_file)

  sys.exit(1)

def assetShare(args):
  nirac = getNiraClient(args)

  asset_invitation = nirac.shareAsset(getShortUuidFromPossibleUrl(args.asset_short_uuid), args.user_email, args.role, args.expiration_date)

  print(str(json.dumps(asset_invitation, indent=2)))

  sys.exit(1)

def assetDelete(args):
  nirac = getNiraClient(args)

  nirac.deleteAsset(getShortUuidFromPossibleUrl(args.asset_short_uuid))

  sys.exit(1)

def assetDeleteBefore(args):
  nirac = getNiraClient(args)

  deletedAssets = nirac.deleteAssetsBefore(args.before, args.confirm)

  print(str(json.dumps(deletedAssets['result']['assets'], indent=2)))

  if (args.confirm != True):
    print("This is a dry run. Specify --confirm to actually delete the assets shown.", file=sys.stderr)

  sys.exit(1)

def assetCreate(args):
  nirac = getNiraClient(args)

  assets = nirac.listAssets({'name': args.name});

  if len(assets) != 0:
    sys.exit("Asset '" + args.name + "' already exists! Use the addfiles command to add files to this asset.")

  if len(args.files) > 0:
    files=[]
    for filepath in args.files:
      files.append({
        'path': filepath
      })
  else:
    print("Reading file list json from stdin...", file=sys.stderr)

    filesStr = ''
    for line in sys.stdin:
      filesStr += line.rstrip()

    files = json.loads(filesStr)

  uploadInfo = nirac.uploadAsset(files, args.type, args.name, dccname=args.dccname, useCompression=args.use_upload_compression, maxWaitSeconds=args.wait_max_seconds)

  if uploadInfo.jobStatus != NiraJobStatus.ProcessingError:
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

  if len(args.files) > 0:
    files=[]
    for filepath in args.files:
      files.append({
        'path': filepath
      })
  else:
    print("Reading file list json from stdin...", file=sys.stderr)

    filesStr = ''
    for line in sys.stdin:
      filesStr += line.rstrip()

    files = json.loads(filesStr)

  uploadInfo = nirac.uploadAsset(files, asset['type'], asset['name'], dccname=args.dccname, useCompression=args.use_upload_compression, maxWaitSeconds=args.wait_max_seconds)

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

  assets = nirac.listAssets(query);
  print(str(json.dumps(assets, indent=2)))

def sessionsExpire(args):
  nirac = getNiraClient(args)

  group = nirac.expireUserSessions(args.user_email);
  print(str(json.dumps(group, indent=2)))

def groupList(args):
  nirac = getNiraClient(args)

  query = {}

  if args.name:
    query['name'] = args.name

  groups = nirac.listGroups(query);
  print(str(json.dumps(groups, indent=2)))

def groupGet(args):
  nirac = getNiraClient(args)

  group = nirac.getGroup(args.group_uuid);
  print(str(json.dumps(group, indent=2)))

def groupDelete(args):
  nirac = getNiraClient(args)

  group = nirac.deleteGroup(args.group_uuid);
  print(str(json.dumps(group, indent=2)))

def groupCreate(args):
  nirac = getNiraClient(args)

  group = nirac.createGroup(args.name);
  print(str(json.dumps(group, indent=2)))

def assetSetPublic(args):
  nirac = getNiraClient(args)

  asset = nirac.setPublic(getShortUuidFromPossibleUrl(args.asset_short_uuid), args.public_flag == "on");
  print(str(json.dumps(asset, indent=2)))

def configure(args):
  newNiraConfig = NiraConfig()

  newNiraConfig.org = input("Enter your Nira organization name including .nira.app, e.g. yourorg.nira.app\nNira organization name: ")

  if not newNiraConfig.org.endswith(".nira.app"):
    print("\nERROR: Nira organization names must end with .nira.app")
    print("\nIf you have a custom URL, you should still use the original .nira.app org name assigned to you when interacting with the API")
    sys.exit(1)

  print("Enter your Nira API key, generated from within your Nira admin dashboard's API Keys section, e.g. https://your-org.nira.app/admin/apikeys")
  print("NOTE: Your API key will not print to the screen as you enter it!")

  apikey = getpass("Nira API key (77 characters, will not echo!): ")

  if len(apikey) != 77:
    print("ERROR: The API key must be 77 characters!")
    sys.exit(1)

  newNiraConfig.apiKeyId, newNiraConfig.apiKeySecret = apikey.split(":")

  if len(newNiraConfig.apiKeyId) != 36:
    print("ERROR: Invalid API Key! The id portion must be 36 characters.")
    sys.exit(1)

  if len(newNiraConfig.apiKeySecret) != 40:
    print("ERROR: Invalid API Key! The secret portion must be 40 characters.")
    sys.exit(1)

  nirac = NiraClient(niraConfig=newNiraConfig, printRequests=args.print_requests, printResponses=args.print_responses, printAndDumpRequests=args.print_and_dump_requests, useClientSideAuthTokenExchange=args.use_client_side_auth_token_exchange, requestApiTokenExpirationTime=args.request_api_token_expiration_time)
  nirac.authorize() # This will raise if the authorization fails
  newNiraConfig.write()

  print("Authorization successful, configuration saved.")

  curNiraConfig = NiraConfig()
  curNiraConfig.read()

  if curNiraConfig.org != newNiraConfig.org:
    defaultOrgWrite = input("Your default org is currently set to %s. Would you like to set it to %s instead [y/n]? "%(curNiraConfig.org, newNiraConfig.org))

    if defaultOrgWrite == 'y':
      newNiraConfig.write(forceDefaultOrgWrite=True)
      print("Changed default org to %s (was %s)" %(newNiraConfig.org, curNiraConfig.org))
    else:
      print("Keeping existing default org %s" %curNiraConfig.org)

calloutsExportParser.set_defaults(func=exportCallouts)
calloutsImportParser.set_defaults(func=importCallouts)
assetCreateParser.set_defaults(func=assetCreate)
assetDeleteParser.set_defaults(func=assetDelete)
assetDeleteBeforeParser.set_defaults(func=assetDeleteBefore)
assetShareUserAddParser.set_defaults(func=assetShare)
assetSetPublicParser.set_defaults(func=assetSetPublic)
assetAddfilesParser.set_defaults(func=assetFilesAdd)
assetListParser.set_defaults(func=assetList)
groupListParser.set_defaults(func=groupList)
groupGetParser.set_defaults(func=groupGet)
groupDeleteParser.set_defaults(func=groupDelete)
groupCreateParser.set_defaults(func=groupCreate)
configureParser.set_defaults(func=configure)
userSessionsDeleteParser.set_defaults(func=sessionsExpire)

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
