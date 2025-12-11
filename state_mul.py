import uuid
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'
from selenium.webdriver.support.ui import Select
import base64
import easyocr
import os as os_module
from io import BytesIO
import numpy as np
import re  # Ensure to import re for regex operations
from PIL import Image
from selenium.webdriver.chrome.options import Options
import json
import random
import requests
from urllib.parse import parse_qs
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from selenium.common.exceptions import WebDriverException, ElementNotInteractableException, TimeoutException
from datetime import datetime
from collections import defaultdict
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException
import traceback

class fssai_multiple_filing:

    def __init__(self,otp_data, session_data, otp_submission_status, session_id=None):
        self.otp_data = otp_data
        self.session_data = session_data
        self.current_session_id = session_id
        self.otp_submission_status = otp_submission_status
    
    def save_base64_file(self, base64_data, file_name, folder_path, convert_to_pdf = False):
        """Decode a base64 string and save it as a file."""
        try:
            if not base64_data or base64_data.lower() == "none":
                return None #Skip saving if data in "none"
            os.makedirs(folder_path, exist_ok = True) # Create folder if it doesn't exist
            #Generate a random ID to append to the file name
            random_id = random.randint(1000,9999)
            file_extension = os.path.splitext(file_name)[1].lower() #get file extension
            unique_file_name = f"{os.path.splitext(file_name)[0]}_{random_id}{file_extension}"
            file_path = os.path.join(folder_path, unique_file_name)
            #Decode Base64
            decoded_bytes = base64.b64decode(base64_data)

            #check if it is a valid jpeg image
            is_image = False
            image_format = None
            try:
                image = Image.open(BytesIO(decoded_bytes))
                image_format = image.format
                is_image = image_format in ["JPEG", "JPG", "PNG"]
            except Exception:
                pass

            # Save as JPG or PDF based on content
            if is_image:
                # If conversion to PDF is required (for Aadhar & PAN)
                if convert_to_pdf and image_format in ["JPEG", "JPG", "PNG"]:
                    file_path = file_path.replace(file_extension, ".pdf")
                    pdf_path = self.convert_image_to_pdf(image, file_path)
                    return pdf_path
                
                # Otherwise, keep the original format for photos
                with open(file_path, "wb") as file:
                    file.write(decoded_bytes)
                print(f"Image saved at: {file_path}")
                return file_path
            else:
                # If not an image, save as PDF directly
                file_path = file_path.replace(file_extension, ".pdf")
                with open(file_path, "wb") as file:
                    file.write(decoded_bytes)
                print(f"PDF saved at: {file_path}")
                return file_path
            
        except Exception as e:
            print(f"Error saving file: {e}")
            return None
        
    def convert_image_to_pdf(self,image, pdf_path):
        """Convert an image to PDF."""
        try:
            image = image.convert("RGB")
            image.save(pdf_path, "PDF", resolution=100.0)
            print(f"Converted and saved PDF at: {pdf_path}")
            return pdf_path
        except Exception as e:
            print(f"Error converting image to PDF: {e}")
            return None 
        
    def map_kind_of_business_to_type(self, kinds_of_business_list):
        food_services_categories = [
            "Restaurants", "Food Vending Establishment", "Club/Canteen",
            "Caterer", "Mid-Day meal - Caterer", "Mid-Day meal - Canteen"
        ]
        trade_retail_categories = [
            "Wholesaler", "Distributor", "Transportation", "Transportation (having a number of specialized vehicles like insulated refrigerated van/ wagon and milk tankers etc.)",
            "Retailer", "Direct Seller", "Hotel", "Storage (Except Controlled Atmosphere and Cold)" , "Storage (Cold / Refrigerated)" , "Storage (Controlled Atmosphere + Cold)"
        ]
        manufacturer_categories = [
            "Dairy Units", "Meat processing units", "Fish and Fish Products",
            "Substances Added to Food", "General Manufacturing"
        ]

        matched_map = defaultdict(list)  # Using defaultdict to handle missing keys automatically

        for kob in kinds_of_business_list:
            kob_clean = kob.strip()
            if kob_clean in food_services_categories:
                matched_map["Food Services"].append(kob_clean)
            elif kob_clean in trade_retail_categories:
                matched_map["Trade/Retail"].append(kob_clean)
            elif kob_clean in manufacturer_categories:
                matched_map["Manufacturer"].append(kob_clean)

        if matched_map:
            return dict(matched_map)  # This returns a dict like: {'Manufacturer': [...], 'Trade/Retail': [...]}
        else:
            return "Unknown", kinds_of_business_list
        
    def transform_data(self,input_data):

        """
        Transforms input JSON data into the required client_info format.
        """
        kinds_of_business = input_data["result"]["payload"].get("kind_of_business", [])
        service_map = self.map_kind_of_business_to_type(kinds_of_business)
        service_type_aliases = {
            "Manufacturing": "Manufacturer"
        }
         # Rename keys if needed using alias map
        mapped_service_map = {}
        for key, val in service_map.items():
            new_key = service_type_aliases.get(key, key)
            mapped_service_map[new_key] = val
        
        state= input_data["result"]["payload"].get("state","").title()
        if not state:
            print("no state is specified")
            return False
        
        state_aliases ={
            "DADRA AND NAGAR HAVELI & DAMAN & DIU":"Dadra and Nagar Haveli & Daman & Diu"
        }
        state = state_aliases.get(state, state)
        print(f"Transformed state: {state}")  # Debug print

        print(f"Transformed service map: {mapped_service_map}")  # Debug print
        transformed_data = {
            "state": state,
            "service_types":mapped_service_map,
            "name_company":input_data["result"]["payload"].get("business_name", ""),
            "address":input_data["result"]["payload"].get("address", ""),
            "district":input_data["result"]["payload"].get("district", ""),
            "subdistrict":input_data["result"]["payload"].get("sub_division", ""),
            "pincode":input_data["result"]["payload"].get("pincode", ""),
            "pan_no":input_data["people_data"].get("pan",""),
            "doi":"2023-10-01",
            "kind_of_business":"Manufacturer",
            "holder_name":" ".join(filter(None, [
            input_data["people_data"].get("first_name", ""),
            input_data["people_data"].get("middle_name", ""),
            input_data["people_data"].get("last_name", "")])).strip(),
            "holder_dob":input_data["people_data"].get("dob",""),
            "gender":"Male" if input_data["people_data"].get("salutation", "").strip() == "Mr." else "Female",
            "production_capacity": input_data["result"]["payload"].get("production_capacity",""),
            "categories":input_data["result"]["payload"].get("food_category_name", []),
            "sub_categories":input_data["result"]["payload"].get("food_sub_category_name",[]),
            "add_products":input_data["result"]["payload"].get("product",[]),
            "applicantname":input_data["result"]["payload"].get("client_name",""),
            "primaryemail":input_data["result"]["payload"].get("client_email",""),
            "primarymobile":input_data["result"]["payload"].get("client_mobile",""),
            "secondaryemail":input_data["result"]["payload"].get("created_by_email",""),
            "secondarymobile":input_data["result"].get("rm_mobile",""),
            "password":"I##23",
            "Incharge_operation":input_data["result"]["payload"].get("client_name",""),
            "qualification":input_data["people_data"].get("qualification",""),
            "mobile_no":input_data["result"]["payload"].get("client_mobile",""),
            "email":input_data["result"]["payload"].get("client_email",""),
            "id_number":input_data["people_data"].get("aadhaar",""),
            "no_of_years": input_data["result"]["payload"].get("no_of_years", "1"),
            "blueprint_layout_plan":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "substances_doc":input_data["result"]["doc"].get("substances_food",""),
            "list_of_director":input_data["result"]["doc"].get("list_of_director",""),
            "list_of_equip":input_data["result"]["doc"].get("list_equip",""),
            "analysis_report":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "photo_id":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "address_proof":input_data["result"]["doc"].get("electricity_bill","") or input_data["result"]["doc"].get("rental_agreement", ""),
            "partnership_deed":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "formix":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "recall_plan":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "production_unit_photograph":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "source_plan":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "NOC_municipal":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "list_of_veh":input_data["result"]["doc"].get("list_of_veh",""),
            "direct_selling_agreement":input_data["result"]["doc"].get("direct_selling_agreement",""),
            "any_other_doc":input_data["result"]["doc"].get("FSMS_PLAN",""),
            "any_other_doc2":input_data["result"]["doc"].get("property_tax_receipt","")
        }
        print(transformed_data["state"])
        print(transformed_data["service_types"])
        print(transformed_data["add_products"])
        return transformed_data
    
    def multiple_service_automation(self,input_data):

        client_info = self.transform_data(input_data)
        
        download_dir = r"C:\Users\Ledgers\Preview_state_applications"  # Desired download directory
        temp_folder = r"D:\fssai_decoded_files"
        os_module.makedirs(temp_folder, exist_ok=True)
        print(f"Temporary folder created: {temp_folder}")
        
        options = webdriver.ChromeOptions() 

        prefs = {
            "download.default_directory": download_dir,  # Set custom download location
            "download.prompt_for_download": False,       # Disable download prompt
            "directory_upgrade": True                    # Overwrite existing files
        }
        
        # Add the argument to ignore SSL errors
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-logging")  # Reduce logging
        options.add_argument("--log-level=3")  # Suppress unnecessary logs
        options.add_argument("--disable-gpu")  # Prevent GPU rendering issues
        # options.add_argument("--incognito")
        options.add_experimental_option("prefs", prefs)

        # Your existing Selenium code here 
        
        driver = webdriver.Chrome(options=options)
        driver.get("https://foscos.fssai.gov.in/public/fbo/open-eligibility/N")
        driver.maximize_window()

        try:
                # Select State from Dropdown
            state_dropdown = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div/p/select'))  # Using the provided XPath
            )
            
            state_dropdown.click()  # Open the dropdown
            
            # Wait for the specific option to be clickable based on the selected state value
            state_option = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, f"//option[contains(text(), '{client_info['state']}')]"))  # Use the state from your selected_info
            )
            state_option.click()  # Select the option
            print(f"Selected '{client_info['state']}' from State.")
            
           # client_info['service_types'] is now a dict: {ServiceType: [Establishments]}
            for service_type, establishment_list in client_info['service_types'].items():
                service_type = service_type.strip()
                print(f"Handling service type: {service_type}")

                try:
                    
                    # Click the service type button (Food Services / Manufacturer / Trade Retail)
                    service_type_button = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{service_type}')]"))
                    )
                    service_type_button.click() 
                    print(f"Clicked '{service_type}' button.")

                    time.sleep(2)  # Give a small gap before handling establishments
                    
                    
                    # Now handle establishment types
                    for establishment_type in establishment_list:
                        establishment_type = establishment_type.strip()

                        if establishment_type == "Dairy Units":
                            establishment_type = establishment_type.lower().capitalize()  # Only convert "Dairy Units" to "Dairy units"
                            print(f"After conversion (Dairy Units): {establishment_type}")  # Debug print
                        elif establishment_type == "Transportation":
                            establishment_type = "Transportation (having a number of specialized vehicles like insulated refrigerated van/ wagon and milk tankers etc.)"
                            print(f"After conversion (Transportation): {establishment_type}")
                            
                        else:
                            # Keep original case exactly as is - no modifications
                            print(f"Non-dairy type, keeping original: {establishment_type}")  # Debug print
                        
                        
                        print(f"Final establishment_type: {establishment_type}")  # Debug print

                        print(f"Handling establishment type: {establishment_type} under '{service_type}'")

                        try:
                            
                            # Click establishment accordion
                            establishment_element = WebDriverWait(driver, 20).until(
                                EC.element_to_be_clickable((By.XPATH, f"//div[@class='accordion']//span[contains(normalize-space(), '{establishment_type}')]"))
                            )
                            establishment_element.click()

                            # Handle radio button
                            path = None
                            if establishment_type == 'Dairy units':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[1]/div[2]/div/div[1]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Vegetable oil and processing units':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[1]/div[2]/div/div[2]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Meat processing units':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[1]/div[2]/div/div[4]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Fish and Fish Products':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[1]/div[2]/div/div[5]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Substances Added to Food':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[1]/div[2]/div/div[10]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'General Manufacturing':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[1]/div[2]/div/div[7]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Restaurants':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[3]/div[2]/div/div[3]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Food Vending Establishment':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[3]/div[2]/div/div[4]/div[2]/div/div/table/tbody/tr/td[2]/div[1]/div/div/input'
                            elif establishment_type == 'Club/Canteen':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[3]/div[2]/div/div[5]/div[2]/div/div/table/tbody/tr/td[2]/div[1]/div/div/input'
                            elif establishment_type == 'Caterer':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[3]/div[2]/div/div[6]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Mid-Day meal - Caterer':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[3]/div[2]/div/div[8]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Mid-Day meal - Canteen':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[3]/div[2]/div/div[9]/div[2]/div/div/table/tbody/tr/td[2]/div[1]/div/div/input'
                            elif establishment_type == 'Storage (Except Controlled Atmosphere and Cold)':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[1]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Storage (Cold / Refrigerated)':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[2]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Storage (Controlled Atmosphere + Cold)':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[3]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Wholesaler':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[4]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Distributor':
                                path ='//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[5]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                                
                            elif establishment_type == 'Transportation (having a number of specialized vehicles like insulated refrigerated van/ wagon and milk tankers etc.)' or establishment_type == 'Transportation': 
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[6]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'

                            elif establishment_type == 'Retailer':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[7]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'
                            elif establishment_type == 'Direct Seller':
                                path = '//*[@id="content"]/div/div/div[3]/app-eligibility-panel/div[2]/div[2]/div/div[8]/div[2]/div/div/table/tbody/tr/td[2]/div[2]/div/div/input'

                            elif establishment_type == 'Hotel':
                                # tier_text = " ".join(client_info.get("tier", [])).lower()  # Combine list items & lowercase for consistent match
                                tier_text = client_info.get("tier", "").lower()
                                # Decide choice based on star keywords
                                if "one star" in tier_text or "two star" in tier_text:
                                    choice = "1"
                                elif "three star" in tier_text or "four star" in tier_text:
                                    choice = "2"
                                else:
                                    choice = "1"
                                    # raise ValueError("Could not determine hotel tier from the provided 'tier' info.")

                                # Map choice to Hotel type string
                                if choice == "1":
                                    Hotel_type = "One Star, Two Star or non-Star Rating having turnover more than Rs. 12 Lacs per annum [State License]"
                                else:
                                    Hotel_type = "Three Star or Four Star (Ministry of Tourism Certificate required) [State License]"

                                # XPath to dynamically find the matching radio button
                                xpath = f'//span[contains(text(),"{Hotel_type}")]/preceding-sibling::input[@type="radio"]'

                                # Wait for the radio button to be clickable
                                radio_button = WebDriverWait(driver, 20).until(
                                    EC.element_to_be_clickable((By.XPATH, xpath))
                                )

                                # Click the radio button
                                radio_button.click()
                                print(f"Clicked on '{Hotel_type}' state license radio button")
                            else:
                                print(f"No radio path matched for '{establishment_type}'")
                            
                            if path:
                                try:
                                    # Wait for radio button section to expand properly
                                    WebDriverWait(driver, 5).until(
                                        EC.presence_of_element_located((By.XPATH, path))
                                    )
                                    time.sleep(1)

                                    radio_button = WebDriverWait(driver, 20).until(
                                        EC.element_to_be_clickable((By.XPATH, path))
                                    )
                                    driver.execute_script("arguments[0].click();", radio_button)
                                    print(f"Clicked radio button for '{establishment_type}'")
                                except Exception as click_err:
                                    print(f"Failed to click radio button for '{establishment_type}': {click_err}")

                        except Exception as est_err:
                            print(f"Error handling establishment '{establishment_type}': {est_err}")

                except Exception as service_err:
                    print(f"Error handling service type '{service_type}': {service_err}")
            
            # Click Proceed Button
            proceed_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@type='button' and @value='Proceed' and contains(@class, 'w3-btn w3-my-green')]"))
            )
            proceed_button.click()
            print("Clicked 'Proceed' button.")
            
            # Eligibility Button Click
            eligibility_button = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and contains(@class,'w3-btn w3-my-green w3-round w3-ripple')]"))
            )
            eligibility_button.click()
            print("Clicked 'Eligibility' button.")
            
            
            #name of company  
            path = '//*[@id="content"]/div/div/div[3]/form/div[1]/div/div/div[2]/input'
            name_of_company =  WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, path))
            )
            name_of_company.send_keys(client_info['name_company'])
            
            
            path = '//*[@id="content"]/div/div/div[3]/form/div[2]/div[1]/div[1]/div[2]/input'
            address_ = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, path))
            )
            address_.send_keys(client_info['address'])
            
            time.sleep(2)
            
            #choose district from dropdown
            try:
                #path = '//*[@id="content"]/div/div/div[3]/form/div[2]/div[2]/div[1]/div[2]/select' 
                path = '//*[@id="content"]/div/div/div[3]/form/div[2]/div[2]/div[1]/div[2]/select'
                district_dropdown = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH,path))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);",district_dropdown)
                select__ = Select(district_dropdown)
                
                select__.select_by_visible_text(client_info['district'])
                time.sleep(5)
            
            
                path = '//*[@id="content"]/div/div/div[3]/form/div[2]/div[2]/div[2]/div[2]/select'
                sub_district = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, path))
                )
                select = Select(sub_district)
                select.select_by_visible_text(client_info['subdistrict'])
                time.sleep(5)
                
                
                path = '//*[@id="content"]/div/div/div[3]/form/div[2]/div[2]/div[3]/div[2]/input'
                pincode_ = driver.find_element(By.XPATH, path)
                pincode_.send_keys(client_info['pincode'])
                print("pincode entered successfully")
                
                path = '//*[@id="content"]/div/div/div[3]/form/div[2]/div[5]/div/div[2]/input'
                pan_number = driver.find_element(By.XPATH, path)
                pan_number.send_keys(client_info['pan_no'])
                print("PAN entered successfully")
                time.sleep(5)
            
                # path = '//*[@id="content"]/div/div/div[3]/form/div[2]/div[5]/div/div[1]/label'
                # space_click = driver.find_element(By.XPATH, path)
                # space_click.click()  

                pincode_.click()

                pan_no = client_info['pan_no']

                if pan_no[3] == "C":
                    print("Company PAN detected, keeping default selection.")

                    # Enter Company Name
                    company_name_input = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[11]/div/app-pan-card-template-tatkal/form/div/div[2]/div[1]/div/input'))
                    )
                    company_name_input.send_keys(client_info['name_company'])
                    print("Company Name entered successfully")

                    date_str = client_info['doi']
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        date_value = date_obj.strftime('%d-%m-%Y')
                    except ValueError:
                        date_value = date_str

                    # Enter Date of Issue (DOI)
                    doi_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[11]/div/app-pan-card-template-tatkal/form/div/div[2]/div[2]/div/input'))
                    )
                    # doi_input.clear()
                    # doi_input.send_keys(date_value)
                    # doi_value = client_info['doi']
                    driver.execute_script("arguments[0].value = arguments[1];", doi_input, date_value)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", doi_input)
                    print(f"Date of Issue set to {date_value}")

                else:
                    print("Individual PAN detected, switching selection to Individual.")

                    # Select Individual Option
                    pan_individual = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[11]/div/app-pan-card-template-tatkal/form/div/div[1]/div/p/input[1]'))
                    )
                    pan_individual.click()
                    print("Individual option selected")

                    # Enter PAN Holder Name
                    pan_holder_name_input = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[formcontrolname="panHolderName"]'))
                    )
                    pan_holder_name_input.send_keys(client_info['holder_name'])
                    print("PAN Holder Name entered successfully")

                    date_str = client_info['holder_dob']
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        date_value = date_obj.strftime('%d-%m-%Y')
                    except ValueError:
                        date_value = date_str

                    # Enter Date of Birth (DOB)
                    dob_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[formcontrolname='panHolderDob']"))
                    )           
                    # dob_input.clear()
                    # dob_input.send_keys(date_value)
                    print(f"Date of Birth set to {date_value}.")
                    # dob_value = client_info['holder_dob']
                    driver.execute_script("arguments[0].value = arguments[1];", dob_input, date_value)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", dob_input)
                    # print(f"Date of Birth set to {dob_value}")

                    # Select Gender
                    gender_dropdown = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "select[formcontrolname='panHolderGender']"))
                    )
                    select_gender = Select(gender_dropdown)
                    select_gender.select_by_visible_text(client_info['gender'])
                    print("Gender selected successfully")

                # Click Declare Checkbox
                declare_checkbox = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[11]/div/app-pan-card-template-tatkal/form/div/div[3]/div/input'))
                )
                declare_checkbox.click()
                print("Declaration checkbox checked")

                # Click Submit Button
                submit_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[11]/div/app-pan-card-template-tatkal/form/footer/button'))
                )
                submit_button.click()
                print("Form submitted successfully")
                time.sleep(20)
            
            except WebDriverException as e:
            
                print(f"error occurred : {e}")
                        
            time.sleep(10)            
            
            path = '//*[@id="content"]/div/div/div[3]/form/div[3]/div/button'
            save_button = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH,path))
            )
            driver.execute_script("arguments[0].click();",save_button)
            print("next location")
            
            # input("Please manually drag and verify the location on the map and press Enter once done...")

            path = '//*[@id="Body"]/app-root/app-open-application-details-filing/div[5]/div/div/app-map/div/div/div/h3/div/div/div[3]/div[1]/div[2]/div/div[3]/div/img'
            map_loc = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH,path))
            )
            driver.execute_script("arguments[0].click();",map_loc)
            
            
            path = '//*[@id="Body"]/app-root/app-open-application-details-filing/div[5]/div/footer/input'
            O_k = driver.find_element(By.XPATH, path)
            O_k.click()
            print("moved to product selection page")

            import os 
            
            # def real_user_click(driver, element):
            #     actions = ActionChains(driver)
            #     actions.move_to_element(element).pause(1).click().perform()

            def select_categories(driver, client_info):
                try:
                    # Step 1: Click the correct establishment label
                    label_xpath = f"//label[normalize-space(text())='{establishment_type}']"
                    element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, label_xpath)))
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                    time.sleep(1)
                    WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, label_xpath)))
                    driver.execute_script("arguments[0].click();", element)
                    print(f"Clicked on establishment: {establishment_type}")
                    time.sleep(2)

                    # Step 2: Loop over all visible category-type panels
                    panels = driver.find_elements(By.XPATH, "//app-food-category-templete-panel[not(ancestor-or-self::*[contains(@style,'display: none')])]")

                    if not panels:
                        raise Exception("No visible category panels found.")

                    print(f"Found {len(panels)} category panels.")

                    for i, panel in enumerate(panels, start=1):
                        print(i,panel)
                        print(f"\n Processing panel {i} for {establishment_type}...")

                        try:
                            # Find dropdown inside this panel
                            dropdown = panel.find_element(By.XPATH, ".//tfoot//tr//td[2]//select")
                            select_element = Select(dropdown)

                            for category in client_info["categories"]:
                                category = category.strip()
                                if not category:
                                    continue

                                try:
                                    time.sleep(2)
                                    select_element.select_by_visible_text(category)
                                    print(f"Panel {i}: Selected category: {category}")

                                    # Find and click "Save & Add" inside this panel
                                    save_button = panel.find_element(By.XPATH, ".//a[normalize-space()='Save & Add']")
                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", save_button)
                                    save_button.click()
                                    time.sleep(2)
                                    print(f"Panel {i}: Clicked 'Save & Add'")

                                except Exception as e:
                                    print(f"Panel {i}: Failed to select/save category '{category}': {e}")

                        except Exception as e:
                            print(f"Panel {i}: Error processing panel: {e}")

                except Exception as e:
                    print(f"Error occurred in select_categories: {e}")

                                                  
            def handle_general_dairy(driver,client_info):  

                #KOb selection before category, sub category
                try:
                    label_xpath = f"//label[normalize-space(text())='{establishment_type}']"
        
                    # Wait for the element to appear in the DOM
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, label_xpath))
                    )
                    
                    # Smooth scroll to center
                    driver.execute_script("""
                        arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});
                    """, element)
                    time.sleep(1)  # let scrolling complete and DOM settle

                    # Wait until it's clickable, then click using JS to avoid interception
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, label_xpath)))
                    driver.execute_script("arguments[0].click();", element)
                    print(f"Smooth clicked establishment type: {establishment_type}")
                    time.sleep(1)

                except Exception as e:
                    print(f"Establishment not selected{e}")
                time.sleep(5)
                    
                try:   #dairy,general manufacturing , meat and fish,  //*[@id="content"]/div/div/div[3]/div[4]/div/div/app-food-category-product-level-section/div[1]/input
                    
                    # prod_xpath = f"//label[normalize-space(text())='{establishment_type}']/ancestor::div[contains(@class, 'form-group')]/following-sibling::div//input"
                    production_ = WebDriverWait(driver,10).until(
                        EC.element_to_be_clickable((By.NAME,'manufacturerCapacity'))
                    )
                    production_.send_keys(client_info["production_capacity"])

                    try: #mt_annum selection for meat and fish,  //*[@id="content"]/div/div/div[3]/div[4]/div/div/app-food-category-product-level-section/div[1]/div/div/input[2]
                        
                        mt_annum = WebDriverWait(driver,15).until(
                            EC.element_to_be_clickable((By.NAME,'MtUnit'))
                        )
                        driver.execute_script("arguments[0].click();",mt_annum)
                        time.sleep(1)
                    except Exception as e:
                        pass

                except Exception as e:
                    try: #substances added to food
                        production_ = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,'//*[@id="content"]/div/div/div[3]/div[3]/div/div/app-substances-food-section/div[1]/input'))
                        )
                        production_.send_keys(client_info["production_capacity"])

                    except Exception as e: #vegetable oil processing
                        production_ = WebDriverWait(driver,10).until( 
                            EC.element_to_be_clickable((By.XPATH,'//*[@id="content"]/div/div/div[3]/div[4]/div/div/app-oil-product-section/div[1]/div/div/div/input'))
                        )
                        production_.send_keys(client_info["production_capacity"])              
            
                try:
                    for i in range(len(client_info["categories"])):
                        category = client_info["categories"][i].strip()
                        sub_category = client_info["sub_categories"][i].strip() if i < len(client_info["sub_categories"]) else None
                        add_products = client_info["add_products"][i].strip() if i < len(client_info["add_products"]) else None
                        
                        # Skip category if the category is missing (empty string)
                        if not category:
                            print(f"Skipping category {i + 1} because it is missing.")
                            continue

                        try:
                            # Step 1: Select the category , //*[@id="content"]/div/div/div[3]/div[3]/div/div/app-food-category-product-level-section/div[1]/table/tfoot/tr/td[1]/select
                            categories_dropdown = WebDriverWait(driver, 20).until(
                                EC.element_to_be_clickable((By.NAME, 'foodCategory'))
                            )
                            select_categories = Select(categories_dropdown)
                            time.sleep(1)
                            select_categories.select_by_visible_text(category)
                            print(f"Category '{category}' selected.")

                        except Exception as e:
                            print(f"Failed to select category '{category}': {e}")
                            continue
        
                        if sub_category:
                            
                            try:
                                time.sleep(2)
                                # Step 2: Select the sub-category , //*[@id="content"]/div/div/div[3]/div[3]/div/div/app-food-category-product-level-section/div[1]/table/tfoot/tr/td[2]/select
                                sub_category_dropdown = WebDriverWait(driver, 20).until(
                                    EC.element_to_be_clickable((By.NAME, 'subFoodCategory'))
                                )
                                select_sub_category = Select(sub_category_dropdown)
                                select_sub_category.select_by_visible_text(sub_category)
                                print(f"Sub-category '{sub_category}' selected.")
                            
                            except Exception as e:
                                print(f"Failed to select sub-category '{sub_category}': {e}")
                        else:
                            print(f"Sub Category is missing , so skipping '{sub_category}'")
        
                        if add_products:
                            
                            try:
                                # Build relative XPath
                                add_edit_xpath = "//a[contains(text(), 'Add/Edit Product')]"

                                # Wait and click
                                add_edit_btn = WebDriverWait(driver, 10).until(
                                    EC.element_to_be_clickable((By.XPATH, add_edit_xpath))
                                )
                                driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", add_edit_btn)
                                time.sleep(1)
                                driver.execute_script("arguments[0].click();", add_edit_btn)
                                print(f"Clicked 'Add/Edit Product' for: {establishment_type}")

                                # # Clean and prepare product names from payload
                                products = [product.strip() for product in add_products.split(',')]
                                # products = add_products 
                                print("Products to select:", products)                                

                                for product in products:
                                    try:
                                        tr_element = WebDriverWait(driver,10).until(
                                            EC.presence_of_element_located((By.XPATH,f"//tr[td[contains(normalize-space(text()), '{product.split('[')[0].strip()}')]]"))
                                        )
                                        checkbox = tr_element.find_element(By.XPATH, ".//td[1]/input[@type='checkbox']")
                                        driver.execute_script("arguments[0].click();", checkbox)
                                        print(f"Clicked checkbox for '{product}'")

                                    except Exception as e:
                                        print(f"Could not find or click checkbox for '{product}': {e}")

                                # Step 4: Click the Submit button after selecting checkboxes, 
                                prod_submit = WebDriverWait(driver, 10).until(
                                    EC.element_to_be_clickable((By.XPATH, "//app-food-category-product-level-section//footer//button[@type='submit']"))
                                )
                                driver.execute_script("arguments[0].click();",prod_submit)
                                print("Submit button clicked.")

                            except Exception as e:
                                print(f"Failed to add products for category '{category}': {e}")
                        else:
                            print(f"No add products is given, so skipping '{add_products}'")

                        try:
                            # Step 5: Select the Kind of Business (KOB), //*[@id="content"]/div/div/div[3]/div[3]/div/div/app-food-category-product-level-section/div[1]/table/tfoot/tr/td[4]/select
                            KOB = WebDriverWait(driver, 20).until(
                                EC.element_to_be_clickable((By.NAME, 'kindOfBusiness'))
                            )
                            KOB.send_keys(client_info["kind_of_business"])
                            print(f"Kind of Business '{client_info['kind_of_business']}' selected.")
                        except Exception as e:
                            print(f"Failed to select Kind of Business for category '{category}': {e}")

                        try:
                            # Step 6: Save the selection, //*[@id="content"]/div/div/div[3]/div[3]/div/div/app-food-category-product-level-section/div[1]/table/tfoot/tr/td[5]/a
                            save_add_xpath = "./ancestor::tr//a[contains(text(), 'Save & Add')]"
                            
                            save_button = KOB.find_element(By.XPATH, save_add_xpath)             
                            time.sleep(5)
                            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center', inline:'center'}); arguments[0].click();", save_button)
                            
                            print("Selections saved.")
                        except Exception as e:
                            print(f"Failed to save selections for category '{category}': {e}")
                                    
                except Exception as e:
                    print(f"An error occurred: {e}")            
            
            def handle_substances(driver,client_info):
                 
                try:

                    label_xpath = f"//label[normalize-space(text())='{establishment_type}']"
        
                    # Wait for the element to appear in the DOM
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, label_xpath))
                    )
                    
                    # Smooth scroll to center
                    driver.execute_script("""
                        arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});
                    """, element)
                    time.sleep(1)  # let scrolling complete and DOM settle

                    # Wait until it's clickable, then click using JS to avoid interception
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, label_xpath)))
                    driver.execute_script("arguments[0].click();", element)
                    print(f"Smooth clicked establishment type: {establishment_type}")
                    time.sleep(1)

                except Exception as e:
                    print(f"Establishment not selected{e}")
                    time.sleep(5)
                    
                try:   #dairy,general manufacturing , meat and fish
                    production_ = WebDriverWait(driver,10).until(
                        EC.element_to_be_clickable((By.NAME,'manufacturerCapacity'))
                    )
                    production_.send_keys(client_info["production_capacity"])

                    try: #mt_annum selection for meat and fish
                        mt_annum = WebDriverWait(driver,15).until(
                            EC.element_to_be_clickable((By.NAME,'MtUnit'))
                        )
                        driver.execute_script("arguments[0].click();",mt_annum)
                        time.sleep(1)
                    except Exception as e:
                        pass

                except Exception as e:
                    try: #substances added to food
                        production_ = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.NAME,'manufacturerCapacity'))
                        )
                        production_.send_keys(client_info["production_capacity"])

                    except Exception as e: #vegetable oil processing
                        production_ = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,'//*[@id="content"]/div/div/div[3]/div[4]/div/div/app-oil-product-section/div[1]/div/div/div/input'))
                        )
                        production_.send_keys(client_info["production_capacity"])

                try:
                    
                    # Ensure add_products is always treated as a list
                    add_products_raw = client_info.get("add_products", [])
                    if isinstance(add_products_raw, str):
                        add_products_raw = [add_products_raw]  # Convert single string to list

                    for i in range(len(client_info["categories"])):
                        category = client_info["categories"][i].strip()
                        sub_category = client_info["sub_categories"][i].strip() if i < len(client_info["sub_categories"]) else None

                        # Safely access the i-th product or fallback to the first available product
                        add_product = add_products_raw[i].strip() if i < len(add_products_raw) else (
                            add_products_raw[0].strip() if add_products_raw else None
                        )

                        # Skip category if the category is missing (empty string)
                        if not category:
                            print(f"Skipping category {i + 1} because it is missing.")
                            continue
                        try:
                            # Step 1: Select the category
                            category_selection = WebDriverWait(driver, 20).until(
                                EC.element_to_be_clickable((By.NAME, 'foodCategory'))
                            )
                            select_category = Select(category_selection)
                            select_category.select_by_visible_text(category)
                            print(f"Category '{category}' selected.")
                            time.sleep(1)
                        except Exception as e:
                            print(f"Error in selecting category '{category}': {e}")
                            continue
                    
                        if sub_category:
                            try:
                                # Step 2: Select the sub-category
                                subcategory_selection = WebDriverWait(driver, 20).until(
                                    EC.element_to_be_clickable((By.XPATH, "(//select[@name='subFoodCategory'])[1]"))
                                )
                                subcategory_select = Select(subcategory_selection)
                                subcategory_select.select_by_visible_text(sub_category)
                                print(f"Sub-category '{sub_category}' selected.")
                                time.sleep(1)
                            except Exception as e:
                                print(f"Failed to select sub-category '{sub_category}': {e}")
                        else:
                            print("Sub-category is missing!")

                        if add_product:
                            try:
                                # Step 3: Add/Edit Product
                                add_edit_btn = WebDriverWait(driver, 15).until(
                                    EC.element_to_be_clickable((By.XPATH, "(//select[@name='subFoodCategory'])[2]"))
                                )
                                add_edit_select = Select(add_edit_btn)
                                add_edit_select.select_by_visible_text(add_product)
                                print(f"Product '{add_product}' selected.")
                            except Exception as e:
                                print(f"Failed to add product '{add_product}' for category '{category}': {e}")
                        else:
                            print(f"No valid product found for category '{category}', skipping.")

                    try:
                        # Step 4: Select the Kind of Business (KOB)
                        KOB = WebDriverWait(driver, 20).until(
                            EC.element_to_be_clickable((By.NAME, 'kindOfBusiness'))
                        )
                        KOB.send_keys(client_info["kind_of_business"])
                        print(f"Kind of Business '{client_info['kind_of_business']}' selected.")
                    except Exception as e:
                        print(f"Failed to select Kind of Business for category '{category}': {e}")


                    try:
                        substances_file = self.save_base64_file(client_info["substances_doc"], "substance_food.jpg",temp_folder, convert_to_pdf= True)
                        if substances_file:
                            
                            substance_upload = WebDriverWait(driver,20).until(
                                EC.element_to_be_clickable((By.XPATH,'//input[@type="file"]'))
                            )
                            substance_upload.send_keys(substances_file)
                            time.sleep(6)
                        else:
                            print("error substances file not present")

                    except Exception as e:
                        print(f"error in decoding files{e}")

                    try:
                        # Step 6: Save the selection, //*[@id="content"]/div/div/div[3]/div[3]/div/div/app-food-category-product-level-section/div[1]/table/tfoot/tr/td[5]/a
                        save_add_xpath = "./ancestor::tr//a[contains(text(), 'Save & Add')]"
                        
                        save_button = KOB.find_element(By.XPATH, save_add_xpath)             
                        time.sleep(5)
                        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center', inline:'center'}); arguments[0].click();", save_button)
                        
                        print("Selections saved.")

                        try:

                            #//*[@id="content"]/div/div/div[3]/div[5]/div/button[2]
                            save_and_next = WebDriverWait(driver,10).until(
                                EC.element_to_be_clickable((By.XPATH,'//button[@type="submit" and contains(@class, "w3-my-green")]'))
                            )
                            save_and_next.click()
                            print("save and next clicked")
                        except Exception as e:
                            print(f"error in save and next button{e}")
                        
                        # Cleanup the substances file after successful upload

                        try:
                            files_to_delete = [substances_file]
                            for file_path in files_to_delete:
                                if file_path and os.path.exists(file_path):
                                    os.remove(file_path)
                                    print(f"Deleted substances file: {file_path}")
                        except Exception as e:
                            print(f"Error deleting files: {e}")

                            # try:
                            #     if substances_file and os.path.exists(file_path):
                            #         os.remove(file_path)
                            #         print(f"Deleted substances file: {file_path}")
                            # except Exception as e:
                            #     print(f"Error deleting substances file: {e}")
                            
                    except Exception as e:
                        print(f"Failed to save selections for category '{category}': {e}")
                            
                except Exception as e:
                    print(f"An error occurred: {e}")

            def handle_veg_oil():
                # logic for Vegetable oil and processing units                
                pass

            handlers = {
                "General Manufacturing": handle_general_dairy,
                "Dairy units": handle_general_dairy,
                "Meat processing units": handle_general_dairy,
                "Fish and Fish Products": handle_general_dairy,
                "Substances Added to Food": handle_substances,
                "Vegetable oil and processing units": handle_veg_oil
            }

            for service_type, establishment_list in client_info['service_types'].items():
                for establishment_type in establishment_list:
                    establishment_type = establishment_type.strip()
                    original_type = establishment_type  # Keep original for handler lookup
                    
                    # Handle special case for Dairy Units
                    if establishment_type == "Dairy Units":
                        establishment_type = "Dairy units"  # UI version
                    elif establishment_type == "Transportation":
                        establishment_type = "Transportation (having a number of specialized vehicles like insulated refrigerated van/ wagon and milk tankers etc.)"
                        print(f"After conversion (Transportation): {establishment_type}")
                    
                        print(f"Converting 'Dairy Units' to '{establishment_type}'")
            
                    try:

                        handler_func = handlers.get(establishment_type) or handlers.get(original_type)
                    
                        if handler_func:
                            # Call the specific handler for this establishment type
                            print(f"Using specific handler for: {establishment_type}")
                            handler_func(driver, client_info)
                        else:
                            # If no specific handler, call the default handler immediately
                            print(f"No handler for: {establishment_type}, using default")
                            select_categories(driver, client_info)
                    except Exception as est_err:
                        print(f"Error handling establishment '{establishment_type}': {est_err}")

            try:
                #//*[@id="content"]/div/div/div[3]/div[7]/div/button[2]
                time.sleep(205)
                next_page = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(normalize-space(text()), 'Save') and contains(normalize-space(text()), 'Next') and @type='submit']"))
                )
                driver.execute_script("arguments[0].click();",next_page)
                                
                time.sleep(3) 
            except Exception as e:
                #save and next differ for veg oil 
                next_page = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/div[6]/div/button[2]'))
                )
                driver.execute_script("arguments[0].click();",next_page)
                                
                time.sleep(3)                 
                                                     
            applicant_name = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[1]/div[1]/div[2]/input'))
            )
            applicant_name.send_keys(client_info['applicantname'])            
            
            # Filling out the primary email field
            primary_email = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[2]/div[1]/div[2]/input')
            primary_email.send_keys(client_info['primaryemail'])
            
            
            # Filling out the primary mobile number field
            primary_mobile = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[2]/div[2]/div[2]/input')
            primary_mobile.send_keys(client_info['primarymobile'])
            
            # Selecting 'Self' for the first 'Belongs To' dropdown
            belongs_to_1 = Select(driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[2]/div[3]/div[2]/select'))
            belongs_to_1.select_by_visible_text('Self')
            time.sleep(5)
            
            # Filling out the secondary email field
            secondary_email = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[3]/div[1]/div[2]/input')
            secondary_email.send_keys(client_info['secondaryemail'])
            
            # Filling out the secondary mobile number field
            secondary_mobile = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[3]/div[2]/div[2]/input')
            secondary_mobile.send_keys(client_info['secondarymobile'])
            
            # Selecting 'Authorised Representative' for the second 'Belongs To' dropdown
            belongs_to_2 = Select(driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[4]/div/div[2]/select'))
            belongs_to_2.select_by_visible_text('Authorised Representative')
            time.sleep(5)
            
            # Filling out the password
            pass_ = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[6]/div[1]/div[2]/input')
            pass_.send_keys(client_info['password'])
            time.sleep(3)
            
            # Confirming the password
            confirm_pass = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[6]/div[2]/div[2]/input')
            confirm_pass.send_keys(client_info['password'])
            time.sleep(3)
            print("password entered successfully")
            
            # XPath for the Login ID element
            login_id_xpath = '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[5]/div[1]/div[2]/input'  # Replace with actual XPath if needed
            # Wait until the Login ID input field is visible
            try:
                login_id_element = WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.XPATH, login_id_xpath))
                )
                # Extract the Login ID text (value)
                login_id = login_id_element.get_attribute('value')
            
            # Print the Login ID in Jupyter output
                print(f"Login ID: {login_id}")

                with open("state_loginid.txt",'a') as file:
                    file.write(f"{login_id}\n")

                print("login_id has been appended to state_loginid.txt")
                
            except Exception as e:
                    print(f"Error retrieving Login ID: {e}")    
            

            import os
            os.environ['KMP_DUPLICATE_LIB_OK']='True'
            
            def dbccapcha(img): 
                try:
                    encoded_string = img.screenshot_as_base64  
                    time.sleep(2)
                    dataP = {
                        "username": "xxx",
                        "password": "yyy",
                        "captchafile": "base64:" + str(encoded_string)
                    }
                    url = "http:/abc/captcha"
                    response = requests.post(url, data=dataP)
            
                    parameter_dict = parse_qs(response.text)
                    print("CAPTCHA API Response:", parameter_dict)
            
                    result_text = parameter_dict.get('text', ['fail'])[0]
                    print("Extracted CAPTCHA:", result_text)
            
                    return result_text
                except Exception as e:
                    print("Error in dbccapcha:", e)
                    return None
    
    
            def enter_captcha_and_submit(driver, captcha_xpath, retry_xpath):
                max_attempts = 10
                attempt = 0
            
                while attempt < max_attempts:
                    print(f"\n Attempt {attempt + 1}: Solving CAPTCHA...")
            
                    try:
                        captcha_img = driver.find_element(By.XPATH, captcha_xpath)
                        captcha_result = dbccapcha(captcha_img)
            
                        if not captcha_result:
                            print("Failed to get CAPTCHA result. Retrying...")
                            attempt += 1
                            continue
            
                        # Enter CAPTCHA
                        captcha_input = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[9]/div[2]/input')
                        captcha_input.clear()
                        time.sleep(1)
                        captcha_input.send_keys(captcha_result)
                        time.sleep(1)
            
                        # Click submit
                        submit_button = driver.find_element(By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[10]/button')
                        time.sleep(6)
                        driver.execute_script("arguments[0].click();", submit_button)
                        time.sleep(5)
            
                        # Check for CAPTCHA error
                        try:
                            error_element = WebDriverWait(driver,10).until(
                                EC.visibility_of_element_located((By.CLASS_NAME, 'sn-content'))
                            )
                            error_text = error_element.text.strip()
                            print(error_text)
                            if "Please enter valid captcha code." in error_text:
                                print("Invalid CAPTCHA detected. Refreshing image and retrying...")
                                refresh_button = driver.find_element(By.XPATH, retry_xpath)
                                time.sleep(2)
                                refresh_button.click()
                                time.sleep(2)
                                attempt += 1
                                continue
                        except TimeoutException:
                            # No CAPTCHA error = success
                            print("CAPTCHA accepted. Submit successful.")
                            return True
            
                        # If no error, consider it a success
                        print("No error message detected after submit. Assuming success.")
                        return True
            
                    except Exception as e:
                        print(f"Exception during CAPTCHA attempt: {e}")
                        attempt += 1
                        continue
            
                print("Max CAPTCHA attempts reached. Exiting.")
                return False            
            
            # Example usage
            captcha_xpath = '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[8]/p/img'
            retry_xpath = '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/form/div[8]/p/a/img'
            
            success = enter_captcha_and_submit(driver, captcha_xpath, retry_xpath)
            
            if not success:
                print("Failed to solve CAPTCHA after multiple attempts.")            

            print("Waiting for OTP:")

            attempts = 0
            max_attempts = 10
            otp_submitted = False
            timeout_duration = 600  # 10 minutes
            start_time = time.time()
            
            while attempts < max_attempts and not otp_submitted:
                try:
                    # if self.current_session_id in self.otp_data:
                    otp_entry = self.otp_data.get(self.current_session_id, None)
                    if otp_entry and "otp_self" in otp_entry and "otp_authorized" in otp_entry:
                        print(f"Received OTP: {otp_entry}")
                        
                        otp_self_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/div[1]/div/div/div[1]/input'))
                        )
                        otp_self_input.clear()
                        otp_self_input.send_keys(otp_entry["otp_self"])
                        time.sleep(5)
                    
                        # Wait for the OTP field for 'authorised representative' to be visible
                        otp_authorised_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/div[1]/div/div/div[2]/input'))
                        )
                        otp_authorised_input.clear()
                        otp_authorised_input.send_keys(otp_entry["otp_authorized"])
                        time.sleep(5)
                        
                        # Wait for the submit button to be clickable
                        submit_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/div[1]/div/footer/p/input[1]'))
                        )
                        submit_button.click()
                        print("OTP submitted successfully")

                        print(f"Attempt left: {max_attempts - attempts}")

                        try:
                            OK_Button =  WebDriverWait(driver,10).until(
                                EC.element_to_be_clickable((By.XPATH , '//*[@id="Body"]/app-root/app-open-application-details-filing/div[6]/div/div/app-open-sign-up/div[2]/div/footer/p/input'))
                            )
                            OK_Button.click()
                            otp_submitted = True 
                            print(f"OTP submitted succesfully! for session {self.current_session_id}")
                            self.otp_submission_status[self.current_session_id]= "VALID"  # Mark as successful
                            
                            time.sleep(2)   

                            same_address = WebDriverWait(driver,20).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[3]/div/span/input[1]'))
                            )
                            time.sleep(2)
                            same_address.click()
                            print("address clicked successfully")
                            break #exit loop were processed successfully
                                                    
                        except Exception as e:
                            print(f"An error occurred while handling the OK pop-up: {e}")
                            #Ensure the same incorrect OTP is not fetched again
                            if self.otp_submission_status[self.current_session_id] != "VALID":
                                self.otp_submission_status[self.current_session_id] = "INVALID" 
                                self.otp_data[self.current_session_id] = {} 
                                attempts += 1 #Clear the incorrect OTP
                                continue
                    else:

                        # Check if the timeout has expired
                        if time.time() - start_time > timeout_duration:
                            print("Timeout expired while waiting for OTP")
                            self.otp_submission_status[self.current_session_id] = "INVALID"
                            break  # Exit if timeout is reached

                        # Sleep for a while before checking again
                        time.sleep(5)  # Check every 5 seconds
                
                except Exception as e:
                    print(f"An error occurred: {e}")
                    if otp_entry:
                        self.otp_submission_status[self.current_session_id] = "INVALID"
                    break  # Exit loop if an error occurs
                

            if attempts >= max_attempts:
                print("Maximum OTP attempts reached")
                if otp_entry:
                    self.otp_submission_status[self.current_session_id] = "INVALID"          

            name =  WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[8]/div[1]/div[2]/input'))
            )
            name.send_keys(client_info["Incharge_operation"])
            
            ##content > div > div > div.w3-container.ng-star-inserted > form > div:nth-child(11) > div:nth-child(2) > div:nth-child(2) > input
            qualification_ = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#content > div > div > div.w3-container.ng-star-inserted > form > div:nth-child(11) > div:nth-child(2) > div:nth-child(2) > input'))
            )
            qualification_.send_keys(client_info["qualification"])
            
            Mobile_no = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[9]/div[2]/div[2]/input'))
            )
            Mobile_no.send_keys(client_info["mobile_no"])
            
            email_id = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[10]/div[1]/div[2]/input'))
            )
            email_id.send_keys(client_info["email"])
            
            address_ = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[10]/div[2]/div[2]/input'))
            )
            address_.send_keys(client_info["address"])
            
            select_state = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[11]/div[1]/div[2]/select'))
            )
            option_select = Select(select_state)
            option_select.select_by_visible_text(client_info["state"])
            time.sleep(2)
            
            district_ = WebDriverWait(driver,20).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[11]/div[2]/div[2]/select'))
            )
            district_select = Select(district_)
            district_select.select_by_visible_text(client_info["district"])
            time.sleep(5)
            
            pincode_ = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH,'//*[@id="content"]/div/div/div[3]/form/div[12]/div[1]/div[2]/input'))
            )
            pincode_.send_keys(client_info["pincode"])
            
            Photo_id = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[12]/div[2]/div[2]/select'))
            )
            id_select = Select(Photo_id)
            id_select.select_by_visible_text('Aadhar Card')
            
            id_no = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[13]/div[2]/div[2]/input'))
            )
            id_no.send_keys(client_info["id_number"])
            
            #Incharge  of operation is same as responsible for license

            # Check whether to select "Yes" or "No" for correspondence address
            if client_info.get('address_correspondence') == "none" or not client_info.get('address_correspondence'):
                # Correspondence address is "none" or empty, select the "Yes" radio button to fill the same address
                
                correspondence_yes_radio_button = WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[16]/p/input[1]'))
                )
                driver.execute_script("arguments[0].click();", correspondence_yes_radio_button)
                print("Selected 'Yes' for correspondence address, using the same address as above.")
            
            else:
                #person responsible for license differ from technical incharge
                print("Selected 'No' for correspondence address, entering details.")
                name_license = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[17]/div[1]/div[2]/input'))
                )
                name_license.send_keys(client_info[''])

                qualification_lic = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR,'#content > div > div > div.w3-container.ng-star-inserted > form > div:nth-child(20) > div:nth-child(2) > div:nth-child(2) > input'))
                )
                qualification_lic.send_keys(client_info[''])

                mobile_no_lic = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[18]/div[2]/div[2]/input'))
                )
                mobile_no_lic.send_keys(client_info[''])

                email_lic = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[19]/div[1]/div[2]/input'))
                )
                email_lic.send_keys(client_info[''])

                address_lic = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[19]/div[2]/div[2]/input'))
                )
                address_lic.send_keys(client_info[''])

                state_lic = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[20]/div[1]/div[2]/select'))
                )
                select_statelic = Select(state_lic)
                select_statelic.select_by_visible_text(client_info[''])

                district_lic = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[20]/div[2]/div[2]/select'))
                )
                select_districtlic = Select(district_lic)
                select_districtlic.select_by_visible_text(client_info[''])

                pincode_lic = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[21]/div[1]/div[2]/input'))
                )
                pincode_lic.send_keys(client_info[''])

                photolic_choose = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[21]/div[2]/div[2]/select'))
                )
                select_id = Select(photolic_choose)
                select_id.select_by_visible_text(client_info[''])

                photo_id_no = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH,'//[@id="content"]/div/div/div[3]/form/div[22]/div/div[2]/input'))
                )
                photo_id_no.send_keys(client_info[''])
                
            
            select_years = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[26]/div[1]/div/div[2]/select'))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);",select_years)
            year_select = Select(select_years)
            year_select.select_by_visible_text(str(client_info["no_of_years"]))
            
            
            try:
                save_next = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/form/div[27]/div/button[2]'))
                )
                
                driver.execute_script("arguments[0].click();",save_next)
                print(" clicked ")
            
            except Exception as e:
                print("error")

            # verification_code =  input("Enter Mobile verification Code: " )

            attempts = 0
            max_attempts = 10
            otp_submitted = False
            timeout_duration = 600 #10 minutes
            start_time = time.time()

            while attempts < max_attempts and not otp_submitted:

                try:
                    # if self.current_session_id in self.otp_data:
                    otp_entry = self.otp_data.get(self.current_session_id, None)
                    if otp_entry and "verification_code" in otp_entry:
                        print(f"Received OTP: {otp_entry}")

                        #otp for client mobile only
                        otp_code = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[13]/div/div/div/input'))
                        )
                        otp_code.clear()
                        otp_code.send_keys(otp_entry["verification_code"])
                    
                        submit_OTP = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[13]/div/footer/p/input[1]'))
                        )
                        time.sleep(2)
                        submit_OTP.click()
                        print(f"Attempt left: {max_attempts - attempts}")
                        time.sleep(5)

                        try:
                            # path = '//*[@id="Body"]/app-root/app-open-register/div[1]/div/div/app-open-registration-sign-up/div[2]/div/footer/p/input'
                            # Okay_button = driver.find_element(By.XPATH, path)
                            # Okay_button.click()
                            # print("proceeded to document upload")
                            path = '//*[@id="content"]/div/div/div[3]/table/tbody/tr[1]/td[2]'
                            selection_made = WebDriverWait(driver, 20).until(
                                EC.presence_of_element_located((By.XPATH, path))
                            )
                            driver.execute_script("arguments[0].scrollIntoView(0);",selection_made)
                            selection_made.click()
                            otp_submitted = True 
                            print(f"OTP submitted succesfully! for session {self.current_session_id}")
                            self.otp_submission_status[self.current_session_id]= "VALID"  # Mark as successful
                            # self.otp_submission_status[f"{self.current_session_id}_login_id"] = login_id
                            break #exit loop were processed successfully
                            
                        except Exception as e:
                            print(f"An error occurred while handling the OK pop-up: {e}")
                            #Ensure the same incorrect OTP is not fetched again
                            if self.otp_submission_status[self.current_session_id] != "VALID":
                                self.otp_submission_status[self.current_session_id] = "INVALID" 
                                self.otp_data[self.current_session_id] = {}
                                attempts += 1 #Clear the incorrect OTP
                                continue
                    else:

                        # Check if the timeout has expired
                        if time.time() - start_time > timeout_duration:
                            print("Timeout expired while waiting for OTP")
                            self.otp_submission_status[self.current_session_id] = "INVALID"
                            break  # Exit if timeout is reached

                        # Sleep for a while before checking again
                        time.sleep(5)  # Check every 5 seconds
                
                except Exception as e:
                    print(f"An error occurred: {e}")
                    if otp_entry:
                        self.otp_submission_status[self.current_session_id] = "INVALID"
                    break  # Exit loop if an error occurs                

            if attempts >= max_attempts:
                print("Maximum OTP attempts reached")
                if otp_entry:
                    self.otp_submission_status[self.current_session_id] = "INVALID"
                        
            time.sleep(2)
            
            try:
                # list_of_director, analysis_report(not compulsory), photo_id, proof_of_premises, partnership_deed, form_ix(not_compulsory)
                blue_print_file = self.save_base64_file(client_info["blueprint_layout_plan"], "blueprint.jpg",temp_folder, convert_to_pdf= True)
                list_of_director_file = self.save_base64_file(client_info["list_of_director"], "list_of_director.jpg",temp_folder, convert_to_pdf=True)
                list_equipment = self.save_base64_file(client_info["list_of_equip"], "list_of_equipment.jpg", temp_folder,convert_to_pdf=True)
                analysis_report_file = self.save_base64_file(client_info["analysis_report"], "analysis_report.jpg", temp_folder, convert_to_pdf=True)
                photo_id_file = self.save_base64_file(client_info["photo_id"], "photo_id.jpg", temp_folder, convert_to_pdf= True)
                address_proof_file = self.save_base64_file(client_info["address_proof"], "address_proof.jpg", temp_folder,convert_to_pdf= True)
                partnership_deed_file = self.save_base64_file(client_info["partnership_deed"], "partnership_deed.jpg", temp_folder,convert_to_pdf=True)
                form_ix_file = self.save_base64_file(client_info["formix"], "formix_file.jpg", temp_folder,convert_to_pdf=True)
                recall_file = self.save_base64_file(client_info["recall_plan"], "recall.jpg", temp_folder, convert_to_pdf=True)
                unit_photograph = self.save_base64_file(client_info["production_unit_photograph"],"unit.jpg",temp_folder,convert_to_pdf=True)
                source_material = self.save_base64_file(client_info["source_plan"],"source_plan.jpg",temp_folder,convert_to_pdf=True) 
                noc_file = self.save_base64_file(client_info["NOC_municipal"], "non_municipal.jpg", temp_folder, convert_to_pdf= True)
                list_of_veh_file = self.save_base64_file(client_info["list_of_veh"], "list_of_vehicles.jpg", temp_folder, convert_to_pdf= True) 
                direct_selling_agreement_file = self.save_base64_file(client_info["direct_selling_agreement"], "direct_selling_agreement.jpg", temp_folder, convert_to_pdf= True)
                any_other_file = self.save_base64_file(client_info["any_other_doc"], "any_other_doc.jpg", temp_folder,convert_to_pdf=True)
                any_other_file2 = self.save_base64_file(client_info["any_other_doc2"], "any_other_doc2.jpg", temp_folder, convert_to_pdf= True)                

                if not any([blue_print_file,list_of_director_file,list_equipment, analysis_report_file, photo_id_file, address_proof_file, partnership_deed_file,form_ix_file,recall_file,unit_photograph,source_material,noc_file,list_of_veh_file,direct_selling_agreement_file, any_other_file,any_other_file2]):
                    print("failed to decode one or more files missing")

                try:


                    if blue_print_file:
                        blue_print_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Blueprint/layout plan')]]//input[@type='file']"))
                        )
                        blue_print_choose.send_keys(blue_print_file)

                        blueprint_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Blueprint/layout plan')]]//button[contains(text(), 'Upload')]"))
                        )
                        blueprint_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading blueprint: {e}")

                try:

                    if list_of_director_file: 
                        LOD_choose = WebDriverWait(driver,20).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'List of Directors/Partners/Proprietor/ExecutiveMembers')]]//input[@type='file']"))
                        )
                        LOD_choose.send_keys(list_of_director_file)

                        LOD_upload = WebDriverWait(driver,20).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'List of Directors/Partners/Proprietor/ExecutiveMembers')]]//button[contains(text(), 'Upload')]"))
                        )
                        LOD_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading list of directors: {e}")

                try:
                
                    if list_equipment:

                        list_of_equipments = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Name and List of Equipments and Machinery')]]//input[@type='file']"))
                        )
                        list_of_equipments.send_keys(list_equipment)

                        equip_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Name and List of Equipments and Machinery')]]//button[contains(text(), 'Upload')]"))
                        )
                        equip_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading list of equipment: {e}")
                
                try:

                    if analysis_report_file:
                        report_choose = WebDriverWait(driver,15).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.),'Analysis report(Chemical & Bacteriological)of water')]]//input[@type='file']"))
                        )
                        report_choose.send_keys(analysis_report_file)
                    
                        report_upload = WebDriverWait(driver,20).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Analysis report(Chemical & Bacteriological)of water')]]//button[contains(text(), 'Upload')]"))
                        )
                        report_upload.click()
                        time.sleep(5)                    

                    else:
                        try:
                            not_applicable = WebDriverWait(driver,10).until(
                                EC.element_to_be_clickable((By.XPATH, "//table[@id='data-table-simple']//input[@type='radio' and @value='N']"))
                            )
                            not_applicable.click()
                            print("Not applicable clicked")
                        except Exception as e:
                            print(f"Error in clicking")

                except Exception as e:
                    print(f"Error in uploading analysis report: {e}")

                try:

                    if photo_id_file:
                        photo_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.), 'Photo I.D and address proof issued by Government authority')]]//input[@type='file']"))
                        )
                        photo_choose.send_keys(photo_id_file)

                        photo_upload = WebDriverWait(driver,20).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.), 'Photo I.D and address proof issued by Government authority')]]//button[contains(text(), 'Upload')]"))
                        )
                        photo_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading photo ID: {e}")

                try:

                    if address_proof_file:
                        address_choose = WebDriverWait(driver,20).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.), 'Proof of possession of premises.')]]//input[@type='file']"))
                        )
                        address_choose.send_keys(address_proof_file)

                        address_upload = WebDriverWait(driver,20).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.), 'Proof of possession of premises.')]]//button[contains(text(), 'Upload')]"))
                        )
                        address_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading address proof: {e}")

                try:

                    if partnership_deed_file:
                        partnership_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.),'Partnership Deed/Self Declaration for Proprietorship/Memorandum')]]//input[@type='file']"))
                        )
                        partnership_choose.send_keys(partnership_deed_file)
                    
                        partnership_upload = WebDriverWait(driver,20).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.),'Partnership Deed/Self Declaration for Proprietorship/Memorandum')]]//button[contains(text(), 'Upload')]"))
                        )
                        partnership_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading partnership deed: {e}")
                
                try:
                
                    if form_ix_file:
                        form_ix_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.),'Form IX: Nomination of Person as per Clause 2.5of FSS Rules,')]]//input[@type='file']"))
                        )
                        form_ix_choose.send_keys(form_ix_file)

                        form_ix_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH, "//tr[td[contains(normalize-space(.),'Form IX: Nomination of Person as per Clause 2.5of FSS Rules,')]]//button[contains(text(), 'Upload')]"))
                        )
                        form_ix_upload.click()
                        time.sleep(5)

                    else:
                        try:
                            not_applicable2 = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH,
                                    "//tr[td[contains(normalize-space(.),'Form IX: Nomination of Person as per Clause 2.5of FSS Rules,')]]//input[@type='radio' and @value='N']"
                                ))
                            )
                            not_applicable2.click()
                            print("Not applicable for Form IX clicked")
                        except Exception as e:
                            print(f"Error clicking Form IX Not Applicable: {e}")
                
                except Exception as e:
                    print(f"Error in uploading Form IX: {e}")

                try:

                    if recall_file:
                        recall_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., ' Recall Plan ')]]//input[@type='file']"))
                        )
                        recall_choose.send_keys(recall_file)

                        recall_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., ' Recall Plan ')]]//button[contains(text(), 'Upload')]"))
                        )
                        recall_upload.click()
                        time.sleep(5)

                except Exception as e:
                    print(f"Error in uploading recall plan: {e}")
                
                try:

                    if unit_photograph:
                        unit_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Production unit photographs')]]//input[@type='file']"))
                        )
                        unit_choose.send_keys(unit_photograph)

                        unit_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Production unit photographs')]]//button[contains(text(), 'Upload')]"))
                        )
                        unit_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading unit photograph: {e}")

                try:
                    #only for dairy units and meat process
                    if source_material:

                        sourcedoc_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., 'Source of raw material ')]]//input[@type='file']"))
                        )
                        sourcedoc_choose.send_keys(source_material)

                        sourcedoc_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., 'Source of raw material ')]]//button[contains(text(), 'Upload')]"))
                        )
                        sourcedoc_upload.click()
                        time.sleep(5)
                        
                except Exception as e:
                    print(f"error in source upload : {e}")  

                try:
                
                    if source_material:

                        sourcedoc_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., 'Source or procurement plan for milk ')]]//input[@type='file']"))
                        )
                        sourcedoc_choose.send_keys(source_material)

                        sourcedoc_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., 'Source or procurement plan for milk ')]]//button[contains(text(), 'Upload')]"))
                        )
                        sourcedoc_upload.click()
                        time.sleep(5)

                except Exception as e:
                    print(f"error in source upload : {e}")              

                try :
                    #only for meat
                    if noc_file:
                        
                        noc_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'NoC from Municipal Corporation')]]//input[@type='file']"))
                        )
                        noc_choose.send_keys(noc_file)

                        noc_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'NoC from Municipal Corporation')]]//button[contains(text(), 'Upload')]"))
                        )
                        noc_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Element not appeared{e}")
                
                try:
                    #only for transportation
                    if list_of_veh_file:
                        list_of_veh_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., 'List of Vehicle Registration numbers ')]]//input[@type='file']"))
                        )
                        list_of_veh_choose.send_keys(list_of_veh_file)

                        list_of_veh_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td//text()[contains(., 'List of Vehicle Registration numbers ')]]//button[contains(text(), 'Upload')]"))
                        )
                        list_of_veh_upload.click()
                        time.sleep(5)

                except Exception as e:
                    print(f"Element not appeared{e}")

                try:
                    if direct_selling_agreement_file:
                        direct_selling_choose = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Copy of agreement with the Direct Selling Entity')]]//input[@type='file']"))
                        )
                        direct_selling_choose.send_keys(direct_selling_agreement_file)

                        direct_selling_upload = WebDriverWait(driver,10).until(
                            EC.element_to_be_clickable((By.XPATH,"//tr[td[contains(normalize-space(.),'Copy of agreement with the Direct Selling Entity')]]//button[contains(text(), 'Upload')]"))
                        )
                        direct_selling_upload.click()
                        time.sleep(5)
                except Exception as e:
                    print(f"Error in uploading direct selling agreement: {e}")

                # Upload address proof if present
                if any_other_file:
                
                    any_other_doc = WebDriverWait(driver , 20).until(
                        EC.element_to_be_clickable((By.XPATH,'//*[@id="data-table-simple"]/tfoot/tr/td[2]/select'))
                    )
                    driver.execute_script("arguments[0].click();",any_other_doc)
                    time.sleep(2)
                    
                    #//*[@id="data-table-simple"]/tfoot/tr/td[2]/select/option[2] , //option[contains(text(), 'Any Other Document')]
                    any_option = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="data-table-simple"]/tfoot/tr/td[2]/select/option[2]'))
                    )
                    any_option.click()
                    time.sleep(1)

                    doc_description = WebDriverWait(driver,10).until(
                        EC.element_to_be_clickable((By.XPATH,'//*[@id="data-table-simple"]/tfoot/tr/td[2]/input'))
                    )
                    doc_description.send_keys("FSMS plan")

                    choose_file = driver.find_element(By.XPATH, '//*[@id="data-table-simple"]/tfoot/tr/td[3]/input')
                    # driver.execute_script("arguments[0].click();", address_choose)
                    choose_file.send_keys(any_other_file)
                    # address_choose.click()
                    
                    upload_file = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="data-table-simple"]/tfoot/tr/td[3]/button'))
                    )
                    upload_file.click()
                    print("other doc 1 uploaded")
                    
                    time.sleep(10)

                if any_other_file2:

                    any_other_doc = WebDriverWait(driver , 20).until(
                        EC.element_to_be_clickable((By.XPATH,'//*[@id="data-table-simple"]/tfoot/tr/td[2]/select'))
                    )
                    driver.execute_script("arguments[0].click();",any_other_doc)
                    time.sleep(2)
                    
                    #//*[@id="data-table-simple"]/tfoot/tr/td[2]/select/option[2] , //option[contains(text(), 'Any Other Document')]
                    any_option = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="data-table-simple"]/tfoot/tr/td[2]/select/option[2]'))
                    )
                    any_option.click()
                    time.sleep(1)

                    doc_description = WebDriverWait(driver,10).until(
                        EC.element_to_be_clickable((By.XPATH,'//*[@id="data-table-simple"]/tfoot/tr/td[2]/input'))
                    )
                    doc_description.send_keys("GST")

                    choose_file = driver.find_element(By.XPATH, '//*[@id="data-table-simple"]/tfoot/tr/td[3]/input')
                    # driver.execute_script("arguments[0].click();", address_choose)
                    choose_file.send_keys(any_other_file2)
                    # address_choose.click()
                    
                    upload_file = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="data-table-simple"]/tfoot/tr/td[3]/button'))
                    )
                    upload_file.click()
                    print("other doc 2 uploaded")
                    time.sleep(10)
                 
            except Exception as e:
                self.otp_submission_status[f"{self.current_session_id}_login_id"] = login_id
                print(f"error in document uploading:{e}") 
            
            finally:
                
                # Cleanup only the specific files created using random file names
                try:
                    # List all files in the temp folder and remove the ones created
                    files_to_delete = [
                        blue_print_file,
                        list_of_director_file,
                        list_equipment,
                        analysis_report_file,
                        photo_id_file,
                        address_proof_file,
                        partnership_deed_file,
                        form_ix_file,
                        recall_file,
                        unit_photograph,
                        source_material,
                        noc_file,
                        list_of_veh_file,
                        direct_selling_agreement_file,
                        any_other_file,
                        any_other_file2
                    ]
                    for file_path in files_to_delete:
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"Deleted file: {file_path}")
                except Exception as e:
                    print(f"Error deleting files: {e}")   
            
            declare_checkbox = driver.find_element(By.XPATH,'//*[@id="content"]/div/div/div[3]/div[4]/p[1]/input')
            declare_checkbox.click()
            time.sleep(200)
            
            save_move = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/div[3]/div[5]/button[2]'))
            )
            save_move.click()
            time.sleep(2)

            e_sign_proceed = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[8]/div/form/footer/button[1]'))
            )
            time.sleep(10)
            e_sign_proceed.click()
            time.sleep(2)
            #client registered mobile otp
            # registered_mobileno_otp = input("Enter OTP:")
            attempts = 0
            max_attempts = 10
            otp_submitted = False
            timeout_duration = 600  # 10 minutes
            start_time = time.time()

            while attempts < max_attempts and not otp_submitted:
                try:
                    otp_entry = self.otp_data.get(self.current_session_id, None)
                    if otp_entry and "registered_mobileno_otp" in otp_entry:
                        print(f"Received OTP: {otp_entry}")

                        mobile_otp = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[9]/div/div/div/div/table/tbody/tr/td/input'))
                        )
                        mobile_otp.clear()
                        mobile_otp.send_keys(otp_entry["registered_mobileno_otp"])

                        proceed_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="Body"]/app-root/app-open-application-details-filing/div[9]/div/footer/button[1]'))
                        )
                        time.sleep(2)
                        proceed_button.click()
                        print("OTP entered successfully")
                        time.sleep(10)
                        # Check for error message (Invalid OTP case) 
                        try:
                            WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="Body"]/app-root/simple-notifications/div/simple-notification/div/div[1]/div[2]'))
                            )
                            print("Invalid OTP detected!")
                            self.otp_submission_status[self.current_session_id] = "INVALID"
                            self.otp_data[self.current_session_id] = {}  # Clear incorrect OTP
                            attempts += 1
                            continue  # Retry with the next attempt
                        except:
                            # If no error message is found, OTP is considered valid
                            print(f"OTP submitted successfully! for session {self.current_session_id}")
                            self.otp_submission_status[self.current_session_id] = "VALID"
                            self.otp_submission_status[f"{self.current_session_id}_login_id"] = login_id
                            otp_submitted = True
                            break  # Exit the loop as OTP is valid

                    # Check if timeout has expired
                    if time.time() - start_time > timeout_duration:
                        print("Timeout expired while waiting for OTP")
                        self.otp_submission_status[self.current_session_id] = "INVALID"
                        break  # Exit loop if timeout is reached

                    # Sleep before next attempt
                    time.sleep(5)  # Wait for 5 seconds before retrying

                except Exception as e:
                    print(f"An error occurred: {e}")
                    self.otp_submission_status[self.current_session_id] = "INVALID"
                    break  # Exit loop on unexpected error

            if attempts >= max_attempts:
                print("Maximum OTP attempts reached")
                self.otp_submission_status[self.current_session_id] = "INVALID"

            preview_application = WebDriverWait(driver,10).until(
                EC.element_to_be_clickable((By.XPATH,'//*[@id="content"]/div/div/div[3]/app-open-payment/form/div[5]/button[1]'))
            )
            preview_application.click()
            time.sleep(5)
            # Wait for the new window to open

            try:
                original_window = driver.current_window_handle

                for window_handle in driver.window_handles:
                    if window_handle != original_window:
                        driver.switch_to.window(window_handle)
                        break
                #class ---> w3-btn w3-center download-btn w3-round w3-ripple
                path = '//*[@id="Body"]/app-root/app-view-pdf/div/div[1]/div/button'
                doc_download = WebDriverWait(driver,10).until(
                    EC.element_to_be_clickable((By.XPATH, path))
                )
                time.sleep(2)
                driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center', inline:'center'}); arguments[0].click();", doc_download)
                time.sleep(8)
                print(f"Document successfully downloaded to: {download_dir}")
                # #wait until the file appears in the folder
                # timeout = 30
                # downloaded = False
                # for _ in range(timeout):
                #     files = os.listdir(download_dir)
                #     if any(file.endswith(".pdf")and not file.endswith(".crdownload") for file in files):
                #         downloaded = True
                #         break
                #     time.sleep(1)
                
                # if downloaded:
                #     print(f"Document successfully downloaded to: {download_dir}")
                # else:
                #     print("Document download failed or timed out.")
            except Exception as e:
                print(f"error in download{e}")

            print(f"login id : {login_id}")
                    
        except Exception as e:
            self.otp_submission_status[f"{self.current_session_id}_login_id"] = login_id
            requests.post("http://127.0.0.1:5000/delete_session_state", json={"session_id": self.current_session_id})
            print(f"An error occurred during automation: {str(e)}")

        finally:
            self.otp_submission_status[f"{self.current_session_id}_login_id"] = login_id
            requests.post("http://127.0.0.1:5000/delete_session_state", json={"session_id": self.current_session_id})
            # input("Enter to close the browser:")
