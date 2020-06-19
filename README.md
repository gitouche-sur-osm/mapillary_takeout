# mapillary_takeout

This script downloads your imagery from Mapillary. The official mapillary_tools download option only allows for bulk download of the blurred and compressed versions of the images. This script will download the "original unprocessed" images as you sent them to Mapillary.

## Requirements

* Python 3
* [Requests library](https://requests.readthedocs.io)

## Usage

```
usage: mapillary_takeout.py [-h] [--start-date YYYY-MM-DD]
                            [--end-date YYYY-MM-DD] [-D]
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
  -D, --dry-run         Check sequences status and leave
```							

## Acknowledgments

* Simon Mikkelsen original gist https://gist.github.com/simonmikkelsen/478accbc7b62c0c7786d6cd95fb09cae
* Anonymous helper
