"""
🧮 FastML Agent
TF-IDF + Random Forest/SVM based ML classifier for scam detection.
Fast inference with interpretable feature importance.
"""

import pickle
import os
from typing import List, Optional
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from .base_agent import BaseDetectionAgent
from models.schemas import Message, CouncilVote


class FastMLAgent(BaseDetectionAgent):
    """
    Machine Learning based scam detection using TF-IDF vectorization
    and Random Forest classifier. Provides fast inference with
    feature importance for explainability.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        super().__init__(
            name="🧮 FastML",
            agent_type="ML (TF-IDF + RandomForest)"
        )
        self.model_path = model_path
        self.pipeline: Optional[Pipeline] = None
        self.feature_names: List[str] = []
        
        # Fallback vocabulary for scam detection
        self.scam_keywords = [
            "urgent", "blocked", "verify", "immediately", "suspended",
            "click", "link", "update", "account", "bank", "upi", "otp",
            "pin", "password", "kyc", "aadhar", "pan", "reward", "prize",
            "won", "lottery", "cashback", "refund", "transfer", "payment",
            "customer", "support", "helpline", "expire", "deadline",
            "warning", "alert", "action", "required", "confirm", "share"
        ]
        
        self.non_scam_keywords = [
            "thank", "regards", "hello", "hi", "please", "request",
            "inquiry", "question", "help", "information", "schedule",
            "meeting", "appointment", "reminder", "family", "friend"
        ]
    
    async def initialize(self) -> None:
        """
        Initialize the ML model.
        Loads pre-trained model if available, otherwise uses fallback.
        """
        model_file = Path(self.model_path) if self.model_path else None
        
        if model_file and model_file.exists():
            try:
                with open(model_file, 'rb') as f:
                    self.pipeline = pickle.load(f)
                self._initialized = True
                return
            except Exception:
                pass
        
        # Create a simple fallback pipeline
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(
                max_features=1000,
                ngram_range=(1, 2),
                stop_words='english',
                lowercase=True
            )),
            ('classifier', RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                class_weight='balanced'
            ))
        ])
        
        # Train on minimal synthetic data for fallback
        await self._train_fallback_model()
        self._initialized = True
    
    async def _train_fallback_model(self) -> None:
        """Train a minimal model on synthetic data as fallback."""
        # Synthetic scam messages for training
        scam_samples = [
            "Your bank account will be blocked today. Verify immediately.",
            "URGENT: Your UPI account suspended. Click link to verify.",
            "Dear customer, your KYC expired. Update now to avoid account block.",
            "You won 50000 rupees lottery! Share OTP to claim prize.",
            "SBI Alert: Unauthorized transaction detected. Share OTP to cancel.",
            "Your account is being deactivated. Call customer support immediately.",
            "ICICI Bank: Your card is blocked. Click here to unblock.",
            "Final warning: Account will be closed in 24 hours. Verify KYC.",
            "Congrats! You've won cashback of Rs 10000. Enter UPI PIN to claim.",
            "RBI Alert: Your bank account frozen. Share Aadhar to unlock.",
            "Share your UPI ID to avoid account suspension.",
            "Income Tax refund of Rs 25000 pending. Click to claim now.",
            "Your mobile number linked to suspicious transactions. Verify OTP.",
            "Paytm KYC expired. Update immediately or wallet will be blocked.",
            "Police case registered. Call this number immediately to resolve.",
        ]
        
        # Synthetic non-scam messages
        non_scam_samples = [
            "Hi, how are you doing today?",
            "Please find the attached document for your review.",
            "Meeting scheduled for tomorrow at 3 PM.",
            "Thank you for your help with the project.",
            "Can we discuss the proposal next week?",
            "Happy birthday! Wishing you the best.",
            "Your order has been shipped and will arrive soon.",
            "Reminder: Doctor appointment on Monday.",
            "Flight booking confirmed for next month.",
            "Your food delivery is on the way.",
            "Class schedule for next semester is ready.",
            "Thank you for attending the event.",
            "Project deadline extended to next Friday.",
            "Welcome to our newsletter subscription.",
            "Your subscription renewal is complete.",
        ]
        
        X_train = scam_samples + non_scam_samples
        y_train = [1] * len(scam_samples) + [0] * len(non_scam_samples)
        
        self.pipeline.fit(X_train, y_train)
        
        # Store feature names for explainability
        try:
            self.feature_names = self.pipeline.named_steps['tfidf'].get_feature_names_out().tolist()
        except Exception:
            self.feature_names = []
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        Analyze message using ML classification.
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get prediction and probability
            prediction = self.pipeline.predict([message])[0]
            probabilities = self.pipeline.predict_proba([message])[0]
            
            is_scam = bool(prediction == 1)
            confidence = float(probabilities[1] if is_scam else probabilities[0])
            
            # Get feature importance for explanation
            features = self._extract_important_features(message)
            
            # Generate reasoning
            if is_scam:
                reasoning = f"ML classifier detected scam patterns with {confidence:.1%} confidence. "
                if features:
                    reasoning += f"Key indicators: {', '.join(features[:5])}."
            else:
                reasoning = f"ML classifier found no significant scam indicators. Confidence: {confidence:.1%}."
            
            return self.create_vote(
                is_scam=is_scam,
                confidence=confidence,
                reasoning=reasoning,
                features=features
            )
            
        except Exception as e:
            # Fallback to keyword-based scoring
            return await self._fallback_analysis(message)
    
    def _extract_important_features(self, message: str) -> List[str]:
        """Extract the most important features from the message."""
        features = []
        message_lower = message.lower()
        
        # Check for scam keywords
        for keyword in self.scam_keywords:
            if keyword in message_lower:
                features.append(f"scam_keyword: {keyword}")
        
        return features[:10]
    
    async def _fallback_analysis(self, message: str) -> CouncilVote:
        """Simple keyword-based fallback if ML fails."""
        message_lower = message.lower()
        
        scam_score = sum(1 for kw in self.scam_keywords if kw in message_lower)
        non_scam_score = sum(1 for kw in self.non_scam_keywords if kw in message_lower)
        
        total = scam_score + non_scam_score + 1
        confidence = scam_score / total
        is_scam = confidence > 0.4
        
        return self.create_vote(
            is_scam=is_scam,
            confidence=confidence,
            reasoning=f"Fallback analysis: {scam_score} scam indicators, {non_scam_score} benign indicators.",
            features=[kw for kw in self.scam_keywords if kw in message_lower][:10]
        )
