# Copyright (C) 2019 Nira, Inc. - All Rights Reserved

import time, sys
from niraclient import NiraClient, NiraUploadInfo, NiraJobStatus
import argparse
import requests

parser = argparse.ArgumentParser(description='Nira Client CLI')
parser.add_argument('--apikey', required=True, type=str)
parser.add_argument('--url', required=True, type=str)
parser.add_argument('--useremail', type=str, default='', help="Specifies the user account that certain API operations occur under. For example, if an asset upload is performed, that user's name will appear in the `Uploader` column of Nira's asset listing page. If this argument is not provided, the first admin user found in the user database will be used.")

group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--upload', dest="asset_path", default=[], nargs='+', type=str, help='A list of asset paths to upload and prints a URL for the asset')
parser.add_argument('--wait-for-asset-processing', dest='wait_max_seconds', default=0, type=int, help='If specified, when using --upload, wait up to WAIT_MAX_SECONDS for the asset to be processed on the server before returning. If this argument is not provided, the command will return immediately after upload, and asset processing may not have finished yet. If an error occurs, the command will exit with a non-zero status.')
group.add_argument('--list-assets-updated-within', dest='seconds_ago', default=[], type=int, help='Print a list of asset records (in JSON) that have been updated within SECONDS_AGO')

args = parser.parse_args()

nirac = NiraClient(args.url, args.apikey, args.useremail)

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
    assets = nirac.getAssetsUpdatedSince(time.time() - args.seconds_ago)
    print(assets)
except requests.exceptions.HTTPError as error:
  print(error)
  print(error.response.text)
  sys.exit(1)
except (KeyboardInterrupt, SystemExit):
  raise
except Exception as e:
  print(e)
  sys.exit(1)
