```
---------------
usage: nira.py [--help] [--full-help] [--print-requests] [--print-responses]
               [--print-and-dump-requests] [--org ORG]
               {configure,asset,user} ...

Nira Client CLI

positional arguments:
  {configure,asset,user}
                        Operation
    configure           Perform initial configuration. This is required to use
                        any Nira API commands.
    asset               Perform asset related operations
    user                Perform user related operations

optional arguments:
  --help                show this help message and exit
  --full-help           show help for all possible subcommands and exit
  --print-requests      Print HTTP requests stderr. Useful for leaning about
                        the API, or for debugging purposes
  --print-responses     Print HTTP requests stderr. Useful for leaning about
                        the API, or for debugging purposes
  --print-and-dump-requests
                        Print HTTP requests stderr and also dump the requests
                        to 'request-body-NNN' files in your current directory.
                        Useful for inspecting large request bodies such as
                        file part upload requests
  --org ORG             Your Nira organization name, including the domain
                        name. This is only for advanced usage where multiple
                        orgs are being used.

---------------
usage: nira.py configure [-h]

optional arguments:
  -h, --help  show this help message and exit

---------------
usage: nira.py asset [-h] {create,sharing,list,files} ...

positional arguments:
  {create,sharing,list,files}
                        Asset related operations
    create              Create a new asset, upload the provided files to it,
                        then print a URL to the resulting asset on stdout or
                        an error message if unsuccessful.
    sharing             Perform asset sharing related operations
    list                List assets, optionally filtering by some criteria
    files               Perform operations related to an asset's files

optional arguments:
  -h, --help            show this help message and exit

---------------
usage: nira.py asset create [-h] [--no-upload-compression]
                            [--wait-for-asset-processing WAIT_MAX_SECONDS]
                            asset_name
                            {default,sculpt,photogrammetry,volumetric_video}
                            [files [files ...]]

positional arguments:
  asset_name            A name for the asset. If an asset with this name
                        already exists, an error message will be printed. If
                        you wish to add files to an existing asset, use the
                        addfiles command, instead.
  {default,sculpt,photogrammetry,volumetric_video}
                        Specifies the type of the asset.
  files                 
                        There are two different methods for providing the files you wish to upload:
                        
                        * Method 1: Provide a list of file paths on the command line
                        
                          For example:
                             nira.py asset create myasset photogrammetry assets/tpot.obj assets/tpot.mtl
                          Will upload tpot.obj and tpot.mtl to a new asset called 'myasset'
                        
                          The server will attempt to automatically determine file types based
                          on their content. For photogrammetry files with photos, there's a potential
                          downside of relying upon automatic file type detection -- it is not always
                          possible to automatically determine the difference between a texture ("image")
                          or photo ("photogrammetry_image"). Therefore, for photogrammetry assets
                          with photos, "Method 2" below is suggested.
                        
                        * Method 2: Provide a json array on stdin
                            (Recommended for photogrammetry assets with photos)
                        
                            Here's an example of a json file list:
                            [{
                              "path": "assets/tpot.obj",
                              "type": "scene"
                            }, {
                              "path": "assets/tpot.mtl",
                              "type": "extra"
                            }, {
                              "path": "assets/blue.png",
                              "type": "image"
                            }, {
                              "path": "assets/photos/tpot-photo01.jpg",
                              "type": "photogrammetry_image"
                            }]
                            Providing this array will cause 4 files to be uploaded:
                              An obj geometry file (tpot.obj)
                              An MTL file (tpot.mtl)
                              A texture file (blue.png)
                              A photo (tpot-photo01.jpg)
                        
                        Other Notes:
                          * If you don't provide any file paths on the command line,
                            you wil be prompted to enter a files json array.
                          * If you're trying to automate Nira commands but you're
                            not familiar how to provide data through a command's stdin,
                            you can search for "Piping and redirection" along with your
                            operating system ("linux", "windows") to learn more about it.
                          * File paths may be absolute or relative to the runtime directory.
                          * When creating a new asset, at least one of the files should be
                            a geometry file (obj, ma, mb, zpr, etc). When adding files to an
                            existing asset, this does not apply.

optional arguments:
  -h, --help            show this help message and exit
  --no-upload-compression
                        Disables the use of automatic upload compression.
                        Upload compression is enabled by default. You may wish
                        to disable it if you have a particularly capable
                        upstream network throughput (1gbps+) or have concerns
                        about CPU utilization on the machine doing the
                        uploading.
  --wait-for-asset-processing WAIT_MAX_SECONDS
                        When using --upload, wait up to WAIT_MAX_SECONDS for
                        the asset to be processed on the server before
                        returning. If set to 0, the command will return
                        immediately after upload, and asset processing will
                        not have finished yet. Note, --upload will not print
                        an asset url unless the asset has finished processing,
                        so it is best to use a sufficiently large value for
                        this argument. If an error occurs during upload or
                        processing, the command will exit with a non-zero
                        status and print an error message.

---------------
usage: nira.py asset sharing [-h] {user,set-public} ...

positional arguments:
  {user,set-public}  Asset sharing related operations
    user             Managing sharing of an asset for particular users
    set-public       Set the public sharing flag on or off for an asset

optional arguments:
  -h, --help         show this help message and exit

---------------
usage: nira.py asset sharing user [-h] {add} ...

positional arguments:
  {add}       Asset sharing related operations
    add       Share asset with a user specified by email.

optional arguments:
  -h, --help  show this help message and exit

---------------
usage: nira.py asset sharing user add [-h]
                                      asset_short_uuid user_email role
                                      [expiration_date]

positional arguments:
  asset_short_uuid  A short uuid or URL for an existing asset. If an asset
                    with this name does not exist, an error message will be
                    printed.
  user_email        Specify a user by email
  role              Role name. Could be "viewer" or "contributor"
  expiration_date   Optional expiration datetime in ISO format. e.g.
                    2022-02-24T23:00:00.000Z

optional arguments:
  -h, --help        show this help message and exit

---------------
usage: nira.py asset sharing set-public [-h] asset_short_uuid {on,off}

positional arguments:
  asset_short_uuid  A short uuid or URL for an existing asset. If an asset
                    with this name does not exist, an error message will be
                    printed.
  {on,off}          Enables or disables the public flag for the asset

optional arguments:
  -h, --help        show this help message and exit

---------------
usage: nira.py asset list [-h] [--name NAME] [--uuid UUID]

optional arguments:
  -h, --help   show this help message and exit

Filtering options:
  If multiple filter arguments are provided, they are appied in an AND
  fashion

  --name NAME  Filter by asset name
  --uuid UUID  Filter by UUID

---------------
usage: nira.py asset files [-h] {add} ...

positional arguments:
  {add}       Asset file related operations
    add       Upload the provided files to an existing asset, then print a URL
              to the asset on stdout or an error message if unsuccessful.

optional arguments:
  -h, --help  show this help message and exit

---------------
usage: nira.py asset files add [-h] [--no-upload-compression]
                               [--wait-for-asset-processing WAIT_MAX_SECONDS]
                               asset_name [files [files ...]]

positional arguments:
  asset_name            A name for an existing asset. If an asset with this
                        name does not exist, an error message will be printed.
                        If you wish to create a new asset and add files to it,
                        use the 'asset create' command, instead.
  files                 
                        There are two different methods for providing the files you wish to upload:
                        
                        * Method 1: Provide a list of file paths on the command line
                        
                          For example:
                             nira.py asset create myasset photogrammetry assets/tpot.obj assets/tpot.mtl
                          Will upload tpot.obj and tpot.mtl to a new asset called 'myasset'
                        
                          The server will attempt to automatically determine file types based
                          on their content. For photogrammetry files with photos, there's a potential
                          downside of relying upon automatic file type detection -- it is not always
                          possible to automatically determine the difference between a texture ("image")
                          or photo ("photogrammetry_image"). Therefore, for photogrammetry assets
                          with photos, "Method 2" below is suggested.
                        
                        * Method 2: Provide a json array on stdin
                            (Recommended for photogrammetry assets with photos)
                        
                            Here's an example of a json file list:
                            [{
                              "path": "assets/tpot.obj",
                              "type": "scene"
                            }, {
                              "path": "assets/tpot.mtl",
                              "type": "extra"
                            }, {
                              "path": "assets/blue.png",
                              "type": "image"
                            }, {
                              "path": "assets/photos/tpot-photo01.jpg",
                              "type": "photogrammetry_image"
                            }]
                            Providing this array will cause 4 files to be uploaded:
                              An obj geometry file (tpot.obj)
                              An MTL file (tpot.mtl)
                              A texture file (blue.png)
                              A photo (tpot-photo01.jpg)
                        
                        Other Notes:
                          * If you don't provide any file paths on the command line,
                            you wil be prompted to enter a files json array.
                          * If you're trying to automate Nira commands but you're
                            not familiar how to provide data through a command's stdin,
                            you can search for "Piping and redirection" along with your
                            operating system ("linux", "windows") to learn more about it.
                          * File paths may be absolute or relative to the runtime directory.
                          * When creating a new asset, at least one of the files should be
                            a geometry file (obj, ma, mb, zpr, etc). When adding files to an
                            existing asset, this does not apply.

optional arguments:
  -h, --help            show this help message and exit
  --no-upload-compression
                        Disables the use of automatic upload compression.
                        Upload compression is enabled by default. You may wish
                        to disable it if you have a particularly capable
                        upstream network throughput (1gbps+) or have concerns
                        about CPU utilization on the machine doing the
                        uploading.
  --wait-for-asset-processing WAIT_MAX_SECONDS
                        When using --upload, wait up to WAIT_MAX_SECONDS for
                        the asset to be processed on the server before
                        returning. If set to 0, the command will return
                        immediately after upload, and asset processing will
                        not have finished yet. Note, --upload will not print
                        an asset url unless the asset has finished processing,
                        so it is best to use a sufficiently large value for
                        this argument. If an error occurs during upload or
                        processing, the command will exit with a non-zero
                        status and print an error message.

---------------
usage: nira.py user [-h] {preauth} ...

positional arguments:
  {preauth}   User related operations
    preauth   Generates and prints a preauthentication uid and token for a
              user. This invalidates any prior preauthentication token for the
              user. It also creates the user, if they don't already exist

optional arguments:
  -h, --help  show this help message and exit

---------------
usage: nira.py user preauth [-h] [--name NAME] email

positional arguments:
  email        User email

optional arguments:
  -h, --help   show this help message and exit
  --name NAME  Name for user. This is optional, and by default will use the
               text prior to the '@' in the email address. The specified name
               is only used if the user doesn't already exist; Including
               parameter will not update existing user records.
```
