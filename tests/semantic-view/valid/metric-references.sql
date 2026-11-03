-- A table metric may use its own table's metrics without aggregating them, and a
-- one-to-one relationship (UNIQUE on the referencing column) lets either table
-- read the other's dimensions.
CREATE OR ALTER SEMANTIC VIEW DB.SEMANTIC.REFS
  TABLES (
    orders AS DB.SALES.ORDERS
      PRIMARY KEY (ID),
    order_details AS DB.SALES.ORDER_DETAILS
      UNIQUE (ORDER_ID)
  )
  RELATIONSHIPS (
    order_details_to_orders AS order_details (ORDER_ID) REFERENCES orders (ID)
  )
  DIMENSIONS (
    orders.status AS orders.STATUS,
    order_details.gift_wrap AS order_details.GIFT_WRAP
  )
  METRICS (
    orders.revenue AS SUM(orders.AMOUNT),
    orders.order_count AS COUNT(*),
    orders.average_order_value AS orders.revenue / NULLIF(orders.order_count, 0),
    orders.gift_orders AS COUNT_IF(order_details.gift_wrap = TRUE),
    order_details.paid_details AS COUNT_IF(orders.status = 'paid')
  )
  COMMENT = 'Fixture.';
