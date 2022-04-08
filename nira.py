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
from niraclient import NiraClient, NiraUploadInfo, NiraJobStatus, NiraConfig, isoUtcDateParse
import argparse
import requests.exceptions
import datetime
import traceback
import json
from getpass import getpass

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

subparsers = parser.add_subparsers(help='Operation', dest='Operation')
subparsers.required = True

configureParser = subparsers.add_parser('configure', help='Perform initial configuration. This is required to use any Nira API commands.')

assetParser = subparsers.add_parser('asset', help='Perform asset related operations')
assetSubParser = assetParser.add_subparsers(help='Asset related operations', dest='AssetOperation')
assetSubParser.required = True

userParser = subparsers.add_parser('user', help='Perform user related operations')
userSubParser = userParser.add_subparsers(help='User related operations', dest='UserOperation')
userSubParser.required = True

userPreauthParser = userSubParser.add_parser('preauth', help='''Generates and prints a preauthentication uid and token for a user. This invalidates any prior preauthentication token for the user. It also creates the user, if they don't already exist''')
userPreauthParser.add_argument('--name', type=str, default=None, help='''Name for user. This is optional, and by default will use the text prior to the '@' in the email address. The specified name is only used if the user doesn't already exist; Including parameter will not update existing user records.''')
userPreauthParser.add_argument('email', type=str, help='User email')

def addUploadOptionsToParser(thisParser):
  thisParser.add_argument('--no-upload-compression', action='store_false', dest='use_upload_compression', help="Disables the use of automatic upload compression. Upload compression is enabled by default. You may wish to disable it if you have a particularly capable upstream network throughput (1gbps+) or have concerns about CPU utilization on the machine doing the uploading.")
  thisParser.add_argument('--wait-for-asset-processing', dest='wait_max_seconds', default=3600, type=int, help='When using --upload, wait up to WAIT_MAX_SECONDS for the asset to be processed on the server before returning. If set to 0, the command will return immediately after upload, and asset processing will not have finished yet. Note, --upload will not print an asset url unless the asset has finished processing, so it is best to use a sufficiently large value for this argument. If an error occurs during upload or processing, the command will exit with a non-zero status and print an error message.')

assetCreateParser = assetSubParser.add_parser('create', help='Create a new asset, upload the provided files to it, then print a URL to the resulting asset on stdout or an error message if unsuccessful.', formatter_class=SmartFormatter)
assetCreateParser.add_argument('name', type=str, metavar='asset_name', help='A name for the asset. If an asset with this name already exists, an error message will be printed. If you wish to add files to an existing asset, use the addfiles command, instead.')
assetCreateParser.add_argument('type', choices=["default", "sculpt", "photogrammetry", "volumetric_video"], help="Specifies the type of the asset.")
assetCreateParser.add_argument('files', default=[], nargs='*', type=str, help=uploadFilesHelpText)
addUploadOptionsToParser(assetCreateParser)

assetSharingParser = assetSubParser.add_parser('sharing', help='Perform asset sharing related operations')
assetSharingSubParser = assetSharingParser.add_subparsers(help='Asset sharing related operations', dest='AssetSharingOperation')
assetSharingSubParser.required = True

assetUserParser = assetSharingSubParser.add_parser('user', help='Managing sharing of an asset for particular users')
assetUserSubParser = assetUserParser.add_subparsers(help='Asset sharing related operations', dest='AssetSharingUserOperation')
assetUserSubParser.required = True
assetShareUserAddParser = assetUserSubParser.add_parser('add', help='Share asset with a user specified by email.')
assetShareUserAddParser.add_argument('asset_short_uuid', type=str, metavar='asset_short_uuid', help='A short uuid or URL for an existing asset. If an asset with this name does not exist, an error message will be printed.')
assetShareUserAddParser.add_argument('user_email', type=str, help='Specify a user by email')
assetShareUserAddParser.add_argument('role', type=str, help='Role name. Could be "viewer" or "contributor"')
assetShareUserAddParser.add_argument('expiration_date', type=str, help='Optional expiration datetime in ISO format. e.g. 2022-02-24T23:00:00.000Z', nargs='?')

assetSetPublicParser = assetSharingSubParser.add_parser('set-public', help='Set the public sharing flag on or off for an asset')
assetSetPublicParser.add_argument('asset_short_uuid',  metavar='asset_short_uuid', help='A short uuid or URL for an existing asset. If an asset with this name does not exist, an error message will be printed.')
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
    niraClient = NiraClient(org=args.org, printRequests=args.print_requests, printResponses=args.print_responses, printAndDumpRequests=args.print_and_dump_requests)
    return niraClient
  except Exception as e:
    print("ERROR: " + str(e))
    print("\nMake sure you run '%s configure'!"% sys.argv[0])
    sys.exit(1)

def preauthUser(args):
  nirac = getNiraClient(args)

  user_info = nirac.preauthUser(args.email, args.name)

  print(str(json.dumps(user_info, indent=2)))

  sys.exit(1)

def assetShare(args):
  nirac = getNiraClient(args)

  asset_invitation = nirac.shareAsset(args.asset_short_uuid, args.user_email, args.role, args.expiration_date)

  print(str(json.dumps(asset_invitation, indent=2)))

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

  uploadInfo = nirac.uploadAsset(files, args.type, args.name, useCompression=args.use_upload_compression, maxWaitSeconds=args.wait_max_seconds)

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

  uploadInfo = nirac.uploadAsset(files, asset['type'], asset['name'], useCompression=args.use_upload_compression, maxWaitSeconds=args.wait_max_seconds)

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

def assetSetPublic(args):
  nirac = getNiraClient(args)

  asset = nirac.setPublic(args.asset_short_uuid, args.public_flag == "on");
  print(str(json.dumps(asset, indent=2)))

def configure(args):
  newNiraConfig = NiraConfig()

  newNiraConfig.org = input("Enter your Nira organization name including .nira.app, e.g. yourorg.nira.app\nNira organization name: ")

  if not newNiraConfig.org.endswith(".nira.app"):
    print("\nERROR: Nira organization names must end with .nira.app")
    print("\nIf you have a custom URL, you should still use the original .nira.app org name assigned to you when interacting with the API")
    sys.exit(1)

  print("Enter your Nira API key ID, generated from within your Nira admin dashboard's API Keys section, e.g. https://your-org.nira.app/admin/apikeys")
  newNiraConfig.apiKeyId = input("Nira API key ID (36 characters): ")

  if len(newNiraConfig.apiKeyId) != 36:
    print("ERROR: The API key ID must be 36 characters!")
    sys.exit(1)

  print("Enter your Nira API key secret, also generated from within your Nira admin dashboard's API Keys section")
  print("NOTE: Your API key secret will not print to the screen as you enter it!")
  newNiraConfig.apiKeySecret = getpass("Nira API key secret (40 characters, will not echo!): ")

  if len(newNiraConfig.apiKeySecret) != 40:
    print("ERROR: The API key secret must be 40 characters (You entered %)!" % len(newNiraConfig.apiKeySecret))
    sys.exit(1)

  nirac = NiraClient(niraConfig=newNiraConfig, printRequests=args.print_requests, printResponses=args.print_responses, printAndDumpRequests=args.print_and_dump_requests)
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

assetCreateParser.set_defaults(func=assetCreate)
assetShareUserAddParser.set_defaults(func=assetShare)
assetSetPublicParser.set_defaults(func=assetSetPublic)
assetAddfilesParser.set_defaults(func=assetFilesAdd)
assetListParser.set_defaults(func=assetList)
userPreauthParser.set_defaults(func=preauthUser)
configureParser.set_defaults(func=configure)

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
