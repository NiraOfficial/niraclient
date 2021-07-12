## Nira Client
In this repo is a collection of useful client -> server methods for Nira (niraclient.py) and an accompanying commandline tool (niracmd.py) that implements these methods.

Currently, functions and command-line capabilities are included for:
* Uploading assets - Useful for uploading assets from existing tools such as Perforce, Shotgun, etc. [Here's a Perforce Integration Example](https://www.youtube.com/watch?v=AhfdoJv1TP0)
* (Others coming soon)

As mentioned, there are two main components:
#### niraclient.py
Includes the API calls themselves. Inline documentation can be found in the file. HTML documentation of the class can be found at https://apidocs.nira.app/niraclient.html
#### niracmd.py
A commandline nira client that utilizes `niraclient.py` for some common tasks like asset uploads. Run it with `--help` for usage details.

## Dependencies
Both python2/python3 are supported.

## CLI Usage examples
As user admin@example.org, upload ball.ma, red.png, and blue.png to an asset called 'ball', then wait for the asset to finish processing on the server and print the asset's URL:
```
python niracmd.py --useremail "admin@example.org" --url "https://example.nira.app" --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --asset-name ball --asset-type default --upload "assets/ball.ma" "assets/red.png" "assets/blue.png"
```

As user admin@example.org, upload cube0001.obj through cube0006.obj and cube0001.png through cube0006.png as a playback sequence (aka Volumetric Video, 4D Video, etc), then wait for the asset to finish processing on the server and print its URL.
The naming scheme for the geometry files and texture files should match. For example, cube0001.obj will be matched to cube0001.png. It is also acceptable to have cube0001.obj and cube0001.obj.png.
Also note, the asterisk wildcard usage below is taking advantage of a shell's filename expansion. If executing this command from a context that isn't using a shell, you'll need to separately specify each file name.
```
python niracmd.py --useremail "admin@example.org" --url "https://example.nira.app" --apikey 942a76b6-5aca-4c83-b686-630ef54ded0d --asset-type volumetric_video --asset-name cube-animation --upload assets/sequence/cube*.obj assets/sequence/cube*.png
```
