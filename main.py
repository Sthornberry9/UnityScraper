import os
import requests
import json
from requests.exceptions import RequestException, Timeout
from time import sleep

# Function to save JSON response
def save_json_response(title_id, data, json_type):
    directory_path = f'unityscrape/{title_id}/'
    os.makedirs(directory_path, exist_ok=True)
    file_path = os.path.join(directory_path, f'{json_type}_data.json')
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print(f"Saved {json_type} JSON response for title ID {title_id} at {file_path}")

# Function to make a request with retries
def make_request_with_retries(url, max_retries=3, timeout=25, stream=False):
    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(url, timeout=timeout, stream=stream)
            response.raise_for_status()
            return response
        except (RequestException, Timeout) as e:
            wait = 2 ** retries  # exponential backoff
            print(f"Request failed: {e}. Retrying in {wait} seconds...")
            sleep(wait)
            retries += 1
    return None

# Function to download covers for a given titleid
def download_covers(title_id):
    try:
        print(f"Fetching covers for title ID {title_id}...")
        response = make_request_with_retries(f'http://xboxunity.net/Resources/Lib/CoverInfo.php?titleid={title_id}')
        if not response:
            raise ValueError(f"Failed to fetch covers for title ID {title_id} after retries.")
        covers_data = response.json()
        save_json_response(title_id, covers_data, 'covers')
        for cover in covers_data['Covers']:
            cover_id = cover['CoverID']
            print(f"Downloading cover {cover_id} for title ID {title_id}...")
            image_url = f'http://xboxunity.net/Resources/Lib/Cover.php?size=large&cid={cover_id}'
            image_response = make_request_with_retries(image_url, stream=True)
            if not image_response:
                raise ValueError(f"Failed to download cover {cover_id} for title ID {title_id} after retries.")
            filename = f'{cover_id}.jpg'
            cover_path = f'unityscrape/{title_id}/covers/'
            os.makedirs(cover_path, exist_ok=True)
            with open(os.path.join(cover_path, filename), 'wb') as f:
                for chunk in image_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Cover {cover_id} downloaded successfully.")
        return True
    except Exception as e:
        print(f"An error occurred while processing covers for title ID {title_id}: {e}")
        return False

# Function to download updates for a given titleid
def download_updates(title_id):
    try:
        print(f"Fetching updates for title ID {title_id}...")
        response = make_request_with_retries(f'http://xboxunity.net/Resources/Lib/TitleUpdateInfo.php?titleid={title_id}')
        if not response:
            raise ValueError(f"Failed to fetch updates for title ID {title_id} after retries.")
        updates_data = response.json()
        save_json_response(title_id, updates_data, 'updates')
        for media in updates_data['MediaIDS']:
            media_id = media['MediaID']
            for update in media['Updates']:
                tuid = update['TitleUpdateID']
                version = update['Version']
                print(f"Downloading update {tuid} version {version} for media ID {media_id} under title ID {title_id}...")
                update_url = f'http://xboxunity.net/Resources/Lib/TitleUpdate.php?tuid={tuid}'
                update_response = make_request_with_retries(update_url, stream=True)
                if not update_response:
                    raise ValueError(f"Failed to download update {tuid} for title ID {title_id} after retries.")
                filename = f'update_{tuid}.bin'
                update_version_path = f'unityscrape/{title_id}/{media_id}/updateversion{version}/'
                os.makedirs(update_version_path, exist_ok=True)
                with open(os.path.join(update_version_path, filename), 'wb') as f:
                    for chunk in update_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"Update {tuid} version {version} downloaded successfully.")
        return True
    except Exception as e:
        print(f"An error occurred while processing updates for title ID {title_id}: {e}")
        return False

# Main script
def main():
    title_ids = input("Enter title IDs separated by commas: ").split(',')
    failed_title_ids = []

    for title_id in title_ids:
        title_id = title_id.strip()
        print(f"Processing title ID {title_id}...")
        success_covers = download_covers(title_id)
        success_updates = download_updates(title_id)

        if not success_covers or not success_updates:
            failed_title_ids.append(title_id)

        print(f"Finished processing title ID {title_id}.")

    if failed_title_ids:
        print(f"Failed to process the following title IDs: {', '.join(failed_title_ids)}")

if __name__ == "__main__":
    main()
