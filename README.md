## Nira Client
In this repo is a collection of useful client -> server methods for Nira (niraclient.py) and an accompanying commandline tool (niracmd.py) that implements these methods.

Currently, functions and command-line capabilities are included for:
* Uploading assets - Useful for uploading assets from existing tools such as Perforce, Shotgun, etc. [Here's a Perforce Integration Example](https://www.youtube.com/watch?v=AhfdoJv1TP0)
* Downloading assets - Useful for importing assets into existing tools such as Maya, Unity, etc. [Here's a Maya example](https://www.youtube.com/watch?v=JG06Uf8nUCg). Note, asset downloading is optional and can be completely disabled for your Nira instance if you'd prefer.
* Checking for recently updated assets - Assets that are newly uploaded, have new markups, or have recent approval status changes. Useful for setting up automated notifications for artists or directors.

As mentioned, there are two main components:
#### niraclient.py
Includes the API calls themselves. Inline documentation can be found in the file. HTML documentation of the class can be found at https://apidocs.nira.app/niraclient.html
#### niracmd.py
A commandline nira client that utilizes `niraclient.py` for some common tasks like asset uploads. Run it with `--help` for usage details.

## Dependencies
Both python2/python3 are supported. You may need to install the `requests` module by running `pip install requests` or the equivalent on your OS and python installation.

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

As user admin@example.org, upload cube0001.obj through cube0006.obj and cube0001.png through cube0006.png as a playback sequence (aka Volumetric Video, 4D Video, etc), then wait for the asset to finish processing on the server (timeout after 300 seconds).
This command also enables texture compression, which is highly recommended for sequences. The naming scheme for the geometry files and texture files should match. For example, cube0001.obj will be matched to cube0001.png. It is also acceptable to have cube0001.obj and cube0001.obj.png.
Also note, the asterisk wildcard usage below is taking advantage of the shell's filename expansion. If executing this command from a context that isn't using a shell, you'll need to separately specify each file name.
```
python niracmd.py --useremail "admin@example.org" --url "https://example.nira.app" --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --upload assets/sequence/cube*.obj assets/sequence/cube*.png --is-sequence --compress-textures --wait-for-asset-processing 300
```
