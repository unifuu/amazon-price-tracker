import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import base64
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests import HTTPError
import time

# TODO:
# - https://stackoverflow.com/questions/51487195/how-can-i-use-python-google-api-without-getting-a-fresh-auth-code-via-browser-ea

# Gmail
SCOPES = [
        "https://www.googleapis.com/auth/gmail.send"
    ]
flow = InstalledAppFlow.from_client_secrets_file('cred/gmail-api.json', SCOPES)
creds = flow.run_local_server(port=0)

service = build('gmail', 'v1', credentials=creds)

to_email_addr = ""
msg_to_send = ""

with open('cred/to_email_addr.txt', 'r') as file:
    to_email_addr = file.read()

# Initialize Firebase Admin SDK with service account key
cred = credentials.Certificate("cred/firebase-admin.json")
firebase_admin.initialize_app(cred)

# Target URL
prefix_url = "https://www.amazon.co.jp/gp/product/"
suffix_url = "/ref=ewc_pr_img_2?smid=AN1VRQENFRJN5&psc=1"

# Initialize Firestore client
db = firestore.client()

# Get target URL
def get_target_url(asin):
    return prefix_url + asin + suffix_url

# Retrieve data from a Firestore collection
def get_product_price():
    while True:
        # Reference to your Firestore collection
        collection_ref = db.collection('gunpla')

        # Query the collection
        docs = collection_ref.stream()

        msg_to_send = ""

        for doc in docs:
            data = doc.to_dict()
            asin = data['asin']
            name = data['name']
            target_price = data['price']

            url = get_target_url(asin)
            amz_cur_price = convert_price(get_amazon_product_price(url))
            print(f"{name} ￥{amz_cur_price}")
            
            if check_price(target_price, amz_cur_price):
                msg_to_send += f"{name} ￥{amz_cur_price}\n"
        
            if msg_to_send != "":
                try: 
                    message = MIMEText(msg_to_send)
                    message['to'] = to_email_addr
                    message['subject'] = 'Gunpla'
                    create_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}
                    
                    message = (service.users().messages().send(userId="me", body=create_message).execute())
                except HTTPError as error:
                    print(F'An error occurred: {error}')
                    message = None

        time.sleep(60 * 5)

def check_price(target_price, amz_cur_price):
    if target_price >= amz_cur_price:
        return True
    else:
        return False

def convert_price(crawled_price):
    cleaned_string = crawled_price.replace('￥', '').replace(',', '')
    try:
        return int(cleaned_string)
    except ValueError:
        print("Invalid input format")
        return 9999999

def get_amazon_product_price(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        center_price = soup.find('span', class_='a-price aok-align-center')
        if center_price:
            price_element = center_price.find('span', class_='a-offscreen')
        else:
            return "9999999"

        if price_element:
            return price_element.text.strip()
        else:
            return "Price not found"
    else:
        return "Failed to retrieve page"
    
# Get data from firebase
get_product_price()