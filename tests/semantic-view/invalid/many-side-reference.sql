-- A metric on the one side (customers) that reads the many side (orders); orders.CUSTOMER_ID is not a key, so this needs nested aggregation.
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
    customers.n AS COUNT_IF(orders.st = 'paid')
  )
  COMMENT = 'Fixture.';
