# mapillary_takeout

```diff
-PLEASE NOTE: this script was written for mapillary API version 3, running on
the old mapillary Amazon AWS infrastructure. Starting in June 2021 mapillary 
switched to API v4 on Facebook infrastructure and the takeout scripts stopped working.
The migration from API v3 to v4 is still work in progress, see the mapillary forum.
Given that v4 is not ready for production use we cannot make an estimate when
the mapillary takeout scripts will work again. Sorry!!! And thanks for your patience!
```

This script downloads your imagery from Mapillary.
The official mapillary_tools download option only allows for bulk download of
the blurred and compressed versions of the images. 
This script will download the "original unprocessed" images as you sent them to Mapillary.

Note: due to privacy regulations you may get only a blurred version of your original images,
but the size, resolution, and metadata will still be the same as the original.

## Getting started

### Requirements

* Python 3
* [Requests library](https://requests.readthedocs.io)

on debian run: sudo apt-get install python3-requests

on MacOS run: brew install python3 && python3 -m pip install requests

### Install and run
#### Get the code
With git (preffered) :
```
git clone https://github.com/gitouche-sur-osm/mapillary_takeout.git
cd mapillary_takeout
```
OR with wget :
```
wget https://github.com/gitouche-sur-osm/mapillary_takeout/archive/master.zip
unzip master.zip
cd mapillary_takeout-master
```
#### Run the code
```
./mapillary_takeout.py <email> <password> <username> <output_folder>
```
Example
```
./mapillary_takeout.py gitouche@email.com azerty123 gitouche /path/to/backup
```
You should quote your fields if they contain special characters :
```
./mapillary_takeout.py gitouche@email.com 'password;with special|characters' gitouche '/path/to/MY BACKUP'
```
## Full usage
```
./mapillary_takeout.py --help
usage: mapillary_takeout.py [-h] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
                            [--debug 0..4] [--timeout 1..300] [--timeout-meta 1..300]
                            [--threads 1..128] [--retries 1..512] [-D]
                            email password username output_folder

Download your images from Mapillary, version: 1.2

positional arguments:
  email                 Your email address for mapillary authentication
  password              Your mapillary password
  username              Your mapillary username
  output_folder         Download destination

optional arguments:
  -h, --help            show this help message and exit
  --start-date YYYY-MM-DD
                        Filter sequences that are captured since this date
  --end-date YYYY-MM-DD
                        Filter sequences that are captured before this date 
                        (Note: end date is not included!)
  --debug 0..4          set global debug level, default: 0
  --timeout 1..300      set connection/read timeout in seconds, default: 5
  --timeout-meta 1..300
                        set connection/read timeout for meta requests in seconds, default: 60
  --threads 1..128      number of threads, default: 16
  --retries 1..512      sequence max. retries, default: 128
  -D, --dry-run         Check sequences status, display estimates and leave
  --subfolder           Store images by date and sequence subfolders, default: False
```							

## Friendly projects

* [Mapillary Takeout Web](https://github.com/frodrigo/mapillary_takeout_web) : web frontend for mapillary_takeout
* [Exit Mapillary](https://framagit.org/Midgard/exit-mapillary) : remove all photos from your Mapillary account

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details

## Acknowledgments

* Simon Mikkelsen original gist https://gist.github.com/simonmikkelsen/478accbc7b62c0c7786d6cd95fb09cae
* Wolfram Schneider
* Anonymous helpers - thank you very much!

