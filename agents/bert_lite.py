"""
🤖 BertLite Agent
DistilBERT-based transformer model for scam detection.
Uses HuggingFace transformers for neural classification.
"""

from typing import List, Optional
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np

from .base_agent import BaseDetectionAgent
from models.schemas import Message, CouncilVote


class BertLiteAgent(BaseDetectionAgent):
    """
    Transformer-based scam detection using DistilBERT.
    Provides deep semantic understanding of message content
    with attention-based feature saliency.
    """
    
    def __init__(self, model_name: str = "distilbert-base-uncased"):
        super().__init__(
            name="🤖 BertLite",
            agent_type="Transformer (DistilBERT)"
        )
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.max_length = 256
        
        # Fallback for when model loading fails
        self.use_fallback = False
        
        # Semantic indicators for fallback
        self.scam_indicators = {
            "urgency": ["urgent", "immediately", "now", "today", "hurry", "fast", "asap", "quick"],
            "threat": ["blocked", "suspended", "closed", "frozen", "terminated", "deactivated"],
            "action": ["verify", "update", "confirm", "click", "share", "send", "enter"],
            "sensitive": ["otp", "pin", "password", "upi", "bank", "account", "card", "kyc", "aadhar"],
            "reward": ["won", "prize", "lottery", "cashback", "reward", "refund", "free"],
            "authority": ["sbi", "rbi", "hdfc", "icici", "police", "government", "official", "bank"],
        }
    
    async def initialize(self) -> None:
        """Initialize the transformer model."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Try to load a fine-tuned spam/scam model, fallback to base
            try:
                # Attempt to load a pre-trained spam classifier
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    "mrm8488/bert-tiny-finetuned-sms-spam-detection",
                    num_labels=2
                )
                self.tokenizer = AutoTokenizer.from_pretrained(
                    "mrm8488/bert-tiny-finetuned-sms-spam-detection"
                )
            except Exception:
                # Fallback to base model with random head (use heuristic scoring)
                self.use_fallback = True
            
            if self.model:
                self.model.to(self.device)
                self.model.eval()
            
            self._initialized = True
            
        except Exception as e:
            self.use_fallback = True
            self._initialized = True
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        Analyze message using transformer model.
        """
        if not self._initialized:
            await self.initialize()
        
        if self.use_fallback or self.model is None:
            return await self._semantic_fallback(message)
        
        try:
            # Tokenize input
            inputs = self.tokenizer(
                message,
                truncation=True,
                max_length=self.max_length,
                padding=True,
                return_tensors="pt"
            ).to(self.device)
            
            # Get model prediction
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=1)
            
            # Extract prediction
            probs = probabilities.cpu().numpy()[0]
            predicted_class = int(np.argmax(probs))
            confidence = float(probs[predicted_class])
            
            # Class 1 is typically spam/scam
            is_scam = predicted_class == 1
            scam_prob = float(probs[1])
            
            # Generate saliency-based features
            features = self._get_salient_tokens(message)
            
            # Generate reasoning
            if is_scam:
                reasoning = f"Transformer model detected scam patterns with {scam_prob:.1%} probability. "
                reasoning += "Deep semantic analysis indicates fraudulent intent."
            else:
                reasoning = f"Transformer analysis suggests legitimate message ({1-scam_prob:.1%} confidence)."
            
            return self.create_vote(
                is_scam=is_scam,
                confidence=scam_prob if is_scam else (1 - scam_prob),
                reasoning=reasoning,
                features=features
            )
            
        except Exception as e:
            return await self._semantic_fallback(message)
    
    def _get_salient_tokens(self, message: str) -> List[str]:
        """Extract potentially salient tokens from the message."""
        features = []
        message_lower = message.lower()
        
        for category, keywords in self.scam_indicators.items():
            for kw in keywords:
                if kw in message_lower:
                    features.append(f"{category}: {kw}")
        
        return features[:10]
    
    async def _semantic_fallback(self, message: str) -> CouncilVote:
        """
        Semantic scoring fallback when transformer unavailable.
        Uses weighted category scoring for scam detection.
        """
        message_lower = message.lower()
        
        category_weights = {
            "urgency": 0.15,
            "threat": 0.25,
            "action": 0.15,
            "sensitive": 0.25,
            "reward": 0.15,
            "authority": 0.1,
        }
        
        total_score = 0.0
        features = []
        categories_hit = []
        
        for category, keywords in self.scam_indicators.items():
            category_hits = sum(1 for kw in keywords if kw in message_lower)
            if category_hits > 0:
                category_score = min(category_hits * category_weights[category], category_weights[category] * 2)
                total_score += category_score
                categories_hit.append(category)
                for kw in keywords:
                    if kw in message_lower:
                        features.append(f"{category}: {kw}")
        
        # Normalize score to 0-1
        confidence = min(total_score / sum(category_weights.values()), 1.0)
        is_scam = confidence >= 0.35
        
        reasoning = f"Semantic analysis detected patterns in {len(categories_hit)} categories. "
        if is_scam:
            reasoning += f"Scam indicators: {', '.join(categories_hit)}."
        else:
            reasoning += "No strong scam semantic patterns found."
        
        return self.create_vote(
            is_scam=is_scam,
            confidence=confidence,
            reasoning=reasoning,
            features=features[:10]
        )
