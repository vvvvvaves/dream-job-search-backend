from submodules.google_api.google_sheets_api import SheetHandler
from submodules.linkedin_api.parallel_linkedin_api import ParallelJobSearchScraper, ParallelJobPostingScraper
import json
import os
import re
from datetime import datetime, timedelta
import pandas as pd

class DreamJobSearch:
    def __init__(self, creds_path, client_secret_path, spreadsheet_data_path=None):
        self.job_search_sheet_handler = SheetHandler(creds_path, client_secret_path)
        self.job_posting_sheet_handler = SheetHandler(creds_path, client_secret_path)
        self.linkedin_job_search_schema_path = "job_search_schema.json"
        self.linkedin_job_posting_schema_path = "job_posting_schema.json"
        self.linkedin_job_search_scraper = None
        self.linkedin_job_posting_scraper = None
        self.spreadsheet_data_path = spreadsheet_data_path
        self.creds_path = creds_path
        self.client_secret_path = client_secret_path
        if os.path.exists(self.spreadsheet_data_path):
            with open(self.spreadsheet_data_path, "r") as f:
                self.spreadsheet_data = json.load(f)
            self.job_search_sheet_handler.spreadsheet_id = self.spreadsheet_data["spreadsheet_id"]
            self.job_posting_sheet_handler.spreadsheet_id = self.spreadsheet_data["spreadsheet_id"]
            self.job_search_sheet_handler.sheet_id = self.spreadsheet_data["job_search_sheet_id"]
            self.job_posting_sheet_handler.sheet_id = self.spreadsheet_data["job_posting_sheet_id"]
            self.job_search_sheet_handler.columns = self.spreadsheet_data["job_search_columns"]
            self.job_posting_sheet_handler.columns = self.spreadsheet_data["job_posting_columns"]
            print(f"✓ Loaded existing sheet with spreadsheet_id={self.job_search_sheet_handler.spreadsheet_id}, job_search_sheet_id={self.job_search_sheet_handler.sheet_id}, job_posting_sheet_id={self.job_posting_sheet_handler.sheet_id}")
        else:
            self.setup_sheet()
        
        self.setup_scrapers()

    def extract_job_id(self, linkedin_url):
        """Extract the 10-digit job ID from a LinkedIn job URL."""
        pattern = r"/view/.*?-(\d{10})/?"
        match = re.search(pattern, linkedin_url)
        if match:
            return match.group(1)
        return None

    def filter_by_job_id(self, new_items, existing_df, link_field="link", fallback_filter_func=None):
        """
        Filter items by job ID to prevent duplicates.
        
        Args:
            new_items: List of new items to filter (each should have a link field)
            existing_df: DataFrame with existing items
            link_field: Field name containing the LinkedIn URL (default: "link")
            fallback_filter_func: Function to call for items without extractable job IDs
                                 Should take (item, existing_df) and return True if item should be kept
        
        Returns:
            List of filtered items (duplicates removed)
        """
        # Get existing job IDs
        existing_job_ids = set()
        for existing_link in existing_df[link_field].values.tolist():
            job_id = self.extract_job_id(existing_link)
            if job_id:
                existing_job_ids.add(job_id)
        
        filtered_items = []
        for item in new_items:
            # Extract link based on whether item is a dict or string
            if isinstance(item, dict):
                item_link = item.get(link_field, "")
            else:
                item_link = item
            
            job_id = self.extract_job_id(item_link)
            
            if job_id and job_id not in existing_job_ids:
                filtered_items.append(item)
                existing_job_ids.add(job_id)  # Add to set to avoid duplicates within this batch
            elif not job_id and fallback_filter_func:
                # Use fallback filtering if we can't extract job ID
                if fallback_filter_func(item, existing_df):
                    filtered_items.append(item)
        
        return filtered_items

    def setup_sheet(self, title = "Dream Job Search"):
        self.job_search_sheet_handler.create_spreadsheet(title)
        self.job_search_sheet_handler.add_sheet_to_spreadsheet(sheet_title="Job Search Results")
        self.job_search_sheet_handler.create_table_from_schema(self.linkedin_job_search_schema_path, "Job Search Results", 0, 0)
        
        self.job_posting_sheet_handler.spreadsheet_id = self.job_search_sheet_handler.spreadsheet_id
        self.job_posting_sheet_handler.add_sheet_to_spreadsheet(sheet_title="Job Postings")
        self.job_posting_sheet_handler.create_table_from_schema(self.linkedin_job_posting_schema_path, "Job Postings", 0, 0)


        self.spreadsheet_data = {
            "spreadsheet_id": self.job_search_sheet_handler.spreadsheet_id,
            "job_search_sheet_id": self.job_search_sheet_handler.sheet_id,
            "job_posting_sheet_id": self.job_posting_sheet_handler.sheet_id,
            "job_search_columns": self.job_search_sheet_handler.get_columns(),
            "job_posting_columns": self.job_posting_sheet_handler.get_columns()
        }

        with open(self.spreadsheet_data_path, "w") as f:
            json.dump(self.spreadsheet_data, f)
        print(f"✓ Created sheet '{title}' with spreadsheet_id={self.job_search_sheet_handler.spreadsheet_id}, job_search_sheet_id={self.job_search_sheet_handler.sheet_id}, job_posting_sheet_id={self.job_posting_sheet_handler.sheet_id}")

    def setup_scrapers(self):
        human_behavior_config={
                "reading_time_min": 1.0,
                "reading_time_max": 10.0,
                "scroll_probability": 0.2,
                "use_content_based_time": True,
                "scroll_type": "random",
                "scroll_direction": "down",
                "scroll_distance_min": 50,
                "scroll_distance_max": 200,
                "typing_speed_wpm": 45,
                "min_action_delay": 0.1,
                "max_action_delay": 0.5,
                "scroll_pause_min": 0.5,
                "scroll_pause_max": 2.0,
                "mouse_movement_speed": 1.0,
                "randomness_factor": 0.3,
                "scroll_speed_min": 0.3,
                "scroll_speed_max": 2.5,
                "mouse_speed_min": 0.5,
                "mouse_speed_max": 2.0
            }
        self.linkedin_job_search_scraper = ParallelJobSearchScraper(
            queries=None, 
            locations=None, 
            published_after=None, 
            num_jobs_per_search=None, 
            max_workers=4, 
            headless=True, 
            timeout=15, 
            requests_per_second=(6/60), # 6 requests per minute
            burst_capacity=3, 
            min_delay_between_requests=1.0, 
            enable_exponential_backoff=True, 
            max_retries=3,
            batch_size=20,
            enable_human_behavior=True,
            human_behavior_config=human_behavior_config
            )

        self.linkedin_job_posting_scraper = ParallelJobPostingScraper(
            urls=None,
            max_workers=4,  # Reduced from 8 for better rate limiting
            headless=True,
            timeout=15,
            # Rate limiting configuration
            requests_per_second=(10/60),  # Conservative rate limit
            burst_capacity=3,  # Allow small bursts
            min_delay_between_requests=1.0,  # 1 second minimum delay per thread
            enable_exponential_backoff=True,
            max_retries=3,
            batch_size=20,
            enable_human_behavior=True,
            human_behavior_config=human_behavior_config
        )

    def search_for_jobs(self, queries, locations, published_after=None, num_jobs_per_search=60):
        
        def add_jobs_to_sheet(batch_results):
            if isinstance(batch_results[0], list):
                batch_results = [item for sublist in batch_results for item in sublist]
            print(f"✓ Scraped {len(batch_results)} job links")
            added_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            rows = [{"link": link, "added_at": added_at} for link in batch_results]
            
            # Define fallback filter for items without extractable job IDs
            def fallback_filter(row, existing_df):
                return row["link"] not in existing_df["link"].values.tolist()
            
            # Filter using the centralized filtering function
            job_search_df = self.job_search_sheet_handler.get_dataframe()
            filtered_rows = self.filter_by_job_id(
                new_items=rows,
                existing_df=job_search_df,
                link_field="link",
                fallback_filter_func=fallback_filter
            )
            
            print(f"✓ Adding {len(filtered_rows)} new job links to sheet")
            if filtered_rows:
                self.job_search_sheet_handler.add_rows_to_sheet(
                    filtered_rows,  
                    column_order=self.job_search_sheet_handler.columns
                    )

        self.linkedin_job_search_scraper.scrape_parallel(
            queries=queries, 
            locations=locations, 
            published_after=published_after, 
            num_jobs_per_search=num_jobs_per_search, 
            on_batch_complete=add_jobs_to_sheet
        )

    def scrape_job_postings(self):

        def add_job_postings_to_sheet(batch_results):
            print(f"✓ Scraped {len(batch_results)} job postings")
            added_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for result in batch_results:
                result["added_at"] = added_at
            
            
            # Filter using the centralized filtering function
            job_posting_df = self.job_posting_sheet_handler.get_dataframe()
            filtered_results = self.filter_by_job_id(
                new_items=batch_results,
                existing_df=job_posting_df,
                link_field="link",
                fallback_filter_func=None
            )
            
            print(f"✓ Adding {len(filtered_results)} new job postings to sheet")
            if filtered_results:
                self.job_posting_sheet_handler.add_rows_to_sheet(
                    filtered_results,
                    column_order=self.job_posting_sheet_handler.columns
                    )

        job_search_df = self.job_search_sheet_handler.get_dataframe()
        job_posting_df = self.job_posting_sheet_handler.get_dataframe()
        
        # Define fallback filter for URLs without extractable job IDs
        def url_fallback_filter(url, existing_df):
            return url not in existing_df["link"].values.tolist()
        
        # Filter URLs using the centralized filtering function
        urls = self.filter_by_job_id(
            new_items=job_search_df["link"].values.tolist(),
            existing_df=job_posting_df,
            link_field="link",
            fallback_filter_func=url_fallback_filter
        )
        if len(urls) == 0:
            print("✓ No new job links to scrape")
            return
        self.linkedin_job_posting_scraper.scrape_parallel(
            urls=urls,
            on_batch_complete=add_job_postings_to_sheet
        )


def main():
    dream_job_search = DreamJobSearch(creds_path="creds.json", client_secret_path="client_secret.json", spreadsheet_data_path="spreadsheet_data.json")
    dream_job_search.search_for_jobs(queries=["AI Safety", "Responsible AI", "Full-stack python"], locations=["Poland"], num_jobs_per_search=60)
    dream_job_search.scrape_job_postings()

if __name__ == "__main__":
    main()





