"""
OTP service for generating, sending, and validating one-time passwords.

Handles OTP code generation, expiration tracking, and basic validation
for customer authentication via email or phone.
"""
import random
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException
from app.models.otp_code import OTPCode, OTPPurpose
from app.repositories.otp_repo import OTPRepository


class OTPService:
    """
    Service for OTP business logic operations.

    Attributes:
        session: Async database session
        otp_repo: OTPRepository for OTPCode model operations
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize OTP service with database session.

        Args:
            session: Async database session
        """
        self.session = session
        self.otp_repo = OTPRepository(session)

    async def generate_code(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        purpose: OTPPurpose = OTPPurpose.LOGIN,
        storefront_id: Optional[uuid.UUID] = None,
        expires_in_minutes: int = 10,
    ) -> OTPCode:
        """
        Generate a new 6-digit OTP code.

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            purpose: Purpose of the OTP code
            storefront_id: Optional storefront ID for scoping
            expires_in_minutes: Code expiration time in minutes (default: 10)

        Returns:
            Created OTPCode instance

        Raises:
            BadRequestException: If neither email nor phone provided
            ConflictException: If too many active codes exist for contact
        """
        if not email and not phone:
            raise BadRequestException("Either email or phone must be provided")

        # Validate contact information
        if email:
            await self._validate_email(email)
        if phone:
            await self._validate_phone(phone)

        # Rate limiting: check active codes count
        active_count = await self.otp_repo.get_active_codes_count(
            email=email, phone=phone, storefront_id=storefront_id
        )
        if active_count >= 3:  # Max 3 active codes per contact
            raise ConflictException(
                "Too many active verification codes. Please wait before requesting a new one."
            )

        # Generate 6-digit code
        code = str(random.randint(100000, 999999))

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

        # Create OTP code
        otp_data = {
            "email": email,
            "phone": phone,
            "code": code,
            "purpose": purpose,
            "expires_at": expires_at,
            "used": False,
            "storefront_id": storefront_id,
        }

        return await self.otp_repo.create(**otp_data)

    async def send_code(
        self,
        otp_code: OTPCode,
        channel: str = "whatsapp",
    ) -> Dict[str, Any]:
        """
        Send OTP code via the specified channel.

        Note: This is a placeholder implementation. In production,
        this would integrate with WhatsApp Business API, SendGrid,
        Twilio, or other notification services.

        Args:
            otp_code: OTPCode instance to send
            channel: Preferred channel (whatsapp, email, sms)

        Returns:
            Dictionary with sending results
        """
        # Placeholder implementation
        # In production, this would:
        # 1. Check channel availability based on contact (email/phone)
        # 2. Select fallback channels if primary unavailable
        # 3. Send via appropriate service with templates
        # 4. Log delivery status

        contact = otp_code.email if otp_code.email else otp_code.phone
        contact_type = "email" if otp_code.email else "phone"

        # Simulate sending
        result = {
            "code_id": str(otp_code.id),
            "contact": contact,
            "contact_type": contact_type,
            "channel": channel,
            "code": otp_code.code,  # In production, never expose code in response
            "expires_at": otp_code.expires_at.isoformat(),
            "purpose": otp_code.purpose.value,
            "sent": True,
            "simulated": True,  # Indicates this is a placeholder
            "message": f"OTP code would be sent via {channel} to {contact_type}: {contact}",
        }

        return result

    async def validate_code(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        code: str = "",
        purpose: OTPPurpose = OTPPurpose.LOGIN,
        storefront_id: Optional[uuid.UUID] = None,
    ) -> OTPCode:
        """
        Validate an OTP code.

        Checks if code exists, is not expired, and not used.
        Marks code as used upon successful validation.

        Args:
            email: Email address (optional if phone provided)
            phone: Phone number (optional if email provided)
            code: 6-digit verification code
            purpose: Purpose of the OTP code
            storefront_id: Optional storefront ID for scoping

        Returns:
            Validated OTPCode instance

        Raises:
            BadRequestException: If code is invalid, expired, or already used
        """
        if not email and not phone:
            raise BadRequestException("Either email or phone must be provided")

        if not code or len(code) != 6 or not code.isdigit():
            raise BadRequestException("Invalid OTP code format. Must be 6 digits.")

        # Find valid code
        otp_code = await self.otp_repo.find_valid_code(
            email=email,
            phone=phone,
            code=code,
            purpose=purpose,
            storefront_id=storefront_id,
        )

        if not otp_code:
            # Check if code exists but expired or used
            recent_codes = await self.otp_repo.find_recent_codes(
                email=email,
                phone=phone,
                purpose=purpose,
                limit=1,
                storefront_id=storefront_id,
            )

            if recent_codes:
                recent_code = recent_codes[0]
                if recent_code.used:
                    raise BadRequestException("OTP code has already been used.")
                elif recent_code.expires_at <= datetime.utcnow():
                    raise BadRequestException("OTP code has expired.")
                else:
                    # Code exists but doesn't match (wrong code)
                    raise BadRequestException("Invalid OTP code.")
            else:
                raise BadRequestException("No OTP code found for this contact.")

        # Mark code as used
        await self.otp_repo.mark_code_as_used(otp_code.id)

        # Refresh and return
        await self.session.refresh(otp_code)
        return otp_code

    async def cleanup_expired_codes(
        self, older_than_hours: int = 24
    ) -> int:
        """
        Clean up expired OTP codes.

        Args:
            older_than_hours: Delete codes older than this many hours

        Returns:
            Number of codes deleted
        """
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        return await self.otp_repo.cleanup_expired_codes(older_than=cutoff)

    async def _validate_email(self, email: str) -> None:
        """
        Validate email format.

        Args:
            email: Email address to validate

        Raises:
            BadRequestException: If email format is invalid
        """
        # Basic email validation
        if "@" not in email or "." not in email:
            raise BadRequestException("Invalid email format")

        # Additional validation could be added here
        # e.g., DNS validation, disposable email check, etc.

    async def _validate_phone(self, phone: str) -> None:
        """
        Validate phone number format.

        Args:
            phone: Phone number to validate

        Raises:
            BadRequestException: If phone format is invalid
        """
        # Basic phone validation - remove non-digits and check length
        digits = "".join(filter(str.isdigit, phone))
        if len(digits) < 7 or len(digits) > 15:
            raise BadRequestException("Invalid phone number format")

        # Additional validation could be added here
        # e.g., country code validation, carrier lookup, etc.