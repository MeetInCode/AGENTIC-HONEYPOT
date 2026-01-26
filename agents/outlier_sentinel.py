"""
🔍 OutlierSentinel Agent
SBERT-based anomaly detector for scam detection.
Uses sentence embeddings to identify outlier messages.
"""

from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

from .base_agent import BaseDetectionAgent
from models.schemas import Message, CouncilVote


class OutlierSentinelAgent(BaseDetectionAgent):
    """
    Anomaly detection using Sentence-BERT embeddings.
    Compares message embeddings against a reference set
    of legitimate messages to detect outliers (potential scams).
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        super().__init__(
            name="🔍 OutlierSentinel",
            agent_type="Embedding (SBERT Anomaly)"
        )
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        
        # Reference embeddings for legitimate messages
        self.legitimate_embeddings: Optional[np.ndarray] = None
        self.legitimate_centroid: Optional[np.ndarray] = None
        
        # Reference embeddings for scam messages
        self.scam_embeddings: Optional[np.ndarray] = None
        self.scam_centroid: Optional[np.ndarray] = None
        
        # Reference messages for building embeddings
        self.legitimate_samples = [
            "Hi, how are you doing today?",
            "Please find the attached document.",
            "Meeting scheduled for tomorrow at 3 PM.",
            "Thank you for your help with the project.",
            "Can we discuss the proposal next week?",
            "Happy birthday! Wishing you the best.",
            "Your order has been shipped.",
            "Reminder: Doctor appointment on Monday.",
            "Flight booking confirmed.",
            "Your food delivery is on the way.",
            "Welcome to our subscription.",
            "Project status update attached.",
            "Looking forward to meeting you.",
            "Thanks for the quick response.",
            "Please review the document at your convenience.",
        ]
        
        self.scam_samples = [
            "Your bank account will be blocked today. Verify immediately.",
            "URGENT: Your UPI suspended. Click link to verify.",
            "Dear customer, your KYC expired. Update now.",
            "You won 50000 rupees lottery! Share OTP.",
            "SBI Alert: Unauthorized transaction. Share OTP to cancel.",
            "Your account is being deactivated. Call support.",
            "ICICI Bank: Your card is blocked. Click here.",
            "Warning: Account will be closed in 24 hours.",
            "Congrats! You've won cashback. Enter UPI PIN.",
            "RBI Alert: Bank account frozen. Share Aadhar.",
            "Share your UPI ID to avoid suspension.",
            "Income Tax refund pending. Click to claim.",
            "Police case registered. Call immediately.",
            "Your Paytm wallet will be blocked.",
            "Final notice: Verify or lose access.",
        ]
    
    async def initialize(self) -> None:
        """Initialize the SBERT model and compute reference embeddings."""
        try:
            self.model = SentenceTransformer(self.model_name)
            
            # Compute embeddings for reference sets
            self.legitimate_embeddings = self.model.encode(
                self.legitimate_samples,
                convert_to_numpy=True
            )
            self.scam_embeddings = self.model.encode(
                self.scam_samples,
                convert_to_numpy=True
            )
            
            # Compute centroids
            self.legitimate_centroid = np.mean(self.legitimate_embeddings, axis=0)
            self.scam_centroid = np.mean(self.scam_embeddings, axis=0)
            
            self._initialized = True
            
        except Exception as e:
            self._initialized = True  # Allow fallback
            self.model = None
    
    async def analyze(
        self,
        message: str,
        conversation_history: Optional[List[Message]] = None,
        metadata: Optional[dict] = None
    ) -> CouncilVote:
        """
        Analyze message using embedding-based anomaly detection.
        """
        if not self._initialized:
            await self.initialize()
        
        if self.model is None:
            return self._fallback_vote(message)
        
        try:
            # Encode the input message
            message_embedding = self.model.encode(message, convert_to_numpy=True)
            
            # Calculate distances to centroids
            dist_to_legitimate = self._cosine_distance(
                message_embedding, 
                self.legitimate_centroid
            )
            dist_to_scam = self._cosine_distance(
                message_embedding,
                self.scam_centroid
            )
            
            # Calculate average distances to individual samples
            avg_dist_legitimate = np.mean([
                self._cosine_distance(message_embedding, emb)
                for emb in self.legitimate_embeddings
            ])
            avg_dist_scam = np.mean([
                self._cosine_distance(message_embedding, emb)
                for emb in self.scam_embeddings
            ])
            
            # Find closest scam sample
            min_dist_scam = np.min([
                self._cosine_distance(message_embedding, emb)
                for emb in self.scam_embeddings
            ])
            
            # Calculate scam score based on relative distances
            # Lower distance to scam centroid = higher scam likelihood
            total_dist = dist_to_legitimate + dist_to_scam + 0.001  # Avoid division by zero
            scam_score = dist_to_legitimate / total_dist
            
            # Adjust based on closest match
            if min_dist_scam < 0.3:
                scam_score = max(scam_score, 0.7)
            
            # Outlier score: how different from legitimate centroid
            outlier_score = dist_to_legitimate
            
            is_scam = scam_score > 0.5
            confidence = scam_score if is_scam else (1 - scam_score)
            
            # Generate features
            features = [
                f"dist_to_legitimate: {dist_to_legitimate:.3f}",
                f"dist_to_scam: {dist_to_scam:.3f}",
                f"outlier_score: {outlier_score:.3f}",
                f"min_scam_distance: {min_dist_scam:.3f}",
            ]
            
            # Generate reasoning
            if is_scam:
                reasoning = f"Message embedding is {dist_to_legitimate:.2f} from legitimate centroid and {dist_to_scam:.2f} from scam centroid. "
                reasoning += f"Semantic similarity suggests scam intent (closer to known scam patterns)."
            else:
                reasoning = f"Message embedding is closer to legitimate message patterns. "
                reasoning += f"Distance to scam cluster: {dist_to_scam:.2f}."
            
            return self.create_vote(
                is_scam=is_scam,
                confidence=confidence,
                reasoning=reasoning,
                features=features
            )
            
        except Exception as e:
            return self._fallback_vote(message)
    
    def _cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine distance between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 1.0
        
        cosine_similarity = dot_product / (norm_a * norm_b)
        return float(1 - cosine_similarity)
    
    def _fallback_vote(self, message: str) -> CouncilVote:
        """Fallback when embedding model is unavailable."""
        return self.create_vote(
            is_scam=False,
            confidence=0.5,
            reasoning="Embedding model unavailable. Returning neutral vote.",
            features=["fallback_mode"]
        )
