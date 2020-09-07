# mapillary_takeout

This script downloads your imagery from Mapillary. The official mapillary_tools download option only allows for bulk download of the blurred and compressed versions of the images. This script will download the "original unprocessed" images as you sent them to Mapillary.

## Getting started

### Requirements

* Python 3
* [Requests library](https://requests.readthedocs.io)

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
usage: mapillary_takeout.py [-h] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
                            [--debug 0..3] [--timeout 1..300] [--threads 1..128] [--retries 1..512] [-D]
                            email password username output_folder

Download your images from Mapillary

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
  --debug 0..2          set global debug level
  --timeout 1..300      set connection timeout
  --threads 1..128      number of threads
  --retries 1..512      sequence max retries
  -D, --dry-run         Check sequences status, display estimates and leave
```							

## Friendly projects

* [Mapillary Takeout Web](https://github.com/frodrigo/mapillary_takeout_web) : web frontend for mapillary_takeout
* [Exit Mapillary](https://framagit.org/Midgard/exit-mapillary) : remove all photos from your Mapillary account

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details

## Acknowledgments

* Simon Mikkelsen original gist https://gist.github.com/simonmikkelsen/478accbc7b62c0c7786d6cd95fb09cae
* Anonymous helper (thank you!)
* Another anonymous helper (thank you very much!)
