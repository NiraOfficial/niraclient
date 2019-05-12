# Copyright (C) 2019 Nira, Inc. - All Rights Reserved

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
import uuid
import os
import time

class NiraClient:
  """
  A collection of useful client -> server methods for Nira.

  Includes methods for uploading files, checking for recently updated assets,
  whether an asset has finished being processed by Nira, and a few other things.
  """

  def __init__(self, url, apiKey, userEmail = ''):
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
    Assets get updated upon upload or when a new markup is created for that asset.

    Args:
      since (int): Timestamp value (seconds since epoch, UTC). Assets updated after this timestamp will be returned.

    Returns:
      List of asset records that were updated at some point after the provided timestamp value

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    markupsEndpoint = self.url + "assets"

    assetQueryParams = {
        '$groupByFile': "true",
        '$paginate': "false",
        '$updatedSince': since,
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
    For smaller assets (<100MB), this usually happens within a few seconds.
    For very large assets (e.g. Multi-GB zbrush files), it could take a couple minutes.

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

  def uploadAsset(self, assetpaths):
    """
    Uploads an asset file and its accompanying files to Nira.

    Args:
      assetpaths: List of full paths to each file. The primary asset file (e.g. .ma, .mb, .zpr, .obj file) must be first in the list.
                  Accompanying texture/material files (optional) go after that. Use absolute paths for all files.

    Returns:
      A `NiraUploadInfo` object

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    jobsEndpoint   = self.url + "jobs"
    assetsEndpoint = self.url + "assets"

    batchUuid = str(uuid.uuid4())

    jobCreateParams = {
        'status': "validating",
        'batchId': batchUuid,
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
          }

      r = requests.post(url = assetsEndpoint, data=assetCreateParams, headers=self.headerParams)
      r.raise_for_status()
      asset = r.json()
      assets.append(asset)

      if not parentAssetpathId:
        parentAssetpathId = asset['id']

      multipart_data = MultipartEncoder(
        fields={
          'qquuid': assetUuid,
          'qqfilename': fileName,
          'qqtotalfilesize': str(os.path.getsize(filePath)),
          'qqfile': (fileName, open(filePath, 'rb'), 'text/plain'),
          }
        )

      headers = {}
      headers.update(self.headerParams)
      headers['Content-Type'] = multipart_data.content_type
      response = requests.post(self.url + 'asset-uploads', data=multipart_data,
        headers=headers)

    jobPatchParams = {
        'status': "uploaded",
        'batchId': batchUuid,
        }
    r = requests.patch(url = jobsEndpoint + "/" + str(job['id']), data=jobPatchParams, headers=self.headerParams)
    r.raise_for_status()
    assetJob = r.json()

    uploadInfo = NiraUploadInfo()
    uploadInfo.assetUrl = self.url + "a/" + assets[0]['urlUuid']
    uploadInfo.assetJobId = assetJob['id']
    uploadInfo.assets = assets

    return uploadInfo

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
