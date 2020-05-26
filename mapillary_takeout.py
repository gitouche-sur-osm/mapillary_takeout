#!/usr/bin/env python

import os
import sys
import re
import json
import requests

# mapillary_tools client_id
CLIENT_ID = "MkJKbDA0bnZuZlcxeTJHTmFqN3g1dzo1YTM0NjRkM2EyZGU5MzBh"

SEQUENCES_PER_PAGE = "100" # max from API is 1000, but timeouts.
REQUESTS_PER_CALL = 210  # 220 max.
SEQUENCE_DL_MAX_RETRIES = 5  # If your download speed is really slow, go higher.

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

DRY_RUN = False

def get_mpy_auth(email, password):
    # returns mapillary token
    payload = {"email": email, "password": password}
    r = requests.post(LOGIN_URL, json=payload)
    return r.json()["token"]


def get_user_sequences(mpy_token, username):
    # returns sequences as json https://www.mapillary.com/developer/api-documentation/#the-sequence-object
    response = []
    nb_images = 0
    headers = {"Authorization": "Bearer " + mpy_token}

    r = requests.get(SEQUENCES_URL, headers=headers, params={"usernames": username})
    for feature in r.json()["features"]:
        response.append(feature)
        nb_images += len(feature["properties"]["coordinateProperties"]["image_keys"])

    # '''
    while "next" in r.links:
        r = requests.get(r.links["next"]["url"], headers=headers)
        for feature in r.json()["features"]:
            response.append(feature)
            nb_seq = len(response)
            nb_images += len(
                feature["properties"]["coordinateProperties"]["image_keys"]
            )
        print("Fetching %s sequences (%s images) ..." % (nb_seq, nb_images))
    # '''
    return response


def get_source_urls(download_list, mpy_token, username):
    source_urls = {}
    chunks = [
        download_list[x : x + REQUESTS_PER_CALL]
        for x in range(0, len(download_list), REQUESTS_PER_CALL)
    ]
    for chunk in chunks:
        params = {
            "paths": json.dumps(
                [["imageByKey", chunk, ["original_url"]]], separators=(",", ":")
            ),
            "method": "get",
        }
        headers = {"Authorization": "Bearer " + mpy_token}
        r = requests.get(MODEL_URL, headers=headers, params=params)
        data = r.json()
        if "jsonGraph" in data:
            for image_key, image in data["jsonGraph"]["imageByKey"].items():
                if "value" in image["original_url"]:
                    source_urls[image_key] = image["original_url"]["value"]
                else:
                    print("Cant locate original_url for image %r" % image_key)
    return source_urls


def download_sequence(output_folder, mpy_token, sequence, username):
    sequence_name = (
        sequence["properties"]["captured_at"]
        + "_"
        + sequence["properties"]["created_at"]
    )
    sequence_day = sequence_name.split("T")[0]
    sequence_folder = output_folder + "/downloads/" + sequence_name
    sorted_folder = output_folder + "/sorted/" + sequence_day
    download_list = []
    os.makedirs(sequence_folder, exist_ok=True)
    os.makedirs(sorted_folder, exist_ok=True)

    # First pass on image_keys : sorts which one needs downloading
    image_keys = sequence["properties"]["coordinateProperties"]["image_keys"]
    to_remove = []
    linkless_images = []
    for image_index, image_key in enumerate(image_keys, 1):
        sorted_path = (
            sorted_folder + "/" + sequence_name + "_" + "%04d" % image_index + ".jpg"
        )
        download_path = sequence_folder + "/" + image_key + ".jpg"

        if os.path.isfile(download_path) and os.path.isfile(sorted_path):
            if os.path.samefile(download_path, sorted_path):
                pass
            else:
                # Fail safe, the file will be erased at download time
                # os.remove(download_path)
                linkless_images.append(download_path)
                to_remove.append(sorted_path)
                download_list.append(image_key)
        else:
            if os.path.exists(download_path):
                # Fail safe, the file will be erased at download time
                # os.remove(download_path)
                linkless_images.append(download_path)
                pass
            if os.path.exists(sorted_path):
                to_remove.append(sorted_path)
            download_list.append(image_key)
    if not download_list:
        print(" Sequence %r already fully downloaded" % sequence_name)
        return

    print(" Already downloaded: %d/%d" % (len(image_keys) - len(download_list),len(image_keys)))
    print(" Non-consistent links:", len(to_remove))
    print(" Images without link:", len(linkless_images))

    if DRY_RUN:
        return

    # Delete wrong sorted hard links
    for sorted_path in to_remove:
        os.remove(sorted_path)

    # Second pass : split in chunks and feed into source_urls dict
    source_urls = get_source_urls(download_list, mpy_token, username)

    if len(download_list) > len(source_urls):
        print(
            " Missing %d/%d images"
            % (len(download_list) - len(source_urls), len(download_list))
        )

    # Third pass, download if entry is found in dict
    sequence_dl_retries = 0
    while download_list and not sequence_dl_retries >= SEQUENCE_DL_MAX_RETRIES:
        sequence_dl_retries += 1
        image_index = 0
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
                download_path = sequence_folder + "/" + image_key + ".jpg"
                print(" Downloading image %r" % sorted_path)

                # Get the header first (stream) and compare size
                r = requests.get(source_urls[image_key], stream=True)
                if r.status_code == requests.codes.ok:
                    size = int(r.headers['content-length'])
                    if os.path.isfile(download_path) and os.path.getsize(download_path) == size:
                        print("  Already downloaded as %r", image_key)
                    else:
                        if os.path.isfile(download_path):
                            print("  Size mismatch for %r, replacing..." % image_key)
                        with open(download_path, "wb") as f:
                            f.write(r.content)

                    os.link(download_path, sorted_path)
                    download_list.remove(image_key)
                elif r.status_code == 403 and re.match(
                    '<\?xml version="1\.0" encoding="UTF-8"\?>\\n<Error><Code>AccessDenied<\/Code><Message>Request has expired<\/Message>',
                    r.text,
                ):
                    print(" Download token expired, requesting fresh one ...")
                    source_urls = get_source_urls(download_list, mpy_token, username)
                    r.close()
                    break
                else:
                    print(" Error downloading %r" % sorted_path)
                r.close()


def main(email, password, username, output_folder):
    mpy_token = get_mpy_auth(email, password)
    user_sequences = get_user_sequences(mpy_token, username)
    for sequence in reversed(user_sequences):
        print(
            "Sequence %s_%s"
            % (
                sequence["properties"]["captured_at"],
                sequence["properties"]["created_at"],
            )
        )
        download_sequence(output_folder, mpy_token, sequence, username)
    return 0


if __name__ == "__main__":
    if '-d' in sys.argv:
        DRY_RUN = True
        sys.argv.remove('-d')
    if len(sys.argv) != 5:
        print(
            "Usage: python %s <email> <password> <username> <output_folder>"
            % sys.argv[0]
        )
        sys.exit(-1)
    exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
