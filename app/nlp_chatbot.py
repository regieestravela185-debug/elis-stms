"""
NLP-Based Smart Chat Assistant
Uses NLP for intent recognition and dynamic responses
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple
from collections import Counter

try:
    from rapidfuzz import fuzz, process
except ImportError:
    fuzz = None
    process = None

try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
except ImportError:
    nltk = None
    word_tokenize = None
    stopwords = None


# Intent definitions
INTENTS = {
    "unit_inquiry": {
        "keywords": [
            "unit", "room", "apartment", "studio", "place", "live", "stay", "tira", "tirahan", "kwarto",
            "available", "floor", "building", "size", "bedroom", "bathroom", "vacant", "bakante", "matitirhan"
        ],
        "responses": [
            "We have studio-type residential units available. Check the Units section on the homepage for the full list. / May studio-type units kami—nasa Units section ng homepage ang listahan.",
            "Available units are filterable by building (B1–B5). Want help with the reservation process? / Pwedeng i-filter by building ang units sa homepage.",
        ]
    },
    "pricing": {
        "keywords": [
            "price", "presyo", "halaga", "magkano", "rent", "upa", "monthly", "rate", "cost", "fee",
            "how much", "ilang", "bayad", "budget"
        ],
        "responses": [
            "Sample monthly rates are visible on each unit card. For latest pricing, sign in or contact the office. / Nasa unit cards ang sample monthly rates.",
            "Rent varies per unit/building. Check the Units section for current rates. / Iba-iba ang upa per unit; tingnan sa Units section.",
        ]
    },
    "reservation": {
        "keywords": [
            "reserve", "book", "booking", "reservation", "apply", "application", "secure", "magreserve",
            "magpa-reserve", "how do i reserve", "how to reserve"
        ],
        "responses": [
            "To reserve: sign in, click 'Reserve' on a unit, fill the form with valid ID + selfie (AI verification), then wait for admin approval (1–2 business days). / Para mag-reserve: mag-sign in, piliin ang unit, i-upload ang ID at selfie para sa AI verification.",
            "Reservation requires a valid government ID and a clear selfie for AI identity verification. / Kailangan ng valid ID at malinaw na selfie para sa AI identity verification.",
        ]
    },
    "move_in_out": {
        "keywords": [
            "move in", "move-in", "move out", "move-out", "moving", "lipat", "vacate", "leaving", "checkout", "transfer"
        ],
        "responses": [
            "Move-in: bring valid ID and signed contract. Move-out: 30 days advance notice + office clearance for deposit refund. / Move-in: dalhin ang ID at contract. Move-out: 30 days notice.",
        ]
    },
    "payment": {
        "keywords": [
            "pay", "payment", "bayad", "magbayad", "how to pay", "payment method", "due date", "late",
            "gcash", "bank transfer", "cash", "billing", "bill", "invoice", "receipt", "penalty"
        ],
        "responses": [
            "Tenants pay through the dashboard via GCash or bank transfer. Rent is due monthly per contract; late payments incur penalties. / Magbayad sa dashboard via GCash o bank transfer.",
            "Late payment may incur penalties per contract. Check the Payments section in your tenant dashboard. / May penalty ang late payment ayon sa contract.",
        ]
    },
    "deposit": {
        "keywords": ["deposit", "advance", "security deposit", "refund", "ibalik", "ibabalik", "down payment", "downpayment"],
        "responses": [
            "A security deposit is required upon move-in (typically 1–2 months rent), refundable after office clearance. / Required ang security deposit, refundable pagkatapos ng clearance.",
        ]
    },
    "renewal": {
        "keywords": ["renew", "renewal", "extend", "extension", "contract", "lease", "expire", "expiration", "matapos", "tapos na"],
        "responses": [
            "Request lease renewal through the tenant dashboard. We send reminders 30 days before contract end. / Pwede mag-renew sa dashboard. May reminder 30 days bago mag-expire.",
        ]
    },
    "maintenance": {
        "keywords": [
            "concern", "problem", "issue", "repair", "maintenance", "ayusin", "sira", "broken", "fix",
            "leaking", "tubig", "ilaw", "aircon", "plumbing", "electrical", "complaint", "request"
        ],
        "responses": [
            "Submit a maintenance concern via Dashboard > Concerns. Urgent issues are prioritized within 24 hours. / Mag-submit ng concern sa Dashboard > Concerns.",
        ]
    },
    "amenities": {
        "keywords": [
            "wifi", "internet", "amenity", "amenities", "facility", "facilities", "gym", "pool", "lobby",
            "elevator", "rooftop", "cctv", "kasama", "included", "furnished"
        ],
        "responses": [
            "Amenities vary per building (e.g., CCTV, security, common laundry). Wi-Fi may be per-unit or separate—please confirm with the office. / Iba-iba ang amenities per building. I-confirm sa office.",
        ]
    },
    "parking": {
        "keywords": ["parking", "car", "kotse", "motor", "motorcycle", "garage", "park", "sasakyan"],
        "responses": [
            "Parking depends on the unit/building rules. Ask the office for slot availability. / Depende sa unit/building ang parking. Itanong sa office.",
        ]
    },
    "pets": {
        "keywords": ["pet", "pets", "dog", "cat", "aso", "pusa", "alaga", "hayop", "bird", "ibon"],
        "responses": [
            "Pet policy depends on the unit/building. Please confirm with the office before bringing pets. / Depende sa unit/building ang pet policy. Magtanong sa office.",
        ]
    },
    "noise_curfew": {
        "keywords": ["noise", "loud", "curfew", "quiet", "ingay", "maingay", "tahimik", "gabi"],
        "responses": [
            "Quiet hours are typically 10 PM–7 AM. Excessive noise may be reported. / Quiet hours: 10 PM–7 AM. Iwasan ang sobrang ingay.",
        ]
    },
    "utilities": {
        "keywords": ["water", "electricity", "kuryente", "tubig", "meralco", "maynilad", "bill", "utility", "submeter"],
        "responses": [
            "Water and electricity are billed via sub-meter and added to your monthly statement (varies per unit). / Tubig at kuryente ay naka-sub-meter at idinadagdag sa monthly bill.",
        ]
    },
    "guest_visitor": {
        "keywords": ["guest", "visitor", "bisita", "guests", "overnight", "stay over"],
        "responses": [
            "Guests must be logged at the lobby/office. Overnight stays may require prior approval. / I-log sa lobby/office ang bisita. Overnight stays may approval.",
        ]
    },
    "security": {
        "keywords": ["security", "safe", "safety", "ligtas", "cctv", "guard", "secure", "lock", "key"],
        "responses": [
            "We have 24/7 security and CCTV coverage in common areas for tenant safety. / May 24/7 security at CCTV sa common areas.",
        ]
    },
    "location_viewing": {
        "keywords": ["location", "address", "where", "viewing", "tour", "visit", "saan", "tingnan", "directions"],
        "responses": [
            "ELIS Business Center is located at our main address. For unit viewing, please contact the office to schedule. / Tumawag sa office para mag-set ng viewing schedule.",
        ]
    },
    "contact": {
        "keywords": ["contact", "call", "email", "phone", "hotline", "office", "tawag", "tumawag", "office hours", "schedule"],
        "responses": [
            "Office hours: 9 AM – 5 PM (Mon–Fri). Reach us via the Contact section on the homepage. / Office hours: 9 AM–5 PM (Lunes–Biyernes).",
        ]
    },
    "requirements": {
        "keywords": ["requirement", "requirements", "documents", "papers", "id", "valid id", "kailangan", "documento"],
        "responses": [
            "Reservation requirements: 1 valid government ID, a clear selfie (AI verification), and signed reservation form. / Kailangan: 1 valid government ID, malinaw na selfie, at signed reservation form.",
        ]
    },
    "identity": {
        "keywords": [
            "who are you", "your name", "what's your name", "whats your name", "sino ka", "sino ka ba",
            "ano pangalan mo", "anong pangalan mo", "name mo", "ano ka", "are you a bot", "robot ka",
            "bot ka ba", "ellie", "owl", "kwago", "ai ka"
        ],
        "responses": [
            "I'm Ellie, the virtual assistant of The Elis Center. I can help with units, pricing, reservations, payments, and more! / Ako si Ellie, ang virtual assistant ng The Elis Center. Matutulungan kita sa units, presyo, reservation, payment, at iba pa!",
        ]
    },
    "landmarks": {
        "keywords": [
            "near", "malapit", "landmark", "school", "eskwela", "university", "lpu", "nu", "waltermart",
            "sm", "mall", "highway", "student", "estudyante", "accessible", "commute", "jeep", "terminal"
        ],
        "responses": [
            "The Elis Center is along the highway in Calamba, near LPU Laguna, NU Laguna, WalterMart, and SM—convenient for students and businesses. / Nasa highway ng Calamba, malapit sa LPU, NU Laguna, WalterMart, at SM.",
        ]
    },
    "contract_terms": {
        "keywords": [
            "contract length", "how long", "term", "minimum", "1 year", "one year", "tagal ng contract",
            "gaano katagal", "lease term", "duration", "commitment"
        ],
        "responses": [
            "Commercial units have a minimum 1-year contract term. Residential units are all studio type. Power and water are billed separately (exclusive). / Commercial: minimum 1 taon. Residential: studio type. Hiwalay ang bayad sa kuryente at tubig.",
        ]
    },
    "greeting": {
        "keywords": ["hello", "hi", "hey", "kumusta", "kamusta", "good morning", "good afternoon", "good evening", "magandang"],
        "responses": [
            "Hello! I'm Ellie, your Elis Center assistant. How can I help? / Kumusta! Ako si Ellie, ang assistant ng Elis Center. Paano kita matutulungan?",
            "Hi! Ako si Ellie. Ask me about units, pricing, reservations, payments, amenities, and more. / Magtanong ka tungkol sa units, presyo, reservation, payment, atbp.",
        ]
    },
    "goodbye": {
        "keywords": ["bye", "goodbye", "thanks", "thank you", "salamat", "see you", "later"],
        "responses": [
            "Thanks for chatting! Ako si Ellie—balik ka lang kung may tanong. Have a great day! / Salamat sa pag-chat! Balik ka lang kung may tanong.",
        ]
    },
    "fallback": {
        "keywords": [],
        "responses": [
            "Sorry, hindi ko masyadong nagets. Try asking about units, pricing, reservation, payments, amenities, parking, pets, or maintenance. — Ellie 🦉 / Pakitanong tungkol sa units, presyo, reservation, payments, amenities, parking, alaga, o maintenance.",
            "Could you rephrase that? I can help with reservations, payments, amenities, and more. / Pakiulit ang tanong. Pwede ako tumulong sa reservations, payments, amenities, atbp.",
        ]
    }
}


class NLPChatbot:
    """NLP-based chatbot with intent recognition"""
    
    def __init__(self):
        self.intent_history: List[Dict] = []
        
        # Download NLTK data if available
        if nltk:
            try:
                nltk.download('punkt', quiet=True)
                nltk.download('stopwords', quiet=True)
            except:
                pass
    
    def preprocess_text(self, text: str) -> List[str]:
        """Preprocess text for NLP analysis"""
        if not nltk or not word_tokenize:
            # Fallback: simple split
            return [t for t in text.lower().split() if t.isalnum()]
        
        # Tokenize (fallback to simple split if NLTK data not available)
        try:
            tokens = word_tokenize(text.lower())
        except (LookupError, Exception):
            return [t for t in text.lower().split() if t.isalnum()]
        
        # Remove stopwords if available
        if stopwords:
            try:
                stop_words = set(stopwords.words('english'))
                tokens = [t for t in tokens if t.isalnum() and t not in stop_words]
            except (LookupError, Exception):
                tokens = [t for t in tokens if t.isalnum()]
        else:
            tokens = [t for t in tokens if t.isalnum()]
        
        return tokens
    
    def detect_intent(self, message: str) -> Tuple[str, float]:
        """
        Detect intent from user message using keyword matching and fuzzy matching.
        Scoring rewards strong matches: exact keyword presence = high confidence,
        multiple matches boost it further. Independent of total keyword count.
        Returns (intent, confidence_score)
        """
        message_lower = message.lower()
        tokens = self.preprocess_text(message)
        
        best_intent = "fallback"
        best_score = 0.0
        
        for intent_name, intent_data in INTENTS.items():
            if intent_name == "fallback":
                continue
            
            exact_matches = 0
            fuzzy_matches = 0
            
            # Exact keyword/phrase matching (substring)
            for keyword in intent_data["keywords"]:
                if keyword in message_lower:
                    exact_matches += 1
            
            # Fuzzy matching with tokens (for typos)
            if tokens and fuzz:
                for keyword in intent_data["keywords"]:
                    if " " in keyword:
                        continue  # skip multi-word for fuzzy
                    for token in tokens:
                        if token == keyword:
                            continue  # already counted as exact
                        similarity = fuzz.ratio(token, keyword) / 100
                        if similarity > 0.85:
                            fuzzy_matches += 1
                            break  # one fuzzy match per keyword is enough
            
            # Score: 0.7 for any exact match, +0.1 per additional, +0.05 per fuzzy
            # Caps at 1.0. Independent of how many keywords the intent has.
            if exact_matches > 0:
                score = 0.7 + min(0.3, (exact_matches - 1) * 0.1 + fuzzy_matches * 0.05)
            elif fuzzy_matches > 0:
                score = 0.5 + min(0.2, (fuzzy_matches - 1) * 0.05)
            else:
                score = 0.0
            
            if score > best_score:
                best_score = score
                best_intent = intent_name
        
        confidence = min(best_score, 1.0)
        
        if confidence < 0.5:
            return "fallback", confidence
        
        return best_intent, confidence
    
    def _detect_intent_simple(self, message: str) -> Tuple[str, float]:
        """Simple keyword matching fallback"""
        message_lower = message.lower()
        
        for intent_name, intent_data in INTENTS.items():
            if intent_name == "fallback":
                continue
            
            matches = sum(1 for keyword in intent_data["keywords"] if keyword in message_lower)
            if matches > 0:
                confidence = min(matches / len(intent_data["keywords"]), 1.0)
                return intent_name, confidence
        
        return "fallback", 0.0
    
    def generate_response(self, message: str, user_role: str = "customer") -> Dict:
        """
        Generate response based on detected intent.
        Returns dict with response, intent, and confidence.
        """
        intent, confidence = self.detect_intent(message)
        
        # Get response for intent
        intent_data = INTENTS.get(intent, INTENTS["fallback"])
        responses = intent_data["responses"]
        
        # Simple rotation of responses
        import random
        response = random.choice(responses)
        
        # Log interaction
        self.intent_history.append({
            "message": message,
            "intent": intent,
            "confidence": confidence,
            "response": response,
            "user_role": user_role,
        })
        
        return {
            "response": response,
            "intent": intent,
            "confidence": confidence,
            "success": True,
        }
    
    def extract_entities(self, message: str) -> Dict:
        """
        Extract entities from message (building, price range, etc.)
        Returns dict of extracted entities.
        """
        entities = {}
        message_lower = message.lower()
        
        # Extract building
        buildings = ["b1", "b2", "b3", "b4", "b5"]
        for building in buildings:
            if building in message_lower:
                entities["building"] = building.upper()
                break
        
        # Extract price range
        import re
        prices = re.findall(r'₱?\s*[\d,]+', message)
        if prices:
            entities["price_mentioned"] = prices
        
        # Extract numbers
        numbers = re.findall(r'\d+', message)
        if numbers:
            entities["numbers"] = numbers
        
        return entities
    
    def get_conversation_context(self, last_n: int = 5) -> List[Dict]:
        """Get recent conversation context"""
        return self.intent_history[-last_n:]


# Global chatbot instance
_chatbot_instance = None

def get_chatbot() -> NLPChatbot:
    """Get or create global chatbot instance"""
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = NLPChatbot()
    return _chatbot_instance


def process_chat_message(message: str, user_role: str = "customer") -> Dict:
    """
    Process chat message and return response.
    Convenience function for route handlers.
    """
    chatbot = get_chatbot()
    result = chatbot.generate_response(message, user_role)
    entities = chatbot.extract_entities(message)
    
    result["entities"] = entities
    return result
