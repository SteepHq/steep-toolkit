-- The worked example in skills/steep-to-snowflake/references/mapping.md.
-- tests/steep-import/valid/snowflake-roundtrip/ holds the Steep model it came from.
CREATE OR ALTER SEMANTIC VIEW ANALYTICS.SEMANTIC.ACME
  TABLES (
    orders AS ANALYTICS.SALES.ORDERS
      COMMENT = 'One row per order.',
    customers AS ANALYTICS.SALES.CUSTOMERS
      PRIMARY KEY (ID)
      WITH SYNONYMS = ('clients')
  )
  RELATIONSHIPS (
    customers_to_orders AS orders (CUSTOMER_ID) REFERENCES customers (ID)
  )
  DIMENSIONS (
    orders.country AS orders.COUNTRY
      WITH SYNONYMS = ('market'),
    orders.created_at AS orders.CREATED_AT,
    customers.segment AS customers.SEGMENT
      COMMENT = 'Sales segment.',
    customers.created_at AS customers.CREATED_AT,
    customers.snapshot_date AS customers.SNAPSHOT_DATE,
    customers.snapshot_date_day AS DATE_TRUNC('DAY', customers.SNAPSHOT_DATE)
  )
  METRICS (
    orders.revenue AS SUM(IFF(orders.STATUS IN ('paid', 'refunded'), orders.AMOUNT, NULL))
      WITH SYNONYMS = ('sales'),
    orders.revenue__web AS SUM(IFF(orders.STATUS IN ('paid', 'refunded') AND orders.CHANNEL = 'web', orders.AMOUNT, NULL))
      COMMENT = 'Slice: Web.',
    orders.smb_orders AS COUNT_IF(customers.segment = 'smb'),
    revenue_per_customer AS orders.revenue / NULLIF(customers.new_customers, 0),
    customers.new_customers AS COUNT(*),
    customers.total_balance NON ADDITIVE BY (customers.snapshot_date_day ASC NULLS FIRST) AS SUM(customers.BALANCE)
  )
  COMMENT = 'Exported from Steep on 2026-10-29.'
  AI_SQL_GENERATION 'orders.revenue: Excludes cancelled orders.
Time dimension per metric: orders.revenue → orders.created_at; orders.revenue__web → orders.created_at; orders.smb_orders → orders.created_at; customers.new_customers → customers.created_at; customers.total_balance → customers.snapshot_date
Steep identifiers: orders.smb_orders → smb-orders; revenue_per_customer → revenue-per-customer; customers.new_customers → new-customers; customers.total_balance → total-balance
Format per metric: revenue_per_customer → number
Display names: table customers → Customers; orders.country → Country; orders.smb_orders → SMB orders';
