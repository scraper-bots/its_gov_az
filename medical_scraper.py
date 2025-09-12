import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
from urllib.parse import urljoin

class AzerbaijanMedicalScraper:
    def __init__(self):
        self.base_url = "https://its.gov.az"
        self.search_url = "https://its.gov.az/page/tibb-muessiselerinin-axtarisi"
        self.session = requests.Session()
        
        # Set headers to mimic a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def extract_coordinates(self, coord_string):
        """Extract latitude and longitude from coordinate string"""
        try:
            # Remove brackets and split by comma
            coords = coord_string.strip('[]').split(',')
            if len(coords) == 2:
                lat = float(coords[0].strip())
                lng = float(coords[1].strip())
                return lat, lng
        except:
            pass
        return None, None
    
    def clean_phone(self, phone_text):
        """Clean and format phone numbers"""
        if phone_text:
            # Remove extra whitespace and clean up
            return re.sub(r'\s+', ' ', phone_text.strip())
        return None
    
    def scrape_medical_institutions(self):
        """Scrape medical institutions from the website"""
        try:
            print(f"Fetching data from: {self.search_url}")
            response = self.session.get(self.search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all medical institution items
            institution_items = soup.find_all('div', class_='accordion-header each-item result-item')
            
            institutions = []
            
            for item in institution_items:
                institution_data = {}
                
                # Extract coordinates
                lat = item.get('data-lat')
                lng = item.get('data-long')
                coord_str = item.get('data-coord')
                
                if lat and lng:
                    institution_data['latitude'] = float(lat)
                    institution_data['longitude'] = float(lng)
                elif coord_str:
                    lat, lng = self.extract_coordinates(coord_str)
                    institution_data['latitude'] = lat
                    institution_data['longitude'] = lng
                
                # Extract institution name
                name_elem = item.find('h2', class_='privateHospital')
                if name_elem:
                    institution_data['name'] = name_elem.get_text(strip=True)
                
                # Extract address/location
                location_elem = item.find('div', class_='location')
                if location_elem:
                    location_span = location_elem.find('span')
                    if location_span:
                        institution_data['address'] = location_span.get_text(strip=True)
                
                # Extract phone numbers
                phone_elem = item.find('a', class_='phone')
                if phone_elem:
                    phone_span = phone_elem.find('span')
                    if phone_span:
                        phone_text = phone_span.get_text(strip=True)
                        institution_data['phone'] = self.clean_phone(phone_text)
                    
                    # Also get href attribute if it contains tel:
                    href = phone_elem.get('href', '')
                    if href.startswith('tel:'):
                        institution_data['phone_href'] = href
                
                # Extract map URL if available
                map_url = item.get('data-map-url')
                if map_url:
                    institution_data['map_url'] = map_url
                
                institutions.append(institution_data)
                
            print(f"Found {len(institutions)} medical institutions")
            return institutions
            
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return []
        except Exception as e:
            print(f"Error parsing data: {e}")
            return []
    
    def save_to_json(self, data, filename='medical_institutions.json'):
        """Save data to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving JSON: {e}")
    
    def save_to_csv(self, data, filename='medical_institutions.csv'):
        """Save data to CSV file"""
        try:
            if not data:
                print("No data to save")
                return
            
            # Get all unique keys from all institutions
            all_keys = set()
            for institution in data:
                all_keys.update(institution.keys())
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(data)
            
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving CSV: {e}")
    
    def scrape_with_pagination(self):
        """Scrape data handling potential pagination"""
        all_institutions = []
        
        # Start with the main page
        institutions = self.scrape_medical_institutions()
        all_institutions.extend(institutions)
        
        # Add delay to be respectful
        time.sleep(1)
        
        # Note: You might need to implement pagination logic here
        # if the website uses AJAX or has multiple pages
        
        return all_institutions

def main():
    """Main function to run the scraper"""
    scraper = AzerbaijanMedicalScraper()
    
    print("Starting Azerbaijan Medical Institutions Scraper...")
    print("=" * 50)
    
    # Scrape the data
    institutions = scraper.scrape_with_pagination()
    
    if institutions:
        print(f"\nSuccessfully scraped {len(institutions)} institutions")
        
        # Save to both JSON and CSV
        scraper.save_to_json(institutions)
        scraper.save_to_csv(institutions)
        
        # Display first few results
        print("\nFirst 3 institutions:")
        for i, institution in enumerate(institutions[:3], 1):
            print(f"\n{i}. {institution.get('name', 'N/A')}")
            print(f"   Address: {institution.get('address', 'N/A')}")
            print(f"   Phone: {institution.get('phone', 'N/A')}")
            print(f"   Coordinates: {institution.get('latitude', 'N/A')}, {institution.get('longitude', 'N/A')}")
    else:
        print("No data found or error occurred during scraping")

if __name__ == "__main__":
    main()
