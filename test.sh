#!/bin/bash

NIRA_URL=$1
USER_EMAIL=$2
API_KEY=$3
PYTHON_CMD=$4

if [ -z "$PYTHON_CMD" ]; then
  PYTHON_CMD=python2
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
if [ $? -ne 0 ]; then
  echo "Could not get python version!"
  exit 1
fi

echo Using $PYTHON_VERSION

printUsage() {
  echo "Usage:"
  echo "$0 <nira_url> <user_email> <api_key>"
  exit 1
}

[ -n "$NIRA_URL" ] || printUsage;
[ -n "$USER_EMAIL" ] || printUsage;
[ -n "$API_KEY" ]  || printUsage;

COMMON_ARGS="--useremail $USER_EMAIL --url $NIRA_URL --apikey $API_KEY"

echo -n sphere upload test...
ASSET_URL=$($PYTHON_CMD ./niracmd.py $COMMON_ARGS --upload assets/sphere.abc)
if [ $? -ne 0 ]; then
  exit 1
fi
echo done

# The asset URL is uniquely generated, so we can be assured that by using it in metadata and reading it back, it has been updated. We also include our PID, for good measure!
echo -n asset metadata test...
ASSET_METADATA_INPUT='{"assetMetaTest": "'$$_$ASSET_URL'"}'
echo $ASSET_METADATA_INPUT | $PYTHON_CMD ./niracmd.py $COMMON_ARGS --set-metadata $ASSET_URL --metadata-level asset || exit 1
ASSET_METADATA_OUTPUT=$($PYTHON_CMD ./niracmd.py $COMMON_ARGS --get-metadata $ASSET_URL --metadata-level asset)
if [ $? -ne 0 ]; then
  exit 1
elif [ "$ASSET_METADATA_INPUT" != "$ASSET_METADATA_OUTPUT" ]; then
  echo Metadata mismatch!
  echo input: $ASSET_METADATA_INPUT
  echo output: $ASSET_METADATA_OUTPUT
fi
echo done

echo -n assetversion metadata test...
ASSETVERSION_METADATA_INPUT='{"assetversionMetaTest": "'$$_$ASSET_URL'"}'
echo $ASSETVERSION_METADATA_INPUT | $PYTHON_CMD ./niracmd.py $COMMON_ARGS --set-metadata $ASSET_URL --metadata-level assetversion || exit 1
ASSETVERSION_METADATA_OUTPUT=$($PYTHON_CMD ./niracmd.py $COMMON_ARGS --get-metadata $ASSET_URL --metadata-level assetversion)
if [ $? -ne 0 ]; then
  exit 1
elif [ "$ASSETVERSION_METADATA_INPUT" != "$ASSETVERSION_METADATA_OUTPUT" ]; then
  echo Metadata mismatch!
  echo input: $ASSETVERSION_METADATA_INPUT
  echo output: $ASSETVERSION_METADATA_OUTPUT
fi
echo done

echo -n Sequence upload test...
$PYTHON_CMD ./niracmd.py $COMMON_ARGS --upload assets/sequence/cube*.obj assets/sequence/cube*.png --is-sequence --compress-textures >/dev/null || exit 1
echo done

echo all done!
