#!/usr/bin/env python3

import argparse
import json
import os
import re
import requests
import sys
import time

from multiprocessing.pool import ThreadPool


##################################################################################################
# config
#
NUM_THREADS = 16

# mapillary_tools client_id
CLIENT_ID = "MkJKbDA0bnZuZlcxeTJHTmFqN3g1dzo1YTM0NjRkM2EyZGU5MzBh"

# Max from API is 1000, but timeouts
SEQUENCES_PER_PAGE = "100"

# 220 max
REQUESTS_PER_CALL = 210

# Number of retries for a sequence
# Normally a sequence is limited to 1000 images, but this is no longer true for the iPhone
# Given the low reliability of AWS S3 (<0.99) we need to set an insanse high retry value
# to download 3k of images
SEQUENCE_DL_MAX_RETRIES = 128

# verbose level 0..2
# 0: only import messages, like errors
# 1: more verbose
# 2: full verbose
# 3: debug
DEBUG = 0

# connection timeout to AWS S3
# this will raise an exception for a download, and we retry to download the image later
DOWNLOAD_FILE_TIMEOUT=5

# timeout for login and sequences
META_TIMEOUT=60

API_ENDPOINT = "https://a.mapillary.com"

LOGIN_URL = API_ENDPOINT + "/v2/ua/login?client_id=" + CLIENT_ID
SEQUENCES_URL = (
    API_ENDPOINT
    + "/v3/sequences?client_id="
    + CLIENT_ID
    + "&per_page="
    + SEQUENCES_PER_PAGE
)
MODEL_URL = API_ENDPOINT + "/v3/model.json?client_id=" + CLIENT_ID

AWS_EXPIRED = '<\?xml version="1\.0" encoding="UTF-8"\?>\\n<Error><Code>AccessDenied<\/Code><Message>Request has expired<\/Message>'

DRY_RUN = False

# count downloads per sequence
_DOWNLOAD_SEQUENCE_SIZE = 0
_DOWNLOAD_TOTAL_SIZE = 0

# estimates
AVERAGE_IMAGE_SIZE=2500000


##################################################################################################
# exception classes
#
class SSLException(Exception):
    pass

class DownloadException(Exception):
    pass

class URLExpireException(Exception):
    pass


##################################################################################################
# functions
#
def get_mpy_auth(email, password):
    # Returns mapillary token
    payload = {"email": email, "password": password}
    r = requests.post(LOGIN_URL, json=payload)
    if r and "token" in r.json():
        r.close()
        return r.json()["token"]
    elif r and "message" in r.json():
        print("Authentication failed: %s" % r.json()["message"])
    else:
        print(
            "Authentication failed with HTTP error %r : %r" % (r.status_code, r.text,)
        )
    r.close()
    sys.exit(-1)


def get_user_sequences(mpy_token, username, start_date, end_date):
    # Fetches all sequences for the username and
    # returns them in an array of json objects
    # https://www.mapillary.com/developer/api-documentation/#the-sequence-object
    response = []
    nb_images = 0
    headers = {"Authorization": "Bearer " + mpy_token}

    try:
        r = requests.get(
            SEQUENCES_URL,
            headers=headers,
            params={"usernames": username, "start_time": start_date, "end_time": end_date},
            timeout=META_TIMEOUT
        )
    except:
        raise DownloadException("Error downloading sequence URL %r" % SEQUENCES_URL)

    try:
        r.json()
    except:
        raise DownloadException("Error parsing json response, give up")


    for feature in r.json()["features"]:
        response.append(feature)
        nb_images += len(feature["properties"]["coordinateProperties"]["image_keys"])
    r.close()
    nb_seq = len(response)
    while "next" in r.links:
        try:
            r = requests.get(r.links["next"]["url"], headers=headers, timeout=META_TIMEOUT)
        except:
            print("Error downloading next URL %r" % r.links["next"]["url"])
            continue

        try:
            json = r.json()
            features = json["features"]
        except:
            print("Error parsing json object, ignore")
            continue

        for feature in features:
            response.append(feature)
            nb_images += len(
                feature["properties"]["coordinateProperties"]["image_keys"]
            )
        r.close()
        nb_seq = len(response)
        if DEBUG >= 1:
            print("Fetched %s sequences (%s images) ..." % (nb_seq, nb_images), end="\r")
    return (response, nb_seq)


def get_source_urls(download_list, mpy_token, username):
    if DEBUG >= 2:
        print(" Start get_source_urls()")
        
    # Fetches "unprocessed original" images URL and returns them in a dict
    source_urls = {}
    chunks = [
        download_list[x : x + REQUESTS_PER_CALL]
        for x in range(0, len(download_list), REQUESTS_PER_CALL)
    ]
    
    counter = 0
    for chunk in chunks:
        params = {
            "paths": json.dumps(
                [["imageByKey", chunk, ["original_url"]]], separators=(",", ":")
            ),
            "method": "get",
        }
        headers = {"Authorization": "Bearer " + mpy_token}
        
        try:
            counter += len(chunk)
            if DEBUG >= 3:
                print(" Fetch model URLs in chunks: (%d/%d)" % (counter, len(download_list)))
            r = requests.get(MODEL_URL, headers=headers, params=params, timeout=META_TIMEOUT)
        except:
            raise DownloadException("Error downloading model URL %r, ignore sequence" % MODEL_URL)
                                                                                             
        try:                                                                                     
            data = r.json()
        except:
            print("Error parsing JSON model URL response, ignore sequence")
            r.close()
            continue
            
        if "jsonGraph" in data:
            for image_key, image in data["jsonGraph"]["imageByKey"].items():
                if "value" in image["original_url"]:
                    source_urls[image_key] = image["original_url"]["value"]
        r.close()
       
    return source_urls


def download_file(args):
    image_key, sorted_path, source_url = args
    global _DOWNLOAD_SEQUENCE_SIZE
    
    try:
        r = requests.get(source_url, stream=True, timeout=DOWNLOAD_FILE_TIMEOUT)
    except requests.exceptions.SSLError:
        raise SSLException("SSL error downloading %r, retrying later" % image_key)
    except:
        if DEBUG >= 1:
            raise DownloadException("Error downloading %r, retrying later. Info %r" % (image_key, sys.exc_info()[0],) )
        else:
            return False
            
    if r.status_code == requests.codes.ok:
        size = int(r.headers["content-length"])
        if os.path.isfile(sorted_path) and os.path.getsize(sorted_path) == size:
            if DEBUG >= 3:
                print("  Already downloaded as %r" % sorted_path)
        else:
            if os.path.isfile(sorted_path):
                if DEBUG >= 2:
                    print("  Size mismatch for %r, replacing..." % sorted_path)

            try:
                with open(sorted_path, "wb") as f:
                    f.write(r.content)
            except:
                if DEBUG >= 1:
                     raise DownloadException("Error downloading image %r, retrying later. Info %r" % (image_key, sys.exc_info()[0],))
                else:
                    return False

            # downloaded MB per sequence            
            _DOWNLOAD_SEQUENCE_SIZE += size

        return image_key
    elif r.status_code == 403 and re.match(AWS_EXPIRED, r.text):
        raise URLExpireException("Download token expired, requesting fresh one ...")
    else:
        print(
            "  Error %r downloading image %r : %r" % (r.status_code, image_key, r.text,)
        )
    return False


def download_sequence(output_folder, mpy_token, sequence, username, c, nb_sequences):
    global _DOWNLOAD_SEQUENCE_SIZE
    global _DOWNLOAD_TOTAL_SIZE
    
    if DEBUG >= 3:
        print(" Prepare sequence download")
        
    sequence_name = (
        sequence["properties"]["captured_at"]
        + "_"
        + sequence["properties"]["created_at"]
    )
    if os.name == "nt":
        sequence_name = sequence_name.replace(":", "_")
    sequence_day = sequence_name.split("T")[0]
    sorted_folder = output_folder + "/" + sequence_day
    download_list = []
    os.makedirs(sorted_folder, exist_ok=True)

    # First pass on image_keys : sorts which one needs downloading
    image_keys = sequence["properties"]["coordinateProperties"]["image_keys"]
    for image_index, image_key in enumerate(image_keys, 1):
        sorted_path = (
            sorted_folder + "/" + sequence_name + "_" + "%04d" % image_index + ".jpg"
        )
        if not os.path.exists(sorted_path):
            download_list.append(image_key)
        elif os.stat(sorted_path).st_size == 0:
            download_list.append(image_key)
    if not download_list:
        if DEBUG >= 2:
            print(" Sequence %r already fully downloaded" % sequence_name)
        return 0, 0

    already_downloaded = len(image_keys) - len(download_list)
    if already_downloaded:
        if DEBUG >= 1:
            print(" Already downloaded: %d/%d" % (already_downloaded, len(image_keys)))

    if DRY_RUN:
        return 1, len(download_list)

    # Third pass, download if entry is found in dict
    sequence_dl_retries = 0
    update_urls = True
    while download_list and not sequence_dl_retries >= SEQUENCE_DL_MAX_RETRIES:
        if update_urls:
            source_urls = get_source_urls(download_list, mpy_token, username)
            update_urls = False

        sequence_dl_retries += 1

        # show only on a retry
        if sequence_dl_retries > 1 and DEBUG >= 1:
            print("sequence download retries: %s/%s" % (sequence_dl_retries, SEQUENCE_DL_MAX_RETRIES))

        if len(download_list) > len(source_urls):
            print(
                " Missing %d/%d images : will refresh and retry later"
                % (len(download_list) - len(source_urls), len(download_list))
            )
            
            # if we get nothing wait a little bit
            if len(download_list) - len(source_urls) == len(download_list):
                if DEBUG >= 1:
                    print(" Wait a second due long missing source list")
                time.sleep(2)
                
            sequence_dl_retries -= 1
            # refresh list after this pass
            update_urls = True

        pool = ThreadPool(NUM_THREADS)
        pool_args = []
        for image_index, image_key in enumerate(image_keys, 1):
            if image_key in download_list:
                sorted_path = (
                    sorted_folder
                    + "/"
                    + sequence_name
                    + "_"
                    + "%04d" % image_index
                    + ".jpg"
                )
                if image_key in source_urls:
                    source_url = source_urls[image_key]
                    pool_args.append((image_key, sorted_path, source_url))

        if DEBUG >= 3:
            print(" Filling download pool done")
        
        try:
            for i, image_key in enumerate(pool.imap(download_file, pool_args), 1):
                if image_key:
                    download_list.remove(image_key)
                print(
                    "  Downloading images #%03d out of %03d round: %d" % (i, len(pool_args), sequence_dl_retries),
                    end="\r",
                    flush=True,
                )
        except SSLException as e:
            print(e)
        except DownloadException as e:
            print(e)
        except URLExpireException as e:
            print(e)
            sequence_dl_retries -= 1
            # refresh urls
            update_urls = True
        finally:
            pool.terminate()
            pool.join()
    print(" Done sequence %r (%d/%d) %3.1f MB" % (sequence_name, c, nb_sequences, _DOWNLOAD_SEQUENCE_SIZE/1024/1024), flush=True)
    _DOWNLOAD_TOTAL_SIZE += _DOWNLOAD_SEQUENCE_SIZE
    _DOWNLOAD_SEQUENCE_SIZE = 0
                    
    return 1, len(source_urls)


def add(tgt, src):
    for i in range(len(tgt)):
        tgt[i] += src[i]


def main(email, password, username, output_folder, start_date, end_date):
    mpy_token = get_mpy_auth(email, password)
    user_sequences, nb_sequences = get_user_sequences(
        mpy_token, username, start_date, end_date
    )
    if not nb_sequences:
        print(
            "No sequences found to download. Check this is the valid username at https://www.mapillary.com/app/user/%s"
            % username
        )
        sys.exit(-2)
    accumulated_stats = [0, 0]  # seq, img,
    for c, sequence in enumerate(reversed(user_sequences), 1):
        stats = download_sequence(output_folder, mpy_token, sequence, username, c, nb_sequences )
        add(accumulated_stats, stats)
        
        if DEBUG >= 2:
            print(
                "Sequence %s_%s (%d/%d) contains %d images"
                % (
                    sequence["properties"]["captured_at"],
                    sequence["properties"]["created_at"],
                    c,
                    nb_sequences,
                    stats[1]
                )
            )
    if DRY_RUN:
        print(
            "%s images in %s sequences would have been downloaded without the dry run"
            % (accumulated_stats[1], accumulated_stats[0],)
        )
        download_size = accumulated_stats[1] * AVERAGE_IMAGE_SIZE;

        if accumulated_stats[1] == 0:
            print("You are up-to-date, all images are already downloaded. Great!")
        else:
            print("Estimated download size: %2.1f GB" % (download_size / 1024/1024/1024))
            print("Estimated download time 250Mbit/s: %2.1f min, 100Mbit/s: %2.1f min, 50Mbit/s: %2.1f min, 16Mbit/s %2.1f min" % (
                (download_size / 250/1000/1000*8/60),
                (download_size / 100/1000/1000*8/60),
                (download_size /  50/1000/1000*8/60),
                (download_size /  16/1000/1000*8/60),
            ))

    else:
        global _DOWNLOAD_TOTAL_SIZE
        if accumulated_stats[1] > 0:
            print("Total images: %s total download size: %2.1f GB average image size: %2.1f MB" %
                (accumulated_stats[1],
                _DOWNLOAD_TOTAL_SIZE/1024/1024/1024,
                _DOWNLOAD_TOTAL_SIZE/accumulated_stats[1]/1024/1024))
        else:
            print("Nothing to download")
            
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download your images from Mapillary")
    parser.add_argument("email", help="Your email address for mapillary authentication")
    parser.add_argument("password", help="Your mapillary password")
    parser.add_argument("username", help="Your mapillary username")
    parser.add_argument("output_folder", help="Download destination")
    parser.add_argument(
        "--start-date",
        help="Filter sequences that are captured since this date",
        metavar="YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date",
        help="Filter sequences that are captured before this date",
        metavar="YYYY-MM-DD",
    )
    parser.add_argument( "--debug", metavar="0..3",  help="set global debug level")
    parser.add_argument( "--timeout", metavar="1..300",  help="set connection/read timeout in seconds")
    parser.add_argument( "--timeout-meta", metavar="1..300",  help="set connection/read timeout for meta requests in seconds")
    parser.add_argument( "--threads", metavar="1..128",  help="number of threads")
    parser.add_argument( "--retries", metavar="1..512",  help="sequence max. retries")
    parser.add_argument(
        "-D", "--dry-run", action="store_true", help="Check sequences status, display estimates and leave"
    )
    args = parser.parse_args()

    if args.dry_run:
        DRY_RUN = True

    if args.debug:
        try:
            debug = int(args.debug)
        except:
            print("illegal value for debug: %s" % args.debug)
            sys.exit(-1)
        if debug >= 0 and debug <= 3:
            DEBUG = debug
        else:
            print ("debug parameter is out of range 0..3: %s, ignored" % debug)

    if args.timeout:
        try:
            timeout = float(args.timeout)
        except:
            print("illegal value for timeout: %s" % args.timeout)
            sys.exit(-1)
        if timeout > 0 and timeout <= 300:
            DOWNLOAD_FILE_TIMEOUT = timeout
        else:
            print ("timeout parameter is out of range 0..300: %s, ignored" % timeout)

    if args.timeout_meta:
        try:
            timeout_meta = float(args.timeout_meta)
        except:
            print("illegal value for timeout: %s" % args.timeout_meta)
            sys.exit(-1)
        if timeout_meta > 0 and timeout_meta <= 300:
            META_TIMEOUT = timeout_meta
        else:
            print ("timeout meta parameter is out of range 0..300: %s, ignored" % timeout_meta)

    if args.threads:
        try:
            threads = int(args.threads)
        except:
            print("illegal value for threads: %s" % args.threads)
            sys.exit(-1)
        if threads > 0 and threads <= 128:
            NUM_THREADS = threads
        else:
            print ("timeout parameter is out of range 0..128: %s, ignored" % threads)
            
    if args.retries:
        try:
            retries = int(args.retries)
        except:
            print("illegal value for retries: %s" % args.retries)
            sys.exit(-1)
        if retries > 0 and retries <= 512:
            SEQUENCE_DL_MAX_RETRIES = retries
        else:
            print ("retries parameter is out of range 0..512: %s, ignored" % retries)

    if DEBUG > 0:
        print("number of threads: %d, connection timeout: %2.1f sec., retries: %d, debug: %d" % (NUM_THREADS, DOWNLOAD_FILE_TIMEOUT, SEQUENCE_DL_MAX_RETRIES, DEBUG))
        
    exit(
        main(
            args.email,
            args.password,
            args.username,
            args.output_folder,
            args.start_date,
            args.end_date,
        )
    )
