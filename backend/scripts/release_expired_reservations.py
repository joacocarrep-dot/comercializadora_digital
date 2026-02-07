#!/usr/bin/env python3
"""
Periodic job to release expired stock reservations and cancel orders.

This script should be run periodically (e.g., every 1 minute) to:
1. Find active stock reservations that have expired (expires_at <= now)
2. Release those reservations (decrement inventory.reserved_qty)
3. Cancel associated orders with reason 'reservation_timeout' or 'payment_timeout'
4. Optionally return items from cancelled orders to user's cart

Usage:
    python -m backend.scripts.release_expired_reservations [--limit N] [--dry-run]

Environment variables:
    DATABASE_URL: PostgreSQL connection string
"""
import asyncio
import logging
import sys
from argparse import ArgumentParser
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.core.database import get_db
from app.services.order_service import OrderService
from app.services.stock_reservation_service import StockReservationService
from app.models.order import OrderStatus
from app.models.stock_reservation import StockReservationStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def release_expired_reservations(
    session: AsyncSession,
    limit: int = 100,
    dry_run: bool = False,
) -> dict:
    """
    Release expired stock reservations and cancel associated orders.

    Args:
        session: Async database session
        limit: Maximum number of reservations to process
        dry_run: If True, only log what would be done without making changes

    Returns:
        Dictionary with processing results
    """
    reservation_service = StockReservationService(session)
    order_service = OrderService(session)

    # Get expired reservations
    expired_reservations = await reservation_service.get_expired_reservations(limit=limit)
    
    if not expired_reservations:
        logger.info("No expired reservations found")
        return {
            "processed": 0,
            "released": 0,
            "orders_cancelled": 0,
            "errors": [],
        }

    logger.info(f"Found {len(expired_reservations)} expired reservations")

    results = {
        "processed": len(expired_reservations),
        "released": 0,
        "orders_cancelled": 0,
        "errors": [],
    }

    # Process each expired reservation
    for reservation in expired_reservations:
        try:
            logger.info(
                f"Processing expired reservation {reservation.id} for order {reservation.order_id}, "
                f"expired at {reservation.expires_at}"
            )

            # Release the reservation
            if not dry_run:
                await reservation_service.release_reservation(
                    reservation_id=reservation.id,
                    reason="reservation_expired",
                    released_by=None,  # System job
                )
                results["released"] += 1
            else:
                logger.info(f"DRY RUN: Would release reservation {reservation.id}")

            # Check if all reservations for this order are released
            active_reservations = await reservation_service.get_active_reservations_for_order(
                reservation.order_id
            )

            # If no active reservations remain, cancel the order
            if not active_reservations:
                order = await order_service.order_repo.get_by_id(reservation.order_id)
                if order and order.status in [
                    OrderStatus.RESERVED,
                    OrderStatus.PAYMENT_PENDING,
                ]:
                    # Determine cancellation reason based on order status
                    if order.status == OrderStatus.RESERVED:
                        reason = "reservation_timeout"
                        notes = "Order cancelled because stock reservation expired without payment"
                    else:  # PAYMENT_PENDING
                        reason = "payment_timeout"
                        notes = "Order cancelled because payment was not completed within timeout period"

                    if not dry_run:
                        await order_service.cancel_order(
                            order_id=reservation.order_id,
                            reason=reason,
                            notes=notes,
                            changed_by=None,  # System job
                        )
                        results["orders_cancelled"] += 1
                        logger.info(f"Cancelled order {order.order_number} ({order.id}) due to {reason}")
                    else:
                        logger.info(f"DRY RUN: Would cancel order {order.order_number} due to {reason}")

        except Exception as e:
            error_msg = f"Error processing reservation {reservation.id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results["errors"].append({
                "reservation_id": str(reservation.id),
                "order_id": str(reservation.order_id),
                "error": str(e),
            })

    return results


async def return_items_to_cart(session: AsyncSession, order_id: str) -> None:
    """
    Return items from cancelled order to user's cart.
    
    This is a placeholder implementation. In a complete implementation,
    this would:
    1. Find or create cart for the user
    2. Add items from cancelled order to cart
    3. Only add products that are still active in the storefront
    
    Args:
        session: Async database session
        order_id: Order ID
    """
    # TODO: Implement return to cart logic
    # This would require CartService and ProductService integration
    logger.info(f"TODO: Return items from order {order_id} to user's cart")
    pass


async def main() -> int:
    """Main entry point for the job."""
    parser = ArgumentParser(description="Release expired stock reservations")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of reservations to process (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate processing without making changes",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        help="Database connection URL (overrides DATABASE_URL env var)",
    )
    args = parser.parse_args()

    # Get database URL
    database_url = args.database_url
    if not database_url:
        # Try to get from environment or use default
        import os
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL environment variable not set and --database-url not provided")
            return 1

    # Create database engine
    try:
        engine = create_async_engine(database_url, echo=False)
        
        async with AsyncSession(engine) as session:
            async with session.begin():
                logger.info(
                    f"Starting expired reservations cleanup (limit: {args.limit}, dry-run: {args.dry_run})"
                )
                
                results = await release_expired_reservations(
                    session=session,
                    limit=args.limit,
                    dry_run=args.dry_run,
                )
                
                # Log summary
                logger.info(
                    f"Cleanup completed: "
                    f"Processed: {results['processed']}, "
                    f"Released: {results['released']}, "
                    f"Orders cancelled: {results['orders_cancelled']}, "
                    f"Errors: {len(results['errors'])}"
                )
                
                if results["errors"]:
                    for error in results["errors"]:
                        logger.error(f"Error details: {error}")
                
                # Commit transaction if not dry-run
                if not args.dry_run:
                    await session.commit()
                    logger.info("Transaction committed")
                else:
                    await session.rollback()
                    logger.info("DRY RUN: Transaction rolled back")
                
                return 0 if len(results["errors"]) == 0 else 2
                
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))