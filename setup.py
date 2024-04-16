import os
import shutil
import urllib.request
import zipfile

def download_and_extract_data(url, download_dir):
    # Create download directory if it doesn't exist
    os.makedirs(download_dir, exist_ok=True)

    # Download the data file
    filename = os.path.join(download_dir, 'data.zip')
    urllib.request.urlretrieve(url, filename)

    # Extract the downloaded zip file
    with zipfile.ZipFile(filename, 'r') as zip_ref:
        zip_ref.extractall(download_dir)

    # Remove the zip file after extraction
    os.remove(filename)

def move_data_to_submodule(data_dir, submodule_dir):
    # Create the destination directory if it doesn't exist
    os.makedirs(submodule_dir, exist_ok=True)

    # Move the data to the submodule directory
    shutil.move(data_dir, submodule_dir)

if __name__ == "__main__":
    # URL from which to download the data
    data_url = "https://example.com/data.zip"

    # Directory where the data will be downloaded
    download_directory = "precompiled_data"

    # Submodule directory
    submodule_directory = "pypsa-bo/pypsa-earth"

    # Download and extract the data
    download_and_extract_data(data_url, download_directory)

    # Move the data to the submodule directory
    move_data_to_submodule(os.path.join(download_directory, "data"), submodule_directory)