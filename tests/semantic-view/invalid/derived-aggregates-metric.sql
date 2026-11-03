-- A derived metric that aggregates a metric.
CREATE OR ALTER SEMANTIC VIEW DB.SEMANTIC.BAD
  TABLES (
    orders AS DB.SALES.ORDERS
      PRIMARY KEY (ID),
    customers AS DB.SALES.CUSTOMERS
      PRIMARY KEY (ID)
  )
  RELATIONSHIPS (
    customers_to_orders AS orders (CUSTOMER_ID) REFERENCES customers (ID)
  )
  DIMENSIONS (
    orders.country AS orders.COUNTRY,
    orders.st AS orders.STATUS
  )
  METRICS (
    orders.revenue AS SUM(orders.AMOUNT),
    orders.order_count AS COUNT(*),
    d1 AS SUM(orders.revenue)
  )
  COMMENT = 'Fixture.';
