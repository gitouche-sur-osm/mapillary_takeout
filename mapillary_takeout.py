#!/usr/bin/env python

import os
import sys
import json
import requests

CLIENT_ID = 'MkJKbDA0bnZuZlcxeTJHTmFqN3g1dzo1YTM0NjRkM2EyZGU5MzBh'
SEQUENCES_PER_PAGE = '200' # max from API is 1000, but timeouts.
REQUESTS_PER_CALL = 200 # 220 max, 200 is safe.

def get_mpy_auth(email, password):
    # returns mapillary token
    url = 'https://a.mapillary.com/v2/ua/login?client_id=' + CLIENT_ID
    headers = {'Host': 'a.mapillary.com',
               'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0',
               'Accept': 'application/json',
               'Accept-Language': 'en-US,en;q=0.5',
               'Referer': 'https://www.mapillary.com/app/',
               'Content-Type': 'application/json',
               'Origin': 'https://www.mapillary.com',
               'Connection': 'keep-alive',
               'DNT': '1'}
    payload = {'email': email, 'password': password}
    r = requests.post(url, headers=headers, json=payload)
    return r.json()['token']

def get_user_sequences(mpy_token, username):
    # returns sequences as json https://www.mapillary.com/developer/api-documentation/#the-sequence-object
    response = []
    nb_images = 0

    url = 'https://a.mapillary.com/v3/sequences?client_id=' + CLIENT_ID + '&usernames=' + username + '&per_page=' + SEQUENCES_PER_PAGE + '&end_time=2017-05-24'
    headers = {'Host': 'a.mapillary.com',
               'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0',
               'Accept': '*/*',
               'Accept-Language': 'en-US,en;q=0.5',
               'Referer': 'https://www.mapillary.com/app/&' + username,
               'Content-Type': 'application/x-www-form-urlencoded',
               'Origin': 'https://www.mapillary.com',
               'Connection': 'keep-alive',
               'DNT': '1',
               'Authorization': 'Bearer ' + mpy_token}
    r = requests.get(url, headers=headers)
    for i in r.json()['features']:
        response.append(i)
        nb_images += len(i['properties']['coordinateProperties']['image_keys'])

    # '''
    while 'next' in r.links:
        r = requests.get(r.links['next']['url'], headers=headers)
        for i in r.json()['features']:
            response.append(i)
            nb_seq = len(response)
            nb_images += len(i['properties']['coordinateProperties']['image_keys'])
        print('Fetching %s sequences (%s images) ...' % (nb_seq, nb_images))
    # '''
    return(response)

def download_image(url, sorted_path, download_path):
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0'}
    r = requests.get(url, headers=headers)
    if r.status_code == requests.codes.ok:
        with open(download_path, 'wb') as f:
            f.write(r.content)
            os.link(download_path, sorted_path)
    else:
        print('Error downloading %r, skipping' % sorted_path)

def download_sequence(output_folder, mpy_token, sequence, username):
    sequence_name = sequence['properties']['captured_at']
    sequence_day = sequence_name.split('T')[0]
    sequence_folder = output_folder + '/downloads/' + sequence_name
    sorted_folder = output_folder + '/sorted/' + sequence_day
    download_list = []
    os.makedirs(sequence_folder, exist_ok=True)
    os.makedirs(sorted_folder, exist_ok=True)

    # First pass on image_keys : sorts which one needs downloading
    image_index = 0
    for i in range(len(sequence['properties']['coordinateProperties']['image_keys'])):
        image_index += 1
        image_key = sequence['properties']['coordinateProperties']['image_keys'][i]
        sorted_path = sorted_folder + '/' + sequence_name + '_' + "%04d" % image_index + '.jpg'
        download_path = sequence_folder + '/' + image_key + '.jpg'
        
        if not (os.path.isfile(download_path) and os.path.isfile(sorted_path)):
            if os.path.exists(download_path):
                os.remove(download_path)
            if os.path.exists(sorted_path):
                os.remove(sorted_path)
            download_list.append(sequence['properties']['coordinateProperties']['image_keys'][i])
        else:
            print('Image %r already downloaded' % sorted_path)
    if not download_list:
        print('Sequence %r already fully downloaded' % sequence_name)
        return

    # Second pass : split in chunks and feed into source_urls dict
    source_urls = {}
    chunks = [download_list[x:x+REQUESTS_PER_CALL] for x in range(0, len(sequence['properties']['coordinateProperties']['image_keys']), REQUESTS_PER_CALL)]
    for chunk in chunks:
        # Chunks are sometimes empty. 
        if not chunk:
            break
        image_keys = '[\"' + "\",\"".join(chunk) + '\"]'
        paths='[["imageByKey",' + image_keys + ',["original_url"]]]'
        url = 'https://a.mapillary.com/v3/model.json?client_id=' + CLIENT_ID + '&paths=' + paths + '&method=get'
        headers = {'Host': 'a.mapillary.com',
                   'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0',
                   'Accept': '*/*',
                   'Accept-Language': 'en-US,en;q=0.5',
                   'Referer': 'https://www.mapillary.com/app/&' + username,
                   'Content-Type': 'application/x-www-form-urlencoded',
                   'Origin': 'https://www.mapillary.com',
                   'Connection': 'keep-alive',
                   'DNT': '1',
                   'Authorization': 'Bearer ' + mpy_token}
        r = requests.get(url, headers=headers)
        if 'jsonGraph' in r.json():
            for i in r.json()['jsonGraph']['imageByKey']:
                if 'value' in r.json()['jsonGraph']['imageByKey'][i]['original_url']:
                    source_urls[i] = r.json()['jsonGraph']['imageByKey'][i]['original_url']['value']
                else:
                    print('Cant locate original_url for image %r' % i)
                        
    # Third pass, download if entry is found in dict
    image_index = 0
    for i in range(len(sequence['properties']['coordinateProperties']['image_keys'])):
        image_key = sequence['properties']['coordinateProperties']['image_keys'][i]
        image_index += 1
        if image_key in download_list:
            sorted_path = sorted_folder + '/' + sequence_name + '_' + "%04d" % image_index + '.jpg'
            download_path = sequence_folder + '/' + image_key + '.jpg'
            print('Downloading image %r' % sorted_path)
            download_image(source_urls[image_key], sorted_path, download_path)

def main(email, password, username, output_folder):
    mpy_token = get_mpy_auth(email, password)
    user_sequences = get_user_sequences(mpy_token, username)
    for sequence in user_sequences:
        print('Sequence %r' % sequence['properties']['captured_at'])
        download_sequence(output_folder, mpy_token, sequence, username)
    return 0

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("Usage: python %s <email> <password> <username> <output_folder>" % sys.argv[0])
        sys.exit(-1)
    exit(main(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4]))
