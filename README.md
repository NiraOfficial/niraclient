## Enterprise Only:
The Nira Upload API requires an Enterprise Nira account. The instrutions below only apply to Enterprise accounts.

## Quick Start:
First, download a release or clone the repo and from within the directory, run `python nira.py configure` on a terminal, which will guide you through the process of providing your API key and secret.

After the configuration is complete, you can run this command to upload a small test asset to your Nira organization:
```
python nira.py asset create myasset photogrammetry assets/tpot.obj assets/tpot.mtl assets/blue.png
```
If all goes well, you will see a URL printed to the screen. Open this URL to view your newly uploaded test asset.

The nira.py command has many other capabilities, which are structured into nested sub-commands. To display help for the main top-level subcommands, simply run `python nira.py` on its own.

After you've seen the main subcommands, you can run any subcommand on its own for details about how to use it. For example, to display help for the `asset` sub-command:
```
python nira.py asset
```

This will print all of the asset operations that can be performed. To display help for the `asset create` sub-command:
```
python nira.py asset create
```

To print the help for all subcommands, run `python nira.py --full-help` or click [here](FULL_HELP.md). Also see the [additional examples](#more-cli-usage-examples-with-details) below.

### Understanding REST calls by printing HTTPS requests and responses:
The `--print-requests` and/or `--print-responses` options to the `python nira.py` command will cause all HTTP requests and reponses to be printed to stderr. For example, this will print the HTTP request/response for publicly sharing an asset with id `M2Kdl5k66kdDBmrGgQ5DsA`:
```
python nira.py --print-requests --print-responses asset sharing set-public M2Kdl5k66kdDBmrGgQ5DsA on
```

This is useful if you'd like to learn how to call our REST API directly within application rather than having your application run a separate nira.py command.

> Tip: If you're planning to implement a custom uploader for Nira rather than using nira.py, we suggest reaching out to contact@nira.app and describing your usecase so we can provide you with additional guidance and documentation.

## Details
This repo includes:

#### nira.py
A commandline Nira client tool for performing Nira tasks on the command-line.

#### niraclient.py
Includes the implementation of the API calls. Some inline documentation can be found in the file. This could be imported and used by a larger python application, though we do reserve the right to change its interface, so please bear that in mind.

Currently, capabilities include:
* Creating new assets and uploading an initial set of files to it - Useful for writing scripts that sync assets from your local directories, or uploading assets from existing tools such as Perforce, Shotgun, etc. [Here's a Perforce Integration Example](https://www.youtube.com/watch?v=AhfdoJv1TP0)
* Adding files to existing assets
* Listing assets
* Changing an asset's sharing properties
* Server-side fetching from your HTTPS file source (e.g. object storage) instead of uploading. [More details below.](#server-side-fetch)
* More coming soon

#### Dependencies
Both python2/python3 are supported. All necessary dependencies are already included in this repo under the `deps` directory; You should not need to run `pip`, so please let us know if you do. :)

## More CLI Usage Examples with details

### Upload files by providing a list of file paths on the command line:
```
python nira.py asset create myasset photogrammetry assets/tpot.obj assets/tpot.mtl
```

The example above will create an asset "myasset" and upload tpot.obj and tpot.mtl to it.

The server will attempt to automatically determine the file types based on their content. For photogrammetry assets, there's a potential downside of relying upon this automatic file type detection -- it is not always possible to automatically determine the difference between a texture ("image") or photo ("photogrammetry\_image"). So while this method is simpler than providing a json files list, it may result in photo files being detected as texture files or visa-versa. If this occurs, the files will show up in incorrect areas of the Nira UI, and the only remedy for this is to reprocess the files using the correct type. Therefore, when uploading photogrammetry assets using nira.py, it's recommended to provide a JSON file list and specify a type for all image files; Either "image" for texture files or "photogrammetry\_image" for photos.

If you're uploading a non-photogrammetry asset, this is not an issue, and providing the files on the command line should work fine, as long as your files list does not exceed the maximum command line length or command argument length of your shell.

For other file types (geomtry files, or others), a `type` can be omitted, since the server can auto-detect these reliably based on file extension and/or contents.

### Upload files by providing a json array on stdin:
(Recommended for photogrammetry assets with photos)
```
python nira.py asset create "test asset" photogrammetry < file-list-example.json
```
The example above creates a photogrammetry asset called 'test asset' and uploads the following files to it:
* An obj geometry file (tpot.obj)
* An MTL file (tpot.mtl)
* A texture file (blue.png)
* A photo (tpot-photo01.jpg)

file-list-example.json (also included this repo) defines these files and their types. To show more information on the json format, run `python nira.py asset create`.

The command will print the URL of the asset upon success, or an error message upon failure. The command will also exit with a success code (0) upon success and a failure code (1) upon failure.

> Tip: The last 22 characters of the printed URL can be used as the identifier in a Nira embed.

### How to wait for asset processing to complete

By default, an 'asset create' command execution will complete immediately after the upload finishes and will not wait for processing. If you visit an asset URL while the asset is still processing, a "This asset is still processing." message will be shown, and it will not be possible to view it. To upload an asset and wait for processing to finish, you can specify the `--wait-for-asset-processing MAX_SECONDS` parameter to the asset create command. This will wait up to WAIT\_MAX\_SECONDS for the asset to be processed on the server before the command completes.

### Server-side fetch
> Server-side fetch is an Enterprise-only feature. [Contact us](https://nira.app/contact) before using it in production

If your files are already in a location accessible by our servers (e.g. an object storage bucket),
you can provide a url for each file and we will fetch them rather than you needing to upload them.

To try this using some provided sample file URLs, run:
```
python nira.py asset create "test asset" photogrammetry < file-list-fetchurls-example.json
```

file-list-fetchurls-example.json (also included this repo) defines the each file's name, type, and fetchurl.
server-side fetch currently expects a xxhash64 to be provided for each file, but support for other hash types,
HTTP header provided hashes, or no hashes at all can be added easily upon request ([contact us](https://nira.app/contact)).

Important Notes:
* If you're using presigned URLs for your files, 4 hours should be safe. Typically download/processing
will take far less than this, but it's usually best to have some wiggle room. That said, feel free to
experiment with lower expiration times if your security policies dictate them.

* The example command above will work for any account type with API capabilities, but using the feature with your
own file sources requires an enterprise account and a configuration step on our end. Please [contact us](https://nira.app/contact)
if you'd like to use this feature in production.

### Upload additional files to an asset:
```
python nira.py asset files add "test asset" assets/sphere.abc
```

This uploads an additional geometry file sphere.abc to the existing asset named 'test asset' and prints the asset's URL.

> Tip: Instead of a list of files on the commandline, `asset files add` can be provided with an json array on its stdin, just like `asset create`.

### Export callouts from an asset
```
python nira.py asset callouts export --output-file callouts-export.json <Asset URL>
```
This exports the callouts from the specified asset to a callouts-export.json file. You can omit `--output-file callouts-export.json` to print to stdout. To learn more about this command's options, run `python nira.py asset callouts export` to print the help.

(Note: Replace `<Asset URL>` with the URL of an asset.)

### Import callouts to an asset
```
python nira.py asset callouts import <Asset URL> example_callout_annotation.json
```
This imports the callouts from the example\_callout\_annotation.json to the specified asset.

To learn more about this command's options, run `python nira.py asset callouts import` to print the help. The `--remove-all-existing-callouts` option is particularly useful, because it allows you to remove all of the existing callouts on the asset before importing the new callouts.

Please note, the callout defined by example\_callout\_annotation.json is meant to be imported to an asset using the included assets/tpot.obj file. Here's an example of using two commands to create the approrpiate asset then import the callouts to it:
```
python nira.py asset create --wait-for-asset-processing 60 callout-import-test-asset photogrammetry assets/tpot.obj assets/tpot.mtl

python nira.py asset callouts import <Asset URL> example_callout_annotation.json
```
Note: Replace `<Asset URL>` with the URL printed by the previous `asset create` command.

### List all assets in JSON format:
```
python nira.py asset list
```

### List an asset called 'ball' in JSON format:
```
python nira.py asset list --name "ball"
```

### List an asset with uuid 8d3b6e4a-50b1-4282-8b57-b94d7da4fd7e in JSON format:
```
python nira.py asset list --uuid 8d3b6e4a-50b1-4282-8b57-b94d7da4fd7e
```

### Upload a volumetric video asset:
```
python nira.py asset create cube-animation volumetric_video assets/sequence/cube*.obj assets/sequence/cube*.png
```
Upload cube0001.obj through cube0006.obj and cube0001.png through cube0006.png to a new asset named cube-animation as a playback sequence (aka Volumetric Video, 4D Video, etc) and print its URL.
When uploading volumetric video, the naming scheme for the geometry files and texture files should match. For example, cube0001.obj will be matched to cube0001.png. It is also acceptable to have cube0001.obj and cube0001.obj.png.
Also note, the asterisk wildcard usage in this example is taking advantage of the shell's filename expansion. If executing this command from a context that isn't using a shell, you'll need to separately specify each file name.
