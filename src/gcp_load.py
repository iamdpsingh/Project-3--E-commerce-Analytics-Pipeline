import os
import logging
from google.cloud import bigquery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("gcp_load")

def load_gcs_to_bigquery(client, gcs_uri, dataset_id, table_id):
    """Loads CSV files from GCS into a BigQuery table with schema autodetect."""
    table_ref = f"{client.project}.{dataset_id}.{table_id}"
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        # Truncate table if it exists (for full load)
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    
    logger.info(f"Triggering BigQuery Load Job: {gcs_uri} -> {table_ref} ...")
    
    load_job = client.load_table_from_uri(
        gcs_uri, table_ref, job_config=job_config
    )  
    
    # Wait for the job to complete
    load_job.result()  
    
    # Get table info to verify rows loaded
    destination_table = client.get_table(table_ref)
    logger.info(f"✓ Success! Loaded {destination_table.num_rows:,} rows into {table_ref}")

def main():
    project_id = os.getenv("GCP_PROJECT_ID") or "ecommerce-pipe-ds30"
    bucket = os.getenv("GCP_BUCKET_NAME") or "ecommerce-raw-data-ds30"
    dataset_raw = os.getenv("BIGQUERY_DATASET_RAW") or "ecommerce_raw"
    
    # Initialize BigQuery client
    client = bigquery.Client(project=project_id)
    
    logger.info("=" * 60)
    logger.info("  GCP BIG DATA LOAD — DATA LAKE TO BIGQUERY")
    logger.info("=" * 60)

    # 1. Vendor A (Multi-Category)
    load_gcs_to_bigquery(
        client, 
        f"gs://{bucket}/vendor_a_multicategory/*.csv", 
        dataset_raw, 
        "vendor_a_events"
    )
    
    # 2. Vendor B (Cosmetics)
    load_gcs_to_bigquery(
        client, 
        f"gs://{bucket}/vendor_b_cosmetics/*.csv", 
        dataset_raw, 
        "vendor_b_events"
    )
    
    # 3. Vendor C (Electronics)
    load_gcs_to_bigquery(
        client, 
        f"gs://{bucket}/vendor_c_electronics/*.csv", 
        dataset_raw, 
        "vendor_c_events"
    )

if __name__ == "__main__":
    main()
