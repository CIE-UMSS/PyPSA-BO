import os
import shutil
import urllib.request
import zipfile
import requests
from tqdm import tqdm


'''Function to download data from the zenodo repository'''

def download_file(url, output_file):

    # Check to see if the file already exists 
    if os.path.exists(output_file):
        print(f"File '{output_file}' already exists. Skipping download.")
        return
    
    # Send a HEAD request to the server to get the file size
    response = requests.head(url)
    file_size = int(response.headers.get('content-length', 0))
    print(f"File size: {file_size} bytes")

    # Make the request again, but this time use stream=True to download in chunks
    response = requests.get(url, stream=True)
    with open(output_file, 'wb') as f, tqdm(
        total=file_size,
        unit='B',
        unit_scale=True,
        desc=output_file,
        ascii=True,
    ) as pbar:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                pbar.update(len(chunk))

    print("Download completed successfully.")



'''Function to extract data from zip folder'''

def extract_zip(zip_file, output_dir):

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(output_dir)

    print(f"Extraction completed successfully to '{output_dir}'.")



##### input definition #####

if __name__ == "__main__":
    # Zenodo direct download link
    zenodo_url = "https://zenodo.org/records/10979107/files/Precompiled_data.zip?download=1"

    # Directory where the file will be downloaded (inside pypsa-bo folder)
    download_directory = "pypsa-bo"

    # Local file path to save the downloaded file
    output_file_name = os.path.join(download_directory, "Precompiled_data.zip")

    # Download the file from Zenodo
    download_file(zenodo_url, output_file_name)

    # Ensure that the download directory exists
    os.makedirs(download_directory, exist_ok=True)

    # Local directory to extract the files
    extraction_dir = os.path.join(download_directory)

    # Extract the downloaded zip file
    extract_zip(output_file_name, extraction_dir)


##### First test the correct download

# def move_data_to_submodule(data_dir, submodule_dir):
#     # Create the destination directory if it doesn't exist
#     os.makedirs(submodule_dir, exist_ok=True)

#     # Move the data to the submodule directory
#     shutil.move(data_dir, submodule_dir)

#     # Submodule directory
#     submodule_directory = "pypsa-bo/pypsa-earth"

#     # Move the data to the submodule directory
#     move_data_to_submodule(os.path.join(download_directory_name, "data"), submodule_directory)