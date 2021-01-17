#!/usr/bin/env python
#
# Copyright (C) Nira, Inc. - All Rights Reserved

from __future__ import print_function

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

# To verify we're using the bundled copy of requests
#print(requests.__file__)

parser = argparse.ArgumentParser(description='Nira Client CLI')
parser.add_argument('--apikey', required=True, type=str)
parser.add_argument('--url', required=True, type=str)
parser.add_argument('--useremail', type=str, default='', help="Specifies the user account that certain API operations occur under. For example, if an asset upload is performed, that user's name will appear in the `Uploader` column of Nira's asset listing page. If this argument is not provided, the first admin user found in the user database will be used.")
parser.add_argument('--upload-threads', dest='uploadthreads', type=int, default=4, help="Number of simultaneous upload connection threads to use. Using mulitple simultaneous connections for uploads can accelerate them significantly, particularly over long-distance WAN links.")
parser.add_argument('--upload-chunk-size', dest='uploadchunksize', type=int, default=1024 * 1024 * 10, help="Size of each uploaded chunk, in bytes. When uploading, files will be divided into chunks of this size and sent to the Nira server using the number of threads specified by the --upload-threads option.")
parser.add_argument('--no-upload-compression', action='store_false', dest='use_upload_compression', help="Disables the use of automatic upload compression. Upload compression is enabled by default. You may wish to disable it if you have a particularly upstream network speed (1gbps+) or have concerns about CPU utilization on the machine doing the uploading.")

group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--upload', dest="asset_path", default=[], nargs='+', type=str, help='Takes a space separated list of file paths to upload, uploads them, then prints a URL to the resulting asset on stdout, or an error message if unsuccessful. Accompanying files should also be included (e.g. texture files). At least one of the files should be a primary scene file (ma, mb, zpr, etc)')
parser.add_argument("--asset-type", choices=["default", "sculpt", "photogrammetry", "volumetric_video"], default='default', dest="asset_type")
parser.add_argument("--asset-name", dest="asset_name", help="When using --upload, specify an asset name")
parser.add_argument("--asset-id", dest="asset_id", help='When using --upload, specify an asset id')
group.add_argument('--download', dest="download", default=[], nargs=1, type=str, help='Takes two parameters: An asset\'s URL (or the asset\'s short UUID) and a local destination folder to store the asset. The asset and all of its accompanying assets will be downloaded into this folder.')
group.add_argument('--get-state', dest="get_asset_state_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID) and returns the latest state for the asset.')
group.add_argument('--set-state', dest="set_asset_state_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID), reads state JSON from stdin, and merges this state to the asset on the Nira server.')
group.add_argument('--set-metadata', dest="set_metadata_asset_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID), reads metadata JSON from stdin, and attaches this metadata to the asset on the Nira server. Also see --metadata-level.')
group.add_argument('--get-metadata', dest="get_metadata_asset_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID) and returns metadata for the asset or assetversion. Also see --metadata-level.')
group.add_argument('--get-manifest', dest="get_manifest_asset_url", default='', type=str, help='Takes an asset\'s URL (or the asset\'s short UUID) and returns the manifest for the asset.')
parser.add_argument('--metadata-level', dest='metadata_level', choices=["assetversion", "asset"], default='assetversion', help='When using --set-metadata or --get-metadata, specifying "--metadata-level assetversion" or "--metadata-level asset" controls whether to set/retrieve the metadata attached to the assetversion specified, or the entire asset.')
parser.add_argument('--is-sequence', action='store_true', dest='is_sequence', help='If specified, when using --upload, defines that the assets are part of an animated sequence.')
parser.add_argument('--compress-textures', action='store_true', dest='compress_textures', help='If specified, when using --upload, compresses textures on the server.')
parser.add_argument('--ignore-mtl', action='store_true', dest='ignore_mtl', help='If specified, when using --upload and uploading an OBJ file, do not use the texture assignments and material paramters specified in the MTL file.')
parser.add_argument('--no-vertex-colors', action='store_true', dest='no_vertex_colors', help='If specified, when using --upload, do not use the vertex colors specified in the scene file(s)')
parser.add_argument('--no-normals', action='store_true', dest='no_normals', help='If specified, when using --upload, do not use the normals specified in the scene file(s), and do not generate smooth normals on the server.')
parser.add_argument('--wait-for-asset-processing', dest='wait_max_seconds', default=3600, type=int, help='When using --upload, wait up to WAIT_MAX_SECONDS for the asset to be processed on the server before returning. If set to 0, the command will return immediately after upload, and asset processing will not have finished yet. Note, --upload will not print an asset url unless the asset has finished processing, so it is best to use a sufficiently large value for this argument. If an error occurs during upload or processing, the command will exit with a non-zero status and print an error message.')
group.add_argument('--show-updated-assets-every', dest='update_seconds', default=0, type=int, help='Polls the server every UPDATE_SECONDS, showing any asset updates that have occurred since the last poll. The command does not exit unless it encounters an error or is interrupted by the user.')
group.add_argument('--show-updated-assets-within', dest='seconds_ago', default=0, type=int, help='Show any asset updates that have occurred within SECONDS_AGO, then exit.')

args = parser.parse_args()

nirac = NiraClient(args.url, args.apikey, userEmail=args.useremail, uploadThreadCount=args.uploadthreads, uploadChunkSize=args.uploadchunksize)

def formatAssetUpdates(assetsData, lastUpdateTime):
  formattedAssetUpdates = []

  """
   An asset data record looks like this:
  {
    'status': 'processed',
    'uuid': 'adb693ff-3e7b-4827-b7f0-36867dab17aa',
    'approvalStatus': 'needs_review',
    'filename': 'dragon_attack.mb',
    'newestMarkupTime': '2019-05-13T04:14:53.163Z',
    'version': 2,
    'createdAt': '2019-04-11T10:15:52.152Z',
    'uploader': 'admin',
    'updatedAt': '2019-05-13T04:14:53.146Z',
    'subassetCount': '0',
    'openMarkupCount': '7',
    'urlUuid': 'rbaT_z57SCe38DaGfasXqg'
  }
  """

  # We can format this into a friendlier format as below.
  for assetData in assetsData:
    updateOutput  = ""
    updateOutput += "Asset: {} (version: {})\n".format(assetData['filename'], assetData['version'])

    newestMarkupTime = 0
    if assetData['newestMarkupTime'] is not None:
      newestMarkupTime = isoUtcDateParse(assetData['newestMarkupTime'])
    updatedAt = isoUtcDateParse(assetData['updatedAt'])
    createdAt = isoUtcDateParse(assetData['createdAt'])

    if newestMarkupTime and newestMarkupTime > lastUpdateTime:
      updateOutput += "\tNew Markups at {:%Y/%m/%d %H:%M:%S} UTC!\n".format(newestMarkupTime) # Note: Can use pytz or similar to get local times if desired.
    elif createdAt > lastUpdateTime:
      updateOutput += "\tUploaded at {:%Y/%m/%d %H:%M:%S} UTC!\n".format(createdAt)
    elif updatedAt > lastUpdateTime:
      updateOutput += "\tUpdated at {:%Y/%m/%d %H:%M:%S} UTC!\n".format(updatedAt)

    if assetData['status'] != 'processed':
      updateOutput += "\tStatus:\n".format(assetData['status'])

    updateOutput += "\tApproval Status: {}\n".format(assetData['approvalStatus'])
    if assetData['openMarkupCount']:
      updateOutput += "\tMarkups: {}\n".format(assetData['openMarkupCount'])
    updateOutput += "\tURL: {}\n".format(nirac.formatAssetUrl(assetData['urlUuid']))

    formattedAssetUpdates.append(updateOutput)

  return formattedAssetUpdates

try:
  if len(args.asset_path) > 0:
    uploadInfo = nirac.uploadAsset(args.asset_path, assetType=args.asset_type, assetName=args.asset_name, assetId=args.asset_id, compressTextures=args.compress_textures, noVertexColors=args.no_vertex_colors, noNormals=args.no_normals, ignoreMtl=args.ignore_mtl, useCompression=args.use_upload_compression, maxWaitSeconds=args.wait_max_seconds)

    if uploadInfo.jobStatus == NiraJobStatus.Processed:
      print(uploadInfo.assetUrl)
      sys.exit(0)

    print(uploadInfo.jobStatus)
    sys.exit(1)
  elif len(args.set_metadata_asset_url):
    metadataStr = ''
    for line in sys.stdin:
      metadataStr += line.rstrip()
    nirac.setAssetMetadata(args.set_metadata_asset_url, args.metadata_level, metadataStr)
  elif len(args.get_manifest_asset_url):
    manifest = nirac.getAssetManifest(args.get_manifest_asset_url)
    print(json.dumps(manifest))
  elif len(args.get_metadata_asset_url):
    metadataDict = nirac.getAssetMetadata(args.get_metadata_asset_url, args.metadata_level)
    print(json.dumps(metadataDict))
  elif len(args.get_asset_state_url):
    stateDict = nirac.getAssetState(args.get_asset_state_url)
    print(json.dumps(stateDict))
  elif len(args.set_asset_state_url):
    stateStr = ''
    for line in sys.stdin:
      stateStr += line.rstrip()
    nirac.setAssetState(args.set_asset_state_url, stateStr)
  elif len(args.download) == 2:
    nirac.downloadAsset(args.download[0], args.download[1])
  elif args.seconds_ago:
    sinceDate = datetime.datetime.utcnow() - datetime.timedelta(seconds=args.seconds_ago)
    assets = nirac.getAssetsUpdatedSince(sinceDate)
    formattedUpdates = formatAssetUpdates(assets, sinceDate)
    for formattedUpdate in formattedUpdates:
      print(formattedUpdate)
  elif args.update_seconds:
    lastUpdateTime = datetime.datetime.utcnow()

    while True:
      updateTime = datetime.datetime.utcnow()
      assets = nirac.getAssetsUpdatedSince(lastUpdateTime)
      formattedUpdates = formatAssetUpdates(assets, lastUpdateTime)

      for formattedUpdate in formattedUpdates:
        print(formattedUpdate)

      time.sleep(args.update_seconds)
      lastUpdateTime = updateTime

except requests.exceptions.HTTPError as error:
  print(error, file=sys.stderr)
  print(error.response.text, file=sys.stderr)
  sys.exit(1)
except (KeyboardInterrupt, SystemExit):
  raise
except Exception as e:
  print(traceback.format_exc(), file=sys.stderr)
  sys.exit(1)
