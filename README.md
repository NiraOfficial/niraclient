*NOTE* Still work-in-progress. Just about there...

## Nira Client
In this repo is a collection of collection of useful client -> server methods for Nira.

Currently, methods are included for uploading files, checking for recently updated assets,
and checking whether an asset has finished being processed by Nira after upload.

There are two main components:
*niracmd.py*: A commandline nira client that utilizes `niraclient.py` for some common tasks like asset uploads. Run it with `--help` for usage details.
*niraclient.py*: Includes the API calls themselves. Inline documentation can be found in the file.

## Dependencies
Both python2/python3 are supported.

The only python dependency is `requests_toolbelt`:
```
pip install requests_toolbelt
```


## CLI Usage examples
Upload sphere.ma, sphere_texture_1.tga, sphere_texture_2.tga, then wait for the asset to finish processing on the server (timeout after 300 seconds):
```
python niracmd.py --useremail "admin@example.org" --niraurl "http://example.nira.app:3030" --apikey ccf0d30a-312a-4d09-8a4b-dd70c40e2a9a --upload "/home/dev/sphere.ma" "/home/dev/sphere_texture_1.tga" "/home/dev/sphere_texture_2.tga" --wait-for-asset-processing 300
```

List records (in JSON) of any assets updated within the last 5 minutes:
```
python niracmd.py --useremail "admin@example.org" --niraurl "http://localhost:3030" --apikey ccf0d30a-312a-4d09-8a4b-dd70c40e2a9a --list-assets-updated-within 300
```
