import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import re
import html
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
    
    def parse_coordinates(self, coord_value):
        """Parse coordinates from various formats"""
        if not coord_value:
            return None
            
        try:
            coord_str = str(coord_value).strip()
            
            # Try decimal format first
            try:
                return float(coord_str)
            except ValueError:
                pass
            
            # Handle DMS format like "40°35'00.2"
            if '°' in coord_str and "'" in coord_str:
                numbers = re.findall(r'\d+\.?\d*', coord_str)
                if len(numbers) >= 2:
                    degrees = float(numbers[0])
                    minutes = float(numbers[1])
                    seconds = float(numbers[2]) if len(numbers) > 2 else 0
                    return degrees + minutes/60 + seconds/3600
            
            return None
            
        except Exception as e:
            print(f"    Warning: Could not parse coordinate '{coord_value}': {e}")
            return None
    
    def extract_coordinates_from_string(self, coord_string):
        """Extract lat/lng from coordinate string like '[41.6294932, 46.6420456]'"""
        try:
            if not coord_string:
                return None, None
                
            # Remove brackets and split
            clean_coord = coord_string.strip('[]')
            coords = [c.strip() for c in clean_coord.split(',')]
            
            if len(coords) == 2:
                lat = self.parse_coordinates(coords[0])
                lng = self.parse_coordinates(coords[1])
                return lat, lng
                
        except Exception as e:
            print(f"    Warning: Could not parse coordinate string '{coord_string}': {e}")
            
        return None, None
    
    def extract_map_url(self, map_url_encoded):
        """Extract and decode Google Maps embed URL"""
        try:
            if not map_url_encoded:
                return None
                
            # Decode HTML entities
            decoded = html.unescape(map_url_encoded)
            
            # Extract iframe src URL
            iframe_match = re.search(r'src="([^"]+)"', decoded)
            if iframe_match:
                return iframe_match.group(1)
                
        except Exception:
            pass
            
        return map_url_encoded  # Return original if parsing fails
    
    def extract_subsidiary_institutions(self, item):
        """Extract list of subsidiary medical institutions"""
        subsidiaries = []
        try:
            hospital_list = item.find('div', class_='hospital-list')
            if hospital_list:
                ul_element = hospital_list.find('ul')
                if ul_element:
                    for li in ul_element.find_all('li'):
                        text = li.get_text(strip=True)
                        if text:
                            subsidiaries.append(text)
        except Exception as e:
            print(f"    Warning: Could not extract subsidiaries: {e}")
            
        return subsidiaries
    
    def scrape_medical_institutions(self):
        """Scrape medical institutions from the website"""
        institutions = []
        
        try:
            print(f"Fetching data from: {self.search_url}")
            response = self.session.get(self.search_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find institution items using the specific classes
            institution_items = soup.find_all('div', class_='accordion-header each-item result-item')
            
            if not institution_items:
                print("No institution items found. Trying alternative selectors...")
                # Try fallback selectors
                alternative_selectors = [
                    'div.result-item',
                    'div.each-item', 
                    '[data-lat]',
                    '[data-coord]'
                ]
                
                for selector in alternative_selectors:
                    items = soup.select(selector)
                    if items:
                        print(f"Found {len(items)} items with selector: {selector}")
                        institution_items = items
                        break
            
            if not institution_items:
                print("No medical institutions found on the page")
                return institutions
            
            print(f"Processing {len(institution_items)} medical institutions...")
            
            for i, item in enumerate(institution_items, 1):
                try:
                    print(f"  Processing institution {i}...")
                    
                    institution_data = {}
                    
                    # Extract coordinates
                    lat = self.parse_coordinates(item.get('data-lat'))
                    lng = self.parse_coordinates(item.get('data-long'))
                    
                    # If individual coordinates failed, try coordinate string
                    if lat is None or lng is None:
                        coord_str = item.get('data-coord')
                        if coord_str:
                            lat_from_str, lng_from_str = self.extract_coordinates_from_string(coord_str)
                            if lat is None:
                                lat = lat_from_str
                            if lng is None:
                                lng = lng_from_str
                    
                    institution_data['latitude'] = lat
                    institution_data['longitude'] = lng
                    
                    # Extract Google Maps URL
                    map_url_raw = item.get('data-map-url')
                    if map_url_raw:
                        institution_data['google_maps_embed'] = self.extract_map_url(map_url_raw)
                    
                    # Extract institution name
                    name_elem = item.find('h2')
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        if name:
                            institution_data['name'] = name
                            print(f"    ✓ Name: {name}")
                    
                    # Extract address
                    location_div = item.find('div', class_='location')
                    if location_div:
                        address_span = location_div.find('span')
                        if address_span:
                            address = address_span.get_text(strip=True)
                            if address:
                                institution_data['address'] = address
                                print(f"    ✓ Address: {address}")
                    
                    # Extract phone
                    phone_link = item.find('a', class_='phone')
                    if phone_link:
                        phone_span = phone_link.find('span')
                        if phone_span:
                            phone = phone_span.get_text(strip=True)
                            if phone:
                                institution_data['phone'] = phone
                                print(f"    ✓ Phone: {phone}")
                        
                        # Extract tel: URL
                        tel_href = phone_link.get('href')
                        if tel_href and tel_href.startswith('tel:'):
                            institution_data['phone_link'] = tel_href
                    
                    # Extract subsidiary institutions
                    subsidiaries = self.extract_subsidiary_institutions(item)
                    if subsidiaries:
                        institution_data['subsidiary_institutions'] = subsidiaries
                        institution_data['subsidiary_count'] = len(subsidiaries)
                        print(f"    ✓ Found {len(subsidiaries)} subsidiary institutions")
                    
                    # Add coordinates info
                    if lat and lng:
                        print(f"    ✓ Coordinates: {lat}, {lng}")
                    
                    institutions.append(institution_data)
                    
                except Exception as e:
                    print(f"    ✗ Error processing institution {i}: {e}")
                    # Add minimal error record
                    institutions.append({
                        'institution_number': i,
                        'extraction_error': str(e)
                    })
            
            print(f"\n✓ Successfully processed {len(institutions)} institutions")
            
            # Summary statistics
            valid_institutions = [inst for inst in institutions if inst.get('name')]
            institutions_with_coords = [inst for inst in institutions if inst.get('latitude') and inst.get('longitude')]
            institutions_with_subsidiaries = [inst for inst in institutions if inst.get('subsidiary_institutions')]
            
            print(f"  - Institutions with names: {len(valid_institutions)}")
            print(f"  - Institutions with coordinates: {len(institutions_with_coords)}")
            print(f"  - Institutions with subsidiaries: {len(institutions_with_subsidiaries)}")
            
            return institutions
            
        except Exception as e:
            print(f"Error in scraping: {e}")
            return institutions
    
    def save_to_json(self, data, filename='medical_institutions.json'):
        """Save clean data to JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✓ JSON saved: {filename} ({len(data)} institutions)")
        except Exception as e:
            print(f"✗ Error saving JSON: {e}")
    
    def save_to_csv(self, data, filename='medical_institutions.csv'):
        """Save clean data to CSV"""
        try:
            if not data:
                # Create empty CSV with headers
                headers = ['name', 'address', 'phone', 'latitude', 'longitude', 'subsidiary_count', 'google_maps_embed']
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                print(f"✓ Empty CSV created: {filename}")
                return
            
            # Flatten subsidiary institutions for CSV
            csv_data = []
            for institution in data:
                base_row = {
                    'name': institution.get('name', ''),
                    'address': institution.get('address', ''),
                    'phone': institution.get('phone', ''),
                    'phone_link': institution.get('phone_link', ''),
                    'latitude': institution.get('latitude', ''),
                    'longitude': institution.get('longitude', ''),
                    'google_maps_embed': institution.get('google_maps_embed', ''),
                    'subsidiary_count': institution.get('subsidiary_count', 0),
                    'extraction_error': institution.get('extraction_error', '')
                }
                
                # Add subsidiary institutions as a comma-separated string
                subsidiaries = institution.get('subsidiary_institutions', [])
                if subsidiaries:
                    base_row['subsidiary_institutions'] = '; '.join(subsidiaries)
                else:
                    base_row['subsidiary_institutions'] = ''
                
                csv_data.append(base_row)
            
            # Write CSV
            if csv_data:
                fieldnames = csv_data[0].keys()
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(csv_data)
                
                print(f"✓ CSV saved: {filename} ({len(csv_data)} institutions)")
            
        except Exception as e:
            print(f"✗ Error saving CSV: {e}")
    
    def create_subsidiary_csv(self, data, filename='subsidiary_institutions.csv'):
        """Create separate CSV for subsidiary institutions"""
        try:
            subsidiary_data = []
            
            for institution in data:
                main_name = institution.get('name', 'Unknown')
                main_address = institution.get('address', '')
                subsidiaries = institution.get('subsidiary_institutions', [])
                
                for subsidiary in subsidiaries:
                    subsidiary_data.append({
                        'main_institution': main_name,
                        'main_address': main_address,
                        'subsidiary_name': subsidiary,
                        'latitude': institution.get('latitude', ''),
                        'longitude': institution.get('longitude', '')
                    })
            
            if subsidiary_data:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=subsidiary_data[0].keys())
                    writer.writeheader()
                    writer.writerows(subsidiary_data)
                
                print(f"✓ Subsidiary CSV saved: {filename} ({len(subsidiary_data)} subsidiaries)")
            
        except Exception as e:
            print(f"✗ Error saving subsidiary CSV: {e}")

def main():
    """Main function"""
    scraper = AzerbaijanMedicalScraper()
    
    print("🏥 Azerbaijan Medical Institutions Scraper")
    print("=" * 50)
    
    try:
        # Scrape the data
        institutions = scraper.scrape_medical_institutions()
        
        if institutions:
            print(f"\n📊 Data extraction completed!")
            
            # Save main data
            scraper.save_to_json(institutions)
            scraper.save_to_csv(institutions)
            
            # Create separate subsidiary institutions file
            scraper.create_subsidiary_csv(institutions)
            
            # Display sample results
            valid_institutions = [inst for inst in institutions if inst.get('name')]
            
            if valid_institutions:
                print(f"\n📋 Sample results (first 2 institutions):")
                for i, inst in enumerate(valid_institutions[:2], 1):
                    print(f"\n{i}. {inst.get('name')}")
                    print(f"   📍 {inst.get('address', 'No address')}")
                    print(f"   📞 {inst.get('phone', 'No phone')}")
                    print(f"   🌐 {inst.get('latitude', 'N/A')}, {inst.get('longitude', 'N/A')}")
                    
                    subs = inst.get('subsidiary_institutions', [])
                    if subs:
                        print(f"   🏥 {len(subs)} subsidiary institutions")
                        if len(subs) <= 3:
                            for sub in subs:
                                print(f"      - {sub}")
                        else:
                            for sub in subs[:3]:
                                print(f"      - {sub}")
                            print(f"      ... and {len(subs)-3} more")
            
            print(f"\n✅ Files created:")
            print(f"   📄 medical_institutions.json")
            print(f"   📄 medical_institutions.csv") 
            print(f"   📄 subsidiary_institutions.csv")
        
        else:
            print("❌ No data extracted")
            scraper.save_to_json([])
            scraper.save_to_csv([])
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()