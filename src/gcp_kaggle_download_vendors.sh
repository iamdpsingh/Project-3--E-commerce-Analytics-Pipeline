#!/bin/bash
set -e

apt-get update
apt-get install -y unzip python3-pip

pip3 install kaggle --break-system-packages || pip3 install kaggle

mkdir -p /root/.kaggle
cat << EOF > /root/.kaggle/kaggle.json
{"username":"${KAGGLE_USERNAME}","key":"${KAGGLE_KEY}"}
EOF
chmod 600 /root/.kaggle/kaggle.json

mkdir -p /mnt/vendor_b
cd /mnt/vendor_b
/usr/local/bin/kaggle datasets download mkechinov/ecommerce-events-history-in-cosmetics-shop || ~/.local/bin/kaggle datasets download mkechinov/ecommerce-events-history-in-cosmetics-shop || kaggle datasets download mkechinov/ecommerce-events-history-in-cosmetics-shop
unzip -o ecommerce-events-history-in-cosmetics-shop.zip
rm ecommerce-events-history-in-cosmetics-shop.zip
gsutil -m cp *.csv gs://ecommerce-raw-data-ds30/vendor_b_cosmetics/

mkdir -p /mnt/vendor_c
cd /mnt/vendor_c
/usr/local/bin/kaggle datasets download mkechinov/ecommerce-purchase-history-from-electronics-store || ~/.local/bin/kaggle datasets download mkechinov/ecommerce-purchase-history-from-electronics-store || kaggle datasets download mkechinov/ecommerce-purchase-history-from-electronics-store
unzip -o ecommerce-purchase-history-from-electronics-store.zip
rm ecommerce-purchase-history-from-electronics-store.zip
gsutil -m cp *.csv gs://ecommerce-raw-data-ds30/vendor_c_electronics/

ZONE=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/zone -H "Metadata-Flavor: Google" | awk -F/ '{print $NF}')
INSTANCE_NAME=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/name -H "Metadata-Flavor: Google")
gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE --quiet
