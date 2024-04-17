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

def extract_zip(zip_file, output_directory):

    # Check to see if the file already exists 
    if os.path.exists("pypsa-bo/Precompiled_data"):
        print(f"Unzipped file already exists. Skipping unzipping.")
        return

    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(output_directory)

    print(f"Extraction completed successfully to '{output_directory}'.")



'''Function to move extracted precompiled information to the submodule'''

def move_data_to_submodule(data_dir, submodule_dir):
    
    # Remove the existing submodule directory if it exists
    if os.path.exists(submodule_dir):
        shutil.rmtree(submodule_dir)

    # Copy the data to the submodule directory
    if os.path.isdir(data_dir):  # Check if it's a directory
        shutil.copytree(data_dir, submodule_dir)
    else:  # It's a file
        shutil.copy2(data_dir, submodule_dir)


'''Function to move specific files to the submodule'''

def copy_file_to_submodule(file_path, submodule_dir):
    # Get the filename from the file path
    file_name = os.path.basename(file_path)
    
    # Destination file path in the submodule directory
    dest_file_path = os.path.join(submodule_dir, file_name)

    # Remove the existing file if it exists
    if os.path.exists(dest_file_path):
        os.remove(dest_file_path)

    # Copy the file to the submodule directory
    shutil.copy2(file_path, dest_file_path)    



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

    # Extract the downloaded zip file
    extract_zip(output_file_name, download_directory)

    # Submodule directory
    submodule_directory = "pypsa-bo/pypsa-earth"

    # Move the data to the submodule directory
    move_data_to_submodule(os.path.join(download_directory, "Precompiled_data", "inflows_data"), os.path.join(submodule_directory, "inflows_data"))
    move_data_to_submodule(os.path.join(download_directory, "Precompiled_data", "data"), os.path.join(submodule_directory, "data"))
    move_data_to_submodule(os.path.join(download_directory, "Precompiled_data", "resources"), os.path.join(submodule_directory, "resources"))
    move_data_to_submodule(os.path.join(download_directory, "Precompiled_data", "cutouts"), os.path.join(submodule_directory, "cutouts"))

    print("Data was moved successfully")


    # Submodule directory
    modified_directory = "pypsa-bo/Modified_files"

    # Move modfied files and scripts 
    copy_file_to_submodule(os.path.join(modified_directory, "config.yaml"), os.path.join(submodule_directory))
    copy_file_to_submodule(os.path.join(modified_directory, "config.default.yaml"), os.path.join(submodule_directory))

    copy_file_to_submodule(os.path.join(modified_directory, "scripts", "add_electricity.py"), os.path.join(submodule_directory,"scripts"))
    copy_file_to_submodule(os.path.join(modified_directory, "scripts", "cluster_network.py"), os.path.join(submodule_directory,"scripts"))
    copy_file_to_submodule(os.path.join(modified_directory, "scripts", "simplify_network.py"), os.path.join(submodule_directory,"scripts"))
    copy_file_to_submodule(os.path.join(modified_directory, "scripts", "solve_network.py"), os.path.join(submodule_directory,"scripts"))

    copy_file_to_submodule(os.path.join(modified_directory, "envs", "environment.yaml"), os.path.join(submodule_directory,"envs"))

    print("Modified files were copied successfully")