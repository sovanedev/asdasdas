import asyncio
import base64
import enum
import itertools
import json
from pprint import pprint
import sys
import aiohttp

from playerok.playerok_query import *
from functools import wraps
from typing import Callable, List
import asyncio
import json

from config import scraper_ninja

from colorful_logging import *
from datetime import datetime
        
import json
from typing import Any, Tuple, Optional

async def loading_animation(task: str):
    for frame in itertools.cycle(['-', '\\', '|', '/']):
        sys.stdout.write(f'\r{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | \033[93m[$] {task} {frame}\033[0m')
        sys.stdout.flush()
        await asyncio.sleep(0.1)

class Deal:
    def __init__(self, data: dict):
        deal = data.get('data', {}).get('deal')
        if not deal or not deal.get('id'):
            raise Exception("Invalid Deal JSON")
        
        self.id = deal.get('id')
        self.status = deal.get('status')
        self.chat_id = deal.get('chat', {}).get('id')
        
        item = deal.get('item', {})
        self.item_name = item.get('name')
        self.item_price = item.get('price')
        self.item_game_name = item.get('game', {}).get('name')

        self.game = item.get('game')
        
        self.completed_at = deal.get('completedAt')
        self.completed_by = deal.get('completedBy')
        self.logs = deal.get('logs')
        self.obtaining_fields = deal.get('obtainingFields')
        
        self.raw = data

class Profile:
    def __init__(self, json: json):
        viewer = json.get('data', {}).get('viewer', {})
        self.id = viewer.get('id', 0)
        self.username = viewer.get('username', "")
        self.email = viewer.get('email', "")
        self.role = viewer.get('role', "")
        self.has_frozen_balance = viewer.get('hasFrozenBalance', False)
        self.support_chat_id = viewer.get('supportChatId', 0)
        self.system_chat_id = viewer.get('systemChatId', 0)
        self.unread_chats_counter = viewer.get('unreadChatsCounter',0)
        self.is_blocked = viewer.get('isBlocked', False)
        self.is_blocked_for = viewer.get('isBlockedFor', False)
        self.created_at = viewer.get('createdAt', "")
        self.last_item_created_at = viewer.get('lastItemCreatedAt', "")
        self.profile = viewer.get('profile', {})
        self.raw = json

class Product:
    def __init__(self, node_json: json):
        self.id = node_json['id']
        self.slug = node_json['slug']
        self.name = node_json['name']
        self.description = node_json.get('description')
        self.raw_price = node_json['rawPrice']
        self.price = node_json['price']
        self.status = node_json['status']
        self.priority_position = node_json.get('priorityPosition')
        self.seller_type = node_json.get('sellerType')
        self.fee_multiplier = node_json.get('feeMultiplier')
        self.user = node_json.get('user')
        self.attachments = node_json.get('attachments')
        self.category = node_json.get('category')
        self.game = node_json.get('game', {}).get('name', None)
        self.priority = node_json.get('priority')
        self.sequence = node_json.get('sequence')
        self.priority_price = node_json.get('priorityPrice')
        self.status_expiration_date = node_json.get('statusExpirationDate')
        self.views_counter = node_json.get('viewsCounter')
        self.approval_date = node_json.get('approvalDate')
        self.created_at = node_json.get('createdAt')
        self.updated_at = node_json.get('updatedAt')
        self.raw = node_json
        pass

class EVENT_TYPE(enum.Enum):
    NEW_MESSAGE = "new_message"
    ITEM_PAID = "item_paid"
    CONNECTION_ACK = "connection_ack"
    NEXT = "next"
    USER_UPDATED = "userUpdated"
    CHAT_UPDATED = "chatUpdated"
    LAST_MESSAGE = "lastMessage"
    CHAT_MARKED_AS_READ = "chatMarkedAsRead"
    SKIP = "skip"

_orders_cache = set()

def load_orders() -> set:
    global _orders_cache
    if not _orders_cache:
        try:
            with open("orders.json", "r") as f:
                orders_list = json.load(f)
                _orders_cache = set(orders_list)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            _orders_cache = set()
            LOG_ERROR(f"Failed to load orders.json: {e}")
    return _orders_cache

def save_orders() -> None:
    global _orders_cache
    with open("orders.json", "w") as f:
        json.dump(list(_orders_cache), f)

async def getEvent(message_json: dict) -> Tuple[EVENT_TYPE, Optional[Any]]:
    global _orders_cache
    
    try:
        msg_type = message_json.get('type')
        if msg_type == 'connection_ack':
            return EVENT_TYPE.CONNECTION_ACK, None

        if msg_type == 'next' and 'payload' in message_json:
            payload = message_json['payload']
            data_payload = payload.get('data', {})

            if 'chatMarkedAsRead' in data_payload:
                load_orders()
                chat_data = data_payload.get('chatMarkedAsRead', {})
                last_message = chat_data.get('lastMessage', {})

                if last_message.get('text') == "{{ITEM_PAID}}" and last_message.get('user') is None:
                    deal = last_message.get('deal')
                    if not deal:
                        LOG_WARNING("Deal not found in last message (chatMarkedAsRead)")
                        return EVENT_TYPE.SKIP, None

                    deal_id = deal.get('id')
                    if not deal_id:
                        LOG_WARNING("Deal ID not found in last message (chatMarkedAsRead)")
                        return EVENT_TYPE.SKIP, None

                    if deal_id not in _orders_cache:
                        _orders_cache.add(deal_id)
                        save_orders()
                        return EVENT_TYPE.ITEM_PAID, chat_data
                    else:
                        return EVENT_TYPE.CHAT_MARKED_AS_READ, None

                return EVENT_TYPE.CHAT_MARKED_AS_READ, None

            if 'userUpdated' in data_payload:
                return EVENT_TYPE.USER_UPDATED, None


            if 'chatUpdated' in data_payload:
                chat_updated = data_payload['chatUpdated']
                last_message = chat_updated.get('lastMessage', {})

                if 'text' in last_message:
                    if last_message['text'] == "{{ITEM_PAID}}" and last_message.get('user', None) is None:
                        deal = last_message.get('deal')
                        if not deal:
                            LOG_WARNING("Deal not found in last message (chatUpdated)")
                            return EVENT_TYPE.SKIP, None

                        deal_id = deal.get('id')
                        if not deal_id:
                            LOG_WARNING("Deal ID not found in last message (chatUpdated)")
                            return EVENT_TYPE.SKIP, None

                        if deal_id not in _orders_cache:
                            _orders_cache.add(deal_id)
                            save_orders()
                            return EVENT_TYPE.ITEM_PAID, chat_updated
                        else:
                            return EVENT_TYPE.CHAT_UPDATED, None
                    
                    return EVENT_TYPE.NEW_MESSAGE, chat_updated

            return EVENT_TYPE.SKIP, None
    except Exception as e:
        LOG_ERROR(f"Exception in getEvent: {e}")

    return EVENT_TYPE.SKIP, None

async def ScrapeNinja(url: str, payload, token: str, method="POST", custom_header=None, max_retries=15, disable_auth=False, entire_respone=False) -> json:
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "scrapeninja.p.rapidapi.com",
        "x-rapidapi-key": scraper_ninja
    }
    
    request_payload = {
        "url": url,
        "method": method,
        "retryNum": 3,
        "geo": "eu",
        "data": json.dumps(payload),
        "textNotExpected": [
            "Attention Required"
        ],
        "headers": [
            "content-type: application/json"
        ]
    }

    if not disable_auth:
        request_payload["headers"].append(f"cookie: need_verification=true; need_page_reload=false; chat-greeting=1; token={token}")

    if custom_header:
        request_payload['headers'].append(custom_header)

    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            async with aiohttp.ClientSession(headers=headers, connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
                async with session.post("https://scrapeninja.p.rapidapi.com/scrape", json=request_payload) as web_response:
                    response_text = await web_response.text()

                    if entire_respone:
                        return await web_response.json()

                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError as e:
                        LOG_ERROR(f"[Attempt {attempt}] Failed to decode JSON response: {e}. Response: {response_text}")
                        if attempt < max_retries:
                            await asyncio.sleep(3)
                            continue
                        return None

                    if not response_data.get('body'):
                        if "The API is unreachable" in response_text or "stderr" in response_text:
                            LOG_WARNING(f"[Attempt {attempt}] ScrapeNinja API is unreachable. Waiting for 3 seconds...")
                            await asyncio.sleep(3)
                            continue
                        LOG_ERROR(f"[Attempt {attempt}] Failed to scrape: {response_data}")
                        return None

                    try:
                        body_dict = json.loads(response_data['body'])
                    except json.JSONDecodeError as e:
                        if "Just a moment..." in response_data['body'] and attempt < max_retries:
                            LOG_WARNING(f"[Attempt {attempt}] Cloudflare protection. Waiting for 3 seconds...")
                            await asyncio.sleep(3)
                            continue
                        LOG_ERROR(f"[Attempt {attempt}] Failed to decode JSON body: {e}. Body: {response_data['body']}")
                        return None

                    if 'errors' in body_dict and body_dict['errors']:
                        error_message = body_dict['errors'][0].get('message', 'Unknown error')
                        LOG_ERROR(f"[Attempt {attempt}] Error while scraping: {error_message}")
                        lower_error = error_message.lower()
                        if ("something went wrong" in lower_error or "too many attempts" in lower_error) and attempt < max_retries:
                            LOG_WARNING(f"[Attempt {attempt}] Temporary error. Waiting for 3 seconds...")
                            await asyncio.sleep(3)
                            continue
                        return None

                    if web_response.status == 500:
                        LOG_ERROR(f"[Attempt {attempt}] Internal Server Error (500). Retrying in 3 seconds...")
                        await asyncio.sleep(3)
                        continue

                    if response_data.get('info', {}).get('statusCode') != 200:
                        raise Exception(f"Error while scraping: {response_data.get('info', {}).get('statusCode')}")
                    
                    return body_dict

        except aiohttp.ClientError as e:
            LOG_ERROR(f"[Attempt {attempt}] HTTP client error: {e}")
            if attempt < max_retries:
                await asyncio.sleep(3)
                continue
            return None
        except Exception as e:
            LOG_ERROR(f"[Attempt {attempt}] Unexpected error: {e}")
            return None

    LOG_ERROR(f"Exceeded maximum retries ({max_retries}) for URL: {url}")
    return None

                
class PlayerokLegacyAPI:            
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://playerok.com/graphql"
        self.cookies = { "token": self.token, "chat-greeting": "1", "need_page_reload": "False", "need_verification": "True"}
    
    async def getProfile(self) -> Profile:
        for i in range(3):
            payload_playerok = {
                "operationName": "viewer",
                "query": viewer_query
            }
            raw_profile = await ScrapeNinja(self.base_url, payload_playerok, self.token)
            if not raw_profile or not raw_profile.get("data").get("viewer"):
                await asyncio.sleep(10)
                continue
            
            return Profile(raw_profile)
    
    async def sendChatMessage(self, chatid: str, message: str):
        payload_playerok = {
            "operationName": "createChatMessage",
            "query": createChatMessage_query,
            "variables": {
                "input": {
                    "chatId": chatid,
                    "text": message
                }
            }
        }
        return await ScrapeNinja(self.base_url, payload_playerok, self.token)
    
    #Не работает, мб сделаю если будет не лень
    async def sendImage(self, chatid: str, image: str):
        try:
            with open(image, 'rb') as file:
                binary_data = file.read()
        except FileNotFoundError:
            logging.error("Image not found!")
            return None

        # Base64 encode the image
        encoded_image = base64.b64encode(binary_data).decode("utf-8")

        payload_playerok = {
            "operations": uploadImage_query,
            "map": {"1":["variables.file"]},
            "1": encoded_image
        }
        return await ScrapeNinja(self.base_url, payload_playerok, self.token, "POST", {"Content-Type": "multipart/form-data", "Content-Length": str(encoded_image)})
    
    async def getDeal(self, dealid: str) -> Deal:
        payload_playerok = {
            "operationName": "deal",
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"b06c9dadc3d2dad5c3d36891b5e3b974d1db921fe81f1533b61e9bacd47bfffb"}},
            "variables": {
                "id": dealid
            }
        }
        return Deal(await ScrapeNinja(self.base_url, payload_playerok, self.token))
    
    async def getDealByChatID(self, chatid: str) -> Deal:
        payload_playerok = {
            "operationName": "chat",
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"30623583872b839a4e293007c4b25e07963d10b38369ec083263346974a2f3fc"}},
            "variables": {
                "id": chatid
            }
        }
        
        chat = await ScrapeNinja(self.base_url, payload_playerok, self.token)
        try:
            deals = chat.get('data', {}).get('chat', {}).get('deals', [])
            if not deals:
                return None
            return Deal({"data": {"deal": deals[-1]}})
        except (AttributeError, IndexError, TypeError):
            return None
    
    async def getProductPage(self, slug: str) -> Product:
        payload_playerok = {
            "operationName": "item",
            "variables": {"slug":slug},
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"937add98f8a20b9ff4991bc6ba2413283664e25e7865c74528ac21c7dff86e24"}}
        }
        product = await ScrapeNinja(self.base_url, payload_playerok, self.token)
        
        if not product:
            return None
        
        if product.get("data").get("item") is None:
            return None
        
        return Product(product.get("data").get("item"))
    
    async def getRaisePrice(self, slug: str) -> int:
        raw_product = await self.getProductPage(slug)
        if not raw_product:
            return 999999
        
        playerok_payload = {
            "operationName": "itemPriorityStatuses",
            "variables": {"itemId": raw_product.id,"price": raw_product.raw_price},
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"0c9d72239058f04bb8753782ebfd768977b012fbfff3b86f5eb7c9b4992da970"}}
        }
        respone = await ScrapeNinja(self.base_url, playerok_payload, self.token)
        if respone is None:
            LOG_ERROR(f"Failed to get raise price! {respone}")
            return 999999
        
        if not respone.get("data").get("itemPriorityStatuses"):
            LOG_ERROR(f"Failed to get raise price! {respone}")
            return 999999
        
        return respone["data"]["itemPriorityStatuses"][0]["price"]
    
    async def reactivateProduct(self, slug: str):
        #Черти в Playerok решили разделить productid и ID в транзакции 
        #Горите в аду ублюдки 
        
        raw_product = await self.getProductPage(slug)
        if not raw_product:
            LOG_WARNING(f"Failed to get product page! {slug}")
            return None
        
        playerok_payload = {
            "operationName": "itemPriorityStatuses",
            "variables": {"itemId": raw_product.id,"price": raw_product.raw_price},
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"0c9d72239058f04bb8753782ebfd768977b012fbfff3b86f5eb7c9b4992da970"}}
        }
        product_page = await ScrapeNinja(self.base_url, playerok_payload, self.token)
        if not product_page:
            return None
        
        productid = product_page.get("data").get("itemPriorityStatuses")[0]["id"]
        if not productid:
            return None
        
        payload_playerok = {
            "operationName": "publishItem",
            "query": reenableLot_query,
            "variables": {
            "input": {
                "priorityStatuses": [
                    productid
                ],
                "transactionProviderId": "LOCAL",
                "transactionProviderData": {
                    "paymentMethodId": None
                },
                "itemId": raw_product.id
            }
            }
        }
        #pprint(payload_playerok)
        return await ScrapeNinja(self.base_url, payload_playerok, self.token)
    
    async def raiseProduct(self, slug: str):
        #Черти в Playerok решили разделить productid и ID в транзакции 
        #Горите в аду ублюдки 
        
        raw_product = await self.getProductPage(slug)
        if not raw_product:
            return None
        
        playerok_payload = {
            "operationName": "itemPriorityStatuses",
            "variables": {"itemId": raw_product.id,"price": raw_product.raw_price},
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"0c9d72239058f04bb8753782ebfd768977b012fbfff3b86f5eb7c9b4992da970"}}
        }
        product_page = await ScrapeNinja(self.base_url, playerok_payload, self.token)
        if not product_page:
            return None
        
        productid = product_page.get("data").get("itemPriorityStatuses")[0]["id"]
        if not productid:
            raise Exception(f"Failed To Get Product ID! {product_page}")
            return None
        
        payload_playerok = {
            "operationName": "increaseItemPriorityStatus",
            "query": increaseItemPriorityStatus_query,
            "variables": {
            "input": {
                "priorityStatuses": [
                    productid
                ],
                "transactionProviderId": "LOCAL",
                "transactionProviderData": {
                    "paymentMethodId": None
                },
                "itemId": raw_product.id
            }
            }
        }
        #pprint(payload_playerok)
        return await ScrapeNinja(self.base_url, payload_playerok, self.token)
    
    async def getUserProducts(self, userId: str, max_products = 5, status=["APPROVED", "PENDING_MODERATION", "PENDING_APPROVAL"], silent=False) -> List[Product]:
        payload_playerok = {
            "operationName": "items",
            "variables": {
                "pagination": {"first": max_products},
                "filter": {
                    "userId": userId,
                    "status": status
                }
            },
            "extensions": {"persistedQuery": {"version": 1, "sha256Hash": "d79d6e2921fea03c5f1515a8925fbb816eacaa7bcafe03eb47a40425ef49601e"}}
        }
        
        raw_products = await ScrapeNinja(self.base_url, payload_playerok, self.token)
        
        if not raw_products:
            return []
        
        products = raw_products.get("data", {}).get("items", {}).get("edges", [])
        return_products = []
        
        for product in products:
            if not silent:
                task = asyncio.create_task(loading_animation("Fetching Products "))
            real_product = await self.getProductPage(product.get("node", {}).get("slug"))
            if not silent:
                task.cancel()
                sys.stdout.write('\r' + ' ' * 30 + '\r')
                sys.stdout.flush()
            
            if real_product is None:
                continue
            return_products.append(real_product)
        
        if not silent:
            LOG_INFO("Product fetching complete.")
        return return_products
        
    async def updateDeal(self, dealid: str, status: str):
        payload_playerok = {
            "operationName": "updateDeal",
            "query": updateDeal_query,
            "variables": {
                "input": {
                    "id": dealid,
                    "status": status
                }
            }
        }
        
        for i in range(3):
            respone = await ScrapeNinja(self.base_url, payload_playerok, self.token)
            if respone is not None:
                return True
            await asyncio.sleep(10)
        return False
    
    async def getEmailAuthCode(self, email: str):
        payload_playerok = {
            "operationName": "getEmailAuthCode",
            "query": "mutation getEmailAuthCode($email: String!) {\n  getEmailAuthCode(input: {email: $email})\n}",
            "variables": {
                "email": email
            }
        }
        return await ScrapeNinja(self.base_url, payload_playerok, self.token, disable_auth=True, entire_respone=True)
    
    async def checkEmailAuthCode(self, email: str, code: str, lb_session_id: str):
        payload_playerok = {
            "operationName": "checkEmailAuthCode",
            "query": checkEmailAuthCode_query,
            "variables": {
                "input": {
                    "email": email,
                    "code": code
                }
            }
        }
        custom_header = f"cookie: lb_session_id={lb_session_id}"
        return await ScrapeNinja(self.base_url, payload_playerok, self.token,custom_header=custom_header, disable_auth=True, entire_respone=True)
    
    async def changeNickname(self, username: str):
        payload_playerok = {
            "operationName": "updateViewerProfile",
            "query": updateViewerProfile_query,
            "variables": {
                "input": {
                    "username": username
                }
            }
        }
        return await ScrapeNinja(self.base_url, payload_playerok, self.token)