## Nira Client
In this repo is a collection of collection of useful client -> server methods for Nira.

Currently, methods are included for uploading assets, checking for recently updated assets (i.e. assets that are newly uploaded, have new markups, or have recent approval status changes), and checking whether an asset has finished being processed by Nira after upload.

There are two main components:
#### niraclient.py
Includes the API calls themselves. Inline documentation can be found in the file. HTML documentation of the class can be found at https://apidocs.nira.app/niraclient.html
#### niracmd.py
A commandline nira client that utilizes `niraclient.py` for some common tasks like asset uploads. Run it with `--help` for usage details.

## Dependencies
Both python2/python3 are supported.

The only python dependency is `requests_toolbelt`:
```
pip install requests_toolbelt
```


## CLI Usage examples
As user admin@example.org, upload ball.ma, red.png, and blue.png, then wait for the asset to finish processing on the server (timeout after 300 seconds):
```
python niracmd.py --useremail "admin@example.org" --url "https://example.nira.app" --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --upload "assets/ball.ma" "assets/red.png" "assets/blue.png" --wait-for-asset-processing 300
```

List information about updated assets every 30 seconds:
```
python niracmd.py --useremail "admin@example.org" --url "https://example.nira.app" --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --show-updated-assets-every 30
```
