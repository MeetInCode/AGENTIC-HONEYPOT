"""
Sample Data Generator for Training ML Models
Generates synthetic scam and legitimate messages for model training.
"""

import json
import random
from typing import List, Dict
from pathlib import Path


class SampleDataGenerator:
    """Generate synthetic training data for scam detection models."""
    
    def __init__(self):
        # Scam templates
        self.scam_templates = {
            "bank_block": [
                "Dear Customer, Your {bank} account will be blocked today due to {reason}. {action}",
                "URGENT: Your {bank} account is being suspended. {action}",
                "{bank} Alert: Account termination notice. {action}",
                "Your {bank} account has been flagged for suspicious activity. {action}",
            ],
            "upi_fraud": [
                "Your UPI ID has been suspended. Share OTP to verify: {contact}",
                "URGENT: UPI transaction failed. Share PIN to retry: {contact}",
                "Your UPI limit exceeded. Verify now at {link}",
                "{bank}: UPI service blocked. Update KYC at {link}",
            ],
            "lottery": [
                "Congratulations! You won Rs {amount} in {lottery}! Call {phone} to claim.",
                "Lucky Draw Winner! You've won {amount} rupees. Share bank details to receive.",
                "{lottery} result: You won Rs. {amount}! Click {link} to claim prize.",
                "You are selected for {amount} cashback! Share UPI ID: {contact}",
            ],
            "kyc": [
                "Your {service} KYC expired. Update immediately at {link}",
                "KYC verification pending. Your {service} will be blocked in 24 hours.",
                "Complete KYC now to avoid {service} suspension. Send Aadhar to {contact}",
                "{service}: KYC update required. Share PAN and Aadhar to verify.",
            ],
            "impersonation": [
                "This is {authority}. A case registered against your number. Call {phone}",
                "{authority} Notice: Your {document} linked to fraud. Verify at {link}",
                "Cyber Crime: Suspicious activity from your account. Contact {phone}",
                "IT Department: Tax refund of Rs {amount} pending. Click {link}",
            ],
        }
        
        # Legitimate templates
        self.legitimate_templates = [
            "Hi {name}, the meeting is scheduled for {time}. Please confirm.",
            "Your order #{order_id} has been shipped. Track at {link}",
            "Thank you for your payment of Rs {amount}. Receipt attached.",
            "Reminder: Your appointment is on {date} at {time}.",
            "Happy birthday {name}! Wishing you a great year ahead.",
            "{name}, please review the attached document and share feedback.",
            "Your {service} subscription has been renewed successfully.",
            "Welcome to {service}! Your account is now active.",
            "Meeting reminder: {topic} at {time} in {location}.",
            "Thanks for attending the event. Here's the feedback form.",
        ]
        
        # Fill-in values
        self.banks = ["SBI", "HDFC", "ICICI", "Axis", "PNB", "BOB", "Kotak"]
        self.services = ["Paytm", "PhonePe", "Google Pay", "Amazon Pay", "BHIM"]
        self.authorities = ["RBI", "Police", "Income Tax", "Cyber Crime", "TRAI"]
        self.lotteries = ["Jio Lucky Draw", "Amazon Lucky Draw", "Flipkart Jackpot"]
        self.documents = ["Aadhar", "PAN", "Bank Account", "Mobile Number"]
        self.reasons = ["incomplete KYC", "suspicious activity", "verification pending", "security update"]
        self.actions = [
            "Verify immediately at {link}",
            "Share OTP to confirm",
            "Call {phone} now",
            "Click {link} to update",
            "Send details to {contact}",
        ]
        
        # Fake data
        self.fake_phones = ["+91-98765", "+91-87654", "+91-76543", "089XX"]
        self.fake_links = ["bit.ly/verify", "tinyurl.com/update", "sbi-verify.xyz", "bank-kyc.in"]
        self.fake_upis = ["verify@upi", "support@ybl", "refund@paytm", "claim@okaxis"]
        self.names = ["Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anita"]
        
    def _fill_template(self, template: str, is_scam: bool = True) -> str:
        """Fill a template with random values."""
        replacements = {
            "{bank}": random.choice(self.banks),
            "{service}": random.choice(self.services),
            "{authority}": random.choice(self.authorities),
            "{lottery}": random.choice(self.lotteries),
            "{document}": random.choice(self.documents),
            "{reason}": random.choice(self.reasons),
            "{action}": random.choice(self.actions),
            "{phone}": random.choice(self.fake_phones) + str(random.randint(10000, 99999)),
            "{link}": random.choice(self.fake_links),
            "{contact}": random.choice(self.fake_upis),
            "{amount}": str(random.choice([5000, 10000, 25000, 50000, 100000])),
            "{name}": random.choice(self.names),
            "{time}": f"{random.randint(9, 18)}:{random.choice(['00', '30'])} {'AM' if random.random() > 0.5 else 'PM'}",
            "{date}": f"Jan {random.randint(1, 31)}, 2024",
            "{order_id}": str(random.randint(100000, 999999)),
            "{topic}": random.choice(["Project Review", "Team Sync", "Planning", "Demo"]),
            "{location}": random.choice(["Conference Room", "Online", "Office"]),
        }
        
        result = template
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        # Handle nested replacements
        for key, value in replacements.items():
            result = result.replace(key, value)
        
        return result
    
    def generate_scam_messages(self, count: int = 100) -> List[Dict]:
        """Generate synthetic scam messages."""
        messages = []
        
        for _ in range(count):
            category = random.choice(list(self.scam_templates.keys()))
            template = random.choice(self.scam_templates[category])
            text = self._fill_template(template, is_scam=True)
            
            messages.append({
                "text": text,
                "label": 1,
                "category": category,
            })
        
        return messages
    
    def generate_legitimate_messages(self, count: int = 100) -> List[Dict]:
        """Generate synthetic legitimate messages."""
        messages = []
        
        for _ in range(count):
            template = random.choice(self.legitimate_templates)
            text = self._fill_template(template, is_scam=False)
            
            messages.append({
                "text": text,
                "label": 0,
                "category": "legitimate",
            })
        
        return messages
    
    def generate_dataset(self, scam_count: int = 100, legit_count: int = 100) -> List[Dict]:
        """Generate a balanced dataset."""
        scams = self.generate_scam_messages(scam_count)
        legit = self.generate_legitimate_messages(legit_count)
        
        dataset = scams + legit
        random.shuffle(dataset)
        
        return dataset
    
    def save_dataset(self, filepath: str, scam_count: int = 100, legit_count: int = 100):
        """Generate and save dataset to JSON file."""
        dataset = self.generate_dataset(scam_count, legit_count)
        
        with open(filepath, 'w') as f:
            json.dump(dataset, f, indent=2)
        
        print(f"Dataset saved to {filepath}")
        print(f"  Scam messages: {scam_count}")
        print(f"  Legitimate messages: {legit_count}")
        print(f"  Total: {len(dataset)}")


def main():
    """Generate sample datasets."""
    generator = SampleDataGenerator()
    
    # Create data directory
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Generate training data
    generator.save_dataset(
        str(data_dir / "training_data.json"),
        scam_count=200,
        legit_count=200
    )
    
    # Generate test data
    generator.save_dataset(
        str(data_dir / "test_data.json"),
        scam_count=50,
        legit_count=50
    )
    
    print("\n✅ Sample data generated!")


if __name__ == "__main__":
    main()
