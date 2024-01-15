import os
import requests
import json
from requests.exceptions import RequestException, Timeout

# Function to save JSON response
def save_json_response(title_id, data, json_type):
    directory_path = f'examplefolder/{title_id}/'
    os.makedirs(directory_path, exist_ok=True)
    file_path = os.path.join(directory_path, f'{json_type}_data.json')
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print(f"Saved {json_type} JSON response for title ID {title_id} at {file_path}")

# Function to download covers for a given titleid
def download_covers(title_id):
    try:
        print(f"Fetching covers for title ID {title_id}...")
        response = requests.get(f'http://xboxunity.net/Resources/Lib/CoverInfo.php?titleid={title_id}', timeout=10)
        response.raise_for_status()
        covers_data = response.json()
        save_json_response(title_id, covers_data, 'covers')
        for cover in covers_data['Covers']:
            cover_id = cover['CoverID']
            print(f"Downloading cover {cover_id} for title ID {title_id}...")
            image_url = f'http://xboxunity.net/Resources/Lib/Cover.php?size=large&cid={cover_id}'
            image_response = requests.get(image_url, stream=True, timeout=10)
            image_response.raise_for_status()
            filename = image_response.headers.get('content-disposition')
            if filename:
                filename = filename.split('filename=')[1].strip('"')
            else:
                filename = f'{cover_id}.jpg'
            cover_path = f'examplefolder/{title_id}/covers/'
            os.makedirs(cover_path, exist_ok=True)
            with open(os.path.join(cover_path, filename), 'wb') as f:
                for chunk in image_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"Cover {cover_id} downloaded successfully.")
    except Timeout:
        print(f"Request timed out while fetching covers for title ID {title_id}.")
    except RequestException as e:
        print(f"An error occurred while fetching covers for title ID {title_id}: {e}")
    except json.JSONDecodeError:
        print(f"Failed to parse JSON response for covers of title ID {title_id}.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

# Function to download updates for a given titleid
# Function to download updates for a given titleid
def download_updates(title_id):
    try:
        print(f"Fetching updates for title ID {title_id}...")
        response = requests.get(f'http://xboxunity.net/Resources/Lib/TitleUpdateInfo.php?titleid={title_id}', timeout=10)
        response.raise_for_status()
        updates_data = response.json()
        save_json_response(title_id, updates_data, 'updates')
        for media in updates_data['MediaIDS']:
            media_id = media['MediaID']
            for update in media['Updates']:
                tuid = update['TitleUpdateID']
                version = update['Version']
                print(f"Downloading update {tuid} version {version} for media ID {media_id} under title ID {title_id}...")
                update_url = f'http://xboxunity.net/Resources/Lib/TitleUpdate.php?tuid={tuid}'
                update_response = requests.get(update_url, stream=True, timeout=10)
                update_response.raise_for_status()
                filename = update_response.headers.get('content-disposition')
                if filename:
                    filename = filename.split('filename=')[1].strip('"')
                else:
                    filename = f'update_{tuid}.bin'
                update_version_path = f'examplefolder/{title_id}/{media_id}/updateversion{version}/'
                os.makedirs(update_version_path, exist_ok=True)
                with open(os.path.join(update_version_path, filename), 'wb') as f:
                    for chunk in update_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                print(f"Update {tuid} version {version} downloaded successfully.")
    except Timeout:
        print(f"Request timed out while fetching updates for title ID {title_id}.")
    except RequestException as e:
        print(f"An error occurred while fetching updates for title ID {title_id}: {e}")
    except json.JSONDecodeError:
        print(f"Failed to parse JSON response for updates of title ID {title_id}.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
# Main script
def main():
    title_ids = input("Enter title IDs separated by commas: ").split(',')
    for title_id in title_ids: 
        title_id = title_id.strip()
        print(f"Processing title ID {title_id}...")
        download_covers(title_id)
        download_updates(title_id)
        print(f"Finished processing title ID {title_id}.")

if __name__ == "__main__":
    main()