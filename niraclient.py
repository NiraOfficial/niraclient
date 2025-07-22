# Copyright (C) Nira, Inc. - All Rights Reserved

from __future__ import print_function
import uuid
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

from requests_toolbelt.utils import dump

from datetime import datetime
from datetime import timedelta
import time
import math
import multiprocessing.dummy as mp
import threading
import json
import requests
import subprocess
import base64
import uuid
import platform

try:
  import configparser as configparser
except Exception:
  import ConfigParser as configparser

osSystem = platform.system()

if osSystem == "Windows":
  meowfileExe = myDir + "/meowhash/meowfile_win_x64.exe"
elif osSystem == "Linux":
  meowfileExe = myDir + "/meowhash/meowfile_linux_x64"
elif osSystem == "Darwin":
  if platform.machine() == "aarch64":
    meowfileExe = myDir + "/meowhash/meowfile_mac_arm64"
  else:
    meowfileExe = myDir + "/meowhash/meowfile_mac_x64"
else:
  sys.exit("Unrecognized OS: " + osSystem, file=sys.stderr)

# Always retry
from requests.adapters import HTTPAdapter

http = requests.Session()
from requests.packages.urllib3.util.retry import Retry
retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 401, 413, 429, 501, 502, 503, 504 ])

http.mount('http://', HTTPAdapter(max_retries=retries))
http.mount('https://', HTTPAdapter(max_retries=retries))

def responseHook(resp, *args, **kwargs):
  global dumpRequestInfo, dumpResponseInfo, printAndDumpRequestsToFiles

  try:
    if dumpRequestInfo or printAndDumpRequestsToFiles:

      requestDumpFilenamePrefix=''

      if printAndDumpRequestsToFiles:
        requestDumpFilenamePrefix="request-body"

      data = dump.dump_request(resp, b' ', b' ', None, requestDumpFilenamePrefix)
      print(data.decode('utf-8'), file=sys.stderr)

    if dumpResponseInfo:
      respdata = dump.dump_response(resp, b' ', b' ')
      print(respdata.decode('utf-8'), file=sys.stderr)

  except Exception as e:
    print(str(e), file=sys.stderr)

http.hooks["response"] = responseHook

try:
  from urllib.parse import urlparse
except ImportError:
  from urlparse import urlparse

# Defer import of zlib until uploadAsset is actually called to prevent a needless warning message.
zlib = False

tls = threading.local()

UPLOAD_CHUNK_SIZE = 1024 * 1024 * 20
FILE_MAX_THREAD_COUNT = 4
FILEPARTS_MAX_THREAD_COUNT = 4

NIRA_AUTH_URL = os.getenv("NIRA_AUTH_URL") or "https://auth.nira.app"
NIRA_CLIENT_CONFIG_PATH = (os.getenv("NIRA_CLIENT_CONFIG_PATH") or os.path.expanduser('~') or os.environ['HOME']) + "/.niraclient-config"

def isoUtcDateParse(isoDateStr):
  """
  Parses a UTC ISO-8601 date/time string to a datetime object.

  Args:
  isoDateStr(string): A UTC ISO-8601 date/time string of the following form: "2019-05-13T04:14:53.163Z"
  """
  return datetime.strptime(isoDateStr, '%Y-%m-%dT%H:%M:%S.%fZ')

class NiraConfig:
  """
  Holds the needed authorization configuration data for Nira API calls against
  a particular Nira organization.

  org (string):
    Nira organzation name. Must end with .nira.app. Required.
  apiKeyId (string):
    API key ID. Required.
  apiKeySecret (string):
    API key secret. Required.
  apiToken (string):
    API token.
    This is not required, and it may be populated by a call to authorize()
  apiTokenExpires (int):
    API token expiration time (seconds since epoch, UTC)
    This is not required, since it may be populated by a call to authorize()
  niraAuthUrl (string):
    For internal usage
  """
  def __init__(self):
    self.org = ''
    self.apiKey = ''
    self.apiKeyId = ''
    self.apiKeySecret = ''
    self.apiToken = ''
    self.niraAuthUrl = NIRA_AUTH_URL
    self.apiTokenExpires = 0

  def read(self, org=None, configFile=NIRA_CLIENT_CONFIG_PATH):
    niraConfig = configparser.ConfigParser()
    niraConfig.read(configFile)

    self.org = org

    if self.org is None and niraConfig.has_option("general", "org"):
      self.org = niraConfig.get("general", "org")

    if niraConfig.has_option(self.org, "apiKeyId"):
      self.apiKeyId = niraConfig.get(self.org, "apiKeyId")

    if niraConfig.has_option(self.org, "apiKeySecret"):
      self.apiKeySecret = niraConfig.get(self.org, "apiKeySecret")

    if niraConfig.has_option(self.org, "apiToken"):
      self.apiToken = niraConfig.get(self.org, "apiToken")

    if niraConfig.has_option(self.org, "apiTokenExpires"):
      self.apiTokenExpires = niraConfig.getint(self.org, "apiTokenExpires")

    if niraConfig.has_option(self.org, "niraAuthUrl"):
      self.niraAuthUrl = niraConfig.get(self.org, "niraAuthUrl")

  def write(self, configFile=NIRA_CLIENT_CONFIG_PATH, forceDefaultOrgWrite=False):
    niraConfigForWriting = configparser.ConfigParser()
    niraConfigForWriting.read(configFile)

    if not niraConfigForWriting.has_section(self.org):
      niraConfigForWriting.add_section(self.org)

    niraConfigForWriting.set(self.org, "apiToken",        self.apiToken)
    niraConfigForWriting.set(self.org, "apiTokenExpires", str(self.apiTokenExpires))

    niraConfigForWriting.set(self.org, "apiKeyId",     self.apiKeyId)
    niraConfigForWriting.set(self.org, "apiKeySecret", self.apiKeySecret)

    hasDefaultOrgSetting = niraConfigForWriting.has_section("general") and niraConfigForWriting.has_option("general", "org") and niraConfigForWriting.get("general", "org")
    totalOrgCount = len(set(niraConfigForWriting.sections()) - set(["general"]))

    # If there's only one org, or there's no default org defined at all, it's safe to write a default org entry.
    # Otherwise, we shouldn't assume the default should be changed -- the caller can decide to do so by passing
    # forceDefaultOrgWrite=True.
    if forceDefaultOrgWrite or not hasDefaultOrgSetting or totalOrgCount <= 1:
      if not niraConfigForWriting.has_section("general"):
        niraConfigForWriting.add_section("general")
      niraConfigForWriting.set("general", "org", self.org)

    with open(configFile, 'w') as f:
      niraConfigForWriting.write(f)

  def checkValidity(self):
    configErrMsg = " Did you run 'configure' or specify a NiraConfig for this org?"

    if not self.org:
      raise Exception("Org must be defined!" + configErrMsg)

    if not self.org.endswith(".nira.app"):
      raise Exception("Org must end with .nira.app!" + configErrMsg)

    if not self.apiKeyId:
      raise Exception("API key ID must be defined!" + configErrMsg)

    if not self.apiKeySecret:
      raise Exception("API key secret must be defined!" + configErrMsg)

    if not self.niraAuthUrl:
      raise Exception("niraAuthUrl must be defined!")

class NiraClient:
  """
  A collection of useful client -> server methods for Nira.

  Includes methods for uploading files, checking for recently updated assets,
  whether an asset has finished being processed by Nira, and a few other things.
  """

  def __init__(self, niraConfig=None, org=None, configFilePath=NIRA_CLIENT_CONFIG_PATH, printRequests=False, printResponses=False, printAndDumpRequests=False, useClientSideAuthTokenExchange=False, requestApiTokenExpirationTime=None):
    """
    Constructor.

    Args:
    configFilePath(string): The full path to a configuration file to store NiraConfig items.
                            If configFilePath is defined and NiraConfig is not, items will automatically be read
                            from this file, and renewed token updates will be automatically
                            be written to it. As long as the configuration file contains
                            the required NiraConfig items, the niraConfig object doesn't need
                            to be passed.
                            If configFilePath is set to null or the config file is currently unpopulated, a
                            populated niraConfig object must be passed to the NiraClient constructor.
                            To write a config file, construct a NiraClient, pass it a populated niraConfig
                            object, then call NiraClient.configure(forceConfigWrite=True)
                            The default configFilePath value is NIRA_CLIENT_CONFIG_PATH.
    niraConfig:             A `NiraConfig` object. Optional. If provided, all config items defined here
                            will be used rather than being read from the `configFilePath`.
    """
    self.configFilePath = configFilePath
    self.headerParams = {}
    self.config = niraConfig
    self.useClientSideAuthTokenExchange = useClientSideAuthTokenExchange
    self.requestApiTokenExpirationTime = requestApiTokenExpirationTime

    self.headerParams['User-Agent'] = 'niraclient.py'

    if self.config is None:
      self.config = NiraConfig()

      if self.configFilePath:
        self.config.read(org=org, configFile=self.configFilePath)
      else:
        raise Exception("No NiraConfig specified and no configFilePath provided!")

    global dumpRequestInfo, dumpResponseInfo, printAndDumpRequestsToFiles
    dumpRequestInfo = printRequests
    dumpResponseInfo = printResponses

    printAndDumpRequestsToFiles = printAndDumpRequests

    self.config.checkValidity()

  def authorize(self):
    """
    Ensures that the current authorization token (self.apiToken) is valid.
    If the current token does not appear valid (e.g. it's near expiration, or
    it simply isn't set at all), it will attempt to obtain a token using the
    auth server's /api-key-auth endpoint. The endpoint requires an API key ID and
    API key secret, both of which are available from the administrator dashboard
    of the Nira organization (https://your-org.nira.app/admin > API Keys > Add).

    Raises:
      HTTPError: An error occurred while communicating with the Nira auth server.
    """
    self.config.checkValidity()

    if self.useClientSideAuthTokenExchange:
      gotUpdatedToken = False

      if not self.config.apiToken or not self.isValidExpireTime(self.config.apiTokenExpires):
        authEndpoint = self.config.niraAuthUrl + "/api-key-auth"

        if self.requestApiTokenExpirationTime is not None:
          authEndpoint += "?expires=" + str(self.requestApiTokenExpirationTime)

        headers = {}
        headers['x-nira-org'] = self.config.org
        headers['x-api-key-id'] = self.config.apiKeyId
        headers['x-api-key-secret'] = self.config.apiKeySecret

        r = http.post(url = authEndpoint, headers=headers)
        r.raise_for_status()

        json = r.json();

        self.config.apiToken = json['token']
        self.config.apiTokenExpires = json['expires']

        gotUpdatedToken = True

      if not self.config.apiToken:
        raise Exception("API token must be defined!")

      self.headerParams['x-api-token'] = self.config.apiToken

      if self.configFilePath and gotUpdatedToken:
        self.config.write(self.configFilePath)
    else:
      self.headerParams['x-api-key'] = self.config.apiKeyId + ":" + self.config.apiKeySecret

    self.url = "https://" + self.config.org + "/"

  def isValidExpireTime(self, exp):
    if not exp:
      return False

    expiration_date = datetime.utcfromtimestamp(exp)
    date_now = datetime.utcnow()

    time_delta = timedelta(minutes=30)

    return date_now + time_delta < expiration_date

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
    self.authorize()

    jobEndpoint   = self.url + "api/jobs/" + str(jobId)
    r = http.get(url = jobEndpoint, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def assetUuidToAssetUrl(self, assetUuid):
    uuidForUrl = base64.urlsafe_b64encode(uuid.UUID(assetUuid).bytes).decode("ascii")
    uuidForUrl = uuidForUrl.replace("=", "")
    return self.formatAssetUrl(uuidForUrl)

  def assetUrlToAssetUuid(self, assetUrlOrShortUuid):
    shortUuid = assetUrlOrShortUuid[-22:]

    if (len(shortUuid) != 22):
      print("A valid asset URL or short UUID was not specified. It should be at least 22 characters.", file=sys.stderr)
      return False

    assetUuid = base64.urlsafe_b64decode(shortUuid)
    return assetUuid

  def waitForAssetProcessing(self, assetJobId, timeoutSeconds = 600):
    """
    Polls the server until the asset is processed, then returns its status.
    For smaller assets (OBJ files less than a few hundred GB), this usually happens within a few seconds.
    For very large assets (e.g. Multi-GB zbrush files or large OBJ sequences), it could take a couple minutes.

    Args:
      assetJobId (int): The numeric id of the asset job. This can be found in the asset record returned from uploadAsset.
      timeoutSeconds (int): Maximum number of seconds to wait for a result from the server.

    Returns:
      A `NiraUploadInfo` object.

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """

    sleepTime = 2
    totalSleepTime = 0

    uploadInfo = NiraUploadInfo()
    uploadInfo.assetJobId = assetJobId
    uploadInfo.jobStatus = NiraJobStatus.Pending

    while timeoutSeconds != 0 and True:
      self.authorize()
      updatedJob = self.getAssetJob(assetJobId)

      if updatedJob['status'] == 'complete':
        assetEndpoint = self.url + "api/assets/" + str(updatedJob['assetId'])
        r = http.get(url = assetEndpoint, headers=self.headerParams)
        r.raise_for_status()
        asset = r.json()

        uploadInfo.assetUrl = self.formatAssetUrl(asset['suuid'])
        uploadInfo.jobStatus = NiraJobStatus.Processed
        break

      if updatedJob['status'] == 'error':
        uploadInfo.jobStatus = NiraJobStatus.ProcessingError
        break

      totalSleepTime += sleepTime
      if (totalSleepTime > timeoutSeconds):
        break

      time.sleep(sleepTime)

    return uploadInfo

  def listAssets(self, query):
    self.authorize()

    assetEndpoint = self.url + "api/assets"

    r = http.get(url = assetEndpoint, params=query, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def listGroups(self, query):
    self.authorize()

    groupEndpoint = self.url + "api/groups"

    r = http.get(url = groupEndpoint, params=query, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def getGroup(self, groupUuid):
    self.authorize()

    if not groupUuid:
      raise IOError('group uuid is required!')

    groupEndpoint = self.url + "api/groups/" + groupUuid

    query = {}

    r = http.get(url = groupEndpoint, params=query, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def expireUserSessions(self, userEmail):
    self.authorize()

    if not userEmail:
      raise IOError('user email is required!')

    userSessionsDeleteEndpoint = self.url + "api/users/sessions/?email=" + userEmail

    query = {}

    r = http.delete(url = userSessionsDeleteEndpoint, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def deleteGroup(self, groupUuid):
    self.authorize()

    if not groupUuid:
      raise IOError('group uuid is required!')

    groupEndpoint = self.url + "api/groups/" + groupUuid

    query = {}

    r = http.delete(url = groupEndpoint, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def createGroup(self, groupName):
    self.authorize()

    groupEndpoint = self.url + "api/groups"

    groupCreateData = {
      'name': groupName,
    }

    r = http.post(url = groupEndpoint, json=groupCreateData, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def deleteAsset(self, shortAssetUuid):
    self.authorize()

    deleteAssetEndpoint = self.url + "api/assets/{suuid}".format(suuid = shortAssetUuid)

    r = http.delete(url = deleteAssetEndpoint, headers=self.headerParams)
    r.raise_for_status()

    return

  def deleteAssetsBefore(self, before, confirm):
    self.authorize()

    confirmval = 'false'

    if True == confirm:
      confirmval = 'true'

    deleteAssetEndpoint = self.url + "api/assets?before={before}&confirm={confirm}".format(before = before, confirm = confirmval)

    r = http.delete(url = deleteAssetEndpoint, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def importCallouts(self, shortAssetUuid, fileName, removeCalloutsBeforeImport=False, format=None):
    self.authorize()

    if not os.path.exists(fileName):
      raise IOError('File not found: ' + fileName)

    mime_type = None

    if format == None:
      format = os.path.splitext(fileName)[1][1:]

    if format in ['json', 'tsv', 'csv']:
      if format == 'json':
        mime_type = 'application/json'
      elif format == 'csv':
        mime_type = 'text/csv'
      elif format == 'tsv':
        mime_type = 'text/tab-separated-values'

    if mime_type == None:
      raise Exception('Input file type could not be determined: ' + fileName)

    with open(fileName, 'rb') as f:
      data = f.read()

    importCalloutsEndpoint = self.url + "api/assets/{suuid}/callouts/import?removeCalloutsBeforeImport={removeCalloutsBeforeImport}".format(
      suuid = shortAssetUuid,
      removeCalloutsBeforeImport = 1 if removeCalloutsBeforeImport else 0
    )

    if mime_type == 'application/json':
      json_data = json.loads(data)
      r = http.post(importCalloutsEndpoint, json=json_data, headers=self.headerParams)
    else:
      headers = self.headerParams.copy()
      headers['content-type'] = mime_type
      r = http.post(importCalloutsEndpoint, data=data.decode('utf-8'), headers=headers)

    r.raise_for_status()

    return r

  def exportCallouts(self, shortAssetUuid, format='json', coordsys='latlong', include='pointcallouts,polylinecallouts,photocallouts'):
    self.authorize()

    exportCalloutsEndpoint = self.url + "api/assets/{suuid}/callouts/export?format={format}&coordsys={coordsys}&include={include}".format(suuid = shortAssetUuid, format = format, coordsys = coordsys, include = include)

    r = http.get(url = exportCalloutsEndpoint, headers=self.headerParams)
    r.raise_for_status()

    return r

  def shareAsset(self, shortAssetUuid, email, role, expirationDate=None):
    self.authorize()

    shareAssetData = {
      'email': email,
      'role': role,
    }

    if expirationDate:
      shareAssetData['expirationDate'] = expirationDate

    shareAssetEndpoint = self.url + "api/assets/{suuid}/sharing/users".format(suuid = shortAssetUuid)

    r = http.post(url = shareAssetEndpoint, json=shareAssetData, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def setPublic(self, shortAssetUuid, isPublic):
    self.authorize()

    setPublicEndpoint = self.url + "api/assets/{suuid}/sharing".format(suuid = shortAssetUuid)

    r = http.patch(url = setPublicEndpoint, json={ 'isPublic': isPublic }, headers=self.headerParams)
    r.raise_for_status()

    return r.json()

  def uploadAsset(self, files, assetType, assetName, dccname='', useCompression=True, maxWaitSeconds=3600):
    """
    Creates an asset if necessary, and uploads the specified files to it.

    Args:
      files: A list of dicts. Each dict in the list has the following format:
               {
                'path': <path to file. Absolute or relative to runtime directory>
                'type': "image", "photogrammetry_image", "scene", or "extra"
               }

             If a type isn't specified for a given path, the upload server will attempt
             to detect its type ("image", "photogrammetry_image", "scene", or "extra")
             based on its contents. For image files on photogrammetry assets, automatic detection
             cannot be reliable under every circumstance, so it is recommended to provide your
             own type (either "image" for texture files or "photogrammetry_image" for photos).
             For image files on non-photogrammetry assets, you needn't specify a type since everything
             will be automatically considered an "image" (i.e. texture file).
             For other file types (scene and extra), a `type` can be safely omitted, since the server
             can auto-detect these reliably based on file extension and/or contents.

    Returns:
      A `NiraUploadInfo` object

    Raises:
      HTTPError: An error occurred while communicating with the Nira server.
    """
    self.authorize()

    jobsEndpoint  = self.url + "api/jobs"
    filesEndpoint = self.url + "api/files"
    assetsEndpoint = self.url + "api/assets"

    global zlib
    if useCompression and zlib == False:
      try:
        import zlib
      except ImportError:
        zlib = None
        print("Warning: Python zlib module is not available! Consider installing it for improved upload speeds.", file=sys.stderr)

    useFetching = False

    for f in files:
      if 'fetchurl' in f:
        useFetching = True

    if not useFetching:
      for f in files:
        if not os.path.exists(f['path']):
          raise IOError('File not found: ' + f['path'])

    batchUuid = str(uuid.uuid4())

    jobCreateParams = {
        'status': "validating",
        'assettype': assetType,
        'batchId': batchUuid,
        'assetname': assetName,
        }

    if dccname:
      jobCreateParams.update({
        'dccname': dccname
      })

    if useFetching:
      jobCreateParams.update({
        'fetchfiles': files
      })

    r = http.post(url = jobsEndpoint, json=jobCreateParams, headers=self.headerParams)
    r.raise_for_status()
    job = r.json()

    if not useFetching:
      if not job['uploadServiceHost']:
        raise Exception("uploadServiceHost is expected in job response!")

      uploadServiceHost = os.getenv("NIRA_UPLOAD_SERVICE_HOST") or job['uploadServiceHost']

      def createFileRecord(f):
        self.authorize()

        f['size'] = os.path.getsize(f['path'])

        hash = ''

        try:
          #print("HASHING FILE: " + assetpath)
          hash = subprocess.check_output([meowfileExe, f['path']])
        except subprocess.CalledProcessError as hashExec:
          raise Exception('meowhash exe not found!')
        #print("HASHED FILE: " + assetpath)

        if len(hash) != 36:
          raise Exception('meowhash result unexpected found! result: ' + hash)

        if sys.version_info[0] == 2:
          f['hash'] = hash
        else:
          f['hash'] = str(hash, "UTF-8")

        fileUuid=str(uuid.uuid4())
        fileName = os.path.basename(f['path'])
        userpath = os.path.dirname(f['path'])

        #print("LOOKING UP FILE: " + assetpath)

        fileCreateParams = {
            'fileName': fileName,
            'userpath': userpath,
            'uuid': fileUuid,
            'jobId': job['id'],
            'meowhash': f['hash'],
            'filesize': f['size'],
            }

        if 'type' in f:
          fileCreateParams.update({
            'type': f['type']
          })

        #print("CREATING FILE RECORD: " + assetpath)
        r = http.post(url = filesEndpoint, json=fileCreateParams, headers=self.headerParams)
        r.raise_for_status()
        fileRecord = r.json()

        fileRecord['f'] = f

        return fileRecord

      # Create all file records, in parallel
      cp = mp.Pool(FILE_MAX_THREAD_COUNT)
      fileRecords = cp.map(createFileRecord, files)
      cp.close()
      cp.join()

      self.authorize()

      # Change status of job prior to uploading files
      jobPatchParams = {
          'status': "uploading",
          'batchId': batchUuid,
          }
      r = http.patch(url = jobsEndpoint + "/" + str(job['id']), json=jobPatchParams, headers=self.headerParams)
      r.raise_for_status()

      def uploadFile(fileRecord):
        self.authorize()

        f = fileRecord['f']
        fileUuid = fileRecord['uuid']
        fileName = fileRecord['fileName']

        # Determine if the file is already available on the server
        fileAlreadyOnServer = fileRecord['status'] == 'ready_for_processing'

        totalsize = f['size']
        totalparts = (totalsize//UPLOAD_CHUNK_SIZE) + 1
        #print ("totalparts: " + str(totalparts), file=sys.stderr)

        global compressionRatios
        global disableCompression

        compressionRatios = []
        disableCompression = False

        def sendChunk(partidx):
          global compressionRatios
          global disableCompression

          shouldUseCompression = useCompression and zlib and not disableCompression

          chunkoffset = partidx * UPLOAD_CHUNK_SIZE

          if not hasattr(tls, 'fh'):
            tls.fh = open(f['path'], 'rb')

          tls.fh.seek(chunkoffset)
          chunk = tls.fh.read(UPLOAD_CHUNK_SIZE)

          if not chunk:
            return

          if shouldUseCompression:
            compressedChunk = zlib.compress(chunk, 1)
            compressionRatio = float(len(compressedChunk)) / len(chunk)
            compressionRatios.append(compressionRatio)
            chunk = compressedChunk

          filechunkparams={
            'uuid': fileUuid,
            'chunksize': len(chunk),
            'filename': fileName,
            'partindex': partidx,
            'partbyteoffset': chunkoffset,
            'totalparts': totalparts,
            'totalfilesize': totalsize,
            }

          if shouldUseCompression:
            filechunkparams.update({'compression': 'deflate'})

          mimeparts={
              'params': (None, json.dumps(filechunkparams), 'application/json'),
              'data': (fileName, chunk, 'application/octet-stream'),
              }

          self.authorize()

          headers = {}
          headers.update(self.headerParams)
          response = http.post("https://" + uploadServiceHost + '/file-upload-part', files=mimeparts, headers=headers)
          response.raise_for_status()

          #print(response.headers)
          if shouldUseCompression and not disableCompression:
            # Collect several chunks of results before checking the ratio.
            # If the compression ratio is poor, it's a waste of resources, so don't continue using it
            # on other parts of this file.
            if len(compressionRatios) >= 6:
              avgCompressionRatio = sum(compressionRatios) / len(compressionRatios)
              if avgCompressionRatio >= 0.9:
                disableCompression = True
                #print ("Info: \"" + fileName + "\" compresses poorly (ratio: %.3f" % (1/avgCompressionRatio) + "). Skipping upload compression for this file.", file=sys.stderr)

        def closeHandles(threadid):
          if hasattr(tls, 'fh'):
            tls.fh.close()
            delattr(tls, 'fh')

        # Only perform upload if it's not already on the server
        if not fileAlreadyOnServer:
          #print("UPLOADING FILE: " + assetpath)
          p = mp.Pool(FILEPARTS_MAX_THREAD_COUNT)
          p.map(sendChunk, range(0, totalparts))

          # Note: I believe these handles should close themselves,
          # since an mp.Pool manages processes, not threads.
          p.map(closeHandles, range(0, FILEPARTS_MAX_THREAD_COUNT * 4))

          p.close()
          p.join()

          self.authorize()

          headers = {}
          headers.update(self.headerParams)
          payload={
              'uuid': fileUuid,
              'filename': fileName,
              'totalfilesize': totalsize,
              'totalparts': totalparts,
              'meowhash': f['hash'],
              }
          r = http.post("https://" + uploadServiceHost + '/file-upload-done', json=payload, headers=headers)
          r.raise_for_status()
        else:
          #print("SKIPPING FILE UPLOAD (hash match): " + assetpath)
          pass

      pp = mp.Pool(FILE_MAX_THREAD_COUNT)
      pp.map(uploadFile, fileRecords)
      pp.close()
      pp.join()

      self.authorize()

      jobPatchParams = {
          'status': "uploaded",
          'batchId': batchUuid,
          }
      r = http.patch(url = jobsEndpoint + "/" + str(job['id']), json=jobPatchParams, headers=self.headerParams)
      r.raise_for_status()

    if maxWaitSeconds > 0:
      uploadInfo = self.waitForAssetProcessing(job['id'], timeoutSeconds = maxWaitSeconds)
    else:
      uploadInfo = NiraUploadInfo()
      uploadInfo.assetJobId = job['id']
      uploadInfo.jobStatus = NiraJobStatus.Pending
      uploadInfo.assetUrl = self.formatAssetUrl(job['assetShortUuid'])

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
  jobStatus (NiraJobStatus):
    Numeric id of the asset upload job. Useful for querying the progress of asset processing (see waitForAssetProcessing method).
  """
  pass

class NiraJobStatus:
  Pending = "Pending"
  Processed = "Processed"
  ProcessingError = "Processing Error"
