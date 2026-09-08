#!/bin/bash
# -------------------------------------------------------------
# Script to run on GCP Compute Engine startup.
# Downloads the massive Kaggle dataset directly to GCP and
# uploads it to Google Cloud Storage.
# -------------------------------------------------------------

set -e

# 1. Update and install dependencies
apt-get update
apt-get install -y unzip python3-pip

# 2. Install kaggle CLI
# Using --break-system-packages for Ubuntu 24.04+ (or just pip3 if older)
pip3 install kaggle --break-system-packages || pip3 install kaggle

# 3. Configure Kaggle credentials for root (Injected via metadata or env)
mkdir -p /root/.kaggle
cat << EOF > /root/.kaggle/kaggle.json
{"username":"${KAGGLE_USERNAME}","key":"${KAGGLE_KEY}"}
EOF
chmod 600 /root/.kaggle/kaggle.json

# 4. Prepare working directory
mkdir -p /mnt/data
cd /mnt/data

# 5. Download the dataset from Kaggle
echo "Downloading dataset from Kaggle..."
/usr/local/bin/kaggle datasets download mkechinov/ecommerce-behavior-data-from-multi-category-store || ~/.local/bin/kaggle datasets download mkechinov/ecommerce-behavior-data-from-multi-category-store || kaggle datasets download mkechinov/ecommerce-behavior-data-from-multi-category-store

# 6. Extract the dataset
echo "Extracting zip file..."
unzip -o ecommerce-behavior-data-from-multi-category-store.zip
rm ecommerce-behavior-data-from-multi-category-store.zip

# 7. Upload to Google Cloud Storage
echo "Uploading CSVs to GCS bucket..."
gsutil -m cp *.csv gs://ecommerce-raw-data-ds30/

# 8. Self-destruct the VM to save costs
echo "Data transfer complete. Deleting VM..."
ZONE=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/zone -H "Metadata-Flavor: Google" | awk -F/ '{print $NF}')
INSTANCE_NAME=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/name -H "Metadata-Flavor: Google")
gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --quiet
