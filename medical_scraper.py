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
    
    def dms_to_decimal(self, dms_str):
        """Convert DMS (degrees, minutes, seconds) to decimal degrees"""
        if not dms_str:
            return None
            
        try:
            # Clean the string
            dms_str = str(dms_str).strip().strip('"').strip("'")
            
            # Try decimal first
            try:
                return float(dms_str)
            except ValueError:
                pass
            
            # Handle DMS format like "40°35'00.2"
            if '°' in dms_str:
                # Extract all numbers
                numbers = re.findall(r'\d+\.?\d*', dms_str)
                if len(numbers) >= 2:
                    degrees = float(numbers[0])
                    minutes = float(numbers[1]) if len(numbers) > 1 else 0
                    seconds = float(numbers[2]) if len(numbers) > 2 else 0
                    
                    decimal = degrees + minutes/60 + seconds/3600
                    return decimal
            
            return None
            
        except Exception as e:
            print(f"    Warning: Could not parse coordinate '{dms_str}': {e}")
            return None
    
    def clean_phone(self, phone_text):
        """Clean and format phone numbers"""
        if phone_text:
            return re.sub(r'\s+', ' ', phone_text.strip())
        return None
    
    def extract_data_safely(self, item, field_name, extractor_func):
        """Safely extract data with error handling"""
        try:
            return extractor_func(item)
        except Exception as e:
            print(f"    Warning: Could not extract {field_name}: {e}")
            return None
    
    def scrape_medical_institutions(self):
        """Scrape medical institutions from the website"""
        institutions = []
        
        try:
            print(f"Fetching data from: {self.search_url}")
            response = self.session.get(self.search_url, timeout=30)
            response.raise_for_status()
            
            # Save the raw page for debugging
            with open('raw_page.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("Raw page saved to raw_page.html")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple selectors to find institution items
            selectors_to_try = [
                'div.accordion-header.each-item.result-item',
                'div.result-item',
                'div.each-item',
                'div.accordion-header',
                '[class*="result-item"]',
                '[class*="each-item"]',
                '[data-lat]',
                '[data-coord]'
            ]
            
            institution_items = []
            for selector in selectors_to_try:
                items = soup.select(selector)
                if items:
                    print(f"Found {len(items)} items with selector: {selector}")
                    institution_items = items
                    break
            
            if not institution_items:
                print("No institution items found. Checking page structure...")
                # Look for any divs with data attributes
                all_divs = soup.find_all('div')
                data_divs = [div for div in all_divs if any(attr.startswith('data-') for attr in div.attrs)]
                print(f"Found {len(data_divs)} divs with data attributes")
                
                if data_divs:
                    print("Sample data attributes:")
                    for i, div in enumerate(data_divs[:3]):
                        print(f"  Div {i+1}: {dict(div.attrs)}")
                
                # Try to extract any meaningful content
                content_divs = soup.find_all(['div', 'article', 'section'], class_=re.compile(r'.*'))
                print(f"Found {len(content_divs)} content containers")
                
                return institutions
            
            print(f"Processing {len(institution_items)} institution items...")
            
            for i, item in enumerate(institution_items):
                try:
                    institution_data = {
                        'item_index': i + 1,
                        'raw_html': str(item)[:500] + '...' if len(str(item)) > 500 else str(item)
                    }
                    
                    print(f"  Processing item {i+1}...")
                    
                    # Extract all data attributes
                    for attr_name, attr_value in item.attrs.items():
                        if attr_name.startswith('data-'):
                            institution_data[f'raw_{attr_name.replace("-", "_")}'] = attr_value
                    
                    # Extract coordinates with multiple methods
                    lat_sources = [
                        item.get('data-lat'),
                        item.get('data-latitude')
                    ]
                    
                    lng_sources = [
                        item.get('data-long'),
                        item.get('data-lng'),
                        item.get('data-longitude')
                    ]
                    
                    coord_sources = [
                        item.get('data-coord'),
                        item.get('data-coordinates')
                    ]
                    
                    # Try to parse coordinates
                    latitude = None
                    longitude = None
                    
                    # Method 1: separate lat/lng attributes
                    for lat_val in lat_sources:
                        if lat_val and latitude is None:
                            latitude = self.dms_to_decimal(lat_val)
                            if latitude:
                                print(f"    Parsed latitude: {latitude} from {lat_val}")
                    
                    for lng_val in lng_sources:
                        if lng_val and longitude is None:
                            longitude = self.dms_to_decimal(lng_val)
                            if longitude:
                                print(f"    Parsed longitude: {longitude} from {lng_val}")
                    
                    # Method 2: coordinate string
                    if (latitude is None or longitude is None):
                        for coord_str in coord_sources:
                            if coord_str:
                                try:
                                    # Remove brackets and split
                                    clean_coord = coord_str.strip('[]')
                                    coords = clean_coord.split(',')
                                    if len(coords) == 2:
                                        lat_parsed = self.dms_to_decimal(coords[0].strip())
                                        lng_parsed = self.dms_to_decimal(coords[1].strip())
                                        if lat_parsed and lng_parsed:
                                            latitude = lat_parsed
                                            longitude = lng_parsed
                                            print(f"    Parsed coordinates: {latitude}, {longitude} from {coord_str}")
                                            break
                                except Exception as e:
                                    print(f"    Could not parse coord string '{coord_str}': {e}")
                    
                    institution_data['latitude'] = latitude
                    institution_data['longitude'] = longitude
                    
                    # Extract name with multiple methods
                    name_extractors = [
                        lambda x: x.find('h2', class_='privateHospital'),
                        lambda x: x.find('h2'),
                        lambda x: x.find('h1'),
                        lambda x: x.find('h3'),
                        lambda x: x.find('[class*="hospital"]'),
                        lambda x: x.find('[class*="name"]'),
                        lambda x: x.find('[class*="title"]')
                    ]
                    
                    for extractor in name_extractors:
                        try:
                            name_elem = extractor(item)
                            if name_elem:
                                name = name_elem.get_text(strip=True)
                                if name:
                                    institution_data['name'] = name
                                    print(f"    Found name: {name}")
                                    break
                        except:
                            continue
                    
                    # Extract address
                    address_extractors = [
                        lambda x: x.find('div', class_='location'),
                        lambda x: x.find('[class*="location"]'),
                        lambda x: x.find('[class*="address"]')
                    ]
                    
                    for extractor in address_extractors:
                        try:
                            addr_elem = extractor(item)
                            if addr_elem:
                                addr_span = addr_elem.find('span') or addr_elem
                                if addr_span:
                                    address = addr_span.get_text(strip=True)
                                    if address:
                                        institution_data['address'] = address
                                        print(f"    Found address: {address}")
                                        break
                        except:
                            continue
                    
                    # Extract phone
                    phone_extractors = [
                        lambda x: x.find('a', class_='phone'),
                        lambda x: x.find('[class*="phone"]'),
                        lambda x: x.find('a[href^="tel:"]')
                    ]
                    
                    for extractor in phone_extractors:
                        try:
                            phone_elem = extractor(item)
                            if phone_elem:
                                phone_span = phone_elem.find('span') or phone_elem
                                if phone_span:
                                    phone = phone_span.get_text(strip=True)
                                    if phone:
                                        institution_data['phone'] = self.clean_phone(phone)
                                        print(f"    Found phone: {phone}")
                                
                                href = phone_elem.get('href', '')
                                if href.startswith('tel:'):
                                    institution_data['phone_href'] = href
                                break
                        except:
                            continue
                    
                    # Extract map URL
                    map_url = item.get('data-map-url')
                    if map_url:
                        institution_data['map_url'] = map_url
                    
                    institutions.append(institution_data)
                    
                except Exception as e:
                    print(f"    Error processing item {i+1}: {e}")
                    # Add error info but continue
                    institutions.append({
                        'item_index': i + 1,
                        'error': str(e),
                        'raw_html': str(item)[:200] + '...'
                    })
            
            print(f"Successfully processed {len(institutions)} items")
            return institutions
            
        except Exception as e:
            print(f"Major error in scraping: {e}")
            return institutions  # Return whatever we have
    
    def save_to_json(self, data, filename='medical_institutions.json'):
        """Save data to JSON file with robust error handling"""
        try:
            # Make data JSON serializable
            clean_data = []
            for item in data:
                clean_item = {}
                for key, value in item.items():
                    if value is None:
                        clean_item[key] = None
                    elif isinstance(value, (str, int, float, bool)):
                        clean_item[key] = value
                    else:
                        clean_item[key] = str(value)
                clean_data.append(clean_item)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(clean_data, f, ensure_ascii=False, indent=2)
            print(f"✓ JSON saved: {filename} ({len(clean_data)} items)")
            
        except Exception as e:
            print(f"Error saving JSON: {e}")
            # Save error info
            try:
                with open(f"error_{filename}", 'w', encoding='utf-8') as f:
                    json.dump({
                        "error": str(e),
                        "data_count": len(data),
                        "sample_data": data[:2] if data else []
                    }, f, indent=2, ensure_ascii=False)
            except:
                pass
    
    def save_to_csv(self, data, filename='medical_institutions.csv'):
        """Save data to CSV file with robust error handling"""
        try:
            if not data:
                # Create empty CSV with basic headers
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['name', 'address', 'phone', 'latitude', 'longitude', 'error'])
                print(f"✓ Empty CSV saved: {filename}")
                return
            
            # Get all keys
            all_keys = set()
            for item in data:
                all_keys.update(item.keys())
            
            sorted_keys = sorted(all_keys)
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=sorted_keys, restval='')
                writer.writeheader()
                
                for item in data:
                    clean_row = {}
                    for key in sorted_keys:
                        value = item.get(key, '')
                        if value is None:
                            clean_row[key] = ''
                        else:
                            clean_row[key] = str(value)
                    writer.writerow(clean_row)
            
            print(f"✓ CSV saved: {filename} ({len(data)} items, {len(sorted_keys)} columns)")
            
        except Exception as e:
            print(f"Error saving CSV: {e}")
    
    def scrape_with_pagination(self):
        """Main scraping method"""
        print("Starting data extraction...")
        institutions = self.scrape_medical_institutions()
        time.sleep(1)  # Be respectful
        return institutions

def main():
    """Main function"""
    scraper = AzerbaijanMedicalScraper()
    
    print("Azerbaijan Medical Institutions Scraper")
    print("=" * 50)
    
    try:
        # Run the scraper
        institutions = scraper.scrape_with_pagination()
        
        print(f"\nExtraction complete!")
        print(f"Total items found: {len(institutions)}")
        
        # Save data regardless of content
        scraper.save_to_json(institutions)
        scraper.save_to_csv(institutions)
        
        # Show summary
        valid_names = sum(1 for inst in institutions if inst.get('name'))
        valid_coords = sum(1 for inst in institutions if inst.get('latitude') and inst.get('longitude'))
        errors = sum(1 for inst in institutions if inst.get('error'))
        
        print(f"\nSummary:")
        print(f"  Items with names: {valid_names}")
        print(f"  Items with coordinates: {valid_coords}")
        print(f"  Items with errors: {errors}")
        
        # Show first few results
        if institutions:
            print(f"\nFirst {min(3, len(institutions))} items:")
            for i, inst in enumerate(institutions[:3], 1):
                print(f"\n{i}. Name: {inst.get('name', 'N/A')}")
                print(f"   Address: {inst.get('address', 'N/A')}")
                print(f"   Phone: {inst.get('phone', 'N/A')}")
                print(f"   Coordinates: {inst.get('latitude', 'N/A')}, {inst.get('longitude', 'N/A')}")
                if inst.get('error'):
                    print(f"   Error: {inst.get('error')}")
        
        print(f"\n✓ Files created: medical_institutions.json, medical_institutions.csv")
        print(f"✓ Debug file: raw_page.html")
        
    except Exception as e:
        print(f"Fatal error: {e}")
        # Still try to save something
        scraper.save_to_json([])
        scraper.save_to_csv([])

if __name__ == "__main__":
    main()