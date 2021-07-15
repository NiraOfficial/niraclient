## Nira Client
This repo includes:

#### nira.py
A commandline Nira client tool for performing Nira tasks on the command-line. Run it with `--help` for usage details.

#### niraclient.py
Includes the API calls themselves. Inline documentation can be found in the file.

Currently, capabilities include:
* Creating new assets and uploading an initial set of files to it - Useful for writing scripts that sync assets from your local directories, or uploading assets from existing tools such as Perforce, Shotgun, etc. [Here's a Perforce Integration Example](https://www.youtube.com/watch?v=AhfdoJv1TP0)
* Adding files to existing assets
* Listing assets
* Listing users
* More coming soon

## Dependencies
Both python2/python3 are supported. All necessary dependencies are already included in this repo under the `deps` directory.

## CLI Setup
First, it's important to define the following environment variables:

`NIRA_APIKEY`: Set this to your Nira API key. This can also be specified on the command-line using the `--apikey` option.

`NIRA_URL`: Set this to the URL of your Nira organization. For example: https://example.nira.app. This can also be specified on the command-line using the `--url` option.

`NIRA_USER`: Set this to the email address of the user you'd like API operations to occur under. This can also be specified on the command-line using the `--user` option.

## CLI General Usage
For usage details, run the `nira.py --help`, which contains an overview of its sub-commands. nira.py functionality is structured into nested sub-commands. Run `--help` on a sub-command for more details about it. For example:

To display help for the asset sub-command:
```
./nira.py asset --help
```

To display help for the asset create sub-command:
```
./nira.py asset create --help
```

## CLI Usage Examples
The examples below will assume you've defined these settings using environment variables as outlined above.

Upload ball.ma, red.png, and blue.png to a new asset called 'ball' using the asset type 'photogrammetry', then wait for the asset to finish processing on the server and print the asset's URL:
```
./nira.py asset create ball photogrammetry "assets/ball.ma" "assets/red.png" "assets/blue.png"
```

> Tip: The last 22 characters of the printed URL can be used as the identifier in a Nira embed.

Upload an additional texture "assets/sequence/cube0001.png" and "assets/sequence/cube0002.png" to the existing asset named 'ball', then wait for the files to finish processing on the server and print the asset's URL:
```
./nira.py asset files add ball "assets/sequence/cube0001.png" "assets/sequence/cube0002.png"
```

List all assets in JSON format:
```
./nira.py asset list
```

List an asset called 'ball' in JSON format:
```
./nira.py asset list --name "ball"
```

List an asset with uuid `8d3b6e4a-50b1-4282-8b57-b94d7da4fd7e` in JSON format:
```
./nira.py asset list --uuid 8d3b6e4a-50b1-4282-8b57-b94d7da4fd7e
```

Upload cube0001.obj through cube0006.obj and cube0001.png through cube0006.png to a new asset named cube-animation as a playback sequence (aka Volumetric Video, 4D Video, etc), then wait for the asset to finish processing on the server and print its URL.
When uploading volumetric video, the naming scheme for the geometry files and texture files should match. For example, cube0001.obj will be matched to cube0001.png. It is also acceptable to have cube0001.obj and cube0001.obj.png.
Also note, the asterisk wildcard usage below is taking advantage of a shell's filename expansion. If executing this command from a context that isn't using a shell, you'll need to separately specify each file name.
```
./nira.py asset create cube-animation volumetric_video assets/sequence/cube*.obj assets/sequence/cube*.png
```
