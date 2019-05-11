# Copyright (C) 2015-2019 Nira, Inc. - All Rights Reserved

import time, sys
from niraclient import NiraClient, NiraUploadInfo, NiraJobStatus
import argparse

parser = argparse.ArgumentParser(description='Nira Client CLI')
parser.add_argument('--apikey', required=True, type=str)
parser.add_argument('--niraurl', required=True, type=str)

usergroup = parser.add_mutually_exclusive_group(required=True)
usergroup.add_argument('--useremail', type=str, help="User email of Nira account to create records with")
usergroup.add_argument('--userid', type=int, help="User ID of Nira account to create records with")

group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--upload', dest="asset_path", default=[], nargs='+', type=str, help='A list of asset paths to upload and prints a URL for the asset')
parser.add_argument('--wait-for-asset-processing', dest='wait_max_seconds', default=0, type=int, help='If specified, when using --upload, wait up to WAIT_MAX_SECONDS for the asset to be processed on the server before returning. If not specified, the command will return immediately after upload, and asset processing may not have finished yet.')
group.add_argument('--list-assets-updated-within', dest='seconds_ago', default=[], type=int, help='Print a list of asset records (in JSON) that have been updated within SECONDS_AGO')

args = parser.parse_args()

nirac = NiraClient(args.niraurl, args.apikey)
if args.useremail is not None:
  user = nirac.getUserByEmail(args.useremail)
  nirac.setUserById(user["id"])
else:
  nirac.setUserById(args.userid)

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
