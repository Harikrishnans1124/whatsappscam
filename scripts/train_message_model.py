"""Train and save TF-IDF + Logistic Regression model for message scam classification."""

from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "data" / "models"
MODEL_PATH = MODEL_DIR / "message_classifier.joblib"

# Labeled training dataset: 1 = Scam / Fraud / Spam, 0 = Legitimate chat / inquiry
DATASET = [
    # --- SCAM / FRAUD (Label 1) ---
    ("Dear customer, you won a free iPhone 15 in Flipkart lucky draw! Click link to claim your prize immediately.", 1),
    ("Congratulations! Your number was selected for Rs 25,00,000 lottery jackpot from KBC. Send registration fee to activate.", 1),
    ("Urgent! Your electricity power will be disconnected tonight at 9:30 PM. Call power officer immediately on 9876543210.", 1),
    ("Nike clearance sale! 90% discount on all Air Jordan sneakers today only. Last 2 pairs left in stock, pay advance now.", 1),
    ("Please share the OTP you just received to verify your bank account and prevent card blocking.", 1),
    ("Send me the one-time password to confirm your refund of Rs 4,999 from Amazon.", 1),
    ("To process your delivery cancellation, install AnyDesk on your mobile phone and grant permission to our executive.", 1),
    ("Please download TeamViewer QuickSupport application so our technical support team can assist you with your wallet KYC.", 1),
    ("Sir, pay token amount of Rs 500 now to hold this iPhone 14 Pro Max. Remaining cash on delivery.", 1),
    ("Courier charges of Rs 250 must be paid in advance via Google Pay before dispatching package.", 1),
    ("Move to personal WhatsApp chat for exclusive direct wholesale prices not available on app.", 1),
    ("DM me on Telegram @deal_king for secret discounted luxury watches and gadgets.", 1),
    ("Earn Rs 3,000 to Rs 8,000 daily working from home just by liking YouTube videos and Google reviews.", 1),
    ("Part time job opportunity: review hotels and get paid instantly. Pay security deposit of Rs 1,000 to start.", 1),
    ("Your SBI net banking account is suspended due to missing PAN. Update PAN now at http://sbi-kyc-update.shop.", 1),
    ("Exclusive flash offer! Flat 80% off on Sony Bravia TV. Valid for 10 minutes only. Hurry up, book now!", 1),
    ("Forward the 6 digit code sent by bank to complete your gift voucher redemption.", 1),
    ("Install RustDesk remote application to resolve failed payment transaction with customer care.", 1),
    ("Pay Rs 99 delivery fee immediately to release your parcel detained at customs warehouse.", 1),
    ("Last chance! Today only mega deal. Send payment to 9876543210@ybl to book your order.", 1),
    ("Your SIM card will be deactivated within 24 hours. Call Airtel customer executive immediately.", 1),
    ("Apple official clearance store: iPhone 13 brand new sealed box for only Rs 15,000. Limited stock act fast.", 1),
    ("Refund department: Please share your card expiry date and CVV along with OTP to reverse the failed transaction.", 1),
    ("Contact me personally on 9876543210 for special offline order discount outside Flipkart.", 1),
    ("Exclusive Puma sneakers flat 85% discount. Limited time deal expires in 1 hour.", 1),
    ("Congratulations! You are selected for Amazon lucky shopper reward. Transfer Rs 350 shipping charges.", 1),
    ("Install our support APK file attached to this message to verify your identity.", 1),
    ("Quick verification needed: read out the OTP sent on your SMS.", 1),
    ("Guaranteed stock reservation if you make 50% advance payment right now.", 1),
    ("WhatsApp lottery winner! Your mobile number won 50 Lakhs cash prize. Contact manager on WhatsApp.", 1),
    ("Hurry up! Flash clearance deal ends at midnight. Only 1 piece left in size UK 8.", 1),
    ("Send money to personal UPI ID to get extra 20% discount on order.", 1),
    ("Technical error in transaction. Share your screen via AnyDesk app so our officer can rectify.", 1),
    ("Your credit card reward points worth Rs 9,850 are expiring today. Redeem at http://reward-points.biz.", 1),
    ("Pre-book PlayStation 5 for Rs 2,000 advance token. Balance on doorstep delivery.", 1),
    ("Urgent: KYC verification incomplete. Download screen share app to prevent debit card block.", 1),
    ("Give me the verification code to activate your 50% cashback coupon.", 1),
    ("Dear user, claim your unclaimed tax refund of Rs 18,500. Click here to verify your account details.", 1),
    ("Switch to personal chat on WhatsApp for private deals and bill-free discount.", 1),
    ("Advance payment of Rs 1,500 required for booking delivery slot.", 1),
    ("Special festival loot! Smart LED TV for Rs 3,999 today only. Offer valid till stock lasts.", 1),
    ("Bank alert: Suspicious login from Delhi. Provide OTP to block transaction immediately.", 1),
    ("Download QuickSupport app from play store and read out the 9 digit ID code.", 1),
    ("Win guaranteed cash every hour! Spin the lucky wheel now.", 1),
    ("Official brand factory outlet clearance: all shoes flat Rs 999. Pay advance courier charge.", 1),
    ("Hello sir, message me privately on WhatsApp 9876543210 to buy without GST charges.", 1),
    ("Your parcel has been put on hold due to wrong address. Pay Rs 45 redelivery fee at http://ind-post.shop.", 1),
    ("Tell me the OTP sent to your phone to finish order dispatch.", 1),
    ("Work from home task job. Guaranteed Rs 5,000 per day earnings. Join telegram group.", 1),
    ("Only 2 units remaining! Urgent payment needed to secure reservation.", 1),

    # --- LEGITIMATE / SAFE CHATS (Label 0) ---
    ("Hi, do you have this shirt available in medium size and blue color?", 0),
    ("Could you please tell me when my order #48291 will be shipped?", 0),
    ("What is your store return and exchange policy if the shoes do not fit?", 0),
    ("Is cash on delivery available for delivery to pincode 560001?", 0),
    ("Thank you, I received the package in good condition yesterday.", 0),
    ("What are the store opening hours on Sundays?", 0),
    ("Can I get a tax invoice with GST number for my business purchase?", 0),
    ("Hello, I wanted to inquire about the manufacturer warranty on this laptop.", 0),
    ("Please let me know if you restock size 10 in the white sneakers.", 0),
    ("Where is your physical retail store located in Bangalore?", 0),
    ("Can I cancel my order before it has been dispatched from your warehouse?", 0),
    ("Hi, do you offer free delivery for orders above Rs 1,000?", 0),
    ("Could you share the dimensions and weight of this dining table?", 0),
    ("I have submitted an exchange request on your official website yesterday.", 0),
    ("Does this smartphone support 5G bands in India?", 0),
    ("What material is used for the sole of these running shoes?", 0),
    ("Is there any discount if I purchase 5 pieces for our college event?", 0),
    ("Can I track my shipment using the BlueDart tracking number you sent?", 0),
    ("The delivery boy came but I was away. Can you reschedule delivery for tomorrow?", 0),
    ("Do you accept American Express credit cards on your checkout page?", 0),
    ("Hello, is the color in the picture identical to the actual product?", 0),
    ("Could you confirm if this watch is water resistant up to 50 meters?", 0),
    ("I would like to update my shipping address for the order placed this morning.", 0),
    ("Are these headphones compatible with iPhone and Mac?", 0),
    ("Hi, does the dress come with lining inside?", 0),
    ("How long does standard delivery usually take to Kolkata?", 0),
    ("Could you please help me find the right size chart for kids clothing?", 0),
    ("I checked your website catalog and had a question about the fabric care instructions.", 0),
    ("Thank you for the quick support, the issue has been resolved.", 0),
    ("Can I pick up the item directly from your store in Indiranagar?", 0),
    ("Does this package include the charging adapter and USB-C cable?", 0),
    ("Is the product made in India?", 0),
    ("Hello, my payment succeeded on your website and I got order confirmation #99281.", 0),
    ("Can you provide the expiry date for this skincare cream before I place order?", 0),
    ("We would like to make a bulk corporate inquiry for diwali gift hampers.", 0),
    ("Is assembly service included with this study table delivery?", 0),
    ("Hello, do you have any formal shoes in brown leather?", 0),
    ("I checked the order status on your app and it shows out for delivery.", 0),
    ("Could you guide me on how to return the defective piece through the app?", 0),
    ("Hi, is this cotton fabric pre-shrunk or will it shrink after washing?", 0),
    ("Does this backpack have a dedicated padded laptop compartment?", 0),
    ("Hello, can you send the user manual PDF for this mixer grinder?", 0),
    ("Thank you, the delivery arrived on time and the fit is perfect.", 0),
    ("Are gift wrapping options available during checkout?", 0),
    ("I received an email stating my refund has been initiated to original payment mode.", 0),
    ("Do you offer express one-day delivery in Mumbai?", 0),
    ("Hi, what is the battery life on a single charge for these wireless earbuds?", 0),
    ("Can I exchange this for a larger size at your local franchise store?", 0),
    ("Please confirm if the price shown is inclusive of all taxes.", 0),
    ("Hello, is customer support available on WhatsApp during weekends?", 0),
]


def train_model() -> Pipeline:
    """Train TF-IDF + Logistic Regression pipeline and save model artifact."""
    texts = [item[0] for item in DATASET]
    labels = [item[1] for item in DATASET]

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.25, random_state=42, stratify=labels
    )

    pipeline = Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=1500,
                lowercase=True,
                stop_words="english",
            ),
        ),
        (
            "clf",
            LogisticRegression(
                C=2.0,
                class_weight="balanced",
                random_state=42,
                solver="liblinear",
            ),
        ),
    ])

    pipeline.fit(X_train, y_train)

    # Evaluate
    preds = pipeline.predict(X_test)
    report = classification_report(y_test, preds)
    print("Classification Report on Test Set:")
    print(report)

    # Save
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model successfully saved to {MODEL_PATH}")
    return pipeline


if __name__ == "__main__":
    train_model()
