"""
Integration tests for concurrent database operations - Task 3.5.2.

This module tests database behavior under concurrent load to ensure
proper isolation, locking, and consistency mechanisms.
"""

import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text
from typing import Dict, Any, List
import random

from app.models.order_async import Order, OrderItem
from app.models.menu_async import MenuItem, MenuCategory
from app.models.location_async import Location
from app.db_async import get_db
from app.utils.order_utils_async import create_order_with_validation
from app.utils.menu_db_store_async import update_menu_item_availability


@pytest_asyncio.fixture
async def db_session():
    """Create a real database session for concurrent testing."""
    async for session in get_db():
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def test_location(db_session):
    """Create a test location for concurrent operations."""
    location = Location(
        id="concurrent_test_location",
        name="Concurrent Test Restaurant",
        address="123 Concurrent Street",
        phone="+1234567890",
        email="concurrent@test.com",
        is_active=True
    )
    db_session.add(location)
    await db_session.commit()
    await db_session.refresh(location)
    return location


@pytest_asyncio.fixture
async def test_menu_items(db_session):
    """Create test menu items for concurrent operations."""
    # Create a category first
    category = MenuCategory(
        id=1,
        name="Test Rolls",
        description="Test category for rolls",
        order_index=1
    )
    db_session.add(category)
    
    items = []
    for i in range(10):  # Create multiple items for concurrent testing
        item = MenuItem(
            plu=f"CONCURRENT_{i:03d}",
            name=f"Test Roll {i}",
            description=f"Test roll number {i}",
            price=1200 + (i * 50),  # Varying prices
            is_available=True,
            category_id=1,
            inventory_count=100  # Start with good inventory
        )
        items.append(item)
        db_session.add(item)
    
    await db_session.commit()
    
    for item in items:
        await db_session.refresh(item)
    
    return items


class TestConcurrentDatabaseOperations:
    """Test concurrent database operations for consistency and performance."""
    
    @pytest.mark.asyncio
    async def test_concurrent_order_creation(self, db_session, test_location, test_menu_items):
        """Test multiple orders being created simultaneously."""
        
        async def create_concurrent_order(order_id: int, customer_id: int):
            """Create a single order concurrently."""
            order_data = {
                "location_id": test_location.id,
                "customer_name": f"Customer {customer_id}",
                "customer_phone": f"+123456{customer_id:04d}",
                "customer_email": f"customer{customer_id}@concurrent.com",
                "order_type": "pickup",
                "items": [
                    {
                        "plu": f"CONCURRENT_{random.randint(0, 4):03d}",  # Random item from first 5
                        "quantity": random.randint(1, 3),
                        "price": 1200,
                        "modifiers": []
                    }
                ],
                "subtotal": 1200,
                "tax": 120,
                "total": 1320
            }
            
            try:
                return await create_order_with_validation(db_session, order_data)
            except Exception as e:
                return e
        
        # Create 20 concurrent orders
        tasks = [
            create_concurrent_order(i, i) 
            for i in range(20)
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Analyze results
        successful_orders = [r for r in results if isinstance(r, Order)]
        failed_orders = [r for r in results if isinstance(r, Exception)]
        
        print(f"Concurrent order creation took {end_time - start_time:.2f} seconds")
        print(f"Successful orders: {len(successful_orders)}")
        print(f"Failed orders: {len(failed_orders)}")
        
        # Should have some successful orders (allowing for some failures due to constraints)
        assert len(successful_orders) > 0
        
        # Verify orders in database
        order_count = await db_session.execute(
            text("SELECT COUNT(*) FROM orders WHERE location_id = :location_id"),
            {"location_id": test_location.id}
        )
        db_order_count = order_count.scalar()
        
        # Database count should match successful orders
        assert db_order_count >= len(successful_orders)
    
    @pytest.mark.asyncio
    async def test_concurrent_menu_updates(self, db_session, test_menu_items):
        """Test concurrent menu item updates for race conditions."""
        
        async def update_menu_item_concurrent(item_plu: str, operation: str):
            """Update a menu item concurrently."""
            try:
                if operation == "disable":
                    await update_menu_item_availability(db_session, item_plu, False)
                elif operation == "enable":
                    await update_menu_item_availability(db_session, item_plu, True)
                elif operation == "update_price":
                    # Simulate price update
                    result = await db_session.execute(
                        text("UPDATE menu_items SET price = price + 100 WHERE plu = :plu"),
                        {"plu": item_plu}
                    )
                    await db_session.commit()
                elif operation == "update_inventory":
                    # Simulate inventory update
                    result = await db_session.execute(
                        text("UPDATE menu_items SET inventory_count = inventory_count - 1 WHERE plu = :plu"),
                        {"plu": item_plu}
                    )
                    await db_session.commit()
                
                return f"Success: {operation} on {item_plu}"
            except Exception as e:
                await db_session.rollback()
                return f"Error: {operation} on {item_plu} - {str(e)}"
        
        # Create concurrent updates on the same items
        target_item = test_menu_items[0]
        tasks = []
        
        # Mix different operations on the same item
        operations = ["disable", "enable", "update_price", "update_inventory"]
        for i in range(40):  # 40 concurrent operations
            operation = operations[i % len(operations)]
            tasks.append(update_menu_item_concurrent(target_item.plu, operation))
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"Concurrent menu updates took {end_time - start_time:.2f} seconds")
        
        # Count successful vs failed operations
        successful_ops = [r for r in results if isinstance(r, str) and "Success" in r]
        failed_ops = [r for r in results if isinstance(r, str) and "Error" in r]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        print(f"Successful operations: {len(successful_ops)}")
        print(f"Failed operations: {len(failed_ops)}")
        print(f"Exceptions: {len(exceptions)}")
        
        # Should have completed without major exceptions
        assert len(exceptions) < len(tasks) * 0.1  # Less than 10% exceptions
        
        # Verify final state is consistent
        final_item = await db_session.execute(
            text("SELECT * FROM menu_items WHERE plu = :plu"),
            {"plu": target_item.plu}
        )
        item_data = final_item.fetchone()
        assert item_data is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_inventory_deduction(self, db_session, test_menu_items):
        """Test concurrent inventory deduction for race conditions."""
        
        # Set initial inventory for test item
        test_item = test_menu_items[0]
        await db_session.execute(
            text("UPDATE menu_items SET inventory_count = 50 WHERE plu = :plu"),
            {"plu": test_item.plu}
        )
        await db_session.commit()
        
        async def deduct_inventory(order_id: int, quantity: int):
            """Simulate inventory deduction during order creation."""
            try:
                # Simulate atomic inventory check and deduction
                async with db_session.begin():
                    # Check current inventory
                    result = await db_session.execute(
                        text("SELECT inventory_count FROM menu_items WHERE plu = :plu FOR UPDATE"),
                        {"plu": test_item.plu}
                    )
                    current_inventory = result.scalar()
                    
                    if current_inventory >= quantity:
                        # Deduct inventory
                        await db_session.execute(
                            text("UPDATE menu_items SET inventory_count = inventory_count - :qty WHERE plu = :plu"),
                            {"qty": quantity, "plu": test_item.plu}
                        )
                        return f"Order {order_id}: Deducted {quantity} (remaining: {current_inventory - quantity})"
                    else:
                        raise ValueError(f"Insufficient inventory: {current_inventory} < {quantity}")
                        
            except Exception as e:
                return f"Order {order_id}: Failed - {str(e)}"
        
        # Create 30 concurrent orders trying to deduct inventory
        tasks = [
            deduct_inventory(i, random.randint(1, 3))
            for i in range(30)
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"Concurrent inventory deduction took {end_time - start_time:.2f} seconds")
        
        # Analyze results
        successful_deductions = [r for r in results if isinstance(r, str) and "Deducted" in r]
        failed_deductions = [r for r in results if isinstance(r, str) and "Failed" in r]
        
        print(f"Successful deductions: {len(successful_deductions)}")
        print(f"Failed deductions: {len(failed_deductions)}")
        
        # Verify final inventory is consistent
        final_inventory = await db_session.execute(
            text("SELECT inventory_count FROM menu_items WHERE plu = :plu"),
            {"plu": test_item.plu}
        )
        remaining_inventory = final_inventory.scalar()
        
        print(f"Final inventory: {remaining_inventory}")
        
        # Inventory should not go negative
        assert remaining_inventory >= 0
        
        # Total deducted + remaining should equal original (50)
        total_deducted = sum([
            int(r.split("Deducted ")[1].split(" ")[0]) 
            for r in successful_deductions
        ])
        
        assert total_deducted + remaining_inventory == 50
    
    @pytest.mark.asyncio 
    async def test_concurrent_order_and_menu_operations(self, db_session, test_location, test_menu_items):
        """Test concurrent orders while menu is being updated."""
        
        async def create_order_task(order_id: int):
            """Create an order while menu might be changing."""
            order_data = {
                "location_id": test_location.id,
                "customer_name": f"Mixed Customer {order_id}",
                "customer_phone": f"+155566{order_id:04d}",
                "customer_email": f"mixed{order_id}@test.com",
                "order_type": "delivery",
                "items": [
                    {
                        "plu": f"CONCURRENT_{random.randint(0, 4):03d}",
                        "quantity": 1,
                        "price": 1250,
                        "modifiers": []
                    }
                ],
                "subtotal": 1250,
                "tax": 125,
                "total": 1375,
                "delivery_address": "123 Mixed Test St"
            }
            
            try:
                return await create_order_with_validation(db_session, order_data)
            except Exception as e:
                return e
        
        async def update_menu_task(update_id: int):
            """Update menu items while orders are being created."""
            item_plu = f"CONCURRENT_{random.randint(0, 4):03d}"
            try:
                # Random menu operations
                operations = [
                    lambda: update_menu_item_availability(db_session, item_plu, True),
                    lambda: update_menu_item_availability(db_session, item_plu, False),
                ]
                
                operation = random.choice(operations)
                await operation()
                return f"Menu update {update_id}: Success"
            except Exception as e:
                return f"Menu update {update_id}: Failed - {str(e)}"
        
        # Mix order creation and menu updates
        tasks = []
        
        # 15 order creation tasks
        for i in range(15):
            tasks.append(create_order_task(i))
        
        # 10 menu update tasks
        for i in range(10):
            tasks.append(update_menu_task(i))
        
        # Shuffle to mix operations
        random.shuffle(tasks)
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"Mixed concurrent operations took {end_time - start_time:.2f} seconds")
        
        # Analyze results
        order_results = results[:15]  # First 15 were order tasks
        menu_results = results[15:]   # Last 10 were menu tasks
        
        successful_orders = [r for r in order_results if isinstance(r, Order)]
        successful_menu_updates = [r for r in menu_results if isinstance(r, str) and "Success" in r]
        
        print(f"Successful orders: {len(successful_orders)}")
        print(f"Successful menu updates: {len(successful_menu_updates)}")
        
        # Should have some successful operations of both types
        assert len(successful_orders) > 0
        assert len(successful_menu_updates) > 0
    
    @pytest.mark.asyncio
    async def test_database_connection_pool_under_load(self, db_session, test_location, test_menu_items):
        """Test database connection pool behavior under concurrent load."""
        
        async def database_operation(op_id: int):
            """Perform a database operation that might stress the connection pool."""
            try:
                # Create a new session to test connection pooling
                async for session in get_db():
                    try:
                        # Perform various database operations
                        if op_id % 3 == 0:
                            # Read operation
                            result = await session.execute(
                                text("SELECT COUNT(*) FROM menu_items WHERE is_available = true")
                            )
                            count = result.scalar()
                            return f"Read op {op_id}: {count} items"
                        
                        elif op_id % 3 == 1:
                            # Write operation
                            await session.execute(
                                text("UPDATE menu_items SET updated_at = NOW() WHERE plu = :plu"),
                                {"plu": f"CONCURRENT_{op_id % 5:03d}"}
                            )
                            await session.commit()
                            return f"Write op {op_id}: Updated timestamp"
                        
                        else:
                            # Transaction operation
                            async with session.begin():
                                result = await session.execute(
                                    text("SELECT price FROM menu_items WHERE plu = :plu"),
                                    {"plu": f"CONCURRENT_{op_id % 5:03d}"}
                                )
                                price = result.scalar()
                                
                                # Simulate some processing time
                                await asyncio.sleep(0.01)
                                
                                await session.execute(
                                    text("UPDATE menu_items SET price = :price WHERE plu = :plu"),
                                    {"price": price, "plu": f"CONCURRENT_{op_id % 5:03d}"}
                                )
                            
                            return f"Transaction op {op_id}: Price check/update"
                    
                    finally:
                        await session.close()
                        
            except Exception as e:
                return f"Op {op_id}: Error - {str(e)}"
        
        # Create 50 concurrent database operations
        tasks = [database_operation(i) for i in range(50)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"Connection pool test took {end_time - start_time:.2f} seconds")
        
        # Analyze results
        successful_ops = [r for r in results if isinstance(r, str) and "Error" not in r]
        failed_ops = [r for r in results if isinstance(r, str) and "Error" in r]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        print(f"Successful operations: {len(successful_ops)}")
        print(f"Failed operations: {len(failed_ops)}")
        print(f"Exceptions: {len(exceptions)}")
        
        # Most operations should succeed (connection pool should handle the load)
        success_rate = len(successful_ops) / len(tasks)
        assert success_rate > 0.8  # At least 80% success rate
        
        # Should not have many exceptions (connection pool issues)
        assert len(exceptions) < len(tasks) * 0.1  # Less than 10% exceptions
    
    @pytest.mark.asyncio
    async def test_long_running_transaction_isolation(self, db_session, test_menu_items):
        """Test transaction isolation with long-running operations."""
        
        async def long_transaction(duration: float, item_plu: str):
            """Simulate a long-running transaction."""
            async for session in get_db():
                try:
                    async with session.begin():
                        # Start transaction and read data
                        result = await session.execute(
                            text("SELECT price FROM menu_items WHERE plu = :plu FOR UPDATE"),
                            {"plu": item_plu}
                        )
                        original_price = result.scalar()
                        
                        # Simulate long processing
                        await asyncio.sleep(duration)
                        
                        # Update data
                        new_price = original_price + 100
                        await session.execute(
                            text("UPDATE menu_items SET price = :price WHERE plu = :plu"),
                            {"price": new_price, "plu": item_plu}
                        )
                        
                        return f"Long transaction: Updated price from {original_price} to {new_price}"
                        
                except Exception as e:
                    return f"Long transaction failed: {str(e)}"
                finally:
                    await session.close()
        
        async def quick_read(item_plu: str, read_id: int):
            """Perform quick read operations during long transaction."""
            async for session in get_db():
                try:
                    result = await session.execute(
                        text("SELECT price FROM menu_items WHERE plu = :plu"),
                        {"plu": item_plu}
                    )
                    price = result.scalar()
                    return f"Quick read {read_id}: Price is {price}"
                except Exception as e:
                    return f"Quick read {read_id} failed: {str(e)}"
                finally:
                    await session.close()
        
        target_item = test_menu_items[0]
        
        # Start long transaction and quick reads simultaneously
        tasks = [
            long_transaction(0.5, target_item.plu),  # 500ms transaction
        ]
        
        # Add quick reads that should either see old or new value consistently
        for i in range(10):
            tasks.append(quick_read(target_item.plu, i))
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"Transaction isolation test took {end_time - start_time:.2f} seconds")
        
        # Analyze results
        long_result = results[0]
        read_results = results[1:]
        
        print(f"Long transaction result: {long_result}")
        print(f"Read results: {read_results}")
        
        # Long transaction should succeed
        assert isinstance(long_result, str) and "Updated price" in long_result
        
        # Quick reads should all succeed (may see old or new value due to isolation)
        successful_reads = [r for r in read_results if isinstance(r, str) and "Price is" in r]
        assert len(successful_reads) == 10