import os
import zipfile
import urllib.request
import subprocess

URL = "https://static.fossee.in/esim/installation-files/eSim-2.5.zip"
ZIP_NAME = "eSim-2.5.zip"
EXTRACT_DIR = "eSim-2.5"

print("Downloading eSim-2.5.zip...")

urllib.request.urlretrieve(URL, ZIP_NAME)

print("Download completed.")

print("Extracting ZIP file...")

with zipfile.ZipFile(ZIP_NAME, 'r') as zip_ref:
    zip_ref.extractall()

print("Extraction completed.")

if os.path.isdir(EXTRACT_DIR):

    os.chdir(EXTRACT_DIR)

    print(f"Changed directory to: {os.getcwd()}")

    print("\nInstallation Commands:")
    print("chmod +x install-eSim.sh")
    print("./install-eSim.sh --install")

    choice = input("\nDo you want to run the installation now? (yes/no): ").strip().lower()

    if choice == "yes":

        subprocess.run(["chmod", "+x", "install-eSim.sh"])

        subprocess.run(["./install-eSim.sh", "--install"])

    else:
        print("Installation skipped.")

else:
    print("eSim-2.5 directory not found.")
