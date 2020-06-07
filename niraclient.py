# Copyright (C) Nira, Inc. - All Rights Reserved

from __future__ import print_function
import uuid
import os
myDir = os.path.dirname(os.path.realpath(__file__))
myDir += "/deps"

import sys
sys.path.insert(0, myDir)

from datetime import datetime
import time
import math
import multiprocessing.dummy as mp
import threading
import json
import requests

tls = threading.local()

def isoUtcDateParse(isoDateStr):
  """
  Parses a UTC ISO-8601 date/time string to a datetime object.

  Args:
  isoDateStr(string): A UTC ISO-8601 date/time string of the following form: "2019-05-13T04:14:53.163Z"
  """
  return datetime.strptime(isoDateStr, '%Y-%m-%dT%H:%M:%S.%fZ')

class NiraClient:
  """
  A collection of useful client -> server methods for Nira.

  Includes methods for uploading files, checking for recently updated assets,
  whether an asset has finished being processed by Nira, and a few other things.
  """

  def __init__(self, url, apiKey, userEmail = '', uploadThreadCount = 4, uploadChunkSize = 1024 * 1024 * 10):
    """
    Constructor.

    Args:
    url(string): A base URL to a Nira server, such as "https://example.nira.app".
    apiKey(string): An API key
    userEmail(string): Specifies the user account that certain API operations occur under.
                       For example, if an asset upload is performed, that user's name will appear
                       in the "Uploader" column of Nira's asset listing page. If this argument is
                       unspecified, the first admin user found in the database will be used.
    """
    self.url = url
    self.apiKey = apiKey
    self.userEmail = userEmail
    self.uploadThreadCount = uploadThreadCount
    self.uploadChunkSize = uploadChunkSize

    if not self.url.endswith("/"):
      self.url += "/"

    self.headerParams = {}
    self.headerParams['x-api-key'] = self.apiKey;
    if self.userEmail:
      self.headerParams['x-user-email'] = self.userEmail;

  def getUserByEmail(self, email):
    """
    Retrieve a user account record via the email address.

    Args:
      email (str): Email address of the account you wish to retrieve

    Returns:
      User account record

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    markupsEndpoint = self.url + "users"

    userQueryParams = {
        'email': email,
        '$paginate': "false",
        }

    r = requests.get(url = markupsEndpoint, params=userQueryParams, headers=self.headerParams)
    r.raise_for_status()

    user = r.json()
    if len(user) > 0:
      return user[0]
    else:
      return []

  def getAssetsUpdatedSince(self, since):
    """
    Returns all assets updated since a certain timestamp value.
    Assets get updated upon upload, when a new markup is created for that asset, or upon status change.

    Args:
      since (datetime object in UTC): Assets updated after this datetime will be returned. Must be in UTC.

    Returns:
      List of asset records that were updated at some point after the provided timestamp value

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    markupsEndpoint = self.url + "assets"

    updatedSince = since.strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
    assetQueryParams = {
        '$groupByFile': "true",
        '$paginate': "false",
        '$updatedSince': updatedSince,
      }

    r = requests.get(url = markupsEndpoint, params=assetQueryParams, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def getAssetJob(self, jobId):
    """
    Retrieve a user account record via the email address.

    Args:
      email (str): Email address of the account you wish to retrieve

    Returns:
      User account record (dict)

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    jobEndpoint   = self.url + "jobs" + "/" + str(jobId)
    r = requests.get(url = jobEndpoint, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def waitForAssetProcessing(self, assetJobId, timeoutSeconds = 600):
    """
    Polls the server until the asset is processed, then returns its status.
    For smaller assets (OBJ files less than a few hundred GB), this usually happens within a few seconds.
    For very large assets (e.g. Multi-GB zbrush files or large OBJ sequences), it could take a couple minutes.

    Args:
      assetJobId (int): The numeric id of the asset job. This can be found in the asset record returned from uploadAsset.
      timeoutSeconds (int): Maximum number of seconds to wait for a result from the server.

    Returns:
      A `NiraJobStatus` object property indicating the final status of the processing job.

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """

    sleepTime = 2
    totalSleepTime = 0

    while True:
      updatedJob = self.getAssetJob(assetJobId)

      if updatedJob['status'] == 'processed':
        return NiraJobStatus.Processed

      if updatedJob['status'] == 'processed_with_errors':
        return NiraJobStatus.ProcessingError

      totalSleepTime += sleepTime
      if (totalSleepTime > timeoutSeconds):
        break

      time.sleep(sleepTime)

    return NiraJobStatus.TimedOut

  def setAssetMetadata(self, assetUrlOrShortUuid, level, metadata):
    """
    Given an asset's short UUID or URL, a "asset" or "assetversion" level specifiction, and a user-defined metadata dictionary, attach the metadata to the resource.
    This replaces whatever metadata existed on the resource, if any.

    Args:
      assetUrlOrShortUuid (string):
                                    The short UUID or URL of an asset in Nira. The short UUID can be found in the URL of an asset when you're viewing it.
                                    For example, the short UUID of the following asset URL is "5R5VuRFkSs21FK8CddXM9Q":
                                    https://example.nira.app/a/5R5VuRFkSs21FK8CddXM9Q
                                    If you specify a full URL, this function will extract the short UUID for you.

      level (string):
                                    Either "asset" or "assetversion". This specifies whether you'd like the metadata to be attached to the specified version of
                                    the asset, or attached to the entire asset. Note, since a Nira short UUID/URL already encapsulates both an asset and its version,
                                    you needn't specify the version as a separate prameter when attaching metadata to an assetversion.

      metadata (dict|string):
                                    Metadata you wish to attach to the asset. This can be either a dict or a json string.
    Returns:
      True if the operation was successful.

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    shortUuid = assetUrlOrShortUuid[-22:]

    if (len(shortUuid) != 22):
      print("A valid asset URL or short UUID was not specified. It should be at least 22 characters.", file=sys.stderr)
      return False

    if level != "asset" and level != "assetversion":
      print("level parameter must be 'asset' or 'assetversion'!", file=sys.stderr)
      return False

    if type(metadata) is dict:
      userMetadata = json.dumps(metadata)
    else:
      try:
        json.loads(metadata)
      except Exception as e:
        raise Exception('Invalid metadata json string specified!')
      userMetadata = metadata

    metadataEndpoint   = self.url + "asset-metadata"
    metadataParams = {
        'asset_suuid': shortUuid,
        'level': level,
        'metadata': userMetadata,
        }

    r = requests.get(url = metadataEndpoint, params=metadataParams, headers=self.headerParams)
    r.raise_for_status()

    return True

  def getAssetMetadata(self, assetUrlOrShortUuid, level):
    """
    Given an asset's short UUID or URL and an "asset" or "assetversion" level specifiction, returns the metadata for the resource.

    Args:
      assetUrlOrShortUuid (string):
                                    The short UUID or URL of an asset in Nira. The short UUID can be found in the URL of an asset when you're viewing it.
                                    For example, the short UUID of the following asset URL is "5R5VuRFkSs21FK8CddXM9Q":
                                    https://example.nira.app/a/5R5VuRFkSs21FK8CddXM9Q
                                    If you specify a full URL, this function will extract the short UUID for you.

      level (string):
                                    Either "asset" or "assetversion". This specifies whether you'd like the metadata from the specified version of
                                    the asset, or from the entire asset. Note, since a Nira short UUID/URL already encapsulates both an asset and its version,
                                    you needn't specify the version as a separate prameter when request metadata for an assetversion.

    Returns:
      A dict of the metadata

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    shortUuid = assetUrlOrShortUuid[-22:]

    if (len(shortUuid) != 22):
      print("A valid asset URL or short UUID was not specified. It should be at least 22 characters.", file=sys.stderr)
      return False

    if level != "asset" and level != "assetversion":
      print("level parameter must be 'asset' or 'assetversion'!", file=sys.stderr)
      return False

    metadataEndpoint   = self.url + "asset-metadata"
    metadataParams = {
        'asset_suuid': shortUuid,
        'level': level,
        }

    r = requests.get(url = metadataEndpoint, params=metadataParams, headers=self.headerParams)
    r.raise_for_status()

    return json.loads(r.json())

  def getAssetManifest(self, assetUrlOrShortUuid):
    """
    Given an asset's short UUID or URL, download and return the asset's manifest JSON.
    An asset's manifest contains information about the asset and all of its accompanying assets (textures, etc).
    The asset's scene file (e.g. obj, fbx, ma, usd) will always be first in the manifest. Here's an example manifest::
      [
        {
          'path': 'tpot.obj',
          'version': 1,
          'type': 'scene',
          'id': 223
        },
        {
          'path': 'texture.png',
          'version': 1,
          'type': 'image',
          'id': 226
        },
      ]

    Args:
      assetUrlOrShortUuid (string):
                                    The short UUID or URL of an asset in Nira. The short UUID can be found in the URL of an asset when you're viewing it.
                                    For example, the short UUID of the following asset URL is "5R5VuRFkSs21FK8CddXM9Q":
                                    https://example.nira.app/a/5R5VuRFkSs21FK8CddXM9Q
                                    If you specify a full URL, this function will extract the short UUID for you.

      destDir:
                                    Directory to hold the asset files. This function will attempt to create the directory if it doesn't already exist.

    Returns:
      The manifest (dict). Upon failure, False

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.

    """
    shortUuid = assetUrlOrShortUuid[-22:]

    if (len(shortUuid) != 22):
      print("A valid asset URL or short UUID was not specified. It should be at least 22 characters.", file=sys.stderr)
      return False

    manifestEndpoint   = self.url + "asset-manifest"
    manifestParams = {
        'asset_suuid': shortUuid,
        }

    r = requests.get(url = manifestEndpoint, params=manifestParams, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def downloadAsset(self, assetUrlOrShortUuid, destDir):
    """
    Given an asset's short UUID or URL, download the asset file and all of its accompanying files from Nira into the specified directory.

    Args:
      shortUuid: The short UUID or URL of an asset in Nira. The short UUID can be found in the URL of an asset when you're viewing it.
                 For example, the short UUID of the following asset URL is `5R5VuRFkSs21FK8CddXM9Q`:
                 `https://example.nira.app/a/5R5VuRFkSs21FK8CddXM9Q`

                 If you specify a full URL, this function will extract the short UUID for you.

      destDir:   Directory to hold the asset files. This function will attempt to create the directory if it doesn't already exist.

    Returns:
      sceneFilepath (string) and material state (dict)

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """

    downloadEndpoint   = self.url + "asset-dl"

    manifest = self.getAssetManifest(assetUrlOrShortUuid)
    if manifest == False:
      return False

    if (not os.path.exists(destDir)):
      os.mkdir(destDir)

    if (not os.path.isdir(destDir)):
      print ("Directory could not be created: " + destDir, file=sys.stderr)
      return False

    sceneFilepath = False

    print ("asset manifest: " + str(manifest), file=sys.stderr)

    for asset in manifest['assets']:
      localFilepath = os.path.join(destDir, asset['path'])

      if not sceneFilepath:
        sceneFilepath = localFilepath

      #print ("Attempting download of:" + asset['path'] + " with asset id/version:  " + , file=sys.stderr)

      if (os.path.exists(localFilepath)):
        print ("Skipping download of:" + asset['path'] + "! Destination already exists:" + localFilepath, file=sys.stderr)
        continue

      downloadParams = {
          'assetpath_id': asset['id'],
          'asset_version': asset['version'],
          }

      # stream=True for efficient memory usage
      r = requests.get(url = downloadEndpoint, params=downloadParams, headers=self.headerParams, stream=True)
      r.raise_for_status()

      print ("Writing file:" + localFilepath + " of length:" + str(len(r.content)), file=sys.stderr)

      with open(localFilepath, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1048576):
          if chunk:
            f.write(chunk)
            # f.flush()

    state = manifest['state']
    return sceneFilepath, state

  def uploadAsset(self, assetpaths, isSequence=False, compressTextures=False):
    """
    Uploads an asset file and its accompanying files to Nira.

    Args:
      assetpaths: List of full paths to each file. The primary asset file (e.g. .ma, .mb, .zpr, .obj file) must be first in the list.
                  Accompanying texture/material files (optional) go after that. Paths can be absolute or relative to the runtime directory.

    Returns:
      A `NiraUploadInfo` object

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    jobsEndpoint   = self.url + "jobs"
    assetsEndpoint = self.url + "assets"

    for assetpath in assetpaths:
      if not os.path.exists(assetpath):
        raise IOError('File not found: ' + assetpath)

    batchUuid = str(uuid.uuid4())

    jobCreateParams = {
        'status': "validating",
        'batchId': batchUuid,
        'textureCompression': "BC1" if compressTextures else "none",
        }

    r = requests.post(url = jobsEndpoint, data=jobCreateParams, headers=self.headerParams)
    r.raise_for_status()
    job = r.json()

    parentAssetpathId = 0
    assets = []
    for assetpath in assetpaths:
      assetUuid=str(uuid.uuid4())
      fileName = os.path.basename(assetpath)
      filePath = assetpath

      assetCreateParams = {
          'fileName': fileName,
          'uuid': assetUuid,
          'parentAssetpathId': parentAssetpathId,
          'jobId': job['id'],
          'isSequence': isSequence,
          }

      r = requests.post(url = assetsEndpoint, data=assetCreateParams, headers=self.headerParams)
      r.raise_for_status()
      asset = r.json()
      assets.append(asset)

      if not parentAssetpathId:
        parentAssetpathId = asset['id']

      totalsize = os.path.getsize(filePath)
      totalparts = (totalsize//self.uploadChunkSize) + 1
      #print ("totalparts: " + str(totalparts), file=sys.stderr)

      def sendChunk(partidx):
        chunkoffset = partidx * self.uploadChunkSize

        if not hasattr(tls, 'fh'):
          tls.fh = open(filePath, 'rb')

        tls.fh.seek(chunkoffset)
        chunk = tls.fh.read(self.uploadChunkSize)

        if not chunk:
          return

        fields={
          'qquuid': assetUuid,
          'qqchunksize': str(len(chunk)),
          'qqfilename': fileName,
          'qqpartindex': str(partidx),
          'qqpartbyteoffset': str(chunkoffset),
          'qqtotalparts': str(totalparts),
          'qqtotalfilesize': str(totalsize),
          }

        files={ 'qqfile': (fileName, chunk) }

        headers = {}
        headers.update(self.headerParams)
        response = requests.post(self.url + 'asset-uploads', data=fields, files=files, headers=headers)

      def closeHandles(threadid):
        if hasattr(tls, 'fh'):
          tls.fh.close()
          delattr(tls, 'fh')

      p = mp.Pool(self.uploadThreadCount)
      p.map(sendChunk, range(0, totalparts))
      p.map(closeHandles, range(0, self.uploadThreadCount * 4))
      p.close()
      p.join()

      headers = {}
      headers.update(self.headerParams)
      payload={
          'qquuid': assetUuid,
          'qqfilename': fileName,
          'qqtotalfilesize': str(totalsize),
          'qqtotalparts': str(totalparts),
          }
      response = requests.get(self.url + 'asset-uploads-done', data=payload, headers=headers)

    jobPatchParams = {
        'status': "uploaded",
        'batchId': batchUuid,
        }
    r = requests.patch(url = jobsEndpoint + "/" + str(job['id']), data=jobPatchParams, headers=self.headerParams)
    r.raise_for_status()
    assetJob = r.json()

    uploadInfo = NiraUploadInfo()
    uploadInfo.assetUrl = self.formatAssetUrl(assets[0]['urlUuid'])
    uploadInfo.assetJobId = assetJob['id']
    uploadInfo.assets = assets

    return uploadInfo

  def formatAssetUrl(self, urlUuid):
    return self.url + "a/" + urlUuid

class NiraUploadInfo:
  """
  Holds the following properties:

  assetUrl (string):
    URL to the new asset.
  assetJobId (int):
    Numeric id of the asset upload job. Useful for querying the progress of asset processing (see waitForAssetProcessing method).
  assets:
    A list of asset records. Their order corresponds to the order of the assetpaths argument.
  """
  pass

class NiraJobStatus:
  Processed = "Processed"
  ProcessingError = "Processing Error"
  TimedOut = "Timed Out"
