# Copyright (C) 2019 Nira, Inc. - All Rights Reserved

import time, sys
from niraclient import NiraClient, NiraUploadInfo, NiraJobStatus, isoUtcDateParse
import argparse
import requests
import datetime
import traceback

parser = argparse.ArgumentParser(description='Nira Client CLI')
parser.add_argument('--apikey', required=True, type=str)
parser.add_argument('--url', required=True, type=str)
parser.add_argument('--useremail', type=str, default='', help="Specifies the user account that certain API operations occur under. For example, if an asset upload is performed, that user's name will appear in the `Uploader` column of Nira's asset listing page. If this argument is not provided, the first admin user found in the user database will be used.")

group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--upload', dest="asset_path", default=[], nargs='+', type=str, help='A list of asset paths to upload and prints a URL for the asset')
parser.add_argument('--wait-for-asset-processing', dest='wait_max_seconds', default=0, type=int, help='If specified, when using --upload, wait up to WAIT_MAX_SECONDS for the asset to be processed on the server before returning. If this argument is not provided, the command will return immediately after upload, and asset processing may not have finished yet. If an error occurs, the command will exit with a non-zero status.')
group.add_argument('--show-updated-assets-every', dest='update_seconds', default=0, type=int, help='Polls the server every UPDATE_SECONDS, showing any asset updates that have occurred since the last poll.')
group.add_argument('--show-updated-assets-within', dest='seconds_ago', default=0, type=int, help='Show asset updates that have occurred within SECONDS_AGO')

args = parser.parse_args()

nirac = NiraClient(args.url, args.apikey, args.useremail)

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
    uploadInfo = nirac.uploadAsset(args.asset_path)

    if args.wait_max_seconds > 0:
      processingStatus = nirac.waitForAssetProcessing(uploadInfo.assetJobId, timeoutSeconds = args.wait_max_seconds)
      if processingStatus == NiraJobStatus.Processed:
        print(uploadInfo.assetUrl)
        sys.exit(0)
      else:
        print(processingStatus)
        sys.exit(1)
    else:
      print(uploadInfo.assetUrl)
      sys.exit(0)
  elif args.seconds_ago:
    sinceDate = datetime.datetime.utcnow() - datetime.timedelta(seconds=args.seconds_ago)
    assets = nirac.getAssetsUpdatedSince(sinceDate)
    formattedUpdates = formatAssetUpdates(assets, sinceDate)
    for formattedUpdate in formattedUpdates:
      print formattedUpdate
  elif args.update_seconds:
    lastUpdateTime = datetime.datetime.utcnow()

    while True:
      updateTime = datetime.datetime.utcnow()
      assets = nirac.getAssetsUpdatedSince(lastUpdateTime)
      formattedUpdates = formatAssetUpdates(assets, lastUpdateTime)

      for formattedUpdate in formattedUpdates:
        print formattedUpdate

      time.sleep(args.update_seconds)
      lastUpdateTime = updateTime

except requests.exceptions.HTTPError as error:
  print(error)
  print(error.response.text)
  sys.exit(1)
except (KeyboardInterrupt, SystemExit):
  raise
except Exception as e:
  print(traceback.format_exc())
  sys.exit(1)
