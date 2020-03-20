## Nira Client
In this repo is a collection of useful client -> server methods for Nira (niraclient.py) and an accompanying commandline tool (niracmd.py) that implements these methods.

Currently, functions and command-line capabilities are included for:
* Uploading assets - Useful for uploading assets from existing tools such as Perforce, Shotgun, etc. [Here's a Perforce Integration Example](https://www.youtube.com/watch?v=AhfdoJv1TP0)
* Downloading assets - Useful for importing assets into existing tools such as Maya, Unity, etc. [Here's a Maya example](https://www.youtube.com/watch?v=JG06Uf8nUCg)
* Checking for recently updated assets - Assets that are newly uploaded, have new markups, or have recent approval status changes. Useful for setting up automated notifications for artists or directors.

As mentioned, there are two main components:
#### niraclient.py
Includes the API calls themselves. Inline documentation can be found in the file. HTML documentation of the class can be found at https://apidocs.nira.app/niraclient.html
#### niracmd.py
A commandline nira client that utilizes `niraclient.py` for some common tasks like asset uploads. Run it with `--help` for usage details.

## Dependencies
Both python2/python3 are supported.

## CLI Usage examples
As user admin@example.org, upload ball.ma, red.png, and blue.png, then wait for the asset to finish processing on the server (timeout after 300 seconds):
```
python niracmd.py --useremail "admin@example.org" --url "https://example.nira.app" --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --upload "assets/ball.ma" "assets/red.png" "assets/blue.png" --wait-for-asset-processing 300
```

List information about updated assets every 30 seconds:
```
python niracmd.py --useremail "admin@example.org" --url "https://example.nira.app" --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --show-updated-assets-every 30
```

Download asset with short UUID `V9hsnMpvRU2jBLQVhg-8eA` including all of its accompanying assets (textures, etc.) to the directory /home/bob/tpot-asset:
```
python ./niracmd.py --useremail "admin@example.org" --url http://example.nira.app --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --download V9hsnMpvRU2jBLQVhg-8eA /home/bob/tpot-asset
```
