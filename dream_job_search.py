from submodules.google_api.google_sheets_api import SheetHandler
from submodules.linkedin_api.parallel_linkedin_api import ParallelJobSearchScraper, ParallelJobPostingScraper
import json
import os
import re
from datetime import datetime, timedelta
import pandas as pd

class DreamJobSearch:
    def __init__(self, client_secret=None, creds=None, 
                spreadsheet_data=None, 
                save_spreadsheet_data=False, 
                log_subscribers=None):
        self.job_search_sheet_handler = SheetHandler(creds, client_secret)
        self.job_posting_sheet_handler = SheetHandler(creds, client_secret)
        self.linkedin_job_search_schema = os.environ.get("JOB_SEARCH_SCHEMA")
        self.linkedin_job_posting_schema = os.environ.get("JOB_POSTING_SCHEMA")
        self.linkedin_job_search_scraper = None
        self.linkedin_job_posting_scraper = None
        self.spreadsheet_data = spreadsheet_data
        self.creds = creds
        self.client_secret = client_secret
        self.save_spreadsheet_data = save_spreadsheet_data
        self.log_subscribers = log_subscribers
        # Add logging method        
        self.log_message("🚀 Initializing DreamJobSearch...")
        
        if isinstance(self.spreadsheet_data, str) and os.path.exists(self.spreadsheet_data):
            with open(self.spreadsheet_data, "r") as f:
                self.spreadsheet_data = json.load(f)
        elif isinstance(self.spreadsheet_data, str):
            try:
                self.spreadsheet_data = json.loads(self.spreadsheet_data)
            except json.JSONDecodeError:
                self.spreadsheet_data = None
                self.log_message("Invalid spreadsheet data format. Will create new spreadsheet.")
        elif isinstance(self.spreadsheet_data, dict):
            pass
        else:
            self.spreadsheet_data = None
            self.log_message("Invalid spreadsheet data format. Will create new spreadsheet.")

        if self.spreadsheet_data:
            self.job_search_sheet_handler.spreadsheet_id = self.spreadsheet_data["spreadsheet_id"]
            self.job_posting_sheet_handler.spreadsheet_id = self.spreadsheet_data["spreadsheet_id"]
            self.job_search_sheet_handler.sheet_id = self.spreadsheet_data["job_search_sheet_id"]
            self.job_posting_sheet_handler.sheet_id = self.spreadsheet_data["job_posting_sheet_id"]
            self.job_search_sheet_handler.columns = self.spreadsheet_data["job_search_columns"]
            self.job_posting_sheet_handler.columns = self.spreadsheet_data["job_posting_columns"]
            self.log_message(f"📊 Loaded existing sheet with spreadsheet_id={self.job_search_sheet_handler.spreadsheet_id}")
        else:
            self.log_message("📝 Creating new spreadsheet...")
            self.spreadsheet_data = self.setup_sheet(save_spreadsheet_data=self.save_spreadsheet_data)
        
        self.setup_scrapers()
        self.log_message("🎉 DreamJobSearch initialization completed!")

    def log_message(self, message):
        """Send log message to all subscribers if available"""
        print(f"DEBUG: log_subscribers = {self.log_subscribers}")
        if self.log_subscribers is not None:
            print(f"DEBUG: Sending message to {len(self.log_subscribers)} subscribers: {message}")
            self._safe_send_to_subscribers(message)
        print(message)
    
    def _safe_send_to_subscribers(self, message: str):
        """Safely send message to asyncio queue subscribers from any thread"""
        if not self.log_subscribers:
            return
            
        for subscriber in self.log_subscribers:
            try:
                # Use call_soon_threadsafe to safely put messages in asyncio queues from different threads
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # We're in a different thread, use call_soon_threadsafe
                    loop.call_soon_threadsafe(subscriber.put_nowait, message)
                except RuntimeError:
                    # No running loop, we're in the main thread
                    subscriber.put_nowait(message)
            except Exception as e:
                print(f"Error sending message to subscriber: {subscriber}, Error: {e}")

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

    def setup_sheet(self, save_spreadsheet_data=False):
        self.log_message(f"📝 Creating new spreadsheet: Dream Job Search")
        self.job_search_sheet_handler.create_spreadsheet("Dream Job Search")
        self.log_message("📊 Adding Job Search Results sheet...")
        self.job_search_sheet_handler.add_sheet_to_spreadsheet(sheet_title="Job Search Results")
        self.job_search_sheet_handler.create_table_from_schema(self.linkedin_job_search_schema, "Job Search Results", 0, 0)
        
        self.job_posting_sheet_handler.spreadsheet_id = self.job_search_sheet_handler.spreadsheet_id
        self.log_message("📄 Adding Job Postings sheet...")
        self.job_posting_sheet_handler.add_sheet_to_spreadsheet(sheet_title="Job Postings")
        self.job_posting_sheet_handler.create_table_from_schema(self.linkedin_job_posting_schema, "Job Postings", 0, 0)


        self.spreadsheet_data = {
            "spreadsheet_id": self.job_search_sheet_handler.spreadsheet_id,
            "job_search_sheet_id": self.job_search_sheet_handler.sheet_id,
            "job_posting_sheet_id": self.job_posting_sheet_handler.sheet_id,
            "job_search_columns": self.job_search_sheet_handler.get_columns(),
            "job_posting_columns": self.job_posting_sheet_handler.get_columns()
        }

        if save_spreadsheet_data:
            with open(self.spreadsheet_data, "w") as f:
                json.dump(self.spreadsheet_data, f)
        self.log_message(f"✅ Created sheet 'Dream Job Search' with spreadsheet_id={self.job_search_sheet_handler.spreadsheet_id}")
        return self.spreadsheet_data

    def setup_scrapers(self):
        self.log_message("🔧 Setting up LinkedIn scrapers...")
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
        
        self.log_message("🔍 Initializing job search scraper...")
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
            human_behavior_config=human_behavior_config,
            log_subscribers=self.log_subscribers
            )

        self.log_message("📄 Initializing job posting scraper...")
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
            human_behavior_config=human_behavior_config,
            log_subscribers=self.log_subscribers
        )
        self.log_message("✅ Scrapers initialized successfully")

    def search_for_jobs(self, queries, locations, published_after=None, num_jobs_per_search=60):
        self.log_message(f"🔍 Starting job search for {len(queries)} queries across {len(locations)} locations")
        
        def add_jobs_to_sheet(batch_results):
            if isinstance(batch_results[0], list):
                batch_results = [item for sublist in batch_results for item in sublist]
            self.log_message(f"✅ Scraped {len(batch_results)} job links")
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
            
            self.log_message(f"📝 Adding {len(filtered_rows)} new job links to sheet")
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
        self.log_message("📄 Starting job posting scraping process...")

        def add_job_postings_to_sheet(batch_results):
            self.log_message(f"✅ Scraped {len(batch_results)} job postings")
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
            
            self.log_message(f"📝 Adding {len(filtered_results)} new job postings to sheet")
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
            self.log_message("ℹ️ No new job links to scrape")
            return
        
        self.log_message(f"🔗 Found {len(urls)} URLs to scrape for job postings")
        self.linkedin_job_posting_scraper.scrape_parallel(
            urls=urls,
            on_batch_complete=add_job_postings_to_sheet
        )
    
    def score_job_postings(self, keywords, location = None):
        """
        This function scores job postings based on the amount of keywords they contain. 
        It returns a dataframe with the job postings and the keywords it contains.
        The matching is done by checking the job description.
        The score is the number of keywords that are matched.
        """
        job_posting_df = self.job_posting_sheet_handler.get_dataframe()
        if location:
            job_posting_df = job_posting_df[job_posting_df["location"] == location]
        
        # Find matched keywords for each job posting
        def find_matched_keywords(job_description):
            matched = [keyword for keyword in keywords if keyword.lower() in job_description.lower()]
            result = ', '.join(matched) if matched else ""
            return result
        
        job_posting_df["matched_keywords"] = job_posting_df["job_description"].apply(find_matched_keywords)
        
        # Calculate score based on matched keywords
        def calculate_score(matched_keywords):
            if not matched_keywords:  # Empty string
                return 0
            return len(matched_keywords.split(', '))
        
        job_posting_df["score"] = job_posting_df["matched_keywords"].apply(calculate_score)
        

        return job_posting_df

    def update_database(self, locations, queries):
        """
        This function updates the database with the new job postings.
        The Selenium server is now automatically managed by the ParallelScraper class.
        """
        self.log_message(f"🚀 Starting database update with {len(locations)} locations and {len(queries)} queries")
        self.log_message(f"📍 Locations: {', '.join(locations)}")
        self.log_message(f"🔍 Queries: {', '.join(queries)}")
        
        try:
            self.log_message("🔎 Searching for jobs...")
            self.search_for_jobs(queries, locations)
            
            self.log_message("📄 Scraping job postings...")
            self.scrape_job_postings()
            
            self.log_message("🧹 Cleaning up scrapers...")
            self.linkedin_job_search_scraper.force_cleanup_all()
            self.linkedin_job_posting_scraper.force_cleanup_all()
            
            self.log_message("✅ Database update completed successfully!")
        except Exception as e:
            self.log_message(f"❌ Error during database update: {str(e)}")
            raise

    def find_jobs_by_keywords(self, keywords, location = None):
        """
        This function finds jobs by keywords.
        """
        job_posting_df = self.score_job_postings(keywords, location)
        job_posting_df = job_posting_df[job_posting_df["score"] > 0]
        return job_posting_df[["score", "matched_keywords", "link", "job_title", "job_company", "job_location"]].sort_values(by="score", ascending=False)

def main():
    dream_job_search = DreamJobSearch(creds=None, client_secret=None, spreadsheet_data="spreadsheet_data.json")
    dream_job_search.update_database(locations=["Poland"], queries=["AI Agent", "AI Engineer", "AI Developer", "AI Specialist", "AI Analyst", "AI Consultant", "AI Trainer", "AI Researcher", "AI Strategist", "AI Architect", "AI Safety", "Responsible AI"])
    results = dream_job_search.score_job_postings(keywords=["python", "React", "Azure", "prompt engineering", "web scraping", "selenium", "playwright", "beautifulsoup", "beautiful soup", "beautifulsoup4", "beautifulsoup3", "beautifulsoup2", "beautifulsoup1", "beautifulsoup0", "beautifulsoup-4", "beautifulsoup-3", "beautifulsoup-2", "beautifulsoup-1", "beautifulsoup-0"])
    results = results[["score", "matched_keywords", "link"]].sort_values(by="score", ascending=False).head(10)
    for index, row in results.iterrows():
        print(f"Score: {row['score']}, Matched Keywords: {row['matched_keywords']}, Link: {row['link']}")
        print("-"*100)

if __name__ == "__main__":
    main()





