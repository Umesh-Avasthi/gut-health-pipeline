"""
Utility functions for OTP and SMS sending
"""
import logging

logger = logging.getLogger(__name__)


def send_otp_sms(phone, otp_code):
    """
    Send OTP via SMS.
    
    For development: Prints OTP to console
    For production: Integrate with SMS service like Twilio, AWS SNS, etc.
    
    Args:
        phone: Phone number to send OTP to
        otp_code: The OTP code to send
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        # TODO: Replace with actual SMS service integration
        # Example with Twilio:
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # message = client.messages.create(
        #     body=f'Your OTP code is: {otp_code}',
        #     from_='+1234567890',
        #     to=phone
        # )
        
        # For development: Print to console
        print(f"\n{'='*50}")
        print(f"SMS OTP SENT TO: {phone}")
        print(f"OTP CODE: {otp_code}")
        print(f"{'='*50}\n")
        
        logger.info(f"OTP sent to {phone}: {otp_code}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send OTP to {phone}: {str(e)}")
        return False

