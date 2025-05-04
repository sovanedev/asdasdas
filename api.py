import asyncio
import base64
import enum
import itertools
import json
from pprint import pprint
import random
import sys
import aiohttp

from playerok.playerok_query import *
from functools import wraps
from typing import Callable, List
import asyncio
import json

from colorful_logging import *
from datetime import datetime
        
import json
from typing import Any, Tuple, Optional
import time
from curl_cffi import requests
from curl_cffi.requests import AsyncSession
from curl_cffi.requests import WebSocket

global_session = AsyncSession()

async def get_session_cookies(token):
    global global_session
    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "content-type": "application/json",
        "apollo-require-preflight": "true",
        "access-control-allow-headers": "sentry-trace, baggage",
        "apollographql-client-name": "web",
        "x-timezone-offset": "-300",
        "Sec-GPC": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    data = {
        "operationName": "viewer",
        "variables": {},
        "query": "query viewer {\n  viewer {\n    ...Viewer\n    __typename\n  }\n}\n\nfragment Viewer on User {\n  id\n  username\n  email\n  role\n  hasFrozenBalance\n  supportChatId\n  systemChatId\n  unreadChatsCounter\n  isBlocked\n  isBlockedFor\n  createdAt\n  lastItemCreatedAt\n  hasConfirmedPhoneNumber\n  canPublishItems\n  profile {\n    id\n    avatarURL\n    testimonialCounter\n    __typename\n  }\n  __typename\n}"
    }

    cookies = {
        "need_page_reload": "false",
        "need_verification": "true",
        "token": token
    }

    async with AsyncSession() as session:
        session.cookies.update(cookies)

        response = await session.post('https://playerok.com/graphql', impersonate="chrome131", json=data, headers=headers)
        if response.status_code != 200:
            LOG_WARNING(f"Failed to get session cookies: {response.status_code}. Retrying in 3 seconds...")
            time.sleep(3000)
            return get_session_cookies(token)
        
        LOG_SUCCESS(f"Got the session cookies!")

        return session

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

class Transaction:
    def __init__(self, json: json):
        transaction = json.get('node', {})
        self.id = transaction.get('id')
        self.operation = transaction.get('operation')
        self.direction = transaction.get('direction')
        self.provider_id = transaction.get('providerId')
        self.provider = transaction.get('provider', {})
        self.user = transaction.get('user', {})
        self.creator = transaction.get('creator')
        self.status = transaction.get('status')
        self.status_description = transaction.get('statusDescription')
        self.status_expiration_date = transaction.get('statusExpirationDate')
        self.value = transaction.get('value')
        self.fee = transaction.get('fee')
        self.created_at = transaction.get('createdAt')
        self.props = transaction.get('props', {})
        self.verified_at = transaction.get('verifiedAt')
        self.verified_by = transaction.get('verifiedBy')
        self.completed_by = transaction.get('completedBy')
        self.payment_method_id = transaction.get('paymentMethodId')
        self.completed_at = transaction.get('completedAt')
        self.is_suspicious = transaction.get('isSuspicious')
        self.raw = json

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

class Chat:
    def __init__(self, json: json):
        chat = json.get('node', {})
        self.id = chat.get('id')
        self.type = chat.get('type')
        self.status = chat.get('status')
        self.unread_messages_counter = chat.get('unreadMessagesCounter')
        self.bookmarked = chat.get('bookmarked')
        
        last_message = chat.get('lastMessage', {})
        self.last_message_id = last_message.get('id')
        self.last_message_text = last_message.get('text')
        self.last_message_created_at = last_message.get('createdAt')
        self.last_message_is_read = last_message.get('isRead')
        self.last_message_is_bulk_messaging = last_message.get('isBulkMessaging')
        self.last_message_event = last_message.get('event')
        self.last_message_file = last_message.get('file')
        
        user = last_message.get('user', {})
        if user is not None:
            self.user_id = user.get('id')
            self.user_username = user.get('username')
            self.user_role = user.get('role')
            self.user_avatar_url = user.get('avatarURL')
            self.user_is_online = user.get('isOnline')
            self.user_is_blocked = user.get('isBlocked')
            self.user_rating = user.get('rating')
            self.user_testimonial_counter = user.get('testimonialCounter')
            self.user_created_at = user.get('createdAt')
            self.user_support_chat_id = user.get('supportChatId')
            self.user_system_chat_id = user.get('systemChatId')
        else:
            self.user_id = None
            self.user_username = None
            self.user_role = None
            self.user_avatar_url = None
            self.user_is_online = None
            self.user_is_blocked = None
            self.user_rating = None
            self.user_testimonial_counter = None
            self.user_created_at = None
            self.user_support_chat_id = None
            self.user_system_chat_id = None
        
        self.participants = chat.get('participants', [])
        self.raw = json

class ChatMessage:
    def __init__(self, json: json):
        message = json.get('node', {})
        self.id = message.get('id')
        self.text = message.get('text')
        self.created_at = message.get('createdAt')
        self.deleted_at = message.get('deletedAt')
        self.is_read = message.get('isRead')
        self.is_suspicious = message.get('isSuspicious')
        self.is_bulk_messaging = message.get('isBulkMessaging')
        self.game = message.get('game')
        self.file = message.get('file')
        
        user = message.get('user', {})
        if user is not None:
            self.user_id = user.get('id')
            self.user_username = user.get('username')
            self.user_role = user.get('role')
            self.user_avatar_url = user.get('avatarURL')
            self.user_is_online = user.get('isOnline')
            self.user_is_blocked = user.get('isBlocked')
            self.user_rating = user.get('rating')
            self.user_testimonial_counter = user.get('testimonialCounter')
            self.user_created_at = user.get('createdAt')
            self.user_support_chat_id = user.get('supportChatId')
            self.user_system_chat_id = user.get('systemChatId')
        else:
            self.user_id = None
            self.user_username = None
            self.user_role = None
            self.user_avatar_url = None
            self.user_is_online = None
            self.user_is_blocked = None
            self.user_rating = None
            self.user_testimonial_counter = None
            self.user_created_at = None
            self.user_support_chat_id = None
            self.user_system_chat_id = None
        
        self.deal = message.get('deal')
        self.item = message.get('item')
        self.transaction = message.get('transaction')
        self.moderator = message.get('moderator')
        self.event_by_user = message.get('eventByUser')
        self.event_to_user = message.get('eventToUser')
        self.is_auto_response = message.get('isAutoResponse')
        self.event = message.get('event')
        self.buttons = message.get('buttons')
        
        self.raw = json

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


async def PlayerokRequest(url: str, payload, token: str, method="POST", custom_header=None, max_retries=5) -> json:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "content-type": "application/json",
        "apollo-require-preflight": "true",
        "access-control-allow-headers": "sentry-trace, baggage",
        "apollographql-client-name": "web",
        "x-timezone-offset": "-300",
        "Sec-GPC": "1",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    cookies = {
        "need_page_reload": "false",
        "need_verification": "true",
        "token": token
    }

    session = requests.AsyncSession()
    session.cookies.update(cookies)

    if custom_header:
        headers.update(custom_header)

    for i in range(max_retries):
        try:
            if method == "GET":
                response = await session.get(url, impersonate="chrome131", headers=headers, json=payload)
            elif method == "POST":
                response = await session.post(url, impersonate="chrome131", json=payload, headers=headers)
            else:
                raise Exception(f"Invalid method: {method}")

            if "Что-то пошло не так" in response.text or "Слишком много попыток" in response.text:
                LOG_ERROR(f"[REQUEST] Playerok Returned An Error: {response.text}")
                await asyncio.sleep(5)
                continue

            if "Для выбранного товара нельзя обновить статус" in response.text:
                LOG_WARNING(f"[REQUEST] Cannot update status for this item")
                return None

            if response.status_code == 429:
                LOG_WARNING(f"[REQUEST] Rate limited Hit! Waiting for 10-15 seconds...")
                await asyncio.sleep(random.randint(10, 15))
                continue

            if response.status_code != 200:
                LOG_ERROR(f"[REQUEST] Playerok Returned An Error: {response.status_code} {response.text}")
                await asyncio.sleep(5)
                continue

            try:
                attempt = json.loads(response.text)
            except json.JSONDecodeError as e:
                LOG_ERROR(f"[REQUEST] Failed to decode JSON response: {e}. Response: {response.text}")
                await asyncio.sleep(5)
                continue

            break
        except Exception as e:
            LOG_ERROR(f"PlayerokRequest exception: {e}")
            await asyncio.sleep(3)
            continue
    else:
        LOG_ERROR(f"Exceeded maximum retries ({max_retries}/{max_retries})")
        return None

    log = f"{url}: {response.status_code}"
    if payload.get('operationName', None) != None:
        log = f"{payload['operationName']}: {response.status_code}"

    LOG_INFO(log)
    
    return json.loads(response.text)

         
class PlayerokAPI:            
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://playerok.com/graphql"
        self.cookies = { "token": self.token, "chat-greeting": "1", "need_page_reload": "False", "need_verification": "True"}
        self.profile = Profile({})
        self.was_initialized = False

    async def initialize(self):
        if self.was_initialized:
            LOG_WARNING("PlayerokAPI Is Already Initialized!")
            return
        
        self.profile = await self.getProfile()
        self.was_initialized = True
    
    async def markChatAsRead(self, chatid: str):
        payload_playerok = {
	        "operationName": "markChatAsRead",
            "query": markChatAsRead_query,
            "variables": {
                "input": {
                    "chatId": chatid
                }
            }
        }
        return await PlayerokRequest(self.base_url, payload_playerok, self.token)

    async def getProfile(self, attempts=3) -> Profile:
        for i in range(1,attempts + 1):
            payload_playerok = {
                "operationName": "viewer",
                "query": viewer_query
            }
            raw_profile = await PlayerokRequest(self.base_url, payload_playerok, self.token)
            print(raw_profile)
            if not raw_profile or not raw_profile.get("data").get("viewer"):
                await asyncio.sleep(10)
                continue
            
            return Profile(raw_profile)
        return None
    
    async def getChatMessages(self, chatId: str, first=10) -> List[ChatMessage]:
        payload_playerok = {
            "operationName": "chatMessages",
            "variables": {"pagination":{"first":first},"filter":{"chatId":chatId}},
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"285031731311bb95ea89e10afb57432b9e35d04a01a9e58003a43098fb961b5d"}}
        }
        respone = await PlayerokRequest(self.base_url, payload_playerok, self.token)

        messages = []

        for message in respone.get('data', {}).get('chatMessages', {}).get('edges', {}):
            messages.append(ChatMessage(message))

        return messages

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
        return await PlayerokRequest(self.base_url, payload_playerok, self.token)
    
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
        return await PlayerokRequest(self.base_url, payload_playerok, self.token, "POST", {"Content-Type": "multipart/form-data", "Content-Length": str(encoded_image)})
    
    async def getDeal(self, dealid: str) -> Deal:
        payload_playerok = {
            "operationName": "deal",
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"b06c9dadc3d2dad5c3d36891b5e3b974d1db921fe81f1533b61e9bacd47bfffb"}},
            "variables": {
                "id": dealid
            }
        }
        return Deal(await PlayerokRequest(self.base_url, payload_playerok, self.token))
    
    async def markChatAsRead(self, chatId: str):
        payload_playerok = {
            "operationName": "markChatAsRead",
            "variables": {
                "input": {
                    "chatId": chatId
                }
            },
            "query": "mutation markChatAsRead($input: MarkChatAsReadInput!) {\n  markChatAsRead(input: $input) {\n    ...RegularChat\n    __typename\n  }\n}\n\nfragment RegularChat on Chat {\n  id\n  type\n  unreadMessagesCounter\n  bookmarked\n  isTextingAllowed\n  owner {\n    ...ChatParticipant\n    __typename\n  }\n  agent {\n    ...ChatParticipant\n    __typename\n  }\n  participants {\n    ...ChatParticipant\n    __typename\n  }\n  deals {\n    ...ChatActiveItemDeal\n    __typename\n  }\n  status\n  startedAt\n  finishedAt\n  __typename\n}\n\nfragment ChatParticipant on UserFragment {\n  ...RegularUserFragment\n  __typename\n}\n\nfragment RegularUserFragment on UserFragment {\n  id\n  username\n  role\n  avatarURL\n  isOnline\n  isBlocked\n  rating\n  testimonialCounter\n  createdAt\n  supportChatId\n  systemChatId\n  __typename\n}\n\nfragment ChatActiveItemDeal on ItemDealProfile {\n  id\n  direction\n  status\n  hasProblem\n  statusDescription\n  testimonial {\n    id\n    rating\n    __typename\n  }\n  item {\n    ...ItemEdgeNode\n    __typename\n  }\n  user {\n    ...RegularUserFragment\n    __typename\n  }\n  __typename\n}\n\nfragment ItemEdgeNode on ItemProfile {\n  ...MyItemEdgeNode\n  ...ForeignItemEdgeNode\n  __typename\n}\n\nfragment MyItemEdgeNode on MyItemProfile {\n  id\n  slug\n  priority\n  status\n  name\n  price\n  rawPrice\n  statusExpirationDate\n  sellerType\n  attachment {\n    ...PartialFile\n    __typename\n  }\n  user {\n    ...UserItemEdgeNode\n    __typename\n  }\n  approvalDate\n  createdAt\n  priorityPosition\n  viewsCounter\n  feeMultiplier\n  __typename\n}\n\nfragment PartialFile on File {\n  id\n  url\n  __typename\n}\n\nfragment UserItemEdgeNode on UserFragment {\n  ...UserEdgeNode\n  __typename\n}\n\nfragment UserEdgeNode on UserFragment {\n  ...RegularUserFragment\n  __typename\n}\n\nfragment ForeignItemEdgeNode on ForeignItemProfile {\n  id\n  slug\n  priority\n  status\n  name\n  price\n  rawPrice\n  sellerType\n  attachment {\n    ...PartialFile\n    __typename\n  }\n  user {\n    ...UserItemEdgeNode\n    __typename\n  }\n  approvalDate\n  priorityPosition\n  createdAt\n  viewsCounter\n  feeMultiplier\n  __typename\n}"
        }
        return await PlayerokRequest(self.base_url, payload_playerok, self.token)

    async def getAllChats(self) -> list[Chat]:
        chats = []
        has_next_page = True
        end_cursor = None

        profile = await self.getProfile()

        while has_next_page:
            payload_playerok = {
            "operationName": "chats",
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"4ff10c34989d48692b279c5eccf460c7faa0904420f13e380597b29f662a8aa4"}},
            "variables": {
                "pagination": {
                "first": 1000,
                "after": end_cursor
                },
                "filter": {
                    "userId": profile.id
                }
            }
            }

            chats_raw = await PlayerokRequest(self.base_url, payload_playerok, self.token)
            page_info = chats_raw.get('data', {}).get('chats', {}).get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            end_cursor = page_info.get('endCursor', None)

            chats.extend(chats_raw.get('data', {}).get('chats', {}).get('edges', []))

        chats_class = []
        for transaction_json in chats:
            transaction = Chat(transaction_json)
            chats_class.append(transaction)

        return reversed(chats_class)

    async def getAllTransactions(self, operation: list, dataRange: dict) -> list[Transaction]:
        transactions = []
        has_next_page = True
        end_cursor = None

        profile = await self.getProfile()

        while has_next_page:
            payload_playerok = {
            "operationName": "transactions",
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"9086133fee843665636074aaadb50a13ff93fd41ec2fda3b1a29483f9419c538"}},
            "variables": {
                "pagination": {
                "first": 60,
                "after": end_cursor
                },
                "filter": {
                "userId": profile.id,
                "operation": operation,
                "dateRange": dataRange
                }
            }
            }

            transactions_raw = await PlayerokRequest(self.base_url, payload_playerok, self.token)
            page_info = transactions_raw.get('data', {}).get('transactions', {}).get('pageInfo', {})
            has_next_page = page_info.get('hasNextPage', False)
            end_cursor = page_info.get('endCursor', None)

            transactions.extend(transactions_raw.get('data', {}).get('transactions', {}).get('edges', []))

        transactions_class = []
        for transaction_json in transactions:
            transaction = Transaction(transaction_json)
            transactions_class.append(transaction)

        return reversed(transactions_class)

    async def getDealByChatID(self, chatid: str) -> Deal:
        payload_playerok = {
            "operationName": "chat",
            "extensions": {"persistedQuery":{"version":1,"sha256Hash":"30623583872b839a4e293007c4b25e07963d10b38369ec083263346974a2f3fc"}},
            "variables": {
                "id": chatid
            }
        }
        
        chat = await PlayerokRequest(self.base_url, payload_playerok, self.token)
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
        product = await PlayerokRequest(self.base_url, payload_playerok, self.token)
        
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
        respone = await PlayerokRequest(self.base_url, playerok_payload, self.token)
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
        product_page = await PlayerokRequest(self.base_url, playerok_payload, self.token)
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
        return await PlayerokRequest(self.base_url, payload_playerok, self.token)
    
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
        product_page = await PlayerokRequest(self.base_url, playerok_payload, self.token)
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
        return await PlayerokRequest(self.base_url, payload_playerok, self.token)
    
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
        
        raw_products = await PlayerokRequest(self.base_url, payload_playerok, self.token)
        
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
            respone = await PlayerokRequest(self.base_url, payload_playerok, self.token)
            if respone is not None:
                return True
            await asyncio.sleep(10)
        return False
    
    # async def getEmailAuthCode(self, email: str):
    #     payload_playerok = {
    #         "operationName": "getEmailAuthCode",
    #         "query": "mutation getEmailAuthCode($email: String!) {\n  getEmailAuthCode(input: {email: $email})\n}",
    #         "variables": {
    #             "email": email
    #         }
    #     }
    #     return await ScrapeNinja(self.base_url, payload_playerok, self.token, disable_auth=True, entire_respone=True)
    
    # async def checkEmailAuthCode(self, email: str, code: str, lb_session_id: str):
    #     payload_playerok = {
    #         "operationName": "checkEmailAuthCode",
    #         "query": checkEmailAuthCode_query,
    #         "variables": {
    #             "input": {
    #                 "email": email,
    #                 "code": code
    #             }
    #         }
    #     }
    #     custom_header = f"cookie: lb_session_id={lb_session_id}"
    #     return await ScrapeNinja(self.base_url, payload_playerok, self.token,custom_header=custom_header, disable_auth=True, entire_respone=True)
    
    # async def changeNickname(self, username: str):
    #     payload_playerok = {
    #         "operationName": "updateViewerProfile",
    #         "query": updateViewerProfile_query,
    #         "variables": {
    #             "input": {
    #                 "username": username
    #             }
    #         }
    #     }
    #     return await ScrapeNinja(self.base_url, payload_playerok, self.token)

async def getEvent(message_json: dict, playerok: PlayerokAPI) -> Tuple[EVENT_TYPE, Optional[Any]]:
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
                elif chat_data.get('id', None) != None:
                    messages = await playerok.getChatMessages(chat_data.get('id'))
                    
                    last_index = next((i for i in reversed(range(len(messages))) if messages[i].text == "{{ITEM_PAID}}"), None)
                    if last_index is not None:
                        messages = messages[:last_index + 1]

                    for msg in messages:
                        if msg.user_username == playerok.profile.username:
                            break
                    else:
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